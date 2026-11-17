from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

import config

RED_MARK_MESSAGE = (
    "Red-colored marking detected near the lower printed information area. "
    "Exact expiry-date alignment requires manual verification."
)


def _package_like(image: np.ndarray) -> bool:
    height, width = image.shape[:2]
    if height < 120 or width < 120:
        return False
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 45, 130)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(height * width)
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:80]:
        area = cv2.contourArea(contour)
        if not image_area * 0.08 <= area <= image_area * 0.92:
            continue
        x, y, box_width, box_height = cv2.boundingRect(contour)
        ratio = box_width / max(box_height, 1)
        if not 0.28 <= ratio <= 3.6:
            continue
        perimeter = cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, 0.035 * perimeter, True)
        if 4 <= len(polygon) <= 10:
            return True
    return False


def _detect_red_mark(image: np.ndarray) -> bool:
    height, width = image.shape[:2]
    lower_print_area = image[int(height * 0.5):int(height * 0.96), int(width * 0.08):int(width * 0.92)]
    if lower_print_area.size == 0:
        return False
    hsv = cv2.cvtColor(lower_print_area, cv2.COLOR_BGR2HSV)
    red_a = cv2.inRange(hsv, np.array([0, 90, 55]), np.array([12, 255, 255]))
    red_b = cv2.inRange(hsv, np.array([168, 90, 55]), np.array([180, 255, 255]))
    mask = cv2.bitwise_or(red_a, red_b)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    minimum_component = max(10, int(mask.size * 0.00015))
    return any(stats[index, cv2.CC_STAT_AREA] >= minimum_component for index in range(1, count))


def _reference_match(image: np.ndarray, reference_path: Path) -> Tuple[bool, Optional[float]]:
    reference = cv2.imread(str(reference_path))
    if reference is None:
        return False, None
    detector = cv2.ORB_create(nfeatures=1200)
    query_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    reference_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
    query_points, query_descriptors = detector.detectAndCompute(query_gray, None)
    ref_points, ref_descriptors = detector.detectAndCompute(reference_gray, None)
    if query_descriptors is None or ref_descriptors is None or len(query_points) < 8 or len(ref_points) < 8:
        return False, 0.0
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    pairs = matcher.knnMatch(ref_descriptors, query_descriptors, k=2)
    good = [
        pair[0]
        for pair in pairs
        if len(pair) == 2 and pair[0].distance < 0.72 * pair[1].distance
    ]
    if len(good) < 8:
        return False, min(1.0, len(good) / 24.0)
    source = np.float32([ref_points[item.queryIdx].pt for item in good]).reshape(-1, 1, 2)
    target = np.float32([query_points[item.trainIdx].pt for item in good]).reshape(-1, 1, 2)
    _, inliers = cv2.findHomography(source, target, cv2.RANSAC, 5.0)
    if inliers is None:
        return False, 0.0
    score = float(inliers.ravel().mean())
    return score >= config.REFERENCE_MATCH_THRESHOLD and len(good) >= 12, round(score, 3)


