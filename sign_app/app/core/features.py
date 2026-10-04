"""
Feature extraction from hand landmarks for classification.
Implements translation, scaling, and handedness normalization.
"""

import numpy as np
from typing import Optional, List, Tuple
from dataclasses import dataclass
import logging

from app.core.hand_tracker import HandLandmarks, LandmarkIndex

logger = logging.getLogger(__name__)


@dataclass
class FeatureVector:
    """Extracted feature vector for classification."""
    features: np.ndarray  # Flattened feature array
    raw_landmarks: np.ndarray  # Original normalized landmarks (21, 3)
    handedness: str
    confidence: float


class FeatureExtractor:
    """
    Extracts classification features from hand landmarks.

    Features:
    1. Translate so wrist is at origin
    2. Scale by hand size (wrist to middle MCP distance)
    3. Mirror left hands to right (or keep both)
    4. Optionally include 3D info (z-coordinate)
    5. Include derived features: joint angles, fingertip distances
    """

    def __init__(
        self,
        mirror_left_to_right: bool = True,
        use_3d: bool = True,
        include_angles: bool = True,
        include_distances: bool = True
    ):
        self.mirror_left_to_right = mirror_left_to_right
        self.use_3d = use_3d
        self.include_angles = include_angles
        self.include_distances = include_distances

        # Expected feature dimension
        self._feature_dim = self._calculate_feature_dim()

    def _calculate_feature_dim(self) -> int:
        """Calculate expected feature vector dimension."""
        # Base: 21 landmarks * (2 or 3 coords)
        base_dim = 21 * (3 if self.use_3d else 2)

        # Derived features
        derived = 0
        if self.include_angles:
            # Joint angles: 2 angles per finger * 5 fingers = 10
            # (MCP-PIP and PIP-DIP for each finger, including thumb)
            derived += 10
        if self.include_distances:
            # Fingertip to wrist distances: 5
            # Fingertip to fingertip distances: 10 (5 choose 2)
            derived += 15

        return base_dim + derived

    def extract(self, hand: HandLandmarks) -> FeatureVector:
        """
        Extract features from hand landmarks.
        Returns normalized feature vector ready for classification.
        """
        landmarks = hand.landmarks.copy()  # (21, 3) normalized [0,1]
        handedness = hand.handedness.value

        # 1. Translate to wrist origin
        wrist = landmarks[LandmarkIndex.WRIST]
        landmarks = landmarks - wrist

        # 2. Scale by hand size (wrist to middle MCP distance)
        middle_mcp = landmarks[LandmarkIndex.MIDDLE_MCP]
        hand_scale = np.linalg.norm(middle_mcp[:2]) + 1e-6  # 2D distance
        landmarks = landmarks / hand_scale

        # 3. Mirror left hand to right if enabled
        if self.mirror_left_to_right and handedness == "left":
            landmarks[:, 0] = -landmarks[:, 0]  # Flip x-axis

        # 4. Flatten base features
        if self.use_3d:
            base_features = landmarks.flatten()  # 63 dims
        else:
            base_features = landmarks[:, :2].flatten()  # 42 dims

        # 5. Add derived features
        derived_features = []
        if self.include_angles:
            angles = self._compute_joint_angles(landmarks)
            derived_features.append(angles)

        if self.include_distances:
            distances = self._compute_distances(landmarks)
            derived_features.append(distances)

        if derived_features:
            features = np.concatenate([base_features] + derived_features)
        else:
            features = base_features

        return FeatureVector(
            features=features.astype(np.float32),
            raw_landmarks=hand.landmarks,
            handedness=handedness,
            confidence=hand.confidence
        )

    def _compute_joint_angles(self, landmarks: np.ndarray) -> np.ndarray:
        """
        Compute joint angles for each finger.
        Returns array of angles in radians.
        """
        angles = []

        # Finger chains: (MCP, PIP, DIP, TIP) for each finger
        # Thumb: (CMC, MCP, IP, TIP)
        finger_chains = [
            [LandmarkIndex.THUMB_CMC, LandmarkIndex.THUMB_MCP, LandmarkIndex.THUMB_IP, LandmarkIndex.THUMB_TIP],
            [LandmarkIndex.INDEX_MCP, LandmarkIndex.INDEX_PIP, LandmarkIndex.INDEX_DIP, LandmarkIndex.INDEX_TIP],
            [LandmarkIndex.MIDDLE_MCP, LandmarkIndex.MIDDLE_PIP, LandmarkIndex.MIDDLE_DIP, LandmarkIndex.MIDDLE_TIP],
            [LandmarkIndex.RING_MCP, LandmarkIndex.RING_PIP, LandmarkIndex.RING_DIP, LandmarkIndex.RING_TIP],
            [LandmarkIndex.PINKY_MCP, LandmarkIndex.PINKY_PIP, LandmarkIndex.PINKY_DIP, LandmarkIndex.PINKY_TIP],
        ]

        for chain in finger_chains:
            if len(chain) == 4:
                # Two joint angles per finger (MCP-PIP, PIP-DIP)
                # Vector from joint 1 to joint 2
                v1 = landmarks[chain[1]] - landmarks[chain[0]]
                v2 = landmarks[chain[2]] - landmarks[chain[1]]
                v3 = landmarks[chain[3]] - landmarks[chain[2]]

                # Angle at joint 1 (MCP)
                angle1 = self._angle_between(v1, v2)
                # Angle at joint 2 (PIP)
                angle2 = self._angle_between(v2, v3)
                angles.extend([angle1, angle2])

        return np.array(angles, dtype=np.float32)

    def _compute_distances(self, landmarks: np.ndarray) -> np.ndarray:
        """
        Compute useful distances.
        Returns array of normalized distances.
        """
        distances = []
        wrist = landmarks[LandmarkIndex.WRIST]

        # Fingertip to wrist distances
        fingertips = LandmarkIndex.FINGERTIPS
        for tip_idx in fingertips:
            dist = np.linalg.norm(landmarks[tip_idx] - wrist)
            distances.append(dist)

        # Fingertip to fingertip distances (5 choose 2 = 10)
        for i in range(len(fingertips)):
            for j in range(i + 1, len(fingertips)):
                dist = np.linalg.norm(landmarks[fingertips[i]] - landmarks[fingertips[j]])
                distances.append(dist)

        return np.array(distances, dtype=np.float32)

    @staticmethod
    def _angle_between(v1: np.ndarray, v2: np.ndarray) -> float:
        """Compute angle between two vectors in radians."""
        dot = np.dot(v1, v2)
        norm = np.linalg.norm(v1) * np.linalg.norm(v2)
        if norm < 1e-6:
            return 0.0
        cos_angle = np.clip(dot / norm, -1.0, 1.0)
        return np.arccos(cos_angle)

    @property
    def feature_dim(self) -> int:
        return self._feature_dim


