"""
Core processing pipeline connecting camera, hand tracking, features, and recognition.
Runs in a background thread and emits results via Qt signals.
"""

import numpy as np
from PySide6.QtCore import QObject, Signal, Slot, QThread, QMutex, Qt
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
import logging
import time

from app.core.camera_worker import CameraWorker, FakeCameraWorker
from app.core.hand_tracker import HandTracker, HandLandmarks, HandTrackerResult
from app.core.features import FeatureExtractor, FeatureVector
from app.core.recognizer import Recognizer, RecognitionResult, StaticRecognizer
from app.core.smoothing import TemporalSmoother, ConfidenceMeter, DwellDetector
from app.core.camera_devices import discover_camera_devices, find_device_by_id
from app.core.camera_service import CameraService
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
    # Monotonic ID of the inference state attached to this camera frame. UI
    # consumers use it to avoid scoring the same prediction more than once.
    inference_frame_number: Optional[int] = None


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
        self._recognizer: Optional[Recognizer] = None

        self._target_sign_id: Optional[str] = None
        self._target_landmarks: Optional[np.ndarray] = None
        self._is_running = False
        self._mutex = QMutex()

        # Performance tracking
        self._frame_count = 0
        self._frame_sequence = 0
        self._last_fps_time = time.time()
        self._display_fps = 0.0
        self._inference_fps = 0.0
        self._latency_ms = 0.0
        self._ui_paint_ms = 0.0

        # The camera and inference workers intentionally run at different
        # rates.  Keep the most recent inference state and attach it to the
        # next *real* camera frame instead of emitting landmarks as a pretend
        # video frame.  The latter used to send a (21, 3) landmark array to
        # CameraView, which expects a BGR image and caused visual stutter (or
        # an OpenCV conversion error) as soon as a hand was found.
        self._latest_hands: List[HandLandmarks] = []
        self._latest_recognition: Optional[RecognitionResult] = None
        self._latest_smoothed: Optional[Any] = None
        self._latest_confidence_meter: Tuple[str, float] = ("unknown", 0.0)
        self._latest_dwell_result: Tuple[bool, float] = (False, 0.0)
        self._latest_inference_time_ms = 0.0
        self._latest_inference_frame_number: Optional[int] = None
        self._latest_target_sign_id: Optional[str] = None
        self._latest_target_landmarks: Optional[np.ndarray] = None

    def initialize(self, use_fake_camera: bool = False) -> bool:
        """Initialize all components."""
        # Create inference worker
        self._inference_worker = InferenceWorker(max_hands=1, model_complexity=0)
        if not self._inference_worker.initialize():
            self.error_occurred.emit("Failed to initialize inference worker - running in demo mode")
            # Continue anyway for demo mode
            pass

        # Create camera source. The real camera always comes from the shared
        # CameraService so that every screen sees the same, single open device.
        if use_fake_camera:
            self._camera_worker = FakeCameraWorker(target_fps=30)
        else:
            self._camera_worker = CameraWorker(target_fps=30, resolution=(640, 480))

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
        # InferenceWorker is a QThread subclass.  An explicit queued
        # connection ensures UI-facing state is updated on the GUI thread,
        # rather than from its run loop.
        self._inference_worker.result_ready.connect(
            self._on_inference_result, Qt.QueuedConnection
        )
        self._inference_worker.error_occurred.connect(self.error_occurred.emit)
        self._inference_worker.fps_update.connect(self._on_inference_fps)

        return True

    @Slot(np.ndarray)
    def _on_frame_ready(self, frame: np.ndarray) -> None:
        """Handle new frame from camera - submit to inference and display immediately."""
        if not self._is_running:
            return

        emit_start = time.perf_counter()
        self._frame_sequence += 1
        self._frame_count += 1
        now = time.time()
        if now - self._last_fps_time >= 1.0:
            self._display_fps = self._frame_count / (now - self._last_fps_time)
            self._frame_count = 0
            self._last_fps_time = now

        # Submit frame to inference worker (non-blocking, keeps only latest).
        if self._inference_worker and self._inference_worker.isRunning():
            self._inference_worker.submit_frame(
                frame=frame,
                frame_number=self._frame_sequence,
                timestamp_ms=time.time() * 1000,
                target_sign_id=self._target_sign_id,
                target_landmarks=self._target_landmarks
            )

        # Emit a real camera frame together with the latest tracking state.
        # This leaves display smooth at camera rate while the skeleton and
        # recognition update when inference completes.
        result = PipelineResult(
            frame=frame,
            original_frame=frame,
            hands=self._latest_hands,
            recognition=self._latest_recognition,
            smoothed=self._latest_smoothed,
            confidence_meter=self._latest_confidence_meter,
            dwell_result=self._latest_dwell_result,
            fps=self._display_fps,
            processing_time_ms=0.0,
            inference_time_ms=self._latest_inference_time_ms,
            inference_fps=self._inference_fps,
            target_sign_id=self._latest_target_sign_id,
            target_landmarks=self._latest_target_landmarks,
            inference_frame_number=self._latest_inference_frame_number,
        )
        self.result_ready.emit(result)

        # Time spent on the UI side handing this frame to the view.
        self._ui_paint_ms = (time.perf_counter() - emit_start) * 1000

        # True capture -> display latency, using the capture thread's own
        # arrival timestamp rather than assuming zero transit time.
        captured_ms = getattr(self._camera_worker, "last_capture_timestamp_ms", 0.0)
        if captured_ms:
            self._latency_ms = time.time() * 1000 - captured_ms

    @Slot(object)
    def _on_inference_result(self, result) -> None:
        """Handle inference result from worker."""
        if not self._is_running:
            return

        # Do not emit a second result here: it has no image, and emitting it
        # caused consumers to treat landmarks as a frame.  The next capture
        # frame will carry this state and repaint the overlay.
        self._latest_hands = result.hands
        self._latest_recognition = result.recognition
        self._latest_smoothed = result.smoothed
        self._latest_confidence_meter = result.confidence_meter
        self._latest_dwell_result = result.dwell_result
        self._latest_inference_time_ms = result.inference_time_ms
        self._latest_inference_frame_number = result.frame_number
        self._latest_target_sign_id = result.target_sign_id
        self._latest_target_landmarks = result.target_landmarks

    @Slot(float)
    def _on_inference_fps(self, fps: float) -> None:
        """Handle inference FPS update."""
        self._inference_fps = fps

    def perf_stats(self) -> dict:
        """Live performance metrics for the HUD.

        Every value is measured, never estimated: capture FPS comes from the
        capture thread's own arrival timestamps, inference timings from the
        inference worker, and latency from real capture-to-display timestamps.
        """
        service = CameraService.instance()
        worker = self._inference_worker

        stats = {
            "capture_fps": service.capture_fps(),
            "display_fps": self._display_fps,
            "inference_fps": self._inference_fps,
            "inference_avg_ms": worker.get_avg_inference_time() if worker else 0.0,
            "inference_p95_ms": worker.get_p95_inference_time() if worker else 0.0,
            "dropped_frames": worker.get_dropped_frames() if worker else 0,
            "latency_ms": self._latency_ms,
            "ui_paint_ms": self._ui_paint_ms,
            "camera_name": (service.get_active_device().name
                            if service.get_active_device() else "No camera"),
            "resolution": service.measured_resolution(),
        }
        return stats

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
            if self._inference_worker:
                self._inference_worker.start()
            self._camera_worker.start()

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
        self._clear_latest_inference()
        if self._inference_worker:
            self._inference_worker.set_target_sign(sign_id, landmarks)

    def clear_target(self) -> None:
        """Clear target sign (for dictionary browsing, etc.)."""
        self._target_sign_id = None
        self._target_landmarks = None
        self._clear_latest_inference()
        if self._inference_worker:
            self._inference_worker.clear_target()

    def _clear_latest_inference(self) -> None:
        """Discard feedback for the previous lesson target immediately."""
        self._latest_hands = []
        self._latest_recognition = None
        self._latest_smoothed = None
        self._latest_confidence_meter = ("unknown", 0.0)
        self._latest_dwell_result = (False, 0.0)
        self._latest_inference_time_ms = 0.0
        self._latest_inference_frame_number = None
        self._latest_target_sign_id = self._target_sign_id
        self._latest_target_landmarks = self._target_landmarks

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

    def switch_camera_by_id(self, device_id: str) -> None:
        """Switch cameras by stable unique device ID.

        Device identity is what gets persisted: an index changes whenever a
        virtual camera such as OBS is enabled or disabled, so it must never be
        used to identify a device.
        """
        if not self._camera_worker:
            return
        device = find_device_by_id(discover_camera_devices(), device_id)
        if device is None:
            logger.error("Cannot switch to unknown camera id %s", device_id)
            return
        was_running = self._is_running
        if was_running:
            self.stop()
        self._camera_worker.set_camera_device(device)
        if was_running:
            self.start()

    def get_active_camera_name(self) -> str:
        """Human-readable name of the camera currently in use."""
        service = CameraService.instance()
        device = service.get_active_device()
        return device.name if device else ""

    def set_mirror(self, mirror: bool) -> None:
        if self._camera_worker:
            self._camera_worker.set_mirror(mirror)

    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop()
        if self._inference_worker:
            self._inference_worker.cleanup()
