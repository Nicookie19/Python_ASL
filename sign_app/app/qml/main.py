"""Runnable QML front end for Sign Spark.

The Widgets front end has its own entry point at ``sign_app/main.py``.  This
module is intentionally self-contained: it owns one CorePipeline, exposes a
small QML-friendly bridge, and serves frames through an image provider.  It
does not create a second camera from QML.
"""

from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickImageProvider
from PySide6.QtQuickControls2 import QQuickStyle


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.content.loader import ContentPackLoader, initialize_content_packs
from app.core.camera_service import CameraService
from app.core.pipeline import CorePipeline, PipelineResult


logger = logging.getLogger(__name__)


class CameraImageProvider(QQuickImageProvider):
    """Thread-safe image provider updated from the shared pipeline."""

    def __init__(self) -> None:
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._lock = threading.Lock()
        self._image = QImage()

    def set_image(self, image: QImage) -> None:
        with self._lock:
            self._image = image.copy()

    def requestImage(self, _image_id, size, _requested_size):  # noqa: N802 - Qt API
        with self._lock:
            image = self._image.copy()
        if size is not None:
            size.setWidth(image.width())
            size.setHeight(image.height())
        return image


class QmlBridge(QObject):
    """Minimal, typed boundary between QML and the live ASL pipeline."""

    cameraImageChanged = Signal()
    inferenceResultReady = Signal("QVariant")
    statusChanged = Signal(str, str)
    modulesChanged = Signal()

    def __init__(
        self,
        pipeline: CorePipeline,
        content: ContentPackLoader,
        image_provider: CameraImageProvider,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._pipeline = pipeline
        self._content = content
        self._image_provider = image_provider
        self._frame_version = 0
        self._modules = self._build_modules()

        self._pipeline.result_ready.connect(self._on_pipeline_result)
        self._pipeline.error_occurred.connect(
            lambda message: self.statusChanged.emit(str(message), "error")
        )
        self._pipeline.camera_status_changed.connect(self._on_camera_status)

    @Property("QVariant", constant=True)
    def currentUser(self) -> dict[str, str]:  # noqa: N802 - exposed QML name
        return {"name": "Learner"}

    @Property("QVariant", constant=True)
    def userStats(self) -> dict[str, int]:  # noqa: N802 - exposed QML name
        return {
            "accuracy": 0,
            "streak": 0,
            "completedModules": 0,
            "totalMinutes": 0,
        }

    @Property("QVariant", notify=modulesChanged)
    def modules(self) -> list[dict[str, Any]]:
        return self._modules

    @Property(str, notify=cameraImageChanged)
    def cameraImageUrl(self) -> str:  # noqa: N802 - exposed QML name
        if self._frame_version == 0:
            return ""
        return f"image://camera/frame?v={self._frame_version}"

    def _build_modules(self) -> list[dict[str, Any]]:
        pack = self._content.get_current_pack()
        if pack is None:
            return []

        tones = ("cyan", "violet", "amber")
        return [
            {
                "id": module.id,
                "title": module.name,
                "description": module.description,
                "progress": 0.0,
                "lessons": len(module.sign_ids),
                "tone": tones[index % len(tones)],
            }
            for index, module in enumerate(pack.modules.values())
        ]

    @Slot(str, result="QVariant")
    def lessonSigns(self, module_id: str) -> list[dict[str, Any]]:  # noqa: N802
        signs = self._content.get_signs_for_module(module_id)
        return [
            {
                "id": sign.id,
                "label": sign.label,
                "difficulty": sign.difficulty.value.title(),
                "description": sign.description,
                "tip": self._tip_for(sign.label),
            }
            for sign in signs
        ]

    @Slot(str, result="QVariant")
    def moduleInfo(self, module_id: str) -> dict[str, Any]:  # noqa: N802
        for module in self._modules:
            if module["id"] == module_id:
                return module
        return {}

    @Slot(str)
    def startPractice(self, sign_id: str) -> None:  # noqa: N802
        pack = self._content.get_current_pack()
        sign = pack.signs.get(sign_id) if pack else None
        if sign is None:
            self.statusChanged.emit("That lesson sign is unavailable.", "error")
            return

        landmarks = None
        if sign.reference_landmarks and len(sign.reference_landmarks) == 63:
            landmarks = np.asarray(sign.reference_landmarks, dtype=np.float32).reshape(21, 3)
        self._pipeline.set_target_sign(sign.id, landmarks)
        self._pipeline.start()
        self.statusChanged.emit("Camera started — show one hand clearly.", "info")

    @Slot()
    def stopPractice(self) -> None:  # noqa: N802
        self._pipeline.clear_target()
        self._pipeline.stop()

    @Slot()
    def toggleMirror(self) -> None:  # noqa: N802
        config = CameraService.instance().get_config()
        CameraService.instance().set_mirror(not config.mirror)

    def _on_camera_status(self, running: bool, message: str) -> None:
        state = "info" if running else "warning"
        self.statusChanged.emit(message, state)

    def _on_pipeline_result(self, result: PipelineResult) -> None:
        if isinstance(result.frame, np.ndarray) and result.frame.ndim == 3:
            height, width = result.frame.shape[:2]
            image = QImage(
                result.frame.data,
                width,
                height,
                result.frame.strides[0],
                QImage.Format.Format_BGR888,
            ).copy()
            self._image_provider.set_image(image)
            self._frame_version += 1
            self.cameraImageChanged.emit()

        hands = []
        for hand in result.hands or []:
            handedness = getattr(hand.handedness, "value", str(hand.handedness))
            hands.append(
                {
                    "landmarks": hand.landmarks.tolist(),
                    "handedness": handedness,
                    "confidence": float(hand.confidence),
                }
            )

        recognition = None
        if result.recognition is not None:
            recognition = {
                "label": result.recognition.label,
                "confidence": float(result.recognition.confidence),
                "is_reliable": bool(result.recognition.is_reliable),
            }

        self.inferenceResultReady.emit(
            {
                "hands": hands,
                "recognition": recognition,
                "confidence_meter": list(result.confidence_meter),
                "target_sign_id": result.target_sign_id,
                "target_landmarks": (
                    result.target_landmarks.tolist()
                    if isinstance(result.target_landmarks, np.ndarray) else None
                ),
                "inference_frame_number": result.inference_frame_number,
            }
        )

    @staticmethod
    def _tip_for(label: str) -> str:
        tips = {
            "A": "Keep the thumb outside the fist and in view.",
            "B": "Place your fingers close together and extend them fully.",
            "C": "Leave a comfortable C-shaped gap between thumb and fingers.",
            "D": "Point the index finger up, keeping the other fingers curled.",
            "E": "Curl the fingertips down without hiding the hand from the camera.",
        }
        return tips.get(label, "Keep your hand centered, well lit, and fully visible.")


def main() -> int:
    # Native macOS/Windows control styles ignore custom button backgrounds.
    # Basic keeps the QML's deliberately designed controls consistent
    # across supported desktops.
    QQuickStyle.setStyle("Basic")
    application = QGuiApplication(sys.argv)
    application.setApplicationName("Pysign")
    application.setOrganizationName("Pysign")

    content = initialize_content_packs(PROJECT_ROOT / "content_packs")
    pipeline = CorePipeline()
    pipeline.initialize(use_fake_camera=False)

    engine = QQmlApplicationEngine()
    image_provider = CameraImageProvider()
    engine.addImageProvider("camera", image_provider)
    bridge = QmlBridge(pipeline, content, image_provider)
    engine.rootContext().setContextProperty("bridge", bridge)

    qml_file = Path(__file__).with_name("main.qml")
    engine.load(QUrl.fromLocalFile(str(qml_file)))
    if not engine.rootObjects():
        pipeline.cleanup()
        CameraService.destroy_instance()
        return 1

    exit_code = application.exec()
    pipeline.cleanup()
    CameraService.destroy_instance()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