def _load_references() -> list[Dict[str, str]]:
    manifest_path = config.MEDICINE_REFERENCE_MANIFEST
    if not manifest_path.is_file():
        return []
    try:
        entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read the medicine reference manifest: {exc}") from exc
    if not isinstance(entries, list):
        raise ValueError("The medicine reference manifest must contain a JSON list.")
    references: list[Dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Each medicine reference must be a JSON object.")
        name, filename = entry.get("name"), entry.get("image")
        if (
            isinstance(name, str)
            and name.strip()
            and isinstance(filename, str)
            and Path(filename).name == filename
            and Path(filename).suffix.lower() in {".jpg", ".jpeg", ".png"}
        ):
            references.append({"name": name.strip(), "image": filename})
        else:
            raise ValueError("Each medicine reference needs a name and a local image filename.")
    return references


@lru_cache(maxsize=1)
def _load_model():
    if not config.MODEL_PATH.is_file():
        return None
    try:
        import tensorflow as tf
    except ImportError as exc:
        raise RuntimeError("A trained model exists but TensorFlow is unavailable.") from exc
    return tf.keras.models.load_model(config.MODEL_PATH)


def _model_prediction(image: np.ndarray) -> Optional[Tuple[str, float]]:
    model = _load_model()
    if model is None:
        return None
    labels_path = config.MODEL_PATH.with_suffix(".labels.json")
    labels = json.loads(labels_path.read_text(encoding="utf-8")) if labels_path.is_file() else ["medicine_back", "other"]
    resized = cv2.resize(image, (224, 224)).astype(np.float32)
    batch = np.expand_dims(resized, axis=0)
    import tensorflow as tf

    batch = tf.keras.applications.mobilenet_v2.preprocess_input(batch)
    probabilities = np.asarray(model.predict(batch, verbose=0))[0]
    index = int(np.argmax(probabilities))
    if index >= len(labels):
        raise RuntimeError("Trained model output does not match its saved class labels.")
    return str(labels[index]), float(probabilities[index])


def analyze_image(image_path: str | Path) -> Dict[str, Any]:
    path = Path(image_path)
    image = cv2.imread(str(path))
    if image is None:
        return {
            "classification": "NEEDS MANUAL REVIEW",
            "message": "The captured image could not be read. Capture it again and review manually.",
            "confidence": None,
            "confidence_label": "",
            "visual_observations": [],
            "red_mark_detected": False,
            "red_mark_observation": "",
        }

    height, width = image.shape[:2]
    if min(height, width) < 120:
        return {
            "classification": "NEEDS MANUAL REVIEW",
            "message": "The image is too small for a useful packaging review.",
            "confidence": None,
            "confidence_label": "",
            "visual_observations": [],
            "red_mark_detected": False,
            "red_mark_observation": "",
        }

    red_detected = _detect_red_mark(image)
    observations = [RED_MARK_MESSAGE] if red_detected else []
    red_message = RED_MARK_MESSAGE if red_detected else ""

    model_result = _model_prediction(image)
    geometry_candidate = _package_like(image)
    try:
        references = _load_references()
    except ValueError as exc:
        return {
            "classification": "NEEDS MANUAL REVIEW",
            "message": str(exc),
            "confidence": None,
            "confidence_label": "",
            "visual_observations": observations,
            "red_mark_detected": red_detected,
            "red_mark_observation": red_message,
        }

    reference_confidence: Optional[float] = None
    for reference in references:
        reference_path = config.MEDICINE_REFERENCE_MANIFEST.parent / reference["image"]
        if not reference_path.is_file():
            continue
        matched, score = _reference_match(image, reference_path)
        if matched:
            return {
                "classification": "SUPPORTED MEDICINE FOUND",
                "medicine_name": reference["name"],
                "message": (
                    f"Image matched the configured {reference['name']} package reference. "
                    "This does not verify medicine authenticity."
                ),
                "confidence": score,
                "confidence_label": "REFERENCE MATCH SCORE",
                "visual_observations": observations,
                "red_mark_detected": red_detected,
                "red_mark_observation": red_message,
            }
        if score is not None and (reference_confidence is None or score > reference_confidence):
            reference_confidence = score

    if model_result and model_result[0] == "other" and model_result[1] >= config.ANALYSIS_CONFIDENCE_THRESHOLD:
        return {
            "classification": "NO MEDICINE FOUND",
            "message": "The configured image classifier categorized this image as other. This is not a medicine authenticity test.",
            "confidence": round(model_result[1], 3),
            "confidence_label": "IMAGE CLASSIFIER SCORE",
            "visual_observations": observations,
            "red_mark_detected": red_detected,
            "red_mark_observation": red_message,
        }
    if not geometry_candidate and not (model_result and model_result[0] == "medicine_back"):
        return {
            "classification": "NO MEDICINE FOUND",
            "message": "No clear medicine-package shape was detected by the prototype visual check.",
            "confidence": round(model_result[1], 3) if model_result else None,
            "confidence_label": "IMAGE CLASSIFIER SCORE" if model_result else "",
            "visual_observations": observations,
            "red_mark_detected": red_detected,
            "red_mark_observation": red_message,
        }
    if model_result and model_result[1] < config.ANALYSIS_CONFIDENCE_THRESHOLD:
        return {
            "classification": "NEEDS MANUAL REVIEW",
            "message": "The configured packaging classifier returned an uncertain result. Verify the sample manually.",
            "confidence": round(model_result[1], 3),
            "confidence_label": "IMAGE CLASSIFIER SCORE",
            "visual_observations": observations,
            "red_mark_detected": red_detected,
            "red_mark_observation": red_message,
        }

    if not references or any(
        not (config.MEDICINE_REFERENCE_MANIFEST.parent / reference["image"]).is_file()
        for reference in references
    ):
        return {
            "classification": "NEEDS MANUAL REVIEW",
            "message": (
                "Package-like image detected, but a configured medicine reference image is missing. "
                "Medicine identity cannot be confirmed."
            ),
            "confidence": None,
            "confidence_label": "",
            "visual_observations": observations,
            "red_mark_detected": red_detected,
            "red_mark_observation": red_message,
        }

    return {
        "classification": "NEEDS MANUAL REVIEW",
        "message": "Package-like image detected, but it did not confidently match the supported medicine reference.",
        "confidence": reference_confidence,
        "confidence_label": "REFERENCE MATCH SCORE" if reference_confidence is not None else "",
        "visual_observations": observations,
        "red_mark_detected": red_detected,
        "red_mark_observation": red_message,
    }


def predict(image_path: str | Path) -> Dict[str, Any]:
    """Compatibility entry point used by the app and command-line utility."""
    return analyze_image(image_path)


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Prototype inspection of one supported medicine package.")
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze_image(args.image), indent=2))
