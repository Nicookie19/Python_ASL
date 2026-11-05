"""Fetch a pinned, attributed landmark dataset and train Pysign's static model.

Run from any directory: python sign_app/tools/prepare_public_asl.py
The bundled samples can be retrained offline with --offline.
No external Python code or pickled models are downloaded/executed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.features import FeatureExtractor  # noqa: E402
from app.core.hand_tracker import Handedness, HandLandmarks  # noqa: E402
from app.core.recognizer import StaticRecognizer, StaticRecognizerConfig  # noqa: E402

DATASET = "Siruyy/asl-static-landmarks-v1"
REVISION = "a9cea6cf363eb3265ea0e795a1af573105d85f53"
SOURCE_CODE_REVISION = "74b976b536ab8318dab756a3071a681d5c75bcb0"
CHECKSUMS = {
    "X_train.npy": "764468119867c9af3d483c3f5c445e4c7f6b7aa8c1c08c338152847e49150bd2",
    "X_test.npy": "256a21dfc7935501a8042b19b5b708c41f14c6d5335b26efbdef23298fa6ca0b",
    "y_train.npy": "1c42e9f29003e8c8ad58f6ac1dca8b9529826e9fabfc482571238ab9d21dbf80",
    "y_test.npy": "5a7c641d79f0cfe4f05152c6b3a2712decbe77ecc7750d9469e929589530cf00",
    "mean.npy": "8393adc560d0be7b910b430614dfb13abf1fa32bb6603b1aa7aeb44e4f91ff46",
    "std.npy": "33f6302ee363d971085ca05d5aa41b163a00ad12c0b1e1dfe2fb511adeb0858f",
}
BUNDLE_DIR = PROJECT_ROOT / "training_data" / "asl_static"
MODEL_DIR = PROJECT_ROOT / "content_packs" / "asl" / "model"


def checksum(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decode_source(features, encoded_labels, mean, std):
    """Invert source standardization, retaining the original 21 XYZ landmarks.

    The upstream feature_engineer.py stores flattened XYZ in columns 0:63.
    Its LabelEncoder maps A-Z to 0-25. Handedness/session IDs are not included.
    J and Z cannot be validated from a static frame and are excluded.
    """
    features = np.asarray(features)
    labels = np.asarray(encoded_labels)
    if features.ndim != 2 or features.shape[1] != 86 or labels.shape != (len(features),):
        raise ValueError("Unexpected source dataset shape")
    if mean.shape != (86,) or std.shape != (86,) or not np.isfinite(features).all():
        raise ValueError("Invalid source normalization or features")
    if not np.issubdtype(labels.dtype, np.integer) or not np.isin(labels, np.arange(26)).all():
        raise ValueError("Source labels must be A-Z encoded as 0-25")
    keep = ~np.isin(labels, [9, 25])
    landmarks = (features[keep] * std + mean)[:, :63].reshape(-1, 21, 3).astype(np.float32)
    names = np.array(["asl_" + chr(97 + int(label)) for label in labels[keep]])
    if not np.isfinite(landmarks).all():
        raise ValueError("Non-finite landmarks")
    return landmarks, names


def prepare_bundle(bundle_dir=BUNDLE_DIR):
    import requests
    cache = PROJECT_ROOT / "data" / "downloads" / "asl_static"
    cache.mkdir(parents=True, exist_ok=True)
    arrays = {}
    for name, digest in CHECKSUMS.items():
        path = cache / name
        if not path.exists():
            url = f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{name}"
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            data = response.content
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError(f"Download checksum mismatch: {name}")
            path.write_bytes(data)
        if checksum(path) != digest:
            raise ValueError(f"Cached checksum mismatch: {name}")
        arrays[name] = np.load(path, allow_pickle=False)
    splits = {}
    for split in ("train", "test"):
        landmarks, labels = decode_source(arrays[f"X_{split}.npy"], arrays[f"y_{split}.npy"],
                                          arrays["mean.npy"], arrays["std.npy"])
        splits[f"landmarks_{split}"] = landmarks
        splits[f"labels_{split}"] = labels
    # Prevent exact/rounded duplicate poses from crossing the split boundary.
    keys = {row.round(5).tobytes() for row in splits["landmarks_train"]}
    keep = np.array([row.round(5).tobytes() not in keys for row in splits["landmarks_test"]])
    removed = int((~keep).sum())
    for name in ("landmarks_test", "labels_test"):
        splits[name] = splits[name][keep]
    bundle_dir = Path(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(bundle_dir / "samples.npz", **splits)
    manifest = {
        "dataset": DATASET, "author": "Neel Ulysses Roda (Siruyy)",
        "source_url": f"https://huggingface.co/datasets/{DATASET}",
        "revision": REVISION, "license": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "source_code_url": f"https://github.com/Siruyy/realtime-asl-recognizer/tree/{SOURCE_CODE_REVISION}",
        "source_sha256": CHECKSUMS,
        "samples_sha256": checksum(bundle_dir / "samples.npz"),
        "transformation": "Inverse standardization; recover XYZ columns 0:63; float32; A-Z IDs; remove J/Z; remove rounded train/test duplicates.",
        "handedness": "Not supplied; both X orientations are used for training augmentation.",
        "split": "Upstream stratified random frame split; not signer/session independent.",
        "removed_test_duplicates": removed,
        "counts": {split: {str(label): int(n) for label, n in zip(*np.unique(splits[f'labels_{split}'], return_counts=True))}
                   for split in ("train", "test")},
    }
    (bundle_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return bundle_dir / "samples.npz"


def extract_features(landmarks):
    """Use exactly the live app's translation/scale normalization and 88 features."""
    extractor = FeatureExtractor()
    return np.array([extractor.extract(HandLandmarks(pose, Handedness.RIGHT, 1.0, 640, 480)).features
                     for pose in landmarks], dtype=np.float32)


