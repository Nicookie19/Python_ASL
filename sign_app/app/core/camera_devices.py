"""Camera discovery and selection policy shared by the UI and capture worker."""

from dataclasses import dataclass
from typing import Iterable, Sequence, Optional
import logging
import sys

logger = logging.getLogger(__name__)


VIRTUAL_CAMERA_TERMS = ("obs", "virtual", "snap", "manycam", "ndi", "camera extension", "camo", "continuity")
BUILTIN_CAMERA_TERMS = ("facetime", "built-in", "builtin", "macbook", "integrated", "internal", "face time")


@dataclass(frozen=True)
class CameraDevice:
    """A human-readable Qt device mapped to the platform capture ordering."""

    index: int
    name: str
    device_id: str = ""
    cv_index: int = -1  # OpenCV capture index
    resolution: tuple[int, int] = (0, 0)

    @property
    def is_virtual(self) -> bool:
        return any(term in self.name.casefold() for term in VIRTUAL_CAMERA_TERMS)

    @property
    def is_builtin(self) -> bool:
        return any(term in self.name.casefold() for term in BUILTIN_CAMERA_TERMS)


VIRTUAL_CAMERA_TERMS = ("obs", "virtual", "snap", "manycam", "ndi", "camera extension", "camo", "continuity")
BUILTIN_CAMERA_TERMS = ("facetime", "built-in", "builtin", "macbook", "integrated", "internal", "face time")


def _probe_opencv_cameras(max_test: int = 6) -> list[tuple[int, int, int]]:
    """Probe OpenCV cameras and return list of (cv_index, width, height)."""
    import cv2
    import sys

    cv_devices = []
    for cv_idx in range(max_test):
        cap = cv2.VideoCapture(cv_idx, cv2.CAP_AVFOUNDATION if sys.platform == 'darwin' else cv2.CAP_ANY)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                h, w = frame.shape[:2]
                cv_devices.append((cv_idx, w, h))
            cap.release()
    return cv_devices


def discover_camera_devices() -> list["CameraDevice"]:
    """Return cameras in the OS order, including the name macOS exposes."""
    try:
        from PySide6.QtMultimedia import QMediaDevices
        import cv2
        import sys

        # Probe OpenCV cameras first to get resolution mapping
        cv_devices = _probe_opencv_cameras()

        devices = []
        for index, device in enumerate(QMediaDevices.videoInputs()):
            device_id = bytes(device.id()).decode("utf-8", errors="replace")
            name = device.description() or f"Camera {index}"

            # Try to match Qt device to OpenCV camera by name/resolution
            cv_index = -1
            resolution = (0, 0)
            device_desc = device.description().casefold() if device.description() else ""

            # Match by name keywords and resolution
            for cv_idx, w, h in _probe_opencv_cameras():
                device_desc = device.description().casefold() if device.description() else ""
                
                if cv_idx == 0 and ("facetime" in device_desc or "built-in" in device_desc):
                    cv_index = cv_idx
                    resolution = (w, h)
                    break
                elif cv_idx == 1 and ("obs" in device_desc or "virtual" in device_desc):
                    cv_index = cv_idx
                    resolution = (w, h)
                    break

            devices.append(CameraDevice(
                index=index,
                name=device.description() or f"Camera {index}",
                device_id=bytes(device.id()).decode("utf-8", errors="replace"),
                cv_index=cv_index,
                resolution=resolution
            ))
        return devices
    except Exception as e:
        logger.warning(f"Failed to discover cameras via Qt Multimedia: {e}")
        # Fallback to OpenCV only
        import cv2
        devices = []
        for i in range(6):
            cap = cv2.VideoCapture(i, cv2.CAP_AVFOUNDATION if sys.platform == 'darwin' else cv2.CAP_ANY)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    h, w = frame.shape[:2]
                    name = f"Camera {i}"
                    if i == 0:
                        name = "FaceTime HD Camera"
                    elif i == 1:
                        name = "OBS Virtual Camera"
                    devices.append(CameraDevice(
                        index=i, name=name, device_id="", cv_index=i, resolution=(w, h)
                    ))
                cap.release()
        return devices


def preferred_camera(devices: Sequence[CameraDevice]) -> "CameraDevice | None":
    """Prefer a built-in camera and place virtual sources last."""
    if not devices:
        return None
    return min(devices, key=lambda device: (not device.is_builtin, device.is_virtual, device.index))


def is_static_frame_sequence(frames: Iterable, max_mean_delta: float = 0.15) -> bool:
    """True when consecutive frames are effectively the same still image."""
    import numpy as np

    frames = list(frames)
    if len(frames) < 2:
        return False
    deltas = [np.mean(np.abs(current.astype(np.float32) - previous.astype(np.float32)))
              for previous, current in zip(frames, frames[1:])]
    return bool(deltas) and float(np.mean(deltas)) <= max_mean_delta


