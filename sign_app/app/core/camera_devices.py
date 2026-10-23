"""
Camera device discovery and ranking.

This module is the single source of truth for *which* cameras exist and in what
order they should be preferred.

Enumeration goes through Qt Multimedia exclusively. That is deliberate: the
identity we store and display (``QCameraDevice.id()``) is then the same identity
``CameraService`` later opens with ``QCamera``. OpenCV is deliberately NOT used
for enumeration, because AVFoundation index order does not reliably match Qt's
device list - an index captured from one library and opened by the other yields
a camera that is named one thing and captures another. That mismatch is the
reason virtual cameras such as OBS were previously picked up as "the camera".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Sequence

logger = logging.getLogger(__name__)

# Names that indicate a software/virtual capture source rather than real optics.
VIRTUAL_CAMERA_TERMS = (
    "obs",
    "virtual",
    "snap",
    "manycam",
    "ndi",
    "camo",
    "camera extension",
    "continuity",
    "droidcam",
    "epoccam",
    "screen capture",
)

# Names that indicate a built-in camera we should always prefer.
BUILTIN_CAMERA_TERMS = (
    "facetime",
    "face time",
    "built-in",
    "builtin",
    "macbook",
    "integrated",
    "internal",
)

# Ranking tiers, lower sorts first.
RANK_BUILTIN = 0
RANK_PHYSICAL = 1
RANK_VIRTUAL = 2


@dataclass(frozen=True)
class CameraDevice:
    """A camera exposed by the OS.

    ``device_id`` is the stable unique identifier (Qt's ``QCameraDevice.id()``)
    and is what gets persisted. ``index`` is kept only as a display/order hint:
    it is NOT stable across reboots or when a virtual camera appears or
    disappears, so it must never be persisted or used to open a device.
    """

    index: int
    name: str
    device_id: str = ""
    resolution: tuple[int, int] = (0, 0)

    @property
    def is_virtual(self) -> bool:
        folded = self.name.casefold()
        return any(term in folded for term in VIRTUAL_CAMERA_TERMS)

    @property
    def is_builtin(self) -> bool:
        folded = self.name.casefold()
        return any(term in folded for term in BUILTIN_CAMERA_TERMS)

    @property
    def rank(self) -> int:
        """Built-in cameras first, then other physical cameras, virtual last."""
        if self.is_builtin:
            return RANK_BUILTIN
        if self.is_virtual:
            return RANK_VIRTUAL
        return RANK_PHYSICAL


def discover_camera_devices() -> list[CameraDevice]:
    """Return the attached cameras, ordered best-first.

    Uses Qt Multimedia only - see the module docstring for why OpenCV index
    mapping is not used here.
    """
    try:
        from PySide6.QtMultimedia import QMediaDevices
    except ImportError as exc:  # pragma: no cover - Qt always present in app
        logger.error("Qt Multimedia unavailable, cannot enumerate cameras: %s", exc)
        return []

    devices: list[CameraDevice] = []
    try:
        inputs = list(QMediaDevices.videoInputs())
    except Exception as exc:
        logger.error("Failed to enumerate video inputs: %s", exc)
        return []

    for index, device in enumerate(inputs):
        try:
            device_id = bytes(device.id()).decode("utf-8", errors="replace")
        except Exception:
            device_id = ""
        description = (device.description() or "").strip()
        name = description or f"Camera {index}"
        devices.append(
            CameraDevice(index=index, name=name, device_id=device_id)
        )

    return rank_devices(devices)


def rank_devices(devices: Sequence[CameraDevice]) -> list[CameraDevice]:
    """Sort devices best-first, stable within a tier."""
    return sorted(devices, key=lambda d: (d.rank, d.index))


def visible_devices(
    devices: Sequence[CameraDevice], show_virtual: bool = False
) -> list[CameraDevice]:
    """Filter out virtual cameras unless the user asked to see them."""
    if show_virtual:
        return rank_devices(devices)
    return rank_devices([d for d in devices if not d.is_virtual])


def preferred_camera(
    devices: Sequence[CameraDevice], allow_virtual: bool = False
) -> CameraDevice | None:
    """Return the best camera to use, or None when there are none.

    A device the user explicitly chose always wins; this ranking is only ever
    used to pick a default. Virtual cameras are skipped unless ``allow_virtual``
    is set (the "Show virtual cameras" setting).
    """
    candidates = list(devices) if allow_virtual else [d for d in devices if not d.is_virtual]
    if not candidates:
        # Everything available is virtual - use it rather than showing nothing,
        # but it still sorts last.
        candidates = list(devices)
    if not candidates:
        return None
    return rank_devices(candidates)[0]


def find_device_by_id(devices: Sequence[CameraDevice], device_id: str) -> CameraDevice | None:
    """Look a device up by its stable unique ID."""
    if not device_id:
        return None
    for device in devices:
        if device.device_id == device_id:
            return device
    return None


def is_static_frame_sequence(frames: Iterable, max_mean_delta: float = 0.15) -> bool:
    """True when consecutive frames are effectively the same still image.

    Used to detect idle virtual cameras (e.g. OBS showing its logo) which look
    like a live feed but never change.
    """
    import numpy as np

    frames = list(frames)
    if len(frames) < 2:
        return False
    deltas = [
        np.mean(np.abs(current.astype(np.float32) - previous.astype(np.float32)))
        for previous, current in zip(frames, frames[1:])
    ]
    return bool(deltas) and float(np.mean(deltas)) <= max_mean_delta