class DataAugmentation:
    """
    Data augmentation for training robustness.
    Applies random transformations to landmark features.
    """

    def __init__(
        self,
        rotation_range: float = 0.15,  # radians
        scale_range: float = 0.1,
        noise_std: float = 0.01,
        translate_range: float = 0.02
    ):
        self.rotation_range = rotation_range
        self.scale_range = scale_range
        self.noise_std = noise_std
        self.translate_range = translate_range

    def augment(self, features: np.ndarray, feature_extractor: FeatureExtractor) -> np.ndarray:
        """
        Augment a feature vector by applying random transformations
        to the underlying landmarks and re-extracting.
        """
        # This is a simplified version - in practice you'd augment raw landmarks
        # and re-run the full extraction pipeline
        augmented = features.copy()

        # Add Gaussian noise
        if self.noise_std > 0:
            noise = np.random.normal(0, self.noise_std, features.shape)
            augmented += noise

        # Random scale
        if self.scale_range > 0:
            scale = 1.0 + np.random.uniform(-self.scale_range, self.scale_range)
            augmented *= scale

        return augmented

    def augment_batch(
        self,
        features_batch: np.ndarray,
        labels: np.ndarray,
        feature_extractor: FeatureExtractor,
        n_augment: int = 2
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Augment a batch of features.
        Returns augmented features and corresponding labels.
        """
        augmented_features = [features_batch]
        augmented_labels = [labels]

        for _ in range(n_augment):
            aug_features = np.array([
                self.augment(f, feature_extractor) for f in features_batch
            ])
            augmented_features.append(aug_features)
            augmented_labels.append(labels)

        return np.vstack(augmented_features), np.hstack(augmented_labels)


def normalize_features(
    features: np.ndarray,
    mean: Optional[np.ndarray] = None,
    std: Optional[np.ndarray] = None
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Normalize features to zero mean, unit variance.
    Returns normalized features, mean, std.
    """
    if mean is None:
        mean = np.mean(features, axis=0)
    if std is None:
        std = np.std(features, axis=0) + 1e-8

    normalized = (features - mean) / std
    return normalized, mean, std


def load_feature_stats(stats_path: str) -> Tuple[np.ndarray, np.ndarray]:
    """Load feature normalization stats from file."""
    data = np.load(stats_path)
    return data['mean'], data['std']


def save_feature_stats(mean: np.ndarray, std: np.ndarray, stats_path: str) -> None:
    """Save feature normalization stats to file."""
    np.savez(stats_path, mean=mean, std=std)