VIRTUAL_CAMERA_TERMS = ("obs", "virtual", "snap", "manycam", "ndi", "camera extension", "camo", "continuity")
BUILTIN_CAMERA_TERMS = ("facetime", "built-in", "builtin", "macbook", "integrated", "internal", "face time")


@dataclass(frozen=True)
class CameraDevice:
    """A human-readable Qt device mapped to the platform capture ordering."""

    index: int
    name: str
    device_id: str = ""
    cv_index: int = -1  # OpenCV capture index
    resolution: tuple[int, int] = (0, 0)

    @property
    def is_virtual(self) -> bool:
        return any(term in self.name.casefold() for term in VIRTUAL_CAMERA_TERMS)

    @property
    def is_builtin(self) -> bool:
        return any(term in self.name.casefold() for term in BUILTIN_CAMERA_TERMS)


VIRTUAL_CAMERA_TERMS = ("obs", "virtual", "snap", "manycam", "ndi", "camera extension", "camo", "continuity")
BUILTIN_CAMERA_TERMS = ("facetime", "built-in", "builtin", "macbook", "integrated", "internal", "face time")


def _probe_opencv_cameras(max_test: int = 6) -> list[tuple[int, int, int]]:
    """Probe OpenCV cameras and return list of (cv_index, width, height)."""
    import cv2
    import sys

    cv_devices = []
    for cv_idx in range(max_test):
        cap = cv2.VideoCapture(cv_idx, cv2.CAP_AVFOUNDATION if sys.platform == 'darwin' else cv2.CAP_ANY)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                h, w = frame.shape[:2]
                cv_devices.append((cv_idx, w, h))
            cap.release()
    return cv_devices


def discover_camera_devices() -> list["CameraDevice"]:
    """Return cameras in the OS order, including the name macOS exposes."""
    try:
        from PySide6.QtMultimedia import QMediaDevices
        import cv2
        import sys

        # Probe OpenCV cameras first to get resolution mapping
        cv_devices = _probe_opencv_cameras()

        devices = []
        for index, device in enumerate(QMediaDevices.videoInputs()):
            device_id = bytes(device.id()).decode("utf-8", errors="replace")
            name = device.description() or f"Camera {index}"

            # Try to match Qt device to OpenCV camera by name/resolution
            cv_index = -1
            resolution = (0, 0)
            device_desc = device.description().casefold() if device.description() else ""

            # Match by name keywords and resolution
            for cv_idx, w, h in _probe_opencv_cameras():
                device_desc = device.description().casefold() if device.description() else ""
                
                if cv_idx == 0 and ("facetime" in device_desc or "built-in" in device_desc):
                    cv_index = cv_idx
                    resolution = (w, h)
                    break
                elif cv_idx == 1 and ("obs" in device_desc or "virtual" in device_desc):
                    cv_index = cv_idx
                    resolution = (w, h)
                    break

            devices.append(CameraDevice(
                index=index,
                name=device.description() or f"Camera {index}",
                device_id=bytes(device.id()).decode("utf-8", errors="replace"),
                cv_index=cv_index,
                resolution=resolution
            ))
        return devices
    except Exception as e:
        logger.warning(f"Failed to discover cameras via Qt Multimedia: {e}")
        # Fallback to OpenCV only
        import cv2
        devices = []
        for i in range(6):
            cap = cv2.VideoCapture(i, cv2.CAP_AVFOUNDATION if sys.platform == 'darwin' else cv2.CAP_ANY)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    h, w = frame.shape[:2]
                    name = f"Camera {i}"
                    if i == 0:
                        name = "FaceTime HD Camera"
                    elif i == 1:
                        name = "OBS Virtual Camera"
                    devices.append(CameraDevice(
                        index=i, name=name, device_id="", cv_index=i, resolution=(w, h)
                    ))
                cap.release()
        return devices


def preferred_camera(devices: Sequence[CameraDevice]) -> "CameraDevice | None":
    """Prefer a built-in camera and place virtual sources last."""
    if not devices:
        return None
    return min(devices, key=lambda device: (not device.is_builtin, device.is_virtual, device.index))


def is_static_frame_sequence(frames: Iterable, max_mean_delta: float = 0.15) -> bool:
    """True when consecutive frames are effectively the same still image."""
    import numpy as np

    frames = list(frames)
    if len(frames) < 2:
        return False
    deltas = [np.mean(np.abs(current.astype(np.float32) - previous.astype(np.float32)))
              for previous, current in zip(frames, frames[1:])]
    return bool(deltas) and float(np.mean(deltas)) <= max_mean_delta


