"""
Camera capture worker running in a background QThread.
Provides frames via signals, never blocks the UI thread.
"""

import sys
import time
import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal, Slot, QMutex, QWaitCondition
from typing import Optional, List, Tuple
import logging

from app.core.camera_devices import discover_camera_devices, preferred_camera, is_static_frame_sequence

logger = logging.getLogger(__name__)


class CameraWorker(QThread):
    """
    Background thread for camera capture.
    Emits frames as numpy arrays (BGR) via frame_ready signal.
    """

    frame_ready = Signal(np.ndarray)  # BGR frame
    error_occurred = Signal(str)
    camera_started = Signal(int)  # camera index (OpenCV index)
    camera_stopped = Signal()
    static_feed_detected = Signal(str)

    def __init__(self, camera_device: Optional['CameraDevice'] = None, camera_index: int = 0, target_fps: int = 30, resolution: Tuple[int, int] = (640, 480)):
        super().__init__()
        # Store camera device info
        self._camera_device = camera_device
        # Use cv_index from CameraDevice if available, otherwise fall back to camera_index
        if camera_device is not None and camera_device.cv_index >= 0:
            self.camera_index = camera_device.cv_index
        else:
            self.camera_index = camera_index
        self.target_fps = target_fps
        self.resolution = resolution
        self._running = False
        self._cap: Optional[cv2.VideoCapture] = None
        self._mutex = QMutex()
        self._pause_condition = QWaitCondition()
        self._paused = False
        self._mirror = True
        self._recent_frames: List[np.ndarray] = []
        self._static_warning_sent = False
        self._started_at = 0.0

    def run(self) -> None:
        """Main capture loop."""
        self._running = True
        self._started_at = time.monotonic()
        self._cap = self._open_camera()

        if self._cap is None:
            self.error_occurred.emit(f"Could not open camera index {self.camera_index}")
            self._running = False
            return

        self.camera_started.emit(self.camera_index)
        logger.info(f"Camera {self.camera_index} started at {self.resolution[0]}x{self.resolution[1]} @ {self.target_fps}fps")

        frame_interval = 1.0 / self.target_fps

        while self._running:
            frame_started = time.perf_counter()
            # Handle pause
            self._mutex.lock()
            if self._paused:
                self._pause_condition.wait(self._mutex)
            self._mutex.unlock()

            if not self._running:
                break

            ret, frame = self._cap.read()
            if not ret or frame is None:
                logger.warning("Failed to read frame from camera")
                self.error_occurred.emit("Camera frame read failed")
                self.msleep(100)
                continue

            # AVFoundation can ignore requested capture dimensions (notably
            # returning 1920x1080 on built-in cameras). Downscale here so the
            # inference worker has a predictable latency and the UI receives a
            # sensible preview size. Landmark coordinates stay normalized.
            height, width = frame.shape[:2]
            max_width, max_height = self.resolution
            scale = min(max_width / width, max_height / height, 1.0)
            if scale < 1.0:
                frame = cv2.resize(frame, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)

            # Mirror for selfie view
            if self._mirror:
                frame = cv2.flip(frame, 1)

            # Emit frame (make a copy to avoid race conditions)
            self.frame_ready.emit(frame.copy())

            # A virtual camera's idle card is a valid video frame, so opening
            # successfully is not enough. Detect an effectively unchanged feed
            # after two seconds and surface a choice to the user.
            self._recent_frames.append(cv2.resize(frame, (160, 90)))
            self._recent_frames = self._recent_frames[-30:]
            if (not self._static_warning_sent and time.monotonic() - self._started_at >= 2.0
                    and len(self._recent_frames) >= 12 and is_static_frame_sequence(self._recent_frames)):
                self._static_warning_sent = True
                self.static_feed_detected.emit(
                    "This camera is sending a still image (it may be a virtual camera like OBS). Choose another camera."
                )

            # Throttle to target FPS, accounting for capture + inference time.
            # Sleeping a full interval after processing used to halve FPS.
            elapsed = time.perf_counter() - frame_started
            remaining_ms = int(max(0.0, frame_interval - elapsed) * 1000)
            if remaining_ms:
                self.msleep(remaining_ms)

        self._cleanup()
        self.camera_stopped.emit()
        logger.info("Camera worker stopped")

    def _open_camera(self) -> Optional[cv2.VideoCapture]:
        """Open camera with platform-specific backends."""
        # Try different backends in order of preference
        backends = []

        import sys
        if sys.platform == 'darwin':  # macOS
            backends = [cv2.CAP_AVFOUNDATION, cv2.CAP_ANY]
        elif sys.platform == 'win32':  # Windows
            backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
        else:  # Linux
            backends = [cv2.CAP_V4L2, cv2.CAP_ANY]

        for backend in backends:
            try:
                cap = cv2.VideoCapture(self.camera_index, backend)
                if cap.isOpened():
                    # Set resolution
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
                    cap.set(cv2.CAP_PROP_FPS, self.target_fps)
                    # Reduce buffer to minimize latency
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    logger.info(f"Opened camera with backend {backend}")
                    return cap
            except Exception as e:
                logger.debug(f"Backend {backend} failed: {e}")
                continue

        return None

    def _cleanup(self) -> None:
        """Release camera resources."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    @Slot()
    def stop(self) -> None:
        """Stop the capture loop."""
        self._running = False
        self._mutex.lock()
        self._paused = False
        self._pause_condition.wakeAll()
        self._mutex.unlock()
        self.wait(2000)  # Wait up to 2 seconds for thread to finish

    @Slot(bool)
    def set_paused(self, paused: bool) -> None:
        """Pause/resume capture."""
        self._mutex.lock()
        self._paused = paused
        if not paused:
            self._pause_condition.wakeAll()
        self._mutex.unlock()

    @Slot(bool)
    def set_mirror(self, mirror: bool) -> None:
        """Set mirror mode."""
        self._mirror = mirror

    @Slot(int)
    def set_camera_index(self, index: int) -> None:
        """Change camera index (requires restart)."""
        self.camera_index = index

    @Slot(object)
    def set_camera_device(self, device) -> None:
        """Change camera device (requires restart)."""
        self._camera_device = device
        # Use device index as fallback
        self.camera_index = device.index if device else 0

    @Slot(tuple)
    def set_resolution(self, resolution: Tuple[int, int]) -> None:
        """Change resolution (requires restart)."""
        self.resolution = resolution

    def get_available_cameras(self, max_test: int = 2) -> List[int]:
        """Detect available camera indices."""
        available = []
        for i in range(max_test):
            cap = cv2.VideoCapture(i, cv2.CAP_AVFOUNDATION if sys.platform == 'darwin' else cv2.CAP_ANY)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    available.append(i)
                cap.release()
        return available

    def get_camera_devices(self):
        """Return named devices from Qt Multimedia, falling back to CV indices."""
        devices = discover_camera_devices()
        if devices:
            return devices
        return [type("FallbackCamera", (), {"index": index, "name": f"Camera {index}", "is_virtual": False})
                for index in self.get_available_cameras(max_test=6)]


class FakeCameraWorker(CameraWorker):
    """
    Fake camera for testing without a webcam.
    Plays a recorded landmark sequence or generates synthetic frames.
    """

    def __init__(self, landmark_sequence: Optional[List[np.ndarray]] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.landmark_sequence = landmark_sequence or []
        self._frame_idx = 0
        self._synthetic_mode = landmark_sequence is None

    def get_available_cameras(self, max_test: int = 5) -> List[int]:
        """Return fake camera list for testing."""
        return [-1]  # Fake camera index

    def run(self) -> None:
        self._running = True
        self.camera_started.emit(-1)  # Fake camera index

        if self._synthetic_mode:
            self._run_synthetic()
        else:
            self._run_sequence()

        self.camera_stopped.emit()

    def _run_synthetic(self) -> None:
        """Generate synthetic frames with a moving hand-like pattern."""
        import math
        frame_count = 0
        while self._running:
            self._mutex.lock()
            if self._paused:
                self._pause_condition.wait(self._mutex)
            self._mutex.unlock()

            if not self._running:
                break

            # Create synthetic frame
            frame = np.zeros((self.resolution[1], self.resolution[0], 3), dtype=np.uint8)
            frame[:] = (30, 30, 40)  # Dark background

            # Draw a simple moving "hand" indicator
            cx = int(self.resolution[0] // 2 + 100 * math.sin(frame_count * 0.05))
            cy = int(self.resolution[1] // 2 + 50 * math.cos(frame_count * 0.03))
            cv2.circle(frame, (cx, cy), 30, (100, 200, 100), -1)
            cv2.putText(frame, "SYNTHETIC MODE", (20, 40),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)
            cv2.putText(frame, "No webcam detected", (20, 80),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)

            if self._mirror:
                frame = cv2.flip(frame, 1)

            self.frame_ready.emit(frame.copy())
            frame_count += 1
            self.msleep(int(1000 / self.target_fps))

    def _run_sequence(self) -> None:
        """Play back recorded landmark sequence as visual frames."""
        # This would render landmarks to frames - simplified for now
        self._run_synthetic()
