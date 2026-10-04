#!/usr/bin/env python3
"""
Training Tool for Sign Language Classifier.
Loads collected landmark data, trains a classifier, evaluates, and exports model.
Run: python tools/train_model.py
"""

import sys
import json
import argparse
from pathlib import Path
from typing import List, Tuple, Dict, Optional

import numpy as np
import joblib
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import (
    classification_report, confusion_matrix, accuracy_score,
    precision_recall_fscore_support
)

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.features import FeatureExtractor, DataAugmentation, normalize_features, save_feature_stats
from app.core.recognizer import StaticRecognizer, StaticRecognizerConfig


class ModelTrainer:
    """Trains and evaluates sign language classifier."""

    def __init__(
        self,
        data_dir: Path,
        model_dir: Path,
        model_type: str = "random_forest",
        test_split: float = 0.2,
        augment: bool = True,
        random_state: int = 42
    ):
        self.data_dir = Path(data_dir)
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self.model_type = model_type
        self.test_split = test_split
        self.augment = augment
        self.random_state = random_state

        self.extractor = FeatureExtractor()
        self.augmenter = DataAugmentation() if augment else None

        self.X_train = None
        self.X_test = None
        self.y_train = None
        self.y_test = None
        self.classes = None
        self.feature_mean = None
        self.feature_std = None

    def load_data(self, csv_files: Optional[List[Path]] = None) -> Tuple[np.ndarray, np.ndarray]:
        """Load landmark data from CSV files."""
        if csv_files is None:
            csv_files = list(self.data_dir.glob("landmarks_*.csv"))

        if not csv_files:
            raise FileNotFoundError(f"No CSV files found in {self.data_dir}")

        print(f"Loading data from {len(csv_files)} file(s)...")

        all_features = []
        all_labels = []

        for csv_path in csv_files:
            print(f"  Reading {csv_path.name}...")
            data = np.genfromtxt(csv_path, delimiter=',', skip_header=1, dtype=str)

            if data.size == 0:
                continue

            # Columns: session_id, person_id, timestamp, label, x0...z20, handedness, hand_confidence
            labels = data[:, 3]
            landmarks = data[:, 4:67].astype(np.float32)  # 63 landmark coords
            handedness = data[:, 67]

            # Reconstruct hand landmarks for feature extraction
            for i in range(len(labels)):
                label = labels[i]
                lm = landmarks[i].reshape(21, 3)
                hand = handedness[i]

                # Create a mock hand object for feature extraction
                from app.core.hand_tracker import HandLandmarks, Handedness
                hand_obj = HandLandmarks(
                    landmarks=lm,
                    handedness=Handedness(hand),
                    confidence=1.0,
                    image_width=640,
                    image_height=480
                )

                features = self.extractor.extract(hand_obj)
                all_features.append(features.features)
                all_labels.append(label)

        X = np.array(all_features)
        y = np.array(all_labels)

        print(f"Loaded {len(X)} samples with {X.shape[1]} features")
        print(f"Classes: {sorted(set(y))}")

        return X, y

    def prepare_data(self, X: np.ndarray, y: np.ndarray):
        """Split and normalize data."""
        # Split by session/person if possible to avoid data leakage
        # For now, use stratified split
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(
            X, y, test_size=self.test_split, stratify=y, random_state=self.random_state
        )

        # Normalize
        self.X_train, self.feature_mean, self.feature_std = normalize_features(self.X_train)
        self.X_test = (self.X_test - self.feature_mean) / (self.feature_std + 1e-8)

        self.classes = sorted(np.unique(y))

        print(f"Train: {len(self.X_train)}, Test: {len(self.X_test)}")
        print(f"Classes ({len(self.classes)}): {self.classes}")

        # Augment training data
        if self.augment and self.augmenter:
            print("Applying data augmentation...")
            X_aug, y_aug = self.augmenter.augment_batch(
                self.X_train, self.y_train, self.extractor, n_augment=2
            )
            self.X_train = X_aug
            self.y_train = y_aug
            print(f"Augmented train size: {len(self.X_train)}")

    def create_model(self):
        """Create the classifier based on model_type."""
        if self.model_type == "random_forest":
            return RandomForestClassifier(
                n_estimators=300,
                max_depth=None,
                min_samples_split=5,
                min_samples_leaf=2,
                n_jobs=-1,
                random_state=self.random_state,
                class_weight="balanced"
            )
        elif self.model_type == "svm":
            return SVC(
                C=1.0,
                kernel="rbf",
                gamma="scale",
                probability=True,
                class_weight="balanced",
                random_state=self.random_state
            )
        elif self.model_type == "mlp":
            return MLPClassifier(
                hidden_layer_sizes=(256, 128, 64),
                alpha=0.001,
                max_iter=1000,
                early_stopping=True,
                validation_fraction=0.1,
                random_state=self.random_state
            )
        elif self.model_type == "knn":
            return KNeighborsClassifier(
                n_neighbors=5,
                weights="distance",
                n_jobs=-1
            )
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

    def train(self) -> Dict:
        """Train the model and return metrics."""
        model = self.create_model()

        print(f"\nTraining {self.model_type}...")
        model.fit(self.X_train, self.y_train)

        # Cross-validation on training data
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=self.random_state)
        cv_scores = cross_val_score(model, self.X_train, self.y_train, cv=cv, n_jobs=-1)

        # Test set evaluation
        y_pred = model.predict(self.X_test)
        test_accuracy = accuracy_score(self.y_test, y_pred)

        # Detailed metrics
        report = classification_report(self.y_test, y_pred, output_dict=True, zero_division=0)
        cm = confusion_matrix(self.y_test, y_pred, labels=self.classes)

        # Per-class metrics
        precision, recall, f1, support = precision_recall_fscore_support(
            self.y_test, y_pred, labels=self.classes, zero_division=0
        )

        metrics = {
            "model_type": self.model_type,
            "cv_accuracy_mean": float(cv_scores.mean()),
            "cv_accuracy_std": float(cv_scores.std()),
            "test_accuracy": float(test_accuracy),
            "train_samples": len(self.X_train),
            "test_samples": len(self.X_test),
            "classes": self.classes,
            "per_class": {
                cls: {
                    "precision": float(precision[i]),
                    "recall": float(recall[i]),
                    "f1": float(f1[i]),
                    "support": int(support[i])
                }
                for i, cls in enumerate(self.classes)
            },
            "confusion_matrix": cm.tolist()
        }

        # Save model and metadata
        self._save_model(model, metrics)

        return metrics

    def _save_model(self, model, metrics: Dict):
        """Save model, scaler, and metadata."""
        # Save sklearn model
        model_path = self.model_dir / "model.joblib"
        joblib.dump(model, model_path)

        # Save feature normalization stats
        stats_path = self.model_dir / "feature_stats.npz"
        save_feature_stats(self.feature_mean, self.feature_std, stats_path)

        # Save labels
        labels_path = self.model_dir / "labels.json"
        with open(labels_path, 'w') as f:
            json.dump(self.classes, f, indent=2)

        # Save metadata
        meta_path = self.model_dir / "metadata.json"
        with open(meta_path, 'w') as f:
            json.dump(metrics, f, indent=2)

        # Save recognizer config
        config = StaticRecognizerConfig()
        recognizer = StaticRecognizer(config)
        recognizer._model = model
        recognizer._classes = self.classes
        recognizer._feature_mean = self.feature_mean
        recognizer._feature_std = self.feature_std
        recognizer._label_to_idx = {label: i for i, label in enumerate(self.classes)}
        recognizer._idx_to_label = {i: label for i, label in enumerate(self.classes)}
        recognizer.save(self.model_dir / "recognizer")

        print(f"\nModel saved to {self.model_dir}")
        print(f"  - {model_path}")
        print(f"  - {labels_path}")
        print(f"  - {stats_path}")
        print(f"  - {meta_path}")
        print(f"  - recognizer.joblib + recognizer.json")

    def plot_confusion_matrix(self, cm: np.ndarray, output_path: Path):
        """Plot and save confusion matrix."""
        plt.figure(figsize=(14, 12))
        sns.heatmap(
            cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=self.classes, yticklabels=self.classes
        )
        plt.title(f'Confusion Matrix - {self.model_type}')
        plt.xlabel('Predicted')
        plt.ylabel('True')
        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()
        print(f"Confusion matrix saved to {output_path}")

    def plot_per_class_metrics(self, metrics: Dict, output_path: Path):
        """Plot per-class precision, recall, F1."""
        classes = metrics["classes"]
        precision = [metrics["per_class"][c]["precision"] for c in classes]
        recall = [metrics["per_class"][c]["recall"] for c in classes]
        f1 = [metrics["per_class"][c]["f1"] for c in classes]

        x = np.arange(len(classes))
        width = 0.25

        fig, ax = plt.subplots(figsize=(16, 6))
        ax.bar(x - width, precision, width, label='Precision', color='#22D3EE')
        ax.bar(x, recall, width, label='Recall', color='#4ADE80')
        ax.bar(x + width, f1, width, label='F1', color='#FBBF24')

        ax.set_xlabel('Class')
        ax.set_ylabel('Score')
        ax.set_title(f'Per-Class Metrics - {self.model_type}')
        ax.set_xticks(x)
        ax.set_xticklabels(classes, rotation=45, ha='right')
        ax.legend()
        ax.set_ylim(0, 1.05)
        ax.grid(axis='y', alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()
        print(f"Per-class metrics plot saved to {output_path}")

    def analyze_confusions(self, metrics: Dict, threshold: float = 0.3):
        """Analyze and print common confusions."""
        cm = np.array(metrics["confusion_matrix"])
        classes = metrics["classes"]

        print("\n🔍 Confusion Analysis (off-diagonal > 30%):")
        print("-" * 50)

        for i, true_class in enumerate(classes):
            row = cm[i]
            total = row.sum()
            if total == 0:
                continue

            for j, pred_class in enumerate(classes):
                if i != j and row[j] / total > threshold:
                    print(f"  {true_class} → {pred_class}: {row[j]}/{total} ({row[j]/total:.1%})")

        # Overall accuracy per class
        print("\n📊 Per-Class Accuracy:")
        print("-" * 50)
        for i, cls in enumerate(classes):
            total = cm[i].sum()
            correct = cm[i, i]
            acc = correct / total if total > 0 else 0
            status = "✅" if acc >= 0.9 else "⚠️" if acc >= 0.7 else "❌"
            print(f"  {status} {cls}: {acc:.1%} ({correct}/{total})")


def main():
    parser = argparse.ArgumentParser(description="Train ASL classifier from collected landmarks")
    parser.add_argument("--data", "-d", default="data/collected",
                       help="Directory with collected CSV files")
    parser.add_argument("--output", "-o", default="content_packs/asl/model",
                       help="Output directory for model")
    parser.add_argument("--model", "-m", default="random_forest",
                       choices=["random_forest", "svm", "mlp", "knn"],
                       help="Model type")
    parser.add_argument("--test-split", "-t", type=float, default=0.2,
                       help="Test split ratio")
    parser.add_argument("--no-augment", action="store_true",
                       help="Disable data augmentation")
    parser.add_argument("--plots", "-p", action="store_true",
                       help="Generate plots (requires matplotlib)")

    args = parser.parse_args()

    print("=" * 60)
    print("ASL Model Training Tool")
    print("=" * 60)
    print(f"Data directory: {args.data}")
    print(f"Output directory: {args.output}")
    print(f"Model type: {args.model}")
    print(f"Test split: {args.test_split}")
    print(f"Augmentation: {not args.no_augment}")
    print("=" * 60)

    trainer = ModelTrainer(
        data_dir=args.data,
        model_dir=args.output,
        model_type=args.model,
        test_split=args.test_split,
        augment=not args.no_augment
    )

    try:
        # Load data
        X, y = trainer.load_data()

        if len(X) == 0:
            print("ERROR: No data loaded!")
            return 1

        # Prepare
        trainer.prepare_data(X, y)

        # Train
        metrics = trainer.train()

        # Print results
        print("\n" + "=" * 60)
        print("TRAINING RESULTS")
        print("=" * 60)
        print(f"CV Accuracy: {metrics['cv_accuracy_mean']:.3f} ± {metrics['cv_accuracy_std']:.3f}")
        print(f"Test Accuracy: {metrics['test_accuracy']:.3f}")
        print(f"Train samples: {metrics['train_samples']}")
        print(f"Test samples: {metrics['test_samples']}")

        # Analyze confusions
        trainer.analyze_confusions(metrics)

        # Generate plots
        if args.plots:
            cm = np.array(metrics["confusion_matrix"])
            trainer.plot_confusion_matrix(cm, Path(args.output) / "confusion_matrix.png")
            trainer.plot_per_class_metrics(metrics, Path(args.output) / "per_class_metrics.png")

        # Honest assessment
        print("\n" + "=" * 60)
        print("HONEST ASSESSMENT")
        print("=" * 60)
        if metrics['test_accuracy'] >= 0.9:
            print("✅ Target accuracy (≥90%) ACHIEVED!")
        else:
            print(f"⚠️  Target accuracy (90%) NOT reached. Current: {metrics['test_accuracy']:.1%}")
            print("\nRecommendations:")
            print("  1. Collect more diverse samples (different lighting, angles, people)")
            print("  2. Focus on confused pairs (see confusion analysis above)")
            print("  3. Try different model (SVM or MLP might work better)")
            print("  4. Increase augmentation")
            print("  5. Check for label errors in collected data")

        print("=" * 60)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())