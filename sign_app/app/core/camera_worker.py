"""
Camera sources for the pipeline.

``CameraWorker`` is a thin adapter over the shared :class:`CameraService`. It
opens nothing itself: it acquires the service and republishes its frames. This
keeps a single camera device open for the whole app regardless of how many
screens are visible.

``FakeCameraWorker`` generates synthetic frames without touching any real
camera. It exists for tests, the UI linter and screenshot tooling, and is not a
camera code path.
"""

from __future__ import annotations

import logging
import math
import time
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PySide6.QtCore import QObject, QThread, QMutex, QWaitCondition, Signal, Slot

from app.core.camera_devices import CameraDevice, discover_camera_devices

logger = logging.getLogger(__name__)

_OWNER = "pipeline"


class CameraWorker(QObject):
    """Adapter that republishes the shared CameraService's frames.

    Deliberately not a QThread: capture, decoding and conversion all happen in
    the service's own worker thread. Having a second thread here used to mean
    two threads racing to convert and draw the same frame.
    """

    frame_ready = Signal(np.ndarray)
    error_occurred = Signal(str)
    camera_started = Signal(object)
    camera_stopped = Signal()
    static_feed_detected = Signal(str)

    def __init__(
        self,
        camera_device: Optional[CameraDevice] = None,
        target_fps: int = 30,
        resolution: Tuple[int, int] = (640, 480),
        camera_service=None,
    ):
        super().__init__()
        self.target_fps = target_fps
        self.resolution = resolution
        self._camera_device = camera_device
        self._running = False
        self._acquired = False
        self._service = camera_service
        self.last_capture_timestamp_ms = 0.0

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        """Acquire the shared camera. Reference-counted across screens."""
        if self._running:
            return
        self._running = True

        if self._service is None:
            from app.core.camera_service import CameraService

            self._service = CameraService.instance()

        if self._camera_device and self._camera_device.device_id:
            self._service.set_active_device(self._camera_device.device_id)

        self._service.frame_ready.connect(self._on_camera_frame)
        self._service.error_occurred.connect(self.error_occurred.emit)
        self._service.static_feed_detected.connect(self.static_feed_detected.emit)
        self._service.active_device_changed.connect(self._on_device_changed)

        self._acquired = self._service.acquire(_OWNER)
        self.camera_started.emit(self._service.get_active_device_id())

    def stop(self) -> None:
        """Release the shared camera."""
        if not self._running:
            return
        self._running = False

        if self._service is not None:
            try:
                self._service.frame_ready.disconnect(self._on_camera_frame)
                self._service.error_occurred.disconnect(self.error_occurred.emit)
                self._service.static_feed_detected.disconnect(self.static_feed_detected.emit)
                self._service.active_device_changed.disconnect(self._on_device_changed)
            except (TypeError, RuntimeError):
                pass
            if self._acquired:
                self._service.release(_OWNER)
                self._acquired = False

        self.camera_stopped.emit()

    @Slot(object)
    def _on_camera_frame(self, camera_frame) -> None:
        """CameraService hands us a CameraFrame; the pipeline wants the array."""
        frame = getattr(camera_frame, "frame", camera_frame)
        # Kept so the pipeline can measure real capture -> display latency.
        self.last_capture_timestamp_ms = getattr(camera_frame, "timestamp_ms", 0.0)
        self.frame_ready.emit(frame)

    @Slot(str, str)
    def _on_device_changed(self, _old_id: str, new_id: str) -> None:
        logger.info("Active camera changed to %s", new_id)
        self.camera_started.emit(new_id)

    # -- configuration -----------------------------------------------------
    @Slot(object)
    def set_camera_device(self, device: Optional[CameraDevice]) -> None:
        """Switch to a specific device by stable ID."""
        self._camera_device = device
        if self._service is not None and device is not None and device.device_id:
            self._service.set_active_device(device.device_id)

    @Slot(object)
    def set_camera_index(self, index: int) -> None:
        """Deprecated: indices are not stable.

        Kept so old call sites keep working; resolves to whatever device the
        service currently considers preferred.
        """
        logger.warning("set_camera_index(%s) is deprecated; indices are not stable", index)
        if self._service is not None:
            preferred = self.get_camera_devices()
            builtin = next((d for d in preferred if d.is_builtin), None)
            if builtin is not None:
                self.set_camera_device(builtin)

    @Slot(bool)
    def set_mirror(self, mirror: bool) -> None:
        if self._service is not None:
            self._service.set_mirror(mirror)

    @Slot(tuple)
    def set_resolution(self, resolution: Tuple[int, int]) -> None:
        self.resolution = resolution
        if self._service is not None:
            self._service.set_resolution(*resolution)

    # -- queries -----------------------------------------------------------
    def get_available_cameras(self, max_test: int = 6) -> List[int]:
        """Deprecated: returns device *orders*, not stable indices."""
        return [d.index for d in discover_camera_devices()][:max_test]

    def get_camera_devices(self) -> List[CameraDevice]:
        return discover_camera_devices()


class FakeCameraWorker(QThread):
    """Synthetic frame source for tests and tooling. Opens no real camera."""

    frame_ready = Signal(np.ndarray)
    error_occurred = Signal(str)
    camera_started = Signal(object)
    camera_stopped = Signal()
    static_feed_detected = Signal(str)

    def __init__(
        self,
        target_fps: int = 30,
        resolution: Tuple[int, int] = (640, 480),
        mirror: bool = True,
    ):
        super().__init__()
        self.target_fps = target_fps
        self.resolution = resolution
        self._mirror = mirror
        self._running = False
        self._mutex = QMutex()
        self._pause_condition = QWaitCondition()
        self._paused = False

    def get_available_cameras(self, max_test: int = 5) -> List[int]:
        return [-1]

    def stop(self) -> None:
        """Stop the synthetic frame loop."""
        self._running = False
        self._mutex.lock()
        self._paused = False
        self._pause_condition.wakeAll()
        self._mutex.unlock()
        self.wait(3000)

    def get_camera_devices(self) -> List[CameraDevice]:
        return []

    def run(self) -> None:
        self._running = True
        self.camera_started.emit("fake")
        width, height = self.resolution
        frame_count = 0
        while self._running:
            self._mutex.lock()
            if self._paused:
                self._pause_condition.wait(self._mutex)
            self._mutex.unlock()
            if not self._running:
                break

            frame = np.zeros((height, width, 3), dtype=np.uint8)
            frame[:] = (40, 30, 30)

            # A moving blob so the pipeline sees genuine motion, not a still frame.
            cx = int(width // 2 + 100 * math.sin(frame_count * 0.05))
            cy = int(height // 2 + 50 * math.cos(frame_count * 0.03))
            cv2.circle(frame, (cx, cy), 30, (100, 200, 100), -1)
            cv2.putText(
                frame, "SYNTHETIC MODE", (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2,
            )

            if self._mirror:
                frame = cv2.flip(frame, 1)

            self.frame_ready.emit(frame.copy())
            frame_count += 1
            self.msleep(max(1, int(1000 / self.target_fps)))

        self.camera_stopped.emit()