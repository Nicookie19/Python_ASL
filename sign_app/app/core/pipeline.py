"""
Core processing pipeline connecting camera, hand tracking, features, and recognition.
Runs in a background thread and emits results via Qt signals.
"""

import numpy as np
from PySide6.QtCore import QObject, Signal, Slot, QThread, QMutex, Qt
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import logging
import time

from app.core.camera_worker import CameraWorker, FakeCameraWorker
from app.core.hand_tracker import HandTracker, HandLandmarks, HandTrackerResult
from app.core.features import FeatureExtractor, FeatureVector
from app.core.recognizer import Recognizer, RecognitionResult, StaticRecognizer
from app.core.smoothing import TemporalSmoother, ConfidenceMeter, DwellDetector
from app.core.camera_devices import discover_camera_devices, preferred_camera
from app.core.inference_worker import InferenceWorker, InferenceRequest, InferenceResult

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Complete pipeline result for one frame."""
    frame: np.ndarray  # BGR frame with overlays
    original_frame: np.ndarray  # Original frame without overlays
    hands: List[HandLandmarks]
    recognition: Optional[RecognitionResult]
    smoothed: Optional[Any]  # SmoothedPrediction
    confidence_meter: Tuple[str, float]  # (label, confidence)
    dwell_result: Tuple[bool, float]  # (triggered, progress)
    fps: float
    processing_time_ms: float
    inference_time_ms: float
    inference_fps: float
    target_sign_id: Optional[str] = None
    target_landmarks: Optional[np.ndarray] = None


class CorePipeline(QObject):
    """
    Main processing pipeline.
    Runs camera capture, hand tracking, feature extraction, and recognition.
    Capture and display run at full camera rate; inference runs at its own pace.
    """

    # Signals to UI
    result_ready = Signal(object)  # PipelineResult
    error_occurred = Signal(str)
    camera_status_changed = Signal(bool, str)  # (is_running, message)
    model_loaded = Signal(bool, str)  # (success, message)
    inference_fps_update = Signal(float)  # inference FPS

    def __init__(self):
        super().__init__()
        self._camera_worker = None
        self._inference_worker = None
        self._hand_tracker = HandTracker()
        self._feature_extractor = FeatureExtractor()
        self._recognizer: Optional[Recognizer] = None
        self._smoother = TemporalSmoother()
        self._confidence_meter = ConfidenceMeter()
        self._dwell_detector = DwellDetector()

        self._target_sign_id: Optional[str] = None
        self._target_landmarks: Optional[np.ndarray] = None
        self._is_running = False
        self._mutex = QMutex()

        # Performance tracking
        self._frame_count = 0
        self._last_fps_time = time.time()
        self._display_fps = 0.0
        self._inference_fps = 0.0

    def initialize(self, use_fake_camera: bool = False) -> bool:
        """Initialize all components."""
        # Initialize hand tracker (for drawing overlays)
        if not self._hand_tracker.initialize():
            self.error_occurred.emit("Failed to initialize hand tracker - running in demo mode")
            # Continue anyway for demo mode
            pass

        # Create inference worker
        self._inference_worker = InferenceWorker(max_hands=1, model_complexity=0)
        if not self._inference_worker.initialize():
            self.error_occurred.emit("Failed to initialize inference worker - running in demo mode")
            # Continue anyway for demo mode
            pass

        # Create camera worker
        if use_fake_camera:
            self._camera_worker = FakeCameraWorker(target_fps=30)
        else:
            preferred = preferred_camera(discover_camera_devices())
            self._camera_worker = CameraWorker(camera_device=preferred, target_fps=30, resolution=(640, 480))

        # Connect camera signals - capture runs at full rate
        self._camera_worker.frame_ready.connect(self._on_frame_ready, Qt.DirectConnection)
        self._camera_worker.error_occurred.connect(self.error_occurred.emit)
        self._camera_worker.camera_started.connect(
            lambda idx: self.camera_status_changed.emit(True, f"Camera {idx} started")
        )
        self._camera_worker.camera_stopped.connect(
            lambda: self.camera_status_changed.emit(False, "Camera stopped")
        )
        self._camera_worker.static_feed_detected.connect(
            lambda message: self.camera_status_changed.emit(True, message)
        )

        # Connect inference worker signals
        self._inference_worker.result_ready.connect(self._on_inference_result)
        self._inference_worker.error_occurred.connect(self.error_occurred.emit)
        self._inference_worker.fps_update.connect(self._on_inference_fps)

        return True

    def load_model(self, model_path: str) -> bool:
        """Load recognition model."""
        try:
            self._recognizer = StaticRecognizer.load(model_path)
            self.model_loaded.emit(True, f"Model loaded: {len(self._recognizer.get_classes())} classes")
            logger.info(f"Model loaded successfully with classes: {self._recognizer.get_classes()}")
            
            # Load model into inference worker
            if self._inference_worker:
                self._inference_worker.load_model(model_path)
            return True
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self.model_loaded.emit(False, str(e))
            return False

    def start(self) -> None:
        """Start the pipeline."""
        if not self._is_running:
            self._is_running = True
            if self._camera_worker:
                self._camera_worker.start()
            if self._inference_worker:
                self._inference_worker.start()
            self._smoother.reset()
            self._confidence_meter.reset()

    @property
    def model_available(self) -> bool:
        """Whether recognition can make an honest prediction."""
        return self._recognizer is not None

    def stop(self) -> None:
        """Stop the pipeline."""
        self._is_running = False
        if self._camera_worker:
            self._camera_worker.stop()
        if self._inference_worker:
            self._inference_worker.stop()

    def set_target_sign(self, sign_id: str, landmarks: Optional[np.ndarray] = None) -> None:
        """Set the target sign for practice mode."""
        self._target_sign_id = sign_id
        self._target_landmarks = landmarks
        if self._inference_worker:
            self._inference_worker.set_target_sign(sign_id, landmarks)

    def clear_target(self) -> None:
        """Clear target sign (for dictionary browsing, etc.)."""
        self._target_sign_id = None
        self._target_landmarks = None
        if self._inference_worker:
            self._inference_worker.clear_target()

    def set_dwell_enabled(self, enabled: bool) -> None:
        """Enable/disable hand dwell interaction."""
        if self._inference_worker:
            self._inference_worker.set_dwell_enabled(enabled)

    def set_dwell_duration(self, ms: int) -> None:
        """Set dwell duration."""
        if self._inference_worker:
            self._inference_worker.set_dwell_duration(ms)

    def set_confidence_threshold(self, threshold: float) -> None:
        """Update confidence threshold."""
        if self._inference_worker:
            self._inference_worker.set_confidence_threshold(threshold)

    def set_smoothing_window(self, frames: int) -> None:
        """Update smoothing window."""
        if self._inference_worker:
            self._inference_worker.set_smoothing_window(frames)

    @Slot(np.ndarray)
    def _on_frame_ready(self, frame: np.ndarray) -> None:
        """Handle new frame from camera - submit to inference and display immediately."""
        if not self._is_running:
            return

        self._frame_count += 1
        now = time.time()
        if now - self._last_fps_time >= 1.0:
            self._display_fps = self._frame_count / (now - self._last_fps_time)
            self._frame_count = 0
            self._last_fps_time = now

        # Submit frame to inference worker (non-blocking, drops old frames)
        if self._inference_worker and self._inference_worker.isRunning():
            self._inference_worker.submit_frame(
                frame=frame,
                frame_number=self._frame_count,
                timestamp_ms=time.time() * 1000,
                target_sign_id=self._target_sign_id,
                target_landmarks=self._target_landmarks
            )

        # Emit frame immediately for display (without inference overlay)
        # The UI will receive inference results separately and overlay them
        result = PipelineResult(
            frame=frame,  # Original frame for display
            original_frame=frame,
            hands=[],  # Will be filled by inference result
            recognition=None,
            smoothed=None,
            confidence_meter=("unknown", 0.0),
            dwell_result=(False, 0.0),
            fps=self._display_fps,
            processing_time_ms=0.0,
            inference_time_ms=0.0,
            inference_fps=0.0,
            target_sign_id=self._target_sign_id,
            target_landmarks=self._target_landmarks
        )
        self.result_ready.emit(result)

    @Slot(object)
    def _on_inference_result(self, result) -> None:
        """Handle inference result from worker."""
        if not self._is_running:
            return

        # Create full pipeline result with inference overlay
        result = PipelineResult(
            frame=result.hands[0].landmarks if result.hands else None,  # Placeholder - will be drawn by UI
            original_frame=None,  # Not needed for UI
            hands=result.hands,
            recognition=result.recognition,
            smoothed=result.smoothed,
            confidence_meter=result.confidence_meter,
            dwell_result=result.dwell_result,
            fps=0.0,  # Display FPS is tracked separately
            processing_time_ms=result.processing_time_ms,
            inference_time_ms=result.inference_time_ms,
            inference_fps=self._inference_fps,
            target_sign_id=result.target_sign_id,
            target_landmarks=result.target_landmarks
        )
        self.result_ready.emit(result)

    @Slot(float)
    def _on_inference_fps(self, fps: float) -> None:
        """Handle inference FPS update."""
        self._inference_fps = fps

    def load_model(self, model_path: str) -> bool:
        """Load recognition model."""
        try:
            self._recognizer = StaticRecognizer.load(model_path)
            self.model_loaded.emit(True, f"Model loaded: {len(self._recognizer.get_classes())} classes")
            logger.info(f"Model loaded successfully with classes: {self._recognizer.get_classes()}")
            
            # Load model into inference worker
            if self._inference_worker:
                self._inference_worker.load_model(model_path)
            return True
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self.model_loaded.emit(False, str(e))
            return False

    def start(self) -> None:
        """Start the pipeline."""
        if self._camera_worker and not self._is_running:
            self._is_running = True
            self._camera_worker.start()
            if self._inference_worker:
                self._inference_worker.start()
            self._smoother.reset()
            self._confidence_meter.reset()

    @property
    def model_available(self) -> bool:
        """Whether recognition can make an honest prediction."""
        return self._recognizer is not None

    def stop(self) -> None:
        """Stop the pipeline."""
        self._is_running = False
        if self._camera_worker:
            self._camera_worker.stop()
        if self._inference_worker:
            self._inference_worker.stop()

    def set_target_sign(self, sign_id: str, landmarks: Optional[np.ndarray] = None) -> None:
        """Set the target sign for practice mode."""
        self._target_sign_id = sign_id
        self._target_landmarks = landmarks
        if self._inference_worker:
            self._inference_worker.set_target_sign(sign_id, landmarks)

    def clear_target(self) -> None:
        """Clear target sign (for dictionary browsing, etc.)."""
        self._target_sign_id = None
        self._target_landmarks = None
        if self._inference_worker:
            self._inference_worker.clear_target()

    def set_dwell_enabled(self, enabled: bool) -> None:
        """Enable/disable hand dwell interaction."""
        if self._inference_worker:
            self._inference_worker.set_dwell_enabled(enabled)

    def set_dwell_duration(self, ms: int) -> None:
        """Set dwell duration."""
        if self._inference_worker:
            self._inference_worker.set_dwell_duration(ms)

    def set_confidence_threshold(self, threshold: float) -> None:
        """Update confidence threshold."""
        if self._inference_worker:
            self._inference_worker.set_confidence_threshold(threshold)

    def set_smoothing_window(self, frames: int) -> None:
        """Update smoothing window."""
        if self._inference_worker:
            self._inference_worker.set_smoothing_window(frames)

    def get_camera_worker(self) -> Optional[CameraWorker]:
        return self._camera_worker

    def get_available_cameras(self) -> List[int]:
        if self._camera_worker:
            return self._camera_worker.get_available_cameras()
        return []

    def get_camera_devices(self):
        return self._camera_worker.get_camera_devices() if self._camera_worker else []

    def switch_camera(self, qt_index: int) -> None:
        """Switch to different camera (restarts capture).
        
        qt_index is the Qt Multimedia device index.
        """
        if self._camera_worker:
            was_running = self._is_running
            if was_running:
                self.stop()
            # Find the CameraDevice by Qt index and map to OpenCV index
            from app.core.camera_devices import discover_camera_devices
            devices = discover_camera_devices()
            target_device = None
            for device in devices:
                if device.index == qt_index:
                    target_device = device
                    break
            if target_device:
                self._camera_worker.set_camera_device(target_device)
            else:
                # Fallback to old behavior
                self._camera_worker.set_camera_index(qt_index)
            if was_running:
                self.start()

    def set_mirror(self, mirror: bool) -> None:
        if self._camera_worker:
            self._camera_worker.set_mirror(mirror)

    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop()
        self._hand_tracker.close()
        if self._inference_worker:
            self._inference_worker.cleanup()
