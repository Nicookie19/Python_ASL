#!/usr/bin/env python3
"""
Train the ASL sign recognition model from collected samples.

- Loads samples from data/samples/asl/*.csv
- Trains sklearn models (RF, SVM, KNN, MLP) with cross-validation
- Computes per-sign reference data (median landmarks, finger states, angles, tolerances)
- Saves model to content_packs/asl/model/model.joblib + labels.json
- Updates content_packs/asl/signs.json with reference data and reference_source: "recorded"

Usage:
    python -m tools.train_model [--model-type TYPE] [--output-dir DIR] [--min-samples N]
"""

import argparse
import csv
import json
import logging
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

import numpy as np
import joblib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.recognizer import StaticRecognizer, StaticRecognizerConfig, create_recognizer
from app.core.features import FeatureExtractor
from app.content.loader import initialize_content_packs

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", category=UserWarning)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = PROJECT_ROOT / "data/samples/asl"
MODEL_DIR = PROJECT_ROOT / "content_packs/asl/model"

FEATURE_EXTRACTOR = FeatureExtractor(
    mirror_left_to_right=True,
    use_3d=True,
    include_angles=True,
    include_distances=True
)

LANDMARK_INDEX = {
    "WRIST": 0,
    "THUMB_CMC": 1, "THUMB_MCP": 2, "THUMB_IP": 3, "THUMB_TIP": 4,
    "INDEX_MCP": 5, "INDEX_PIP": 6, "INDEX_DIP": 7, "INDEX_TIP": 8,
    "MIDDLE_MCP": 9, "MIDDLE_PIP": 10, "MIDDLE_DIP": 11, "MIDDLE_TIP": 12,
    "RING_MCP": 13, "RING_PIP": 14, "RING_DIP": 15, "RING_TIP": 16,
    "PINKY_MCP": 17, "PINKY_PIP": 18, "PINKY_DIP": 19, "PINKY_TIP": 20,
}

FINGER_CHAINS = {
    "thumb": (4, 3, 2),
    "index": (8, 6, 5),
    "middle": (12, 10, 9),
    "ring": (16, 14, 13),
    "pinky": (20, 18, 17),
}

FINGER_NAMES = ["thumb", "index", "middle", "ring", "pinky"]


def load_samples(sample_dir: Path, min_samples: int = 5) -> Tuple[np.ndarray, np.ndarray, Dict[str, List[np.ndarray]], Dict[str, List[Dict]], Dict[str, List[Dict]]]:
    """
    Load all samples from CSV files.
    Returns: X (features), y (labels), raw_landmarks_by_sign, finger_states_by_sign, angles_by_sign
    """
    X_list = []
    y_list = []
    raw_landmarks_by_sign = {}
    finger_states_by_sign = {}
    angles_by_sign = {}

    csv_files = list(sample_dir.glob("*.csv"))
    if not csv_files:
        logger.warning(f"No CSV files found in {sample_dir}")
        return np.array([]), np.array([]), {}, {}, {}

    logger.info(f"Found {len(csv_files)} sign sample files")

    for csv_path in csv_files:
        sign_id = csv_path.stem
        landmarks_list = []
        states_list = []
        angles_list = []

        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    landmarks = np.array(json.loads(row["landmarks"]), dtype=np.float32).reshape(21, 3)
                    finger_states = json.loads(row["finger_states"])
                    joint_angles = json.loads(row["joint_angles"])

                    landmarks_list.append(landmarks)
                    states_list.append(finger_states)
                    angles_list.append(joint_angles)
                except Exception as e:
                    logger.warning(f"Skipping malformed row in {sign_id}: {e}")
                    continue

        if len(landmarks_list) < min_samples:
            logger.warning(f"[{sign_id}] Only {len(landmarks_list)} samples (min {min_samples}), skipping")
            continue

        # Extract features for each sample
        for landmarks in landmarks_list:
            # Create a mock HandLandmarks for feature extraction
            from app.core.hand_tracker import HandLandmarks, Handedness
            mock_hand = HandLandmarks(
                landmarks=landmarks,
                handedness=Handedness.RIGHT,  # Already normalized/mirrored
                confidence=1.0,
                image_width=640,
                image_height=480
            )
            feature_vec = FEATURE_EXTRACTOR.extract(mock_hand)
            X_list.append(feature_vec.features)
            y_list.append(sign_id)

        raw_landmarks_by_sign[sign_id] = landmarks_list
        finger_states_by_sign[sign_id] = states_list
        angles_by_sign[sign_id] = angles_list

        logger.info(f"  [{sign_id}] Loaded {len(landmarks_list)} samples")

    if not X_list:
        return np.array([]), np.array([]), {}, {}, {}

    X = np.vstack(X_list)
    y = np.array(y_list)

    logger.info(f"Total samples: {len(y)}, Feature dim: {X.shape[1]}")
    logger.info(f"Classes: {sorted(set(y))}")

    return X, y, raw_landmarks_by_sign, finger_states_by_sign, angles_by_sign


