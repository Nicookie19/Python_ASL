"""
Unit tests for core functionality.
"""

import numpy as np
import pytest

from app.core.features import FeatureExtractor, DataAugmentation, normalize_features
from app.core.smoothing import TemporalSmoother, ConfidenceMeter, DwellDetector
from app.core.hand_tracker import HandLandmarks, Handedness, LandmarkIndex
from app.core.recognizer import StaticRecognizer, StaticRecognizerConfig, RecognitionResult
from app.data.db import (
    User, UserRole, Module, ModuleCategory, Difficulty, Sign,
    UserRepository, ModuleRepository, SignRepository, init_db
)
from app.content.loader import ContentPackLoader, initialize_content_packs, ContentPack
from app.core.camera_devices import CameraDevice, preferred_camera, is_static_frame_sequence
from app.core.inference_worker import InferenceResult
from app.core.pipeline import CorePipeline


def test_feature_extractor():
    """Test feature extraction from hand landmarks."""
    extractor = FeatureExtractor()
    
    # Create mock hand landmarks
    landmarks = np.random.rand(21, 3).astype(np.float32)
    landmarks[0] = [0.5, 0.5, 0.0]  # Wrist at center
    
    hand = HandLandmarks(
        landmarks=landmarks,
        handedness=Handedness.RIGHT,
        confidence=0.9,
        image_width=640,
        image_height=480
    )
    
    features = extractor.extract(hand)
    
    # Feature dimension depends on configuration (88 for default config)
    assert features.features.shape[0] == extractor.feature_dim
    assert features.features.shape[0] == 88
    assert features.handedness == "right"
    assert features.confidence == 0.9
    assert features.features.shape[0] > 0


def test_feature_normalization():
    """Test feature normalization."""
    X = np.random.rand(100, 50).astype(np.float32)
    X_norm, mean, std = normalize_features(X)
    
    assert X_norm.shape == X.shape
    assert np.allclose(np.mean(X_norm, axis=0), 0, atol=1e-6)
    assert np.allclose(np.std(X_norm, axis=0), 1, atol=1e-6)


def test_data_augmentation():
    """Test data augmentation."""
    extractor = FeatureExtractor()
    augmenter = DataAugmentation()
    
    X = np.random.rand(10, extractor.feature_dim).astype(np.float32)
    y = np.array(['A'] * 5 + ['B'] * 5)
    
    X_aug, y_aug = augmenter.augment_batch(X, y, extractor, n_augment=2)
    
    assert len(X_aug) == 30  # 10 original + 2*10 augmented
    assert len(y_aug) == 30


def test_temporal_smoother():
    """Test temporal smoothing."""
    smoother = TemporalSmoother(window_size=5, min_confidence=0.7, stability_threshold=0.8)
    
    # Feed consistent predictions
    for _ in range(5):
        result = smoother.update("A", 0.9)
    
    assert result.is_stable
    assert result.label == "A"
    assert result.confidence > 0.7
    
    # Feed inconsistent predictions
    smoother.reset()
    for label in ["A", "B", "A", "B", "A"]:
        result = smoother.update(label, 0.8)
    
    assert not result.is_stable


def test_confidence_meter():
    """Test confidence meter smoothing."""
    meter = ConfidenceMeter(smoothing_factor=0.3)
    
    label, conf = meter.update("A", 0.9, True)
    assert label == "A"
    assert conf > 0.0
    
    # Decay when not stable
    label, conf = meter.update("B", 0.1, False)
    assert conf < 0.9


def test_landmark_stabilization_reduces_one_frame_jitter():
    """The tracker should steady landmarks but promptly forget a lost hand."""
    from app.core.hand_tracker import HandTracker

    tracker = HandTracker()
    first = HandLandmarks(
        landmarks=np.zeros((21, 3), dtype=np.float32),
        handedness=Handedness.RIGHT,
        confidence=0.9,
        image_width=640,
        image_height=480,
    )
    tracker._stabilize_landmarks([first])

    second = HandLandmarks(
        landmarks=np.ones((21, 3), dtype=np.float32),
        handedness=Handedness.RIGHT,
        confidence=0.9,
        image_width=640,
        image_height=480,
    )
    tracker._stabilize_landmarks([second])
    assert np.allclose(second.landmarks, 0.65)

    for _ in range(3):
        tracker._stabilize_landmarks([])
    assert not tracker._landmark_ema