VIRTUAL_CAMERA_TERMS = ("obs", "virtual", "snap", "manycam", "ndi", "camera extension", "camo", "continuity")
BUILTIN_CAMERA_TERMS = ("facetime", "built-in", "builtin", "macbook", "integrated", "internal", "face time")


@dataclass(frozen=True)
class CameraDevice:
    """A human-readable Qt device mapped to the platform capture ordering."""

    index: int
    name: str
    device_id: str = ""
    cv_index: int = -1  # OpenCV capture index
    resolution: tuple[int, int] = (0, 0)

    @property
    def is_virtual(self) -> bool:
        return any(term in self.name.casefold() for term in VIRTUAL_CAMERA_TERMS)

    @property
    def is_builtin(self) -> bool:
        return any(term in self.name.casefold() for term in BUILTIN_CAMERA_TERMS)


VIRTUAL_CAMERA_TERMS = ("obs", "virtual", "snap", "manycam", "ndi", "camera extension", "camo", "continuity")
BUILTIN_CAMERA_TERMS = ("facetime", "built-in", "builtin", "macbook", "integrated", "internal", "face time")


def _probe_opencv_cameras(max_test: int = 6) -> list[tuple[int, int, int]]:
    """Probe OpenCV cameras and return list of (cv_index, width, height)."""
    import cv2
    import sys

    cv_devices = []
    for cv_idx in range(max_test):
        cap = cv2.VideoCapture(cv_idx, cv2.CAP_AVFOUNDATION if sys.platform == 'darwin' else cv2.CAP_ANY)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                h, w = frame.shape[:2]
                cv_devices.append((cv_idx, w, h))
            cap.release()
    return cv_devices


def discover_camera_devices() -> list["CameraDevice"]:
    """Return cameras in the OS order, including the name macOS exposes."""
    try:
        from PySide6.QtMultimedia import QMediaDevices
        import cv2
        import sys

        # Probe OpenCV cameras first to get resolution mapping
        cv_devices = _probe_opencv_cameras()

        devices = []
        for index, device in enumerate(QMediaDevices.videoInputs()):
            device_id = bytes(device.id()).decode("utf-8", errors="replace")
            name = device.description() or f"Camera {index}"

            # Try to match Qt device to OpenCV camera by name/resolution
            cv_index = -1
            resolution = (0, 0)
            device_desc = device.description().casefold() if device.description() else ""

            # Match by name keywords and resolution
            for cv_idx, w, h in _probe_opencv_cameras():
                device_desc = device.description().casefold() if device.description() else ""
                
                if cv_idx == 0 and ("facetime" in device_desc or "built-in" in device_desc):
                    cv_index = cv_idx
                    resolution = (w, h)
                    break
                elif cv_idx == 1 and ("obs" in device_desc or "virtual" in device_desc):
                    cv_index = cv_idx
                    resolution = (w, h)
                    break

            devices.append(CameraDevice(
                index=index,
                name=device.description() or f"Camera {index}",
                device_id=bytes(device.id()).decode("utf-8", errors="replace"),
                cv_index=cv_index,
                resolution=resolution
            ))
        return devices
    except Exception as e:
        logger.warning(f"Failed to discover cameras via Qt Multimedia: {e}")
        # Fallback to OpenCV only
        import cv2
        devices = []
        for i in range(6):
            cap = cv2.VideoCapture(i, cv2.CAP_AVFOUNDATION if sys.platform == 'darwin' else cv2.CAP_ANY)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    h, w = frame.shape[:2]
                    name = f"Camera {i}"
                    if i == 0:
                        name = "FaceTime HD Camera"
                    elif i == 1:
                        name = "OBS Virtual Camera"
                    devices.append(CameraDevice(
                        index=i, name=name, device_id="", cv_index=i, resolution=(w, h)
                    ))
                cap.release()
        return devices


def preferred_camera(devices: Sequence[CameraDevice]) -> "CameraDevice | None":
    """Prefer a built-in camera and place virtual sources last."""
    if not devices:
        return None
    return min(devices, key=lambda device: (not device.is_builtin, device.is_virtual, device.index))


def is_static_frame_sequence(frames: Iterable, max_mean_delta: float = 0.15) -> bool:
    """True when consecutive frames are effectively the same still image."""
    import numpy as np

    frames = list(frames)
    if len(frames) < 2:
        return False
    deltas = [np.mean(np.abs(current.astype(np.float32) - previous.astype(np.float32)))
              for previous, current in zip(frames, frames[1:])]
    return bool(deltas) and float(np.mean(deltas)) <= max_mean_delta


