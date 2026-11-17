from __future__ import annotations

import json
from pathlib import Path

import config

CLASSES = ["medicine_back", "other"]
IMAGE_SIZE = (224, 224)
BATCH_SIZE = 16


def build_model(tf):
    base = tf.keras.applications.MobileNetV2(
        input_shape=(*IMAGE_SIZE, 3),
        include_top=False,
        weights=None,
    )
    base.trainable = True
    inputs = tf.keras.Input(shape=(*IMAGE_SIZE, 3))
    x = tf.keras.applications.mobilenet_v2.preprocess_input(inputs)
    x = base(x, training=True)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dropout(0.25)(x)
    outputs = tf.keras.layers.Dense(len(CLASSES), activation="softmax")(x)
    model = tf.keras.Model(inputs, outputs)
    model.compile(optimizer=tf.keras.optimizers.Adam(1e-4), loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    return model


def main() -> None:
    train_dir = config.TRAIN_DATASET_DIR
    validation_dir = config.VALIDATION_DATASET_DIR
    for folder in (train_dir, validation_dir):
        missing = [name for name in CLASSES if not (folder / name).is_dir()]
        if missing:
            raise SystemExit(f"Dataset directories missing under {folder}: {', '.join(missing)}")
        empty = [
            name for name in CLASSES
            if not any(path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"} for path in (folder / name).rglob("*"))
        ]
        if empty:
            raise SystemExit(f"No genuine labeled images found under {folder}: {', '.join(empty)}")

    try:
        import tensorflow as tf
    except ImportError as exc:
        raise SystemExit("Optional training requires TensorFlow. Install a compatible TensorFlow version first.") from exc

    train_ds = tf.keras.utils.image_dataset_from_directory(
        train_dir,
        class_names=CLASSES,
        image_size=IMAGE_SIZE,
        batch_size=BATCH_SIZE,
        label_mode="int",
        seed=17,
    )
    val_ds = tf.keras.utils.image_dataset_from_directory(
        validation_dir,
        class_names=CLASSES,
        image_size=IMAGE_SIZE,
        batch_size=BATCH_SIZE,
        label_mode="int",
        shuffle=False,
    )
    model = build_model(tf)
    model.fit(train_ds.prefetch(tf.data.AUTOTUNE), validation_data=val_ds.prefetch(tf.data.AUTOTUNE), epochs=10)
    config.MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save(config.MODEL_PATH)
    labels_path = config.MODEL_PATH.with_suffix(".labels.json")
    labels_path.write_text(json.dumps(CLASSES, indent=2), encoding="utf-8")
    print(f"Saved experimental packaging classifier to {config.MODEL_PATH}")
    print("Evaluate it on genuinely labeled independent images before using it. It does not authenticate medicine.")


if __name__ == "__main__":
    main()
