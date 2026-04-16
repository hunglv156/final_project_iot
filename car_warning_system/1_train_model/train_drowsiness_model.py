"""Train drowsiness classifier using transfer learning (MobileNetV2)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Tuple

import matplotlib.pyplot as plt
import numpy as np
import tensorflow as tf
from sklearn.metrics import classification_report
from tensorflow.keras import layers
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint, ReduceLROnPlateau
from tensorflow.keras.models import Model

AUTOTUNE = tf.data.AUTOTUNE
CLASS_NAMES = ["Non Drowsy", "Drowsy"]
ALLOWED_IMAGE_EXTS = {".bmp", ".gif", ".jpeg", ".jpg", ".png"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_dir", type=Path, default=Path("dataset"))
    parser.add_argument("--output_dir", type=Path, default=Path("outputs"))
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--learning_rate", type=float, default=1e-4)
    parser.add_argument(
        "--img_size",
        type=int,
        default=160,
        help="Input image size (square). Smaller is faster, 160 is a good speed/quality trade-off.",
    )
    parser.add_argument(
        "--mobilenet_alpha",
        type=float,
        default=0.5,
        help="MobileNetV2 width multiplier. Smaller is faster/lighter.",
    )
    parser.add_argument(
        "--early_stopping_patience",
        type=int,
        default=3,
        help="Stop earlier when validation loss stops improving.",
    )
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def load_datasets(
    dataset_dir: Path, batch_size: int, seed: int, img_size: tuple[int, int]
) -> Tuple[tf.data.Dataset, tf.data.Dataset]:
    train_ds = tf.keras.utils.image_dataset_from_directory(
        dataset_dir,
        labels="inferred",
        label_mode="categorical",
        validation_split=0.2,
        subset="training",
        seed=seed,
        image_size=img_size,
        batch_size=batch_size,
    )
    val_ds = tf.keras.utils.image_dataset_from_directory(
        dataset_dir,
        labels="inferred",
        label_mode="categorical",
        validation_split=0.2,
        subset="validation",
        seed=seed,
        image_size=img_size,
        batch_size=batch_size,
    )
    # Cache + prefetch speeds up repeated epochs by reducing disk I/O stalls.
    train_ds = train_ds.cache().prefetch(AUTOTUNE)
    val_ds = val_ds.cache().prefetch(AUTOTUNE)
    return train_ds, val_ds


def validate_dataset_dir(dataset_dir: Path) -> None:
    """Validate dataset directory before TensorFlow dataset loading."""
    if not dataset_dir.exists():
        raise FileNotFoundError(
            f"Dataset directory not found: {dataset_dir.resolve()}\n"
            "Pass --dataset_dir to point to your image dataset."
        )

    missing_classes = [name for name in CLASS_NAMES if not (dataset_dir / name).exists()]
    if missing_classes:
        raise ValueError(
            f"Dataset is missing class folders {missing_classes} in {dataset_dir.resolve()}.\n"
            f"Expected subfolders: {CLASS_NAMES}."
        )

    image_count = sum(
        1
        for p in dataset_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in ALLOWED_IMAGE_EXTS
    )
    if image_count == 0:
        raise ValueError(
            f"No images found in {dataset_dir.resolve()}.\n"
            "Add images (.bmp, .gif, .jpeg, .jpg, .png) under class folders "
            f"{CLASS_NAMES}, or pass --dataset_dir to the correct path."
        )


def build_model(
    learning_rate: float, img_size: tuple[int, int], mobilenet_alpha: float
) -> Model:
    data_augmentation = tf.keras.Sequential(
        [
            layers.RandomRotation(0.08),
            layers.RandomFlip("horizontal"),
            layers.RandomBrightness(0.2),
            layers.RandomZoom(0.1),
        ],
        name="augmentation",
    )
    preprocess = tf.keras.applications.mobilenet_v2.preprocess_input
    base = tf.keras.applications.MobileNetV2(
        input_shape=img_size + (3,),
        include_top=False,
        weights="imagenet",
        alpha=mobilenet_alpha,
    )
    base.trainable = False

    inputs = layers.Input(shape=img_size + (3,))
    x = data_augmentation(inputs)
    x = preprocess(x)
    x = base(x, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dense(128, activation="relu")(x)
    x = layers.Dropout(0.5)(x)
    outputs = layers.Dense(2, activation="softmax")(x)
    model = Model(inputs, outputs)

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate),
        loss="categorical_crossentropy",
        metrics=[
            "accuracy",
            tf.keras.metrics.Precision(name="precision"),
            tf.keras.metrics.Recall(name="recall"),
        ],
    )
    return model


def save_history_plot(history: tf.keras.callbacks.History, output_dir: Path) -> None:
    fig, axs = plt.subplots(1, 2, figsize=(12, 4))
    axs[0].plot(history.history["accuracy"], label="train_acc")
    axs[0].plot(history.history["val_accuracy"], label="val_acc")
    axs[0].set_title("Accuracy")
    axs[0].legend()

    axs[1].plot(history.history["loss"], label="train_loss")
    axs[1].plot(history.history["val_loss"], label="val_loss")
    axs[1].set_title("Loss")
    axs[1].legend()
    fig.tight_layout()
    fig.savefig(output_dir / "training_history.png", dpi=150)
    plt.close(fig)


def evaluate_and_report(
    model: Model, val_ds: tf.data.Dataset, output_dir: Path
) -> Dict[str, object]:
    y_true: list[int] = []
    y_pred: list[int] = []
    for images, labels in val_ds:
        probs = model.predict(images, verbose=0)
        y_pred.extend(np.argmax(probs, axis=1).tolist())
        y_true.extend(np.argmax(labels.numpy(), axis=1).tolist())

    report = classification_report(
        y_true,
        y_pred,
        target_names=CLASS_NAMES,
        digits=4,
        output_dict=True,
        zero_division=0,
    )
    report_text = classification_report(
        y_true, y_pred, target_names=CLASS_NAMES, digits=4, zero_division=0
    )
    (output_dir / "classification_report.txt").write_text(report_text, encoding="utf-8")
    return report


def convert_tflite(model_path: Path, tflite_path: Path) -> None:
    model = tf.keras.models.load_model(model_path)
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    tflite_model = converter.convert()
    tflite_path.write_bytes(tflite_model)


def main() -> None:
    args = parse_args()
    args.dataset_dir = args.dataset_dir.resolve()
    img_size = (args.img_size, args.img_size)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    model_dir = args.output_dir / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "drowsiness_model.h5"
    tflite_path = model_dir / "drowsiness_model.tflite"

    validate_dataset_dir(args.dataset_dir)
    train_ds, val_ds = load_datasets(
        args.dataset_dir, args.batch_size, args.seed, img_size
    )
    model = build_model(args.learning_rate, img_size, args.mobilenet_alpha)

    callbacks = [
        ModelCheckpoint(model_path.as_posix(), monitor="val_accuracy", save_best_only=True),
        EarlyStopping(
            monitor="val_loss",
            patience=args.early_stopping_patience,
            restore_best_weights=True,
        ),
        ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=3, verbose=1),
    ]

    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=args.epochs,
        callbacks=callbacks,
        verbose=1,
    )
    save_history_plot(history, args.output_dir)
    report = evaluate_and_report(model, val_ds, args.output_dir)
    convert_tflite(model_path, tflite_path)

    metrics_path = args.output_dir / "final_metrics.json"
    metrics_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved best model: {model_path}")
    print(f"Saved TFLite model: {tflite_path}")
    print(f"Saved report: {args.output_dir / 'classification_report.txt'}")
    print(f"Validation accuracy: {report['accuracy']:.4f}")


if __name__ == "__main__":
    main()