VIRTUAL_CAMERA_TERMS = ("obs", "virtual", "snap", "manycam", "ndi", "camera extension", "camo", "continuity")
BUILTIN_CAMERA_TERMS = ("facetime", "built-in", "builtin", "macbook", "integrated", "internal", "face time")


@dataclass(frozen=True)
class CameraDevice:
    """A human-readable Qt device mapped to the platform capture ordering."""

    index: int
    name: str
    device_id: str = ""
    cv_index: int = -1  # OpenCV capture index
    resolution: tuple[int, int] = (0, 0)

    @property
    def is_virtual(self) -> bool:
        return any(term in self.name.casefold() for term in VIRTUAL_CAMERA_TERMS)

    @property
    def is_builtin(self) -> bool:
        return any(term in self.name.casefold() for term in BUILTIN_CAMERA_TERMS)


VIRTUAL_CAMERA_TERMS = ("obs", "virtual", "snap", "manycam", "ndi", "camera extension", "camo", "continuity")
BUILTIN_CAMERA_TERMS = ("facetime", "built-in", "builtin", "macbook", "integrated", "internal", "face time")


def _probe_opencv_cameras(max_test: int = 6) -> list[tuple[int, int, int]]:
    """Probe OpenCV cameras and return list of (cv_index, width, height)."""
    import cv2
    import sys

    cv_devices = []
    for cv_idx in range(max_test):
        cap = cv2.VideoCapture(cv_idx, cv2.CAP_AVFOUNDATION if sys.platform == 'darwin' else cv2.CAP_ANY)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                h, w = frame.shape[:2]
                cv_devices.append((cv_idx, w, h))
            cap.release()
    return cv_devices


def discover_camera_devices() -> list["CameraDevice"]:
    """Return cameras in the OS order, including the name macOS exposes."""
    try:
        from PySide6.QtMultimedia import QMediaDevices
        import cv2
        import sys

        # Probe OpenCV cameras first to get resolution mapping
        cv_devices = _probe_opencv_cameras()

        devices = []
        for index, device in enumerate(QMediaDevices.videoInputs()):
            device_id = bytes(device.id()).decode("utf-8", errors="replace")
            name = device.description() or f"Camera {index}"

            # Try to match Qt device to OpenCV camera by name/resolution
            cv_index = -1
            resolution = (0, 0)
            device_desc = device.description().casefold() if device.description() else ""

            # Match by name keywords and resolution
            for cv_idx, w, h in _probe_opencv_cameras():
                device_desc = device.description().casefold() if device.description() else ""
                
                if cv_idx == 0 and ("facetime" in device_desc or "built-in" in device_desc):
                    cv_index = cv_idx
                    resolution = (w, h)
                    break
                elif cv_idx == 1 and ("obs" in device_desc or "virtual" in device_desc):
                    cv_index = cv_idx
                    resolution = (w, h)
                    break

            devices.append(CameraDevice(
                index=index,
                name=device.description() or f"Camera {index}",
                device_id=bytes(device.id()).decode("utf-8", errors="replace"),
                cv_index=cv_index,
                resolution=resolution
            ))
        return devices
    except Exception as e:
        logger.warning(f"Failed to discover cameras via Qt Multimedia: {e}")
        # Fallback to OpenCV only
        import cv2
        devices = []
        for i in range(6):
            cap = cv2.VideoCapture(i, cv2.CAP_AVFOUNDATION if sys.platform == 'darwin' else cv2.CAP_ANY)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    h, w = frame.shape[:2]
                    name = f"Camera {i}"
                    if i == 0:
                        name = "FaceTime HD Camera"
                    elif i == 1:
                        name = "OBS Virtual Camera"
                    devices.append(CameraDevice(
                        index=i, name=name, device_id="", cv_index=i, resolution=(w, h)
                    ))
                cap.release()
        return devices


def preferred_camera(devices: Sequence[CameraDevice]) -> "CameraDevice | None":
    """Prefer a built-in camera and place virtual sources last."""
    if not devices:
        return None
    return min(devices, key=lambda device: (not device.is_builtin, device.is_virtual, device.index))


def is_static_frame_sequence(frames: Iterable, max_mean_delta: float = 0.15) -> bool:
    """True when consecutive frames are effectively the same still image."""
    import numpy as np

    frames = list(frames)
    if len(frames) < 2:
        return False
    deltas = [np.mean(np.abs(current.astype(np.float32) - previous.astype(np.float32)))
              for previous, current in zip(frames, frames[1:])]
    return bool(deltas) and float(np.mean(deltas)) <= max_mean_delta