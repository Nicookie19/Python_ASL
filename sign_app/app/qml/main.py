"""Runnable QML front end for Sign Spark.

The Widgets front end has its own entry point at ``sign_app/main.py``.  This
module is intentionally self-contained: it owns one CorePipeline, exposes a
small QML-friendly bridge, and serves frames through an image provider.  It
does not create a second camera from QML.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, date, timedelta
from dataclasses import asdict
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
from app.data.db import (AttemptRepository, AttemptResult, PracticeAttempt,
                         UserRepository, SettingsRepository, init_db, transaction)


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
    statsChanged = Signal()
    settingsChanged = Signal()

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
        init_db()
        for pack in content._packs.values():
            content.sync_to_database(pack)
        users = UserRepository.get_learners()
        self._user = users[0] if users else UserRepository.create("Learner", "#22D3EE")
        self._settings = SettingsRepository.get(self._user.id)
        CameraService.instance().load_config(self._settings)
        self._pipeline.set_confidence_threshold(self._settings.confidence_threshold)
        self._quiz = []
        self._quiz_answered = set()
        self._frame_version = 0
        self._modules = self._build_modules()

        self._pipeline.result_ready.connect(self._on_pipeline_result)
        self._pipeline.error_occurred.connect(
            lambda message: self.statusChanged.emit(str(message), "error")
        )
        self._pipeline.camera_status_changed.connect(self._on_camera_status)

    @Property("QVariant", notify=settingsChanged)
    def currentUser(self):
        return {"name": self._user.name}

    @Property("QVariant", notify=settingsChanged)
    def settings(self):
        return asdict(self._settings)

    @Property(bool, constant=True)
    def modelAvailable(self):
        return self._pipeline.model_available

    @Property("QVariant", notify=statsChanged)
    def userStats(self):
        with transaction() as conn:
            row = conn.execute("SELECT COUNT(*) AS total, SUM(result IN ('correct','incorrect','timeout')) AS scored, SUM(result='correct') AS correct, "
                               "SUM(duration_ms) AS duration FROM practice_attempts WHERE user_id=?",
                               (self._user.id,)).fetchone()
            days = {r[0] for r in conn.execute("SELECT DISTINCT substr(timestamp,1,10) "
                    "FROM practice_attempts WHERE user_id=?", (self._user.id,))}
        day = date.today()
        if day.isoformat() not in days:
            day -= timedelta(days=1)
        streak = 0
        while day.isoformat() in days:
            streak += 1
            day -= timedelta(days=1)
        return {"accuracy": round(100 * (row["correct"] or 0) / row["scored"]) if row["scored"] else 0,
                "streak": streak, "completedModules": sum(m["progress"] >= 1 for m in self._modules),
                "totalMinutes": round((row["duration"] or 0) / 60000), "attempts": row["total"]}

    @Slot(result="QVariant")
    def cameras(self):
        return [{"id": d.device_id, "name": d.name} for d in CameraService.instance().get_devices()]

    @Slot(str, str, bool, str)
    def saveSettings(self, name, camera_id, mirror, theme):
        name = name.strip()
        if not name:
            self.statusChanged.emit("Please enter a learner name.", "warning")
            return
        self._user.name = name[:80]
        UserRepository.update(self._user)
        self._settings.mirror_camera = mirror
        self._settings.theme = theme if theme in ("dark", "light") else "dark"
        if camera_id:
            self._pipeline.switch_camera_by_id(camera_id)
            self._settings.camera_device_id = camera_id
        self._pipeline.set_mirror(mirror)
        SettingsRepository.update(self._settings)
        self.settingsChanged.emit()
        self.statusChanged.emit("Settings saved.", "success")

    @Slot(bool)
    def setDarkMode(self, dark):
        self._settings.theme = "dark" if dark else "light"
        SettingsRepository.update(self._settings)
        self.settingsChanged.emit()

    def _sign_dict(self, sign):
        image = PROJECT_ROOT / sign.image if sign.image else None
        return {"id": sign.id, "label": sign.label, "difficulty": sign.difficulty.value.title(),
                "category": sign.category.value, "description": sign.description,
                "tip": self._tip_for(sign.label), "scored": sign.scored,
                "canScore": sign.scored and self.modelAvailable and (sign.id in self._pipeline._recognizer.get_classes() or sign.label in self._pipeline._recognizer.get_classes()),
                "image": QUrl.fromLocalFile(str(image)).toString() if image and image.is_file() else ""}

    @Slot(result="QVariant")
    def dictionarySigns(self):
        pack = self._content.get_current_pack()
        return [self._sign_dict(s) for s in pack.signs.values()] if pack else []

    @Slot(result="QVariant")
    def progressDetails(self):
        with transaction() as conn:
            rows = conn.execute("SELECT s.label, COUNT(*) AS attempts, SUM(a.result IN ('correct','incorrect','timeout')) AS scored, SUM(a.result='correct') AS correct "
                "FROM practice_attempts a JOIN signs s ON s.id=a.sign_id WHERE a.user_id=? "
                "GROUP BY s.id ORDER BY s.label", (self._user.id,)).fetchall()
        return [{"label": r["label"], "attempts": r["attempts"],
                 "accuracy": round(100 * r["correct"] / r["scored"]) if r["scored"] else 0} for r in rows]

    @Slot(result="QVariant")
    def startQuiz(self):
        signs = [s for s in self.dictionarySigns() if s["description"]]
        self._quiz = random.sample(signs, min(10, len(signs)))
        self._quiz_answered = set()
        questions = []
        for sign in self._quiz:
            others = [s["label"] for s in signs if s["label"] != sign["label"]]
            options = random.sample(others, min(3, len(others))) + [sign["label"]]
            random.shuffle(options)
            questions.append({"prompt": sign["description"], "options": options})
        return questions

    @Slot(int, str, result="QVariant")
    def answerQuiz(self, index, answer):
        if index < 0 or index >= len(self._quiz) or index in self._quiz_answered:
            return {}
        self._quiz_answered.add(index)
        sign = self._quiz[index]
        # Knowledge quizzes are deliberately separate from camera accuracy.
        return {"correct": answer == sign["label"], "answer": sign["label"]}

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

        with transaction() as conn:
            practiced = {r[0] for r in conn.execute("SELECT DISTINCT sign_id FROM practice_attempts WHERE user_id=?", (self._user.id,))}
        tones = ("cyan", "violet", "amber")
        return [
            {
                "id": module.id,
                "title": module.name,
                "description": module.description,
                "progress": sum(s in practiced for s in module.sign_ids) / max(1, len(module.sign_ids)),
                "lessons": len(module.sign_ids),
                "tone": tones[index % len(tones)],
            }
            for index, module in enumerate(pack.modules.values())
        ]

    @Slot(str, result="QVariant")
    def lessonSigns(self, module_id: str) -> list[dict[str, Any]]:  # noqa: N802
        pack = self._content.get_current_pack()
        signs = [pack.signs[module_id]] if pack and module_id in pack.signs else self._content.get_signs_for_module(module_id)
        return [self._sign_dict(sign) for sign in signs]

    @Slot(str, result="QVariant")
    def moduleInfo(self, module_id: str) -> dict[str, Any]:  # noqa: N802
        for module in self._modules:
            if module["id"] == module_id:
                return module
        return {"id": "", "title": "Dictionary practice"}

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
        message = "Show one hand clearly and hold the sign steady." if self._sign_dict(sign)["canScore"] else "Self-guided practice — compare your hand with the reference, then mark reviewed."
        self.statusChanged.emit(message, "info")

    @Slot()
    def stopPractice(self) -> None:  # noqa: N802
        self._pipeline.clear_target()
        self._pipeline.stop()

    @Slot()
    def toggleMirror(self) -> None:  # noqa: N802
        config = CameraService.instance().get_config()
        self._settings.mirror_camera = not config.mirror
        self._pipeline.set_mirror(self._settings.mirror_camera)
        SettingsRepository.update(self._settings)
        self.settingsChanged.emit()

    @Slot(str, str, bool, float, str, int)
    def saveAttempt(self, sign_id: str, module_id: str, correct: bool, confidence: float, predicted: str, duration_ms: int) -> None:
        """Save practice attempt to database."""
        try:
            from app.data.db import AttemptRepository, AttemptResult
            from datetime import datetime

            result = AttemptResult.CORRECT if correct else AttemptResult.INCORRECT
            attempt = PracticeAttempt(
                id=0,
                user_id=self._user.id,
                sign_id=sign_id,
                module_id=module_id if module_id else None,
                result=result,
                confidence=confidence,
                predicted_label=predicted,
                target_label=sign_id.replace("asl_", "").upper(),
                duration_ms=max(0, duration_ms),
                timestamp=datetime.now(),
            )
            AttemptRepository.record(attempt)
            self._modules = self._build_modules()
            self.modulesChanged.emit()
            self.statsChanged.emit()
            logger.info(f"Saved attempt: {sign_id} {'correct' if correct else 'incorrect'}")
        except Exception as e:
            logger.exception("Failed to save attempt")
            self.statusChanged.emit("Could not save your progress. Please try again.", "error")

    @Slot(str, str, int)
    def markReviewed(self, sign_id, module_id, duration_ms):
        pack = self._content.get_current_pack()
        if not pack or sign_id not in pack.signs:
            return
        sign = pack.signs[sign_id]
        AttemptRepository.record(PracticeAttempt(0, self._user.id, sign_id,
            module_id or None, AttemptResult.SKIPPED, 0.0, None, sign.label,
            max(0, duration_ms), datetime.now()))
        self._modules = self._build_modules()
        self.modulesChanged.emit()
        self.statsChanged.emit()

    def _on_camera_status(self, running: bool, message: str) -> None:
        if running and not self.modelAvailable:
            message += " · Self-guided practice"
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
                "label": self._display_label(result.recognition.label),
                "confidence": float(result.recognition.confidence),
                "is_reliable": bool(result.recognition.is_reliable),
            }

        # Sign checking result (Task 2)
        check_result = None
        if result.check_result is not None:
            cr = result.check_result
            check_result = {
                "is_correct": cr.is_correct,
                "confidence": cr.confidence,
                "rule_confidence": cr.rule_confidence,
                "ml_confidence": cr.ml_confidence,
                "hint": cr.hint,
                "ml_prediction": cr.ml_prediction,
                "joint_statuses": [
                    {
                        "index": js.index,
                        "name": js.name,
                        "distance": js.distance,
                        "status": js.status,
                        "hint": js.hint,
                    }
                    for js in cr.joint_statuses
                ],
                "finger_statuses": [
                    {
                        "name": fs.name,
                        "target_state": fs.target_state,
                        "actual_state": fs.actual_state,
                        "match": fs.match,
                        "hint": fs.hint,
                    }
                    for fs in cr.finger_statuses
                ],
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
                "check_result": check_result,
            }
        )

    def _display_label(self, label):
        pack = self._content.get_current_pack()
        return pack.signs[label].label if pack and label in pack.signs else label

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
    pipeline.initialize(use_fake_camera="--demo" in sys.argv)
    pack = content.get_current_pack()
    if pack and pack.model_path:
        pipeline.load_model(str(pack.model_path))

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

    application.aboutToQuit.connect(pipeline.stop)
    exit_code = application.exec()
    pipeline.cleanup()
    CameraService.destroy_instance()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
