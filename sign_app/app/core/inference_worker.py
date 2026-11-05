"""
Inference worker running in a separate thread.
Handles MediaPipe hand tracking and recognition independently from camera capture.
"""

from pathlib import Path
import time
import numpy as np
from PySide6.QtCore import QThread, Signal, Slot, QMutex, QWaitCondition
from dataclasses import dataclass
from typing import Optional, List, Tuple, Any, Dict
import logging

from app.core.hand_tracker import HandTracker, HandLandmarks, HandTrackerResult
from app.core.features import FeatureExtractor, FeatureVector
from app.core.recognizer import Recognizer, RecognitionResult, StaticRecognizer
from app.core.smoothing import TemporalSmoother, ConfidenceMeter, DwellDetector
from app.core.sign_checker import SignChecker, CheckResult, create_sign_checker

logger = logging.getLogger(__name__)


@dataclass
class InferenceRequest:
    """Request for inference on a frame."""
    frame: np.ndarray
    frame_number: int
    timestamp_ms: float
    target_sign_id: Optional[str] = None
    target_landmarks: Optional[np.ndarray] = None


@dataclass
class InferenceResult:
    """Result from inference processing."""
    frame_number: int
    timestamp_ms: float
    hands: List[HandLandmarks]
    recognition: Optional[RecognitionResult]
    smoothed: Optional[Any]  # SmoothedPrediction
    confidence_meter: Tuple[str, float]  # (label, confidence)
    dwell_result: Tuple[bool, float]  # (triggered, progress)
    processing_time_ms: float
    inference_time_ms: float
    target_sign_id: Optional[str] = None
    target_landmarks: Optional[np.ndarray] = None
    check_result: Optional[CheckResult] = None


