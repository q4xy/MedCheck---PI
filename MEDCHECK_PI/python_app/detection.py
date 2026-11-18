"""
detection.py
Practical OpenCV presence, rectangular contour geometry, ROI containment,
and temporal stability detection for positioning a medicine packet's back side
inside the camera alignment frame.

Note: Visual geometry detection verifies object presence, scale, alignment,
and steadiness inside the target zone; it does not claim pharmaceutical
authenticity on its own.
"""

from dataclasses import dataclass
from collections import deque
from typing import Deque, Optional, Tuple
import cv2
import numpy as np


@dataclass
class DetectionResult:
    status: str                          # "MEDICINE_NOT_ALIGNED", "MEDICINE_ADJUST", "MEDICINE_ALIGNED"
    label: str                           # Human-readable UI status
    detected: bool                       # Whether a packet-sized rectangular object was found
    inside_roi: bool                     # Whether bounding box lies well inside alignment frame
    stable: bool                         # Whether position remained steady across consecutive frames
    bbox: Optional[Tuple[int, int, int, int]]  # (x, y, w, h)
    roi: Tuple[int, int, int, int]       # (rx1, ry1, rx2, ry2)
    stability_progress: float            # 0.0 to 1.0


class MedicinePlacementDetector:
    def __init__(
        self,
        required_stable_frames: int = 12,
        max_center_jitter_px: float = 16.0,
        max_area_jitter_ratio: float = 0.14,
        min_area_ratio: float = 0.08,
        max_area_ratio: float = 0.78,
    ) -> None:
        self.required_stable_frames = required_stable_frames
        self.max_center_jitter_px = max_center_jitter_px
        self.max_area_jitter_ratio = max_area_jitter_ratio
        self.min_area_ratio = min_area_ratio
        self.max_area_ratio = max_area_ratio

        self.history: Deque[Tuple[float, float, float]] = deque(maxlen=required_stable_frames)
        self.aligned_locked = False
        self.miss_frames = 0

    def reset(self) -> None:
        self.history.clear()
        self.aligned_locked = False
        self.miss_frames = 0

    @staticmethod
    def compute_roi(frame_w: int, frame_h: int) -> Tuple[int, int, int, int]:
        """Central placement guide frame (margins: 16% horizontal, 15% vertical)."""
        rx1 = int(frame_w * 0.16)
        ry1 = int(frame_h * 0.15)
        rx2 = int(frame_w * 0.84)
        ry2 = int(frame_h * 0.85)
        return rx1, ry1, rx2, ry2

    def _find_packet_candidate(
        self, frame: np.ndarray
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Preprocess frame using grayscale, bilateral/Gaussian smoothing,
        adaptive Canny + morphological closing, and contour shape filtering
        to locate the largest packet-like rectangular contour.
        """
        fh, fw = frame.shape[:2]
        frame_area = float(fw * fh)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)

        # Automatic Canny thresholds based on median luminance
        med_val = float(np.median(blurred))
        low_t = int(max(20, 0.55 * med_val))
        high_t = int(min(240, 1.45 * med_val))
        edges = cv2.Canny(blurred, low_t, high_t)

        # Close small gaps along packet edges
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best_bbox: Optional[Tuple[int, int, int, int]] = None
        best_score = 0.0

        for cnt in contours:
            area = cv2.contourArea(cnt)
            area_ratio = area / frame_area
            if area_ratio < self.min_area_ratio or area_ratio > self.max_area_ratio:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            if w <= 0 or h <= 0:
                continue

            # Aspect ratio filter suitable for medicine strips/boxes (horizontal or vertical)
            aspect = max(w / float(h), h / float(w))
            if aspect > 4.2:
                continue

            # Rectangularity check (contour area vs bounding box area)
            rect_fill = area / float(w * h)
            if rect_fill < 0.52:
                continue

            # Polygon approximation to favor clean 4-sided packet silhouettes
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
            vertex_bonus = 1.2 if 4 <= len(approx) <= 8 else 1.0

            score = area * rect_fill * vertex_bonus
            if score > best_score:
                best_score = score
                best_bbox = (x, y, w, h)

        return best_bbox

    def _is_inside_roi(
        self, bbox: Tuple[int, int, int, int], roi: Tuple[int, int, int, int]
    ) -> bool:
        x, y, w, h = bbox
        rx1, ry1, rx2, ry2 = roi
        roi_w = rx2 - rx1
        roi_h = ry2 - ry1

        # Packet center must lie comfortably inside central 60% of the ROI
        cx = x + w * 0.5
        cy = y + h * 0.5
        margin_x = roi_w * 0.20
        margin_y = roi_h * 0.20
        center_ok = (rx1 + margin_x <= cx <= rx2 - margin_x) and (
            ry1 + margin_y <= cy <= ry2 - margin_y
        )

        # At least 75% of the detected packet bounding box must fall inside the ROI
        ix1 = max(x, rx1)
        iy1 = max(y, ry1)
        ix2 = min(x + w, rx2)
        iy2 = min(y + h, ry2)
        if ix2 <= ix1 or iy2 <= iy1:
            return False

        inter_area = float((ix2 - ix1) * (iy2 - iy1))
        overlap_ratio = inter_area / float(w * h)

        # Packet must also fill a reasonable portion of the ROI (not tiny)
        size_ok = (w * h) >= (roi_w * roi_h * 0.16)

        return center_ok and (overlap_ratio >= 0.75) and size_ok

    def _check_temporal_stability(self) -> bool:
        if len(self.history) < self.required_stable_frames:
            return False

        pts = np.array(self.history, dtype=np.float32)
        max_dx = float(np.max(pts[:, 0]) - np.min(pts[:, 0]))
        max_dy = float(np.max(pts[:, 1]) - np.min(pts[:, 1]))
        mean_area = float(np.mean(pts[:, 2]))
        area_span = float(np.max(pts[:, 2]) - np.min(pts[:, 2]))

        if max_dx > self.max_center_jitter_px or max_dy > self.max_center_jitter_px:
            return False
        if mean_area > 0 and (area_span / mean_area) > self.max_area_jitter_ratio:
            return False

        return True

    def analyze(self, frame: np.ndarray) -> DetectionResult:
        fh, fw = frame.shape[:2]
        roi = self.compute_roi(fw, fh)
        bbox = self._find_packet_candidate(frame)

        # Hysteresis: tolerate up to 3 transient dropped frames without flickering
        if bbox is None:
            self.miss_frames += 1
            if self.miss_frames > 3:
                self.reset()
            return DetectionResult(
                status="MEDICINE_NOT_ALIGNED",
                label="PLACE YOUR MEDICINE",
                detected=False,
                inside_roi=False,
                stable=False,
                bbox=None,
                roi=roi,
                stability_progress=0.0,
            )

        self.miss_frames = 0
        x, y, w, h = bbox
        inside = self._is_inside_roi(bbox, roi)

        if not inside:
            self.history.clear()
            self.aligned_locked = False
            return DetectionResult(
                status="MEDICINE_ADJUST",
                label="ADJUST MEDICINE POSITION",
                detected=True,
                inside_roi=False,
                stable=False,
                bbox=bbox,
                roi=roi,
                stability_progress=0.0,
            )

        # Inside ROI -> record center & area for temporal stability check
        cx = x + w * 0.5
        cy = y + h * 0.5
        area = float(w * h)
        self.history.append((cx, cy, area))

        progress = min(1.0, len(self.history) / float(self.required_stable_frames))
        is_stable = self._check_temporal_stability()

        if is_stable or self.aligned_locked:
            self.aligned_locked = True
            return DetectionResult(
                status="MEDICINE_ALIGNED",
                label="MEDICINE ALIGNED",
                detected=True,
                inside_roi=True,
                stable=True,
                bbox=bbox,
                roi=roi,
                stability_progress=1.0,
            )

        return DetectionResult(
            status="MEDICINE_ADJUST",
            label="HOLD STEADY TO ALIGN",
            detected=True,
            inside_roi=True,
            stable=False,
            bbox=bbox,
            roi=roi,
            stability_progress=progress,
        )