def compute_reference_data(
    landmarks_list: List[np.ndarray],
    finger_states_list: List[Dict[str, str]],
    angles_list: List[Dict[str, float]]
) -> Dict[str, Any]:
    """Compute median landmarks, finger state consensus, angle statistics, and tolerances."""
    if not landmarks_list:
        return {}

    # Median landmarks (21, 3)
    landmarks_stack = np.stack(landmarks_list)  # (N, 21, 3)
    median_landmarks = np.median(landmarks_stack, axis=0)
    std_landmarks = np.std(landmarks_stack, axis=0)

    # Finger state consensus
    finger_consensus = {}
    for finger in FINGER_NAMES:
        states = [s.get(finger, "unknown") for s in finger_states_list]
        # Most common state
        state_counts = {}
        for s in states:
            state_counts[s] = state_counts.get(s, 0) + 1
        consensus = max(state_counts, key=state_counts.get)
        confidence = state_counts[consensus] / len(states)
        finger_consensus[finger] = {
            "state": consensus,
            "confidence": confidence,
            "distribution": state_counts
        }

    # Angle statistics
    angle_stats = {}
    all_angle_names = set()
    for a in angles_list:
        all_angle_names.update(a.keys())

    for angle_name in sorted(all_angle_names):
        values = [a.get(angle_name, 0.0) for a in angles_list if angle_name in a]
        if values:
            angle_stats[angle_name] = {
                "median": float(np.median(values)),
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "min": float(np.min(values)),
                "max": float(np.max(values)),
                "count": len(values)
            }

    # Per-landmark tolerances (2 std deviations, minimum threshold)
    landmark_tolerances = np.maximum(std_landmarks * 2.0, 0.02)  # At least 0.02 normalized units

    return {
        "median_landmarks": median_landmarks.tolist(),
        "landmark_std": std_landmarks.tolist(),
        "landmark_tolerances": landmark_tolerances.tolist(),
        "finger_states": finger_consensus,
        "joint_angles": angle_stats,
        "sample_count": len(landmarks_list)
    }