class InferenceWorker(QThread):
    """
    Background thread for hand tracking and recognition.
    Runs independently from camera capture to avoid blocking frame capture.
    """

    result_ready = Signal(object)  # InferenceResult
    error_occurred = Signal(str)
    fps_update = Signal(float)  # inference FPS

    def __init__(self, max_hands: int = 1, model_complexity: int = 0):
        super().__init__()
        self.max_hands = max_hands
        self.model_complexity = model_complexity

        # A lower detection threshold reacquires a hand quickly.  Tracking and
        # presence stay at a balanced value so weak detections do not make the
        # skeleton jump between unrelated shapes.
        self._hand_tracker = HandTracker(
            max_hands=max_hands,
            min_detection_confidence=0.4,
            min_tracking_confidence=0.5,
            min_presence_confidence=0.5,
            model_complexity=model_complexity
        )

        # Feature extractor
        self._feature_extractor = FeatureExtractor()

        # Recognizer
        self._recognizer: Optional[Recognizer] = None

        # Smoothing
        self._smoother = TemporalSmoother()
        self._confidence_meter = ConfidenceMeter()
        self._dwell_detector = DwellDetector()

        # Target sign for practice mode
        self._target_sign_id: Optional[str] = None
        self._target_landmarks: Optional[np.ndarray] = None

        # Sign checker (Task 2)
        self._sign_checker: Optional[SignChecker] = None
        self._signs_data: Dict[str, Dict] = {}

        # Stability window for correct detection
        self._stable_frames = 0
        self._required_stable_frames = 3  # ~100ms at 30fps
        self._hold_frames = 0
        self._required_hold_frames = 24  # ~800ms at 30fps

        # Thread control
        self._running = False
        self._mutex = QMutex()
        self._pause_condition = QWaitCondition()
        self._paused = False

        # Request queue (only keep latest)
        self._pending_request: Optional[InferenceRequest] = None
        self._request_mutex = QMutex()

        # Performance tracking
        self._frame_count = 0
        self._dropped_frames = 0
        self._consecutive_errors = 0
        self._last_fps_time = time.time()
        self._inference_times: List[float] = []

    def initialize(self) -> bool:
        """Initialize hand tracker."""
        if not self._hand_tracker.initialize():
            self.error_occurred.emit("Failed to initialize hand tracker - running in demo mode")
            return False
        return True

    def load_model(self, model_path: str) -> bool:
        """Load recognition model and initialize sign checker."""
        try:
            self._recognizer = StaticRecognizer.load(Path(model_path))
            logger.info(f"Model loaded successfully with classes: {self._recognizer.get_classes()}")

            # Load signs data for sign checker
            from app.content.loader import initialize_content_packs
            loader = initialize_content_packs(Path(__file__).resolve().parents[2] / "content_packs")
            pack = loader.get_current_pack()
            if pack:
                self._signs_data = {s.id: s for s in pack.signs.values()}

            # Initialize sign checker
            self._sign_checker = create_sign_checker(
                Path(__file__).resolve().parents[2] / "content_packs" / "asl",
                recognizer=self._recognizer,
                strictness="normal"
            )

            return True
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self.error_occurred.emit(str(e))
            return False

    @property
    def model_available(self) -> bool:
        return self._recognizer is not None

    def set_target_sign(self, sign_id: str, landmarks: Optional[np.ndarray] = None) -> None:
        """Set the target sign for practice mode."""
        self._target_sign_id = sign_id
        self._target_landmarks = landmarks
        self._reset_smoothing()

    def clear_target(self) -> None:
        """Clear target sign."""
        self._target_sign_id = None
        self._target_landmarks = None
        self._reset_smoothing()

    def _reset_smoothing(self) -> None:
        """Reset smoothing state."""
        self._smoother.reset()
        if self._recognizer:
            self._recognizer.reset_smoothing()
        self._confidence_meter.reset()
        if self._dwell_detector:
            self._dwell_detector = DwellDetector()
        self._hold_frames = 0

    def set_dwell_enabled(self, enabled: bool) -> None:
        """Enable/disable hand dwell interaction."""
        if enabled:
            self._dwell_detector = DwellDetector()
        else:
            self._dwell_detector = None

    def set_dwell_duration(self, ms: int) -> None:
        """Set dwell duration."""
        if self._dwell_detector:
            self._dwell_detector = DwellDetector(dwell_time_ms=ms)

    def set_confidence_threshold(self, threshold: float) -> None:
        """Update confidence threshold."""
        self._smoother.min_confidence = threshold
        if self._recognizer:
            self._recognizer.config.confidence_threshold = threshold

    def set_smoothing_window(self, frames: int) -> None:
        """Update smoothing window."""
        self._smoother.window_size = frames
        self._smoother.min_frames_for_stable = max(3, frames // 2)
        if self._recognizer:
            self._recognizer.config.smoothing_window = frames
            self._recognizer._smoothing_window = frames

    def set_strictness(self, strictness: str) -> None:
        """Update strictness level for sign checking."""
        if self._sign_checker:
            self._sign_checker.set_strictness(strictness)
            logger.info(f"Sign checker strictness set to: {strictness}")

    def set_hold_duration(self, ms: int) -> None:
        """Set required hold duration for correct detection."""
        fps = 30  # Approximate
        self._required_hold_frames = max(1, int(ms / 1000 * fps))
        logger.info(f"Hold duration set to {ms}ms ({self._required_hold_frames} frames)")

    @Slot()
    def submit_frame(self, frame: np.ndarray, frame_number: int, timestamp_ms: float,
                     target_sign_id: Optional[str] = None,
                     target_landmarks: Optional[np.ndarray] = None) -> None:
        """Submit a frame for inference, replacing any stale pending frame.

        Frames emitted by CameraService are immutable after delivery, so they
        can be safely shared read-only with inference.  Avoiding a full-frame
        copy here removes a large allocation at every capture tick.
        """
        self._request_mutex.lock()
        try:
            if self._pending_request is not None:
                self._dropped_frames += 1
            self._pending_request = InferenceRequest(
                frame=frame,
                frame_number=frame_number,
                timestamp_ms=timestamp_ms,
                target_sign_id=target_sign_id,
                target_landmarks=target_landmarks,
            )
        finally:
            self._request_mutex.unlock()

    @Slot()
    def set_paused(self, paused: bool) -> None:
        """Pause/resume inference."""
        self._mutex.lock()
        self._paused = paused
        if not paused:
            self._pause_condition.wakeAll()
        self._mutex.unlock()

    @Slot()
    def stop(self) -> None:
        """Stop the inference loop."""
        self._running = False
        self._mutex.lock()
        self._paused = False
        self._pause_condition.wakeAll()
        self._mutex.unlock()
        self.wait(2000)

    def run(self) -> None:
        """Main inference loop."""
        self._running = True
        self._smoother.reset()
        if self._recognizer:
            self._recognizer.reset_smoothing()
        self._confidence_meter.reset()
        if self._dwell_detector:
            self._dwell_detector = DwellDetector()

        logger.info("Inference worker started")

        while self._running:
            # Handle pause
            self._mutex.lock()
            if self._paused:
                self._pause_condition.wait(self._mutex)
            self._mutex.unlock()

            if not self._running:
                break

            # Get latest request (drop older ones)
            self._request_mutex.lock()
            request = self._pending_request
            self._pending_request = None
            self._request_mutex.unlock()

            if request is None:
                # No frame available, sleep briefly
                self.msleep(1)
                continue

            # Process frame
            try:
                result = self._process_frame(request)
                self.result_ready.emit(result)
                self._consecutive_errors = 0
            except Exception as e:
                # Throttled: a per-frame error here would both flood the log and
                # add latency to every single frame.
                self._consecutive_errors += 1
                if self._consecutive_errors == 1 or self._consecutive_errors % 60 == 0:
                    logger.error(
                        f"Inference error ({self._consecutive_errors} consecutive): {e}"
                    )
                    self.error_occurred.emit(str(e))

            # Update FPS
            self._frame_count += 1
            now = time.time()
            if now - self._last_fps_time >= 1.0:
                fps = self._frame_count / (now - self._last_fps_time)
                self.fps_update.emit(fps)
                self._frame_count = 0
                self._last_fps_time = now

        logger.info("Inference worker stopped")

    def _process_frame(self, request: InferenceRequest) -> Any:
        """Process a single frame for hand tracking and recognition."""
        from app.core.hand_tracker import HandTrackerResult
        from app.core.smoothing import SmoothedPrediction
        import cv2

        start_time = time.perf_counter()

        # The capture service requests 640x480.  Keep that detail for reliable
        # fingertip detection and only reduce unexpectedly high-resolution
        # devices; this avoids both a resize and loss of small-hand detail for
        # the normal camera path.
        inference_frame = request.frame
        h, w = request.frame.shape[:2]
        max_dim = max(h, w)
        if max_dim > 640:
            scale = 640.0 / max_dim
            new_w = int(w * scale)
            new_h = int(h * scale)
            inference_frame = cv2.resize(request.frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # Hand tracking (use downscaled frame for faster inference)
        tracker_result = HandTrackerResult(hands=[])
        if self._hand_tracker._initialized:
            tracker_result = self._hand_tracker.process(inference_frame, timestamp_ms=int(request.timestamp_ms))

        # Recognition
        recognition = None
        smoothed = None
        confidence_display = ("unknown", 0.0)
        dwell_result = (False, 0.0)
        check_result = None

        if self._recognizer and tracker_result.hands:
            # Use the most confident hand
            best_hand = max(tracker_result.hands, key=lambda h: h.confidence)

            # Extract features
            feature_vec = self._feature_extractor.extract(best_hand)

            # Recognize
            recognition = self._recognizer.predict(feature_vec.features)

            # Temporal smoothing
            smoothed = self._smoother.update(recognition.label, recognition.confidence)

            # Confidence meter for UI
            confidence_display = self._confidence_meter.update(
                smoothed.label, smoothed.confidence, smoothed.is_stable
            )

            # Dwell detection using index fingertip
            if self._dwell_detector:
                fingertip = best_hand.landmarks[8]  # Index tip (normalized)
                # Convert to pixel coordinates for dwell detection
                # Note: we use the frame dimensions from the request
                h, w = request.frame.shape[:2]
                fingertip_px = (fingertip[0] * w, fingertip[1] * h)
                dwell_result = self._dwell_detector.update(fingertip_px, "target_button")

            # Sign checking (Task 2) - only when target sign is set
            if self._sign_checker and request.target_sign_id and request.target_sign_id in self._signs_data:
                check_result = self._sign_checker.check(best_hand, request.target_sign_id)

                # Stability window: require consecutive correct frames
                if check_result.is_correct:
                    self._hold_frames += 1
                    if self._hold_frames == 1:
                        # First correct frame - log
                        logger.debug(f"Sign check: {self._target_sign_id} correct, starting hold timer")
                else:
                    self._hold_frames = 0

                # Override is_correct based on hold duration
                if check_result.is_correct and self._hold_frames < self._required_hold_frames:
                    check_result = CheckResult(
                        is_correct=False,
                        confidence=check_result.confidence,
                        rule_confidence=check_result.rule_confidence,
                        ml_confidence=check_result.ml_confidence,
                        joint_statuses=check_result.joint_statuses,
                        finger_statuses=check_result.finger_statuses,
                        hint=f"Hold steady... ({self._hold_frames}/{self._required_hold_frames})",
                        ml_prediction=check_result.ml_prediction,
                        ml_scores=check_result.ml_scores
                    )

        if not tracker_result.hands:
            self._hold_frames = 0
            self._smoother.reset()
            self._confidence_meter.reset()

        inference_time = (time.perf_counter() - start_time) * 1000
        processing_time = inference_time

        # Track inference time
        self._inference_times.append(inference_time)
        if len(self._inference_times) > 100:
            self._inference_times.pop(0)

        # Create result
        result = InferenceResult(
            frame_number=request.frame_number,
            timestamp_ms=request.timestamp_ms,
            hands=tracker_result.hands,
            recognition=recognition,
            smoothed=smoothed,
            confidence_meter=confidence_display,
            dwell_result=dwell_result,
            processing_time_ms=processing_time,
            inference_time_ms=inference_time,
            # The queued request is authoritative.  The user may switch
            # lesson targets while this frame is being processed.
            target_sign_id=request.target_sign_id,
            target_landmarks=request.target_landmarks,
            check_result=check_result
        )

        return result

    def get_avg_inference_time(self) -> float:
        """Get average inference time in ms."""
        if not self._inference_times:
            return 0.0
        return sum(self._inference_times) / len(self._inference_times)

    def get_p95_inference_time(self) -> float:
        """Get p95 inference time in ms."""
        if not self._inference_times:
            return 0.0
        sorted_times = sorted(self._inference_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[idx]

    def get_dropped_frames(self) -> int:
        """Number of frames skipped because inference was still busy."""
        return self._dropped_frames

    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop()
        self._hand_tracker.close()