def test_pipeline_never_emits_landmarks_as_a_video_frame():
    """Regression test for the paint-path crash/stutter on hand detection."""
    pipeline = CorePipeline()
    pipeline._is_running = True
    emitted = []
    pipeline.result_ready.connect(emitted.append)

    hand = HandLandmarks(
        landmarks=np.zeros((21, 3), dtype=np.float32),
        handedness=Handedness.RIGHT,
        confidence=0.9,
        image_width=640,
        image_height=480,
    )
    pipeline._on_inference_result(InferenceResult(
        frame_number=7,
        timestamp_ms=1000.0,
        hands=[hand],
        recognition=None,
        smoothed=None,
        confidence_meter=("unknown", 0.0),
        dwell_result=(False, 0.0),
        processing_time_ms=8.0,
        inference_time_ms=8.0,
        target_sign_id="asl_a",
    ))

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    pipeline._on_frame_ready(frame)

    assert len(emitted) == 1
    result = emitted[0]
    assert result.frame is frame
    assert result.frame.shape == (480, 640, 3)
    assert result.hands == [hand]
    assert result.inference_frame_number == 7


def test_dwell_detector():
    """Test dwell detection."""
    detector = DwellDetector(dwell_time_ms=100, max_movement_px=10)
    
    # Start dwell
    detector.update((100, 100), "button1")
    
    # Should not trigger immediately
    triggered, progress = detector.update((100, 100), "button1")
    assert not triggered
    assert progress > 0
    
    # Note: Full timing test would require time manipulation


def test_recognizer_config():
    """Test recognizer configuration."""
    config = StaticRecognizerConfig(
        model_type="random_forest",
        n_estimators=10,
        confidence_threshold=0.8
    )
    
    recognizer = StaticRecognizer(config)
    assert recognizer.config.confidence_threshold == 0.8
    assert recognizer.config.n_estimators == 10


def test_db_initialization(tmp_path):
    """Test database initialization."""
    import os
    os.environ['XDG_DATA_HOME'] = str(tmp_path)
    
    # Re-import to pick up new path
    import importlib
    import app.data.db
    importlib.reload(app.data.db)
    from app.data.db import init_db, UserRepository
    
    init_db()
    
    user = UserRepository.create("Test User", "#22D3EE", UserRole.LEARNER)
    assert user.id >= 1  # ID may not be 1 due to test isolation
    assert user.name == "Test User"
    assert user.role.value == UserRole.LEARNER.value


def test_content_pack_loader(tmp_path):
    """Test content pack loader."""
    from app.content.loader import ContentPackLoader, create_default_asl_pack
    
    packs_dir = tmp_path / "packs"
    packs_dir.mkdir()
    
    # Create default pack manually
    create_default_asl_pack(packs_dir)
    
    loader = ContentPackLoader(packs_dir)
    packs = loader.discover_packs()
    
    # Should find the ASL pack
    assert len(packs) == 1
    assert packs[0].id == "asl"
    assert "asl" in loader._packs


def test_sign_repository():
    """Test sign repository operations."""
    from app.data.db import Sign, ModuleCategory, Difficulty
    
    sign = Sign(
        id="test_a",
        label="A",
        category=ModuleCategory.FINGERSPELLING,
        difficulty=Difficulty.EASY,
        description="Test sign",
        scored=True,
        handedness="both"
    )
    
    from app.data.db import SignRepository
    SignRepository.upsert(sign)
    
    retrieved = SignRepository.get_by_id("test_a")
    assert retrieved is not None
    assert retrieved.label == "A"
    assert retrieved.category == ModuleCategory.FINGERSPELLING


def test_module_repository():
    """Test module repository operations."""
    from app.data.db import Module, ModuleCategory, Difficulty, SignRepository, Sign
    
    # Create signs first
    sign1 = Sign(id="s1", label="A", category=ModuleCategory.FINGERSPELLING, difficulty=Difficulty.EASY, description="Test", handedness="both", scored=True)
    sign2 = Sign(id="s2", label="B", category=ModuleCategory.FINGERSPELLING, difficulty=Difficulty.EASY, description="Test", handedness="both", scored=True)
    SignRepository.upsert(sign1)
    SignRepository.upsert(sign2)
    
    module = Module(
        id="mod1",
        name="Test Module",
        category=ModuleCategory.FINGERSPELLING,
        difficulty=Difficulty.EASY,
        sign_ids=["s1", "s2"],
        description="Test module",
        estimated_time_minutes=10
    )
    
    from app.data.db import ModuleRepository
    ModuleRepository.upsert(module)
    
    retrieved = ModuleRepository.get_by_id("mod1")
    assert retrieved is not None
    assert retrieved.name == "Test Module"
    assert len(retrieved.sign_ids) == 2


def test_camera_preference_deprioritizes_obs_virtual_camera():
    devices = [
        CameraDevice(0, "OBS Virtual Camera"),
        CameraDevice(1, "FaceTime HD Camera"),
        CameraDevice(2, "USB Camera"),
    ]
    assert preferred_camera(devices).index == 1


def test_static_frame_detection():
    static = [np.full((20, 20, 3), 42, dtype=np.uint8) for _ in range(12)]
    moving = [np.full((20, 20, 3), value, dtype=np.uint8) for value in range(12)]
    assert is_static_frame_sequence(static)
    assert not is_static_frame_sequence(moving)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
