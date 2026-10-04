"""
CameraService - Single source of truth for camera management.
Provides device enumeration, selection, capture, and frame distribution.
Reference-counted so multiple screens can share the same camera.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Callable, Any
from collections import OrderedDict

import cv2
import numpy as np
from PySide6.QtCore import QObject, Signal, Slot, QThread, QTimer, Qt, QMutex, QWaitCondition
from PySide6.QtMultimedia import QMediaDevices, QCamera, QMediaCaptureSession, QVideoSink
from PySide6.QtMultimediaWidgets import QVideoWidget

from app.core.camera_devices import CameraDevice, discover_camera_devices, preferred_camera, is_static_frame_sequence

logger = logging.getLogger(__name__)


@dataclass
class CameraConfig:
    """Configuration for camera capture."""
    device_id: str = ""  # Qt QCameraDevice.id() - stable unique identifier
    target_fps: int = 30
    resolution: tuple[int, int] = (640, 480)
    mirror: bool = True


@dataclass
class CameraFrame:
    """Frame data emitted by the camera service."""
    frame: np.ndarray  # BGR frame (already mirrored if configured)
    timestamp_ms: float
    frame_number: int
    camera_device_id: str


class CameraCaptureWorker(QThread):
    """
    Background thread for camera capture using Qt Multimedia.
    Uses QCamera + QMediaCaptureSession + QVideoSink for native device handling.
    """
    
    frame_ready = Signal(object)  # CameraFrame
    error_occurred = Signal(str)
    started_signal = Signal(str)  # device_id
    stopped_signal = Signal(str)  # device_id
    static_feed_detected = Signal(str)
    
    def __init__(self, config: CameraConfig):
        super().__init__()
        self.config = config
        self._running = False
        self._camera: Optional[QCamera] = None
        self._capture_session: Optional[QMediaCaptureSession] = None
        self._video_sink: Optional[QVideoSink] = None
        _mutex = QMutex()
        _pause_condition = QWaitCondition()
        _paused = False
        
        self._frame_count = 0
        _recent_frames: List[np.ndarray] = []
        _static_warning_sent = False
        _started_at = 0.0
        
    def run(self) -> None:
        """Main capture loop using Qt Multimedia."""
        self._running = True
        self._started_at = time.monotonic()
        
        # Find the Qt camera device by ID
        qt_device = None
        for device in QMediaDevices.videoInputs():
            if bytes(device.id()).decode("utf-8", errors="replace") == self.config.device_id:
                qt_device = device
                break
        
        if qt_device is None:
            self.error_occurred.emit(f"Camera device not found: {self.config.device_id}")
            self._running = False
            return
        
        # Create camera and capture session
        self._camera = QCamera(qt_device)
        self._capture_session = QMediaCaptureSession()
        self._capture_session.setCamera(self._camera)
        
        self._video_sink = QVideoSink()
        self._capture_session.setVideoSink(self._video_sink)
        
        # Connect video sink frame ready signal
        self._video_sink.videoFrameChanged.connect(self._on_video_frame)
        
        # Start camera
        self._camera.start()
        
        if not self._camera.isActive():
            self.error_occurred.emit(f"Failed to start camera: {self._camera.errorString()}")
            self._running = False
            return
        
        self.started_signal.emit(self.config.device_id)
        logger.info(f"Camera {self.config.device_id} started at {self.config.resolution[0]}x{self.config.resolution[1]} @ {self.config.target_fps}fps")
        
        # Event loop for the thread
        self.exec()
        
    @Slot()
    def _on_video_frame(self, frame) -> None:
        """Handle new video frame from Qt Multimedia."""
        if not self._running or self._paused:
            return
            
        # Convert QVideoFrame to numpy array
        np_frame = self._video_frame_to_numpy(frame)
        if np_frame is None:
            return
            
        # Mirror if needed
        if self.config.mirror:
            np_frame = cv2.flip(np_frame, 1)
            
        # Static feed detection
        self._check_static_feed(np_frame)
        
        # Emit frame
        self._frame_count += 1
        camera_frame = CameraFrame(
            frame=np_frame,
            timestamp_ms=time.monotonic() * 1000,
            frame_number=self._frame_count,
            camera_device_id=self.config.device_id
        )
        self.frame_ready.emit(camera_frame)
        
    def _video_frame_to_numpy(self, frame) -> Optional[np.ndarray]:
        """Convert QVideoFrame to numpy BGR array."""
        if not frame.isValid():
            return None
            
        # Map frame to memory
        frame.map(QVideoFrame.MapMode.ReadOnly)
        try:
            # Get image format
            fmt = frame.pixelFormat()
            width = frame.width()
            height = frame.height()
            bytes_per_line = frame.bytesPerLine()
            
            # Get raw data
            bits = frame.bits()
            if bits is None:
                return None
                
            # Convert based on format
            # Common formats: Format_YUV420P, Format_NV12, Format_RGB24, Format_BGR24, Format_RGBA8888
            if fmt == QVideoFrame.Format.Format_RGB24:
                arr = np.frombuffer(bits, dtype=np.uint8).reshape((height, bytes_per_line // 3, 3))
                arr = arr[:, :width, :]
                return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            elif fmt == QVideoFrame.Format.Format_BGR24:
                arr = np.frombuffer(bits, dtype=np.uint8).reshape((height, bytes_per_line // 3, 3))
                arr = arr[:, :width, :]
                return arr.copy()
            elif fmt == QVideoFrame.Format.Format_RGBA8888 or fmt == QVideoFrame.Format.Format_ARGB32:
                arr = np.frombuffer(bits, dtype=np.uint8).reshape((height, bytes_per_line // 4, 4))
                arr = arr[:, :width, :3]
                return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            elif fmt == QVideoFrame.Format.Format_YUV420P or fmt == QVideoFrame.Format.Format_NV12:
                # YUV conversion needed
                y_size = width * height
                uv_size = y_size // 4
                y_data = np.frombuffer(bits[:y_size], dtype=np.uint8).reshape((height, width))
                uv_data = np.frombuffer(bits[y_size:y_size+uv_size*2], dtype=np.uint8).reshape((height//2, width//2, 2))
                # Simple YUV to BGR (approximate)
                yuv = cv2.merge([y_data, 
                                cv2.resize(uv_data[:,:,0], (width, height)),
                                cv2.resize(uv_data[:,:,1], (width, height))])
                return cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_I420)
            else:
                # Fallback: try to convert via QImage
                image = frame.toImage()
                if image.isNull():
                    return None
                image = image.convertToFormat(QImage.Format.Format_RGB888)
                arr = np.frombuffer(image.bits().asarray(image.sizeInBytes()), dtype=np.uint8)
                arr = arr.reshape((image.height(), image.width(), 3))
                return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        finally:
            frame.unmap()
            
    def _check_static_feed(self, frame: np.ndarray) -> None:
        """Detect if camera is sending static frames (virtual camera idle)."""
        self._recent_frames.append(cv2.resize(frame, (160, 90)))
        self._recent_frames = self._recent_frames[-30:]
        
        if (not self._static_warning_sent and 
            time.monotonic() - self._started_at >= 2.0 and 
            len(self._recent_frames) >= 12 and 
            is_static_frame_sequence(self._recent_frames)):
            self._static_warning_sent = True
            self.static_feed_detected.emit(
                "This camera is sending a still image (it may be a virtual camera like OBS). Choose another camera."
            )
            
    @Slot()
    def stop(self) -> None:
        """Stop the capture loop."""
        self._running = False
        self._mutex.lock()
        self._paused = False
        self._pause_condition.wakeAll()
        self._mutex.unlock()
        
        if self._camera:
            self._camera.stop()
        self.quit()
        self.wait(2000)
        
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
        self.config.mirror = mirror


class CameraService(QObject):
    """
    Singleton camera service managing device enumeration, selection, and capture.
    Reference-counted: multiple screens can acquire() the same camera.
    """
    
    # Signals
    device_list_changed = Signal(list)  # List[CameraDevice]
    active_device_changed = Signal(str, str)  # old_device_id, new_device_id
    frame_ready = Signal(object)  # CameraFrame
    error_occurred = Signal(str)
    static_feed_detected = Signal(str)
    
    _instance: Optional[CameraService] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        super().__init__()
        
        self._initialized = True
        
        # Device management
        self._devices: List[CameraDevice] = []
        self._active_device_id: str = ""
        self._config = CameraConfig()
        
        # Capture worker
        self._worker: Optional[CameraCaptureWorker] = None
        
        # Reference counting for shared camera access
        self._ref_counts: Dict[str, int] = {}  # owner -> count
        
        # Static feed detection
        self._static_feed_timer: Optional[QTimer] = None
        
        # Hot-plug detection
        try:
            QMediaDevices.videoInputsChanged.connect(self._on_devices_changed)
        except AttributeError:
            # Signal may not be available in this Qt version
            logger.warning("QMediaDevices.videoInputsChanged signal not available, hot-plug detection disabled")
        
        # Initial device discovery
        self._refresh_devices()
        
    @classmethod
    def instance(cls) -> CameraService:
        if cls._instance is None:
            cls._instance = CameraService()
        return cls._instance
    
    @classmethod
    def destroy_instance(cls):
        if cls._instance:
            cls._instance.shutdown()
            cls._instance = None
    
    def shutdown(self):
        """Clean up all resources."""
        self.release_all()
        if self._worker:
            self._worker.stop()
            self._worker = None
        try:
            QMediaDevices.videoInputsChanged.disconnect(self._on_devices_changed)
        except (AttributeError, TypeError):
            pass
        
    def _refresh_devices(self):
        """Refresh device list from Qt Multimedia."""
        old_ids = {d.device_id for d in self._devices}
        self._devices = discover_camera_devices()
        new_ids = {d.device_id for d in self._devices}
        
        # If active device was removed, pick a new one
        if self._active_device_id and self._active_device_id not in new_ids:
            self._active_device_id = ""
            
        # Auto-select preferred if none active
        if not self._active_device_id and self._devices:
            pref = preferred_camera(self._devices)
            if pref:
                self._active_device_id = pref.device_id
                
        self.device_list_changed.emit(self._devices)
        
    @Slot()
    def _on_devices_changed(self):
        """Handle hot-plug events."""
        logger.info("Camera devices changed (hot-plug detected)")
        self._refresh_devices()
        
        # If current camera was unplugged, try to switch to preferred
        if self._active_device_id:
            still_exists = any(d.device_id == self._active_device_id for d in self._devices)
            if not still_exists:
                logger.warning(f"Active camera {self._active_device_id} no longer available, switching to preferred")
                self._switch_to_preferred()
    
    def _switch_to_preferred(self):
        """Switch to preferred available camera."""
        pref = preferred_camera(self._devices)
        if pref:
            self.set_active_device(pref.device_id)
        else:
            self._active_device_id = ""
            self.active_device_changed.emit(self._active_device_id, "")
            
    def get_devices(self) -> List[CameraDevice]:
        """Get list of available camera devices."""
        return self._devices[:]
    
    def get_active_device(self) -> Optional[CameraDevice]:
        """Get currently active camera device."""
        for d in self._devices:
            if d.device_id == self._active_device_id:
                return d
        return None
    
    def get_active_device_id(self) -> str:
        return self._active_device_id
    
    def set_active_device(self, device_id: str) -> bool:
        """Set the active camera device by stable device ID."""
        if not device_id:
            # No device ID provided - use preferred camera
            return self._switch_to_preferred()
            
        if device_id == self._active_device_id:
            return True
            
        # Verify device exists
        device = next((d for d in self._devices if d.device_id == device_id), None)
        if not device:
            logger.error(f"Device not found: {device_id}")
            return False
            
        old_id = self._active_device_id
        self._active_device_id = device_id
        
        # Update config
        self._config.device_id = device_id
        
        # Restart worker if running
        if self._worker and self._worker.isRunning():
            was_running = True
            self._worker.stop()
            self._start_worker()
        else:
            was_running = False
            
        self.active_device_changed.emit(old_id, device_id)
        return True
    
    def _start_worker(self):
        """Start the capture worker with current config."""
        if self._worker:
            self._worker.frame_ready.disconnect()
            self._worker.error_occurred.disconnect()
            self._worker.started_signal.disconnect()
            self._worker.stopped_signal.disconnect()
            self._worker.static_feed_detected.disconnect()
            
        self._worker = CameraCaptureWorker(self._config)
        self._worker.frame_ready.connect(self._on_frame_ready)
        self._worker.error_occurred.connect(self.error_occurred.emit)
        self._worker.started_signal.connect(lambda _: None)
        self._worker.stopped_signal.connect(lambda _: None)
        self._worker.static_feed_detected.connect(self._on_static_feed)
        self._worker.start()
        
    def _on_frame_ready(self, frame: CameraFrame):
        """Handle frame from worker and distribute to subscribers."""
        self.frame_ready.emit(frame)
        
    def _on_static_feed(self, message: str):
        """Handle static feed detection."""
        self.static_feed_detected.emit(message)
        
    def acquire(self, owner: str) -> bool:
        """
        Acquire camera for a screen/owner.
        Returns True if camera started successfully.
        """
        count = self._ref_counts.get(owner, 0)
        self._ref_counts[owner] = count + 1
        
        if count == 0:
            # First owner - start camera if not running
            if self._active_device_id and (not self._worker or not self._worker.isRunning()):
                self._start_worker()
            elif self._worker and self._worker.isRunning() and self._worker.config.device_id != self._active_device_id:
                # Device changed - restart
                self._worker.stop()
                self._start_worker()
                
        return True
    
    def release(self, owner: str) -> bool:
        """
        Release camera for a screen/owner.
        Returns True if camera stopped (no more owners).
        """
        count = self._ref_counts.get(owner, 0)
        if count <= 0:
            return False
            
        if count == 1:
            del self._ref_counts[owner]
        else:
            self._ref_counts[owner] = count - 1
            
        # If no more owners, stop camera
        if not self._ref_counts:
            if self._worker:
                self._worker.stop()
            return True
        return False
    
    def release_all(self):
        """Release camera for all owners."""
        self._ref_counts.clear()
        if self._worker:
            self._worker.stop()
            
    def set_mirror(self, mirror: bool):
        self._config.mirror = mirror
        if self._worker:
            self._worker.set_mirror(mirror)
            
    def set_resolution(self, width: int, height: int):
        self._config.resolution = (width, height)
        # Requires restart
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._start_worker()
            
    def set_fps(self, fps: int):
        self._config.target_fps = fps
        if self._worker:
            # Worker will pick up new FPS on next frame
            pass
            
    def get_config(self) -> CameraConfig:
        return self._config
    
    def save_config(self, settings_repo):
        """Persist camera config to settings."""
        # Save device_id instead of index
        pass  # Implementation in SettingsRepository
        
    def load_config(self, settings):
        """Load camera config from settings."""
        if settings and hasattr(settings, 'camera_device_id') and settings.camera_device_id:
            self.set_active_device(settings.camera_device_id)
        elif self._devices and not self._active_device_id:
            # First run - pick preferred
            self._switch_to_preferred()


class OpenCVCameraWorker(QThread):
    """
    Fallback OpenCV-based camera worker for when Qt Multimedia is not available
    or for compatibility with existing MediaPipe pipeline.
    """
    
    frame_ready = Signal(object)  # CameraFrame
    error_occurred = Signal(str)
    started_signal = Signal(str)
    stopped_signal = Signal(str)
    static_feed_detected = Signal(str)
    
    def __init__(self, config: CameraConfig):
        super().__init__()
        self.config = config
        self._running = False
        self._cap: Optional[cv2.VideoCapture] = None
        self._mutex = QMutex()
        self._pause_condition = QWaitCondition()
        self._paused = False
        self._recent_frames: List[np.ndarray] = []
        self._static_warning_sent = False
        self._started_at = 0.0
        self._frame_count = 0
        
    def run(self) -> None:
        self._running = True
        self._started_at = time.monotonic()
        
        # Map device_id to OpenCV index
        cv_index = self._map_device_to_cv_index()
        self._cap = self._open_camera(cv_index)
        
        if self._cap is None:
            self.error_occurred.emit(f"Could not open camera for device {self.config.device_id}")
            self._running = False
            return
            
        self.started_signal.emit(self.config.device_id)
        logger.info(f"OpenCV Camera {self.config.device_id} (CV index {cv_index}) started at {self.config.resolution[0]}x{self.config.resolution[1]} @ {self.config.target_fps}fps")
        
        frame_interval = 1.0 / self.config.target_fps
        
        while self._running:
            frame_started = time.perf_counter()
            
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
                
            # Downscale if needed
            height, width = frame.shape[:2]
            max_width, max_height = self.config.resolution
            scale = min(max_width / width, max_height / height, 1.0)
            if scale < 1.0:
                frame = cv2.resize(frame, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)
                
            if self.config.mirror:
                frame = cv2.flip(frame, 1)
                
            # Static feed detection
            self._recent_frames.append(cv2.resize(frame, (160, 90)))
            self._recent_frames = self._recent_frames[-30:]
            if (not self._static_warning_sent and 
                time.monotonic() - self._started_at >= 2.0 and 
                len(self._recent_frames) >= 12 and 
                is_static_frame_sequence(self._recent_frames)):
                self._static_warning_sent = True
                self.static_feed_detected.emit(
                    "This camera is sending a still image (it may be a virtual camera like OBS). Choose another camera."
                )
                
            self._frame_count += 1
            camera_frame = CameraFrame(
                frame=frame.copy(),
                timestamp_ms=time.monotonic() * 1000,
                frame_number=self._frame_count,
                camera_device_id=self.config.device_id
            )
            self.frame_ready.emit(camera_frame)
            
            elapsed = time.perf_counter() - frame_started
            remaining_ms = int(max(0.0, frame_interval - elapsed) * 1000)
            if remaining_ms:
                self.msleep(remaining_ms)
                
        self._cleanup()
        self.stopped_signal.emit(self.config.device_id)
        logger.info("OpenCV Camera worker stopped")
        
    def _map_device_to_cv_index(self) -> int:
        """Map Qt device_id to OpenCV index by probing."""
        # Try to find device by opening each index and checking properties
        # This is a fallback - ideally we'd use Qt Multimedia for capture too
        try:
            from app.core.camera_devices import discover_camera_devices, map_qt_device_to_cv_index
            devices = discover_camera_devices()
            for device in devices:
                if device.device_id == self.config.device_id:
                    return map_qt_device_to_cv_index(device)
        except Exception as e:
            logger.warning(f"Could not map device to CV index: {e}")
        return 0  # Default fallback
        
    def _open_camera(self, cv_index: int) -> Optional[cv2.VideoCapture]:
        import sys
        backends = []
        if sys.platform == 'darwin':
            backends = [cv2.CAP_AVFOUNDATION, cv2.CAP_ANY]
        elif sys.platform == 'win32':
            backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
        else:
            backends = [cv2.CAP_V4L2, cv2.CAP_ANY]
            
        for backend in backends:
            try:
                cap = cv2.VideoCapture(cv_index, backend)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.resolution[0])
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.resolution[1])
                    cap.set(cv2.CAP_PROP_FPS, self.config.target_fps)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    logger.info(f"Opened camera with backend {backend}")
                    return cap
            except Exception as e:
                logger.debug(f"Backend {backend} failed: {e}")
                continue
        return None
        
    def _cleanup(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            
    @Slot()
    def stop(self) -> None:
        self._running = False
        self._mutex.lock()
        self._paused = False
        self._pause_condition.wakeAll()
        self._mutex.unlock()
        self.wait(2000)
        
    @Slot(bool)
    def set_paused(self, paused: bool) -> None:
        self._mutex.lock()
        self._paused = paused
        if not paused:
            self._pause_condition.wakeAll()
        self._mutex.unlock()
        
    @Slot(bool)
    def set_mirror(self, mirror: bool) -> None:
        self.config.mirror = mirror


# Export
__all__ = [
    'CameraService',
    'CameraConfig',
    'CameraFrame',
    'CameraCaptureWorker',
    'OpenCVCameraWorker',
]