def train_and_evaluate_models(X: np.ndarray, y: np.ndarray) -> Tuple[Any, Dict[str, Any]]:
    """Train multiple model types and return the best one with metrics."""
    from sklearn.model_selection import cross_val_score, StratifiedKFold
    from sklearn.metrics import classification_report, confusion_matrix
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.svm import SVC
    from sklearn.neural_network import MLPClassifier
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline

    models = {
        "random_forest": RandomForestClassifier(
            n_estimators=300,
            max_depth=None,
            min_samples_split=5,
            min_samples_leaf=2,
            n_jobs=-1,
            random_state=42,
            class_weight="balanced"
        ),
        "svm": Pipeline([
            ("scaler", StandardScaler()),
            ("svc", SVC(
                C=1.0,
                kernel="rbf",
                gamma="scale",
                probability=True,
                class_weight="balanced",
                random_state=42
            ))
        ]),
        "knn": Pipeline([
            ("scaler", StandardScaler()),
            ("knn", KNeighborsClassifier(
                n_neighbors=5,
                weights="distance",
                n_jobs=-1
            ))
        ]),
        "mlp": Pipeline([
            ("scaler", StandardScaler()),
            ("mlp", MLPClassifier(
                hidden_layer_sizes=(128, 64),
                alpha=0.001,
                max_iter=500,
                early_stopping=True,
                validation_fraction=0.1,
                random_state=42
            ))
        ]),
    }

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    best_model = None
    best_score = -1.0
    best_name = ""
    results = {}

    logger.info("\nModel comparison (5-fold CV):")
    logger.info("-" * 60)

    for name, model in models.items():
        try:
            scores = cross_val_score(model, X, y, cv=cv, n_jobs=-1, scoring="accuracy")
            mean_score = scores.mean()
            std_score = scores.std()
            results[name] = {"mean": mean_score, "std": std_score, "scores": scores.tolist()}
            logger.info(f"  {name:20s}  {mean_score:.4f} (+/- {std_score:.4f})")

            if np.isfinite(mean_score) and mean_score > best_score:
                best_score = mean_score
                best_model = model
                best_name = name
        except Exception as e:
            logger.warning(f"  {name:20s}  FAILED: {e}")

    logger.info("-" * 60)
    logger.info(f"Best model: {best_name} (CV accuracy: {best_score:.4f})")

    # Train best model on all data
    if best_model is None:
        raise ValueError("No model could be trained. Collect at least five samples for each of two or more signs.")
    best_model.fit(X, y)

    # Full evaluation on training data
    y_pred = best_model.predict(X)
    report = classification_report(y, y_pred, output_dict=True, zero_division=0)
    cm = confusion_matrix(y, y_pred, labels=sorted(set(y)))

    logger.info(f"\nTraining accuracy: {report['accuracy']:.4f}")

    # Per-class metrics
    logger.info("\nPer-class metrics:")
    classes = sorted(set(y))
    for cls in classes:
        if cls in report:
            m = report[cls]
            logger.info(f"  {cls:12s}  precision={m['precision']:.3f}  recall={m['recall']:.3f}  f1={m['f1-score']:.3f}  support={int(m['support'])}")

    # Confusion matrix for confusable pairs
    logger.info("\nConfusion matrix (rows=true, cols=pred):")
    logger.info("     " + "  ".join(f"{c:>5s}" for c in classes))
    for i, cls in enumerate(classes):
        row = cm[i]
        logger.info(f"  {cls:>4s} " + "  ".join(f"{v:5d}" for v in row))

    # Highlight common confusions
    logger.info("\nNotable confusions (off-diagonal > 5%):")
    for i, true_cls in enumerate(classes):
        for j, pred_cls in enumerate(classes):
            if i != j and cm[i, j] > 0:
                total = cm[i].sum()
                pct = cm[i, j] / total * 100
                if pct > 5:
                    logger.info(f"  {true_cls} -> {pred_cls}: {cm[i, j]}/{total} ({pct:.1f}%)")

    metrics = {
        "best_model": best_name,
        "cv_accuracy": best_score,
        "cv_std": results[best_name]["std"],
        "train_accuracy": report["accuracy"],
        "per_class": {k: v for k, v in report.items() if k not in ("accuracy", "macro avg", "weighted avg")},
        "confusion_matrix": cm.tolist(),
        "classes": classes,
        "all_results": results
    }

    return best_model, metrics


def update_signs_json_with_references(
    signs_path: Path,
    reference_data: Dict[str, Dict],
    model_classes: List[str]
):
    """Update signs.json with computed reference data and reference_source."""
    with open(signs_path, "r", encoding="utf-8") as f:
        signs = json.load(f)

    for sign in signs:
        sign_id = sign["id"]
        if sign_id in reference_data:
            ref = reference_data[sign_id]
            sign["reference"] = {
                "median_landmarks": ref["median_landmarks"],
                "landmark_tolerances": ref["landmark_tolerances"],
                "finger_states": ref["finger_states"],
                "joint_angles": ref["joint_angles"],
                "sample_count": ref["sample_count"]
            }
            sign["reference_source"] = "recorded"
            logger.info(f"  [{sign_id}] Updated with recorded reference ({ref['sample_count']} samples)")
        elif sign.get("reference_source") != "recorded":
            # Mark as rig-based if not already recorded
            if "reference_source" not in sign:
                sign["reference_source"] = "rig"
                logger.info(f"  [{sign_id}] Marked as rig-based reference")

    with open(signs_path, "w", encoding="utf-8") as f:
        json.dump(signs, f, indent=2)

    logger.info(f"Updated {signs_path}")


