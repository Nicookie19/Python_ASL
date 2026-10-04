"""
Recognizer interface and static classifier implementation.
Designed to allow future sequence models (LSTM/GRU) without code changes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
import numpy as np
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class RecognitionResult:
    """Result of a recognition attempt."""
    label: str
    confidence: float
    all_scores: Dict[str, float]  # label -> confidence
    is_reliable: bool  # Above threshold and stable


class Recognizer(ABC):
    """Abstract base class for sign recognizers."""

    @abstractmethod
    def predict(self, features: np.ndarray) -> RecognitionResult:
        """Predict sign from feature vector."""
        pass

    @abstractmethod
    def predict_proba(self, features: np.ndarray) -> Dict[str, float]:
        """Get probability distribution over all classes."""
        pass

    @abstractmethod
    def get_classes(self) -> List[str]:
        """Get list of class labels."""
        pass

    @abstractmethod
    def save(self, path: Path) -> None:
        """Save model to disk."""
        pass

    @classmethod
    @abstractmethod
    def load(cls, path: Path) -> 'Recognizer':
        """Load model from disk."""
        pass


@dataclass
class StaticRecognizerConfig:
    """Configuration for static recognizer."""
    model_type: str = "random_forest"  # "random_forest", "svm", "mlp", "knn"
    n_estimators: int = 200
    max_depth: Optional[int] = None
    min_samples_split: int = 5
    min_samples_leaf: int = 2
    # SVM params
    svm_C: float = 1.0
    svm_kernel: str = "rbf"
    svm_gamma: str = "scale"
    # MLP params
    mlp_hidden_layers: Tuple[int, ...] = (128, 64)
    mlp_alpha: float = 0.001
    mlp_max_iter: int = 500
    # KNN params
    knn_neighbors: int = 5
    knn_weights: str = "distance"
    # Common
    confidence_threshold: float = 0.7
    smoothing_window: int = 5


class StaticRecognizer(Recognizer):
    """
    Static sign classifier using scikit-learn.
    Supports multiple model types with a unified interface.
    """

    def __init__(self, config: Optional[StaticRecognizerConfig] = None):
        self.config = config or StaticRecognizerConfig()
        self._model = None
        self._classes: List[str] = []
        self._feature_mean: Optional[np.ndarray] = None
        self._feature_std: Optional[np.ndarray] = None
        self._label_to_idx: Dict[str, int] = {}
        self._idx_to_label: Dict[int, str] = {}

        # Temporal smoothing
        self._prediction_buffer: List[Tuple[str, float]] = []
        self._smoothing_window = self.config.smoothing_window

    def _create_model(self):
        """Create the underlying sklearn model based on config."""
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.svm import SVC
        from sklearn.neural_network import MLPClassifier
        from sklearn.neighbors import KNeighborsClassifier

        if self.config.model_type == "random_forest":
            return RandomForestClassifier(
                n_estimators=self.config.n_estimators,
                max_depth=self.config.max_depth,
                min_samples_split=self.config.min_samples_split,
                min_samples_leaf=self.config.min_samples_leaf,
                n_jobs=-1,
                random_state=42,
                class_weight="balanced"
            )
        elif self.config.model_type == "svm":
            return SVC(
                C=self.config.svm_C,
                kernel=self.config.svm_kernel,
                gamma=self.config.svm_gamma,
                probability=True,
                class_weight="balanced",
                random_state=42
            )
        elif self.config.model_type == "mlp":
            return MLPClassifier(
                hidden_layer_sizes=self.config.mlp_hidden_layers,
                alpha=self.config.mlp_alpha,
                max_iter=self.config.mlp_max_iter,
                early_stopping=True,
                validation_fraction=0.1,
                random_state=42
            )
        elif self.config.model_type == "knn":
            return KNeighborsClassifier(
                n_neighbors=self.config.knn_neighbors,
                weights=self.config.knn_weights,
                n_jobs=-1
            )
        else:
            raise ValueError(f"Unknown model type: {self.config.model_type}")

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_mean: Optional[np.ndarray] = None,
        feature_std: Optional[np.ndarray] = None,
        class_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Train the classifier.
        Returns training metrics.
        """
        from sklearn.model_selection import cross_val_score, StratifiedKFold
        from sklearn.metrics import classification_report, confusion_matrix
        import numpy as np

        self._feature_mean = feature_mean
        self._feature_std = feature_std

        # Normalize features if stats provided
        if self._feature_mean is not None and self._feature_std is not None:
            X = (X - self._feature_mean) / (self._feature_std + 1e-8)

        # Determine classes
        if class_names is not None:
            self._classes = sorted(class_names)
        else:
            self._classes = sorted(np.unique(y).tolist())

        self._label_to_idx = {label: i for i, label in enumerate(self._classes)}
        self._idx_to_label = {i: label for i, label in enumerate(self._classes)}

        # Map labels to indices
        y_idx = np.array([self._label_to_idx[label] for label in y])

        # Create and train model
        self._model = self._create_model()
        self._model.fit(X, y_idx)

        # Cross-validation for honest accuracy estimate
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        cv_scores = cross_val_score(self._model, X, y_idx, cv=cv, n_jobs=-1)

        # Predictions for detailed metrics
        y_pred = self._model.predict(X)
        y_pred_labels = [self._idx_to_label[i] for i in y_pred]

        report = classification_report(y, y_pred_labels, output_dict=True, zero_division=0)
        cm = confusion_matrix(y, y_pred_labels, labels=self._classes)

        logger.info(f"Training complete. CV Accuracy: {cv_scores.mean():.3f} (+/- {cv_scores.std()*2:.3f})")
        logger.info(f"Training accuracy: {report['accuracy']:.3f}")

        return {
            "cv_accuracy_mean": float(cv_scores.mean()),
            "cv_accuracy_std": float(cv_scores.std()),
            "train_accuracy": float(report['accuracy']),
            "per_class_metrics": {k: v for k, v in report.items() if k not in ('accuracy', 'macro avg', 'weighted avg')},
            "confusion_matrix": cm.tolist(),
            "classes": self._classes,
            "model_type": self.config.model_type
        }

    def predict(self, features: np.ndarray) -> RecognitionResult:
        """Predict with temporal smoothing."""
        if self._model is None:
            return RecognitionResult(
                label="unknown",
                confidence=0.0,
                all_scores={},
                is_reliable=False
            )

        # Normalize
        if self._feature_mean is not None and self._feature_std is not None:
            features = (features - self._feature_mean) / (self._feature_std + 1e-8)

        # Get probabilities
        proba = self._model.predict_proba(features.reshape(1, -1))[0]
        scores = {self._idx_to_label[i]: float(p) for i, p in enumerate(proba)}

        # Top prediction
        top_idx = np.argmax(proba)
        top_label = self._idx_to_label[top_idx]
        top_confidence = float(proba[top_idx])

        # Temporal smoothing
        self._prediction_buffer.append((top_label, top_confidence))
        if len(self._prediction_buffer) > self._smoothing_window:
            self._prediction_buffer.pop(0)

        # Check stability: same label for majority of window
        if len(self._prediction_buffer) >= self._smoothing_window:
            labels = [p[0] for p in self._prediction_buffer]
            confidences = [p[1] for p in self._prediction_buffer]
            most_common = max(set(labels), key=labels.count)
            count = labels.count(most_common)
            avg_confidence = np.mean([c for l, c in self._prediction_buffer if l == most_common])

            if count >= self._smoothing_window * 0.6 and avg_confidence >= self.config.confidence_threshold:
                return RecognitionResult(
                    label=most_common,
                    confidence=avg_confidence,
                    all_scores=scores,
                    is_reliable=True
                )

        # Not stable enough or low confidence
        return RecognitionResult(
            label=top_label if top_confidence >= self.config.confidence_threshold else "unknown",
            confidence=top_confidence,
            all_scores=scores,
            is_reliable=False
        )

    def predict_proba(self, features: np.ndarray) -> Dict[str, float]:
        """Get probability distribution."""
        if self._model is None:
            return {}

        if self._feature_mean is not None and self._feature_std is not None:
            features = (features - self._feature_mean) / (self._feature_std + 1e-8)

        proba = self._model.predict_proba(features.reshape(1, -1))[0]
        return {self._idx_to_label[i]: float(p) for i, p in enumerate(proba)}

    def get_classes(self) -> List[str]:
        return self._classes.copy()

    def reset_smoothing(self) -> None:
        """Clear the prediction buffer."""
        self._prediction_buffer.clear()

    def save(self, path: Path) -> None:
        """Save model and metadata to disk."""
        import joblib

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        model_path = path.with_suffix('.joblib')
        meta_path = path.with_suffix('.json')

        joblib.dump(self._model, model_path)

        metadata = {
            "config": {
                "model_type": self.config.model_type,
                "n_estimators": self.config.n_estimators,
                "max_depth": self.config.max_depth,
                "min_samples_split": self.config.min_samples_split,
                "min_samples_leaf": self.config.min_samples_leaf,
                "svm_C": self.config.svm_C,
                "svm_kernel": self.config.svm_kernel,
                "svm_gamma": self.config.svm_gamma,
                "mlp_hidden_layers": self.config.mlp_hidden_layers,
                "mlp_alpha": self.config.mlp_alpha,
                "mlp_max_iter": self.config.mlp_max_iter,
                "knn_neighbors": self.config.knn_neighbors,
                "knn_weights": self.config.knn_weights,
                "confidence_threshold": self.config.confidence_threshold,
                "smoothing_window": self.config.smoothing_window
            },
            "classes": self._classes,
            "label_to_idx": self._label_to_idx,
            "feature_mean": self._feature_mean.tolist() if self._feature_mean is not None else None,
            "feature_std": self._feature_std.tolist() if self._feature_std is not None else None
        }

        with open(meta_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Model saved to {model_path} and {meta_path}")

    @classmethod
    def load(cls, path: Path) -> 'StaticRecognizer':
        """Load model from disk."""
        import joblib

        path = Path(path)
        model_path = path.with_suffix('.joblib')
        meta_path = path.with_suffix('.json')

        if not model_path.exists() or not meta_path.exists():
            raise FileNotFoundError(f"Model files not found at {path}")

        recognizer = cls()
        recognizer._model = joblib.load(model_path)

        with open(meta_path, 'r') as f:
            metadata = json.load(f)

        recognizer._classes = metadata["classes"]
        recognizer._label_to_idx = metadata["label_to_idx"]
        recognizer._idx_to_label = {int(k): v for k, v in metadata["label_to_idx"].items()}

        if metadata.get("feature_mean"):
            recognizer._feature_mean = np.array(metadata["feature_mean"])
        if metadata.get("feature_std"):
            recognizer._feature_std = np.array(metadata["feature_std"])

        # Restore config
        cfg = metadata["config"]
        recognizer.config = StaticRecognizerConfig(**cfg)
        recognizer._smoothing_window = recognizer.config.smoothing_window

        logger.info(f"Model loaded from {model_path} with classes: {recognizer._classes}")
        return recognizer


class SequenceRecognizer(Recognizer):
    """
    Placeholder for future sequence model (LSTM/GRU/Transformer).
    Same interface as StaticRecognizer for seamless integration.
    """

    def __init__(self, *args, **kwargs):
        raise NotImplementedError("SequenceRecognizer not implemented in V1. Use StaticRecognizer.")

    def predict(self, features: np.ndarray) -> RecognitionResult:
        pass

    def predict_proba(self, features: np.ndarray) -> Dict[str, float]:
        pass

    def get_classes(self) -> List[str]:
        pass

    def save(self, path: Path) -> None:
        pass

    @classmethod
    def load(cls, path: Path) -> 'SequenceRecognizer':
        pass


def create_recognizer(model_type: str = "static", **kwargs) -> Recognizer:
    """Factory function to create recognizer."""
    if model_type == "static":
        config = StaticRecognizerConfig(**kwargs)
        return StaticRecognizer(config)
    elif model_type == "sequence":
        return SequenceRecognizer(**kwargs)
    else:
        raise ValueError(f"Unknown recognizer type: {model_type}")