from __future__ import annotations

import sys
from pathlib import Path

try:
    import tensorflow as tf
except ImportError as exc:  # pragma: no cover
    raise SystemExit("TensorFlow is not installed. Install it with: pip install tensorflow") from exc

MODEL_DIR = Path(__file__).resolve().parent / "model"
TARGET_MODEL = MODEL_DIR / "trained_model.keras"


def predict(image_path: str) -> str:
    if not TARGET_MODEL.exists():
        print("No trained model available. Train the experimental AI model with: python intelligence/train.py")
        return "MODEL_UNAVAILABLE"

    model = tf.keras.models.load_model(TARGET_MODEL)
    image = tf.keras.utils.load_img(image_path, target_size=(224, 224))
    tensor = tf.keras.utils.img_to_array(image)
    tensor = tf.expand_dims(tensor, axis=0)
    prediction = model.predict(tensor, verbose=0)
    return str(prediction)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python intelligence/predict.py <image_path>")
        raise SystemExit(1)
    result = predict(sys.argv[1])
    print(result)