def mirror_poses(landmarks):
    result = landmarks.copy()
    result[:, :, 0] = 1.0 - result[:, :, 0]
    return result


def train_bundle(bundle_dir=BUNDLE_DIR, output_dir=MODEL_DIR):
    from sklearn.ensemble import ExtraTreesClassifier
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
    from sklearn.model_selection import train_test_split
    import sklearn
    bundle_dir, output_dir = Path(bundle_dir), Path(output_dir)
    manifest = json.loads((bundle_dir / "manifest.json").read_text())
    if checksum(bundle_dir / "samples.npz") != manifest["samples_sha256"]:
        raise ValueError("Bundled samples checksum mismatch")
    with np.load(bundle_dir / "samples.npz", allow_pickle=False) as data:
        poses, y = data["landmarks_train"], data["labels_train"]
        test_poses, y_test = data["landmarks_test"], data["labels_test"]
    x, mirrored = extract_features(poses), extract_features(mirror_poses(poses))
    train, validation = train_test_split(np.arange(len(y)), test_size=.2, stratify=y, random_state=42)
    def new_model():
        return ExtraTreesClassifier(n_estimators=100, max_depth=24, min_samples_leaf=3,
                                    class_weight="balanced", random_state=42, n_jobs=1)
    model = new_model()
    model.fit(np.vstack([x[train], mirrored[train]]), np.tile(y[train], 2))
    validation_accuracy = accuracy_score(y[validation], model.predict(x[validation]))
    # Fixed threshold selected conservatively from training-split validation.
    threshold = .70
    model = new_model()
    model.fit(np.vstack([x, mirrored]), np.tile(y, 2))
    classes = list(model.classes_)
    recognizer = StaticRecognizer(StaticRecognizerConfig(model_type="extra_trees", n_estimators=100,
                                  max_depth=24, min_samples_leaf=3, confidence_threshold=threshold, smoothing_window=5))
    recognizer._model = model
    recognizer._classes = classes
    recognizer._label_to_idx = {label: i for i, label in enumerate(classes)}
    recognizer._idx_to_label = dict(enumerate(classes))
    recognizer.save(output_dir / "model")
    x_test = extract_features(test_poses)
    probability = model.predict_proba(x_test)
    predicted = np.array(classes)[probability.argmax(axis=1)]
    accepted = probability.max(axis=1) >= threshold
    metrics = {
        "dataset": DATASET, "revision": REVISION, "license": "CC-BY-4.0",
        "training_samples": len(y), "augmented_training_samples": 2 * len(y),
        "held_out_samples": len(y_test), "validation_accuracy": float(validation_accuracy),
        "held_out_accuracy": float(accuracy_score(y_test, predicted)),
        "confidence_threshold": threshold, "accepted_coverage": float(accepted.mean()),
        "accepted_accuracy": float(accuracy_score(y_test[accepted], predicted[accepted])) if accepted.any() else None,
        "mirrored_held_out_accuracy": float(accuracy_score(y_test, model.predict(extract_features(mirror_poses(test_poses))))),
        "classes": classes, "feature_count": x.shape[1], "sklearn_version": sklearn.__version__,
        "model_bytes": (output_dir / "model.joblib").stat().st_size,
        "per_class": classification_report(y_test, predicted, output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(y_test, predicted, labels=classes).tolist(),
        "limitations": ["Random frame split, not unseen signers or sessions.",
                        "No unknown/negative class; confidence does not prove a sign is valid.",
                        "24 static letters only; no numbers, J/Z motion, or phrases.",
                        "Live webcam accuracy and camera-domain transfer are not measured."],
        "model_sha256": checksum(output_dir / "model.joblib"),
        "samples_sha256": manifest["samples_sha256"],
    }
    (output_dir / "evaluation.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps({k: v for k, v in metrics.items() if k not in ("per_class", "confusion_matrix")}, indent=2))
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Retrain from bundled landmarks without network access")
    parser.add_argument("--output-dir", type=Path, default=MODEL_DIR)
    args = parser.parse_args()
    if not args.offline:
        prepare_bundle()
    train_bundle(output_dir=args.output_dir)


if __name__ == "__main__":
    main()