def main():
    parser = argparse.ArgumentParser(description="Train ASL recognition model from samples")
    parser.add_argument("--model-type", choices=["random_forest", "svm", "knn", "mlp", "auto"], default="auto", help="Model type (auto = best CV)")
    parser.add_argument("--sample-dir", default=str(SAMPLE_DIR), help="Sample data directory")
    parser.add_argument("--output-dir", default=str(MODEL_DIR), help="Model output directory")
    parser.add_argument("--min-samples", type=int, default=10, help="Minimum samples per sign to include")
    parser.add_argument("--force-model", help="Force specific model type (skip CV comparison)")
    args = parser.parse_args()

    sample_dir = Path(args.sample_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load content pack for sign metadata
    loader = initialize_content_packs(PROJECT_ROOT / "content_packs")
    pack = loader.get_current_pack()

    # Load samples
    X, y, raw_landmarks, finger_states, angles = load_samples(sample_dir, args.min_samples)

    if len(X) == 0:
        logger.error("No valid samples found. Run collect_samples.py first.")
        return 1

    # Check which signs have enough samples
    signs_with_samples = set(y)
    scored_signs = [s.id for s in pack.signs.values() if s.scored and not s.metadata.get("motion_sign")]
    missing_signs = set(scored_signs) - signs_with_samples

    if missing_signs:
        logger.warning(f"\nSigns with insufficient samples (need >= {args.min_samples}):")
        for s in sorted(missing_signs):
            logger.warning(f"  {s}")
        logger.warning("These will keep reference_source='rig' and won't be in the classifier.")

    # Train model
    chosen_model = args.force_model or (args.model_type if args.model_type != "auto" else None)
    if chosen_model:
        # Use specific model
        config = StaticRecognizerConfig(model_type=chosen_model)
        recognizer = StaticRecognizer(config)
        metrics = recognizer.train(X, y, class_names=sorted(set(y)))
        best_name = chosen_model
    else:
        # Auto-select best model
        model, metrics = train_and_evaluate_models(X, y)
        # Wrap in StaticRecognizer for saving
        config = StaticRecognizerConfig(model_type=metrics["best_model"])
        recognizer = StaticRecognizer(config)
        recognizer._model = model
        recognizer._classes = metrics["classes"]
        recognizer._label_to_idx = {label: i for i, label in enumerate(metrics["classes"])}
        recognizer._idx_to_label = {i: label for i, label in enumerate(metrics["classes"])}
        # Compute feature stats
        # CV models were fitted to raw features (pipelines own their scaling).
        recognizer._feature_mean = None
        recognizer._feature_std = None
        best_name = metrics["best_model"]

    # Compute reference data for all signs with samples
    reference_data = {}
    for sign_id in signs_with_samples:
        ref = compute_reference_data(
            raw_landmarks[sign_id],
            finger_states[sign_id],
            angles[sign_id]
        )
        reference_data[sign_id] = ref

    # Save model
    model_path = output_dir / "model"
    recognizer.save(model_path)
    logger.info(f"\nModel saved to {model_path}.joblib + {model_path}.json")

    # Update signs.json with references
    signs_path = PROJECT_ROOT / "content_packs/asl/signs.json"
    update_signs_json_with_references(signs_path, reference_data, metrics["classes"])

    # Print summary
    recorded = sum(1 for s in pack.signs.values() if s.id in reference_data)
    rig = sum(1 for s in pack.signs.values() if s.scored and not s.metadata.get("motion_sign") and s.id not in reference_data)
    motion = sum(1 for s in pack.signs.values() if s.metadata.get("motion_sign"))

    logger.info(f"\n=== SUMMARY ===")
    logger.info(f"Model: {best_name}")
    logger.info(f"CV Accuracy: {metrics['cv_accuracy']:.4f} (+/- {metrics['cv_std']:.4f})")
    logger.info(f"Train Accuracy: {metrics['train_accuracy']:.4f}")
    logger.info(f"Signs with recorded reference: {recorded}")
    logger.info(f"Signs with rig reference: {rig}")
    logger.info(f"Motion signs (not classified): {motion}")
    logger.info(f"Total scored signs: {recorded + rig + motion}")

    return 0


if __name__ == "__main__":
    import csv
    sys.exit(main())
