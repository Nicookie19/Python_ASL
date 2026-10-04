"""
Core processing modules
"""

from app.core.camera_worker import CameraWorker, FakeCameraWorker
from app.core.camera_service import CameraService, CameraConfig, CameraFrame, CameraCaptureWorker
from app.core.hand_tracker import HandTracker, HandLandmarks, Handedness, LandmarkIndex
from app.core.features import FeatureExtractor, FeatureVector, DataAugmentation, normalize_features
from app.core.recognizer import Recognizer, RecognitionResult, StaticRecognizer, StaticRecognizerConfig, SequenceRecognizer, create_recognizer
from app.core.smoothing import TemporalSmoother, ConfidenceMeter as SmoothingConfidenceMeter, DwellDetector
from app.core.pipeline import CorePipeline, PipelineResult
from app.core.camera_devices import CameraDevice, discover_camera_devices, preferred_camera, is_static_frame_sequence
from app.core.inference_worker import InferenceWorker, InferenceRequest, InferenceResult

__all__ = [
    "CameraWorker",
    "FakeCameraWorker",
    "CameraService",
    "CameraConfig",
    "CameraFrame",
    "CameraCaptureWorker",
    "InferenceWorker",
    "InferenceRequest",
    "InferenceResult",
    "HandTracker",
    "HandLandmarks",
    "Handedness",
    "LandmarkIndex",
    "FeatureExtractor",
    "FeatureVector",
    "DataAugmentation",
    "normalize_features",
    "Recognizer",
    "RecognitionResult",
    "StaticRecognizer",
    "StaticRecognizerConfig",
    "SequenceRecognizer",
    "create_recognizer",
    "TemporalSmoother",
    "SmoothingConfidenceMeter",
    "DwellDetector",
    "CorePipeline",
    "PipelineResult",
    "CameraDevice",
    "discover_camera_devices",
    "preferred_camera",
    "is_static_frame_sequence",
]
