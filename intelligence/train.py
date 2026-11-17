from __future__ import annotations

from pathlib import Path

try:
    import tensorflow as tf
except ImportError as exc:  # pragma: no cover
    raise SystemExit("TensorFlow is not installed. Install it with: pip install tensorflow") from exc

BASE_DIR = Path(__file__).resolve().parent
REFERENCE_DIR = BASE_DIR / "dataset" / "reference"
ANOMALY_DIR = BASE_DIR / "dataset" / "simulated_anomaly"
MODEL_DIR = BASE_DIR / "model"


def build_model(image_size=(224, 224), classes=2):
    base_model = tf.keras.applications.MobileNetV2(
        input_shape=(image_size[0], image_size[1], 3),
        include_top=False,
        weights="imagenet",
    )
    base_model.trainable = False
    inputs = tf.keras.Input(shape=(image_size[0], image_size[1], 3))
    x = tf.keras.applications.mobilenet_v2.preprocess_input(inputs)
    x = base_model(x, training=False)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dense(128, activation="relu")(x)
    outputs = tf.keras.layers.Dense(classes, activation="softmax")(x)
    model = tf.keras.Model(inputs, outputs)
    model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])
    return model


def main() -> None:
    if not REFERENCE_DIR.exists() or not ANOMALY_DIR.exists():
        print("Dataset directories are missing. Create reference/ and simulated_anomaly/ images in intelligence/dataset/.")
        print("This AI module is experimental and is not used to determine the operator result.")
        return

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    print("Experimental AI training starting...")
    print("The model is not used for live selection; this module only demonstrates how to train a rear-side image classifier.")
    print("Prepare labelled image datasets first, then run this script again.")


if __name__ == "__main__":
    main()
