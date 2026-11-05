"""Regressions covering startup, persistence, models and actual QML navigation."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from app.content.loader import initialize_content_packs
from app.data import db
from app.qml.main import QmlBridge, CameraImageProvider, PROJECT_ROOT


class StubPipeline(QObject):
    result_ready = Signal(object)
    error_occurred = Signal(str)
    camera_status_changed = Signal(bool, str)
    model_available = False

    def __init__(self):
        super().__init__()
        self.running = False

    def set_confidence_threshold(self, value): pass
    def set_target_sign(self, *args): pass
    def clear_target(self): pass
    def start(self): self.running = True
    def stop(self): self.running = False
    def set_mirror(self, value): pass
    def switch_camera_by_id(self, value): pass


@pytest.fixture
def bridge(qapp):
    content = initialize_content_packs(PROJECT_ROOT / "content_packs")
    return QmlBridge(StubPipeline(), content, CameraImageProvider())


def test_repairs_database_incorrectly_stamped_v7():
    with db.transaction() as conn:
        conn.execute("ALTER TABLE signs DROP COLUMN image")
        conn.execute("ALTER TABLE app_settings DROP COLUMN reduced_motion")
    db.init_db()
    with db.transaction() as conn:
        assert "image" in {r[1] for r in conn.execute("PRAGMA table_info(signs)")}
        assert "reduced_motion" in {r[1] for r in conn.execute("PRAGMA table_info(app_settings)")}


def test_progress_persists_and_reviews_are_not_wrong_answers(bridge):
    module = bridge.modules[0]
    signs = bridge.lessonSigns(module["id"])
    bridge.saveAttempt(signs[0]["id"], module["id"], True, .9, signs[0]["label"], 60000)
    bridge.markReviewed(signs[1]["id"], module["id"], 60000)
    assert bridge.userStats["attempts"] == 2
    assert bridge.userStats["accuracy"] == 100
    assert bridge.userStats["totalMinutes"] == 2
    assert bridge.userStats["streak"] == 1
    reopened = QmlBridge(StubPipeline(), bridge._content, CameraImageProvider())
    assert reopened.currentUser == bridge.currentUser
    assert reopened.userStats == bridge.userStats
    assert reopened.modules[0]["progress"] == 2 / len(signs)


def test_settings_images_and_label_mapping(bridge):
    bridge.saveSettings("  Nico  ", "", False, "light")
    assert db.SettingsRepository.get(bridge._user.id).theme == "light"
    assert db.UserRepository.get_by_id(bridge._user.id).name == "Nico"
    assert bridge._display_label("asl_a") == "A"
    for sign in bridge.dictionarySigns():
        if sign["image"]:
            assert Path(QUrl(sign["image"]).toLocalFile()).is_file()


def test_quiz_cannot_answer_twice(bridge):
    questions = bridge.startQuiz()
    assert len(questions) == 10
    assert all(len(set(q["options"])) == 4 for q in questions)
    label = bridge._quiz[0]["label"]
    assert bridge.answerQuiz(0, label)["correct"]
    assert bridge.answerQuiz(0, label) == {}
    assert bridge.answerQuiz(-1, label) == {}
    assert bridge.userStats["attempts"] == 0


def test_new_content_directory(tmp_path):
    loader = initialize_content_packs(tmp_path / "missing" / "packs")
    assert loader.get_current_pack() is not None


def test_qml_navigation_and_camera_release(bridge, qtbot):
    QQuickStyle.setStyle("Basic")
    engine = QQmlApplicationEngine()
    engine.addImageProvider("camera", bridge._image_provider)
    engine.rootContext().setContextProperty("bridge", bridge)
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
    engine.load(QUrl.fromLocalFile(str(PROJECT_ROOT / "app/qml/main.qml")))
    assert engine.rootObjects()
    root = engine.rootObjects()[0]
    for mode in ("dictionary", "progress", "quiz"):
        root.openLibrary(mode)
        qtbot.wait(250)
        root.goBack()
        qtbot.wait(250)
    root.openSettings()
    qtbot.wait(250)
    root.goBack()
    qtbot.wait(250)
    root.openLesson(bridge.modules[0]["id"])
    qtbot.wait(250)
    assert bridge._pipeline.running
    root.goBack()
    qtbot.wait(300)
    assert not bridge._pipeline.running
    root.close()
    assert not warnings, "\n".join(warnings)
    engine.deleteLater()
    qtbot.wait(20)


def test_old_sign_feedback_is_rejected_and_cleared():
    from app.core.pipeline import CorePipeline
    from app.core.inference_worker import InferenceResult
    pipeline = CorePipeline()
    pipeline._is_running = True
    pipeline.set_target_sign("asl_b")
    stale = InferenceResult(1, 100, [], None, None, ("unknown", 0),
                            (False, 0), 1, 1, target_sign_id="asl_a")
    pipeline._on_inference_result(stale)
    assert pipeline._latest_inference_frame_number is None
    pipeline._latest_check_result = object()
    pipeline.clear_target()
    assert pipeline._latest_check_result is None


def test_training_csv_import_and_roundtrip(tmp_path):
    import csv
    import json
    import numpy as np
    from tools.train_model import load_samples
    from app.core.recognizer import StaticRecognizer, StaticRecognizerConfig
    landmarks = np.random.default_rng(9).random((21, 3)).tolist()
    with (tmp_path / "asl_a.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=["landmarks", "finger_states", "joint_angles"])
        writer.writeheader()
        writer.writerow({"landmarks": json.dumps(landmarks), "finger_states": "{}", "joint_angles": "{}"})
    x, y, *_ = load_samples(tmp_path, min_samples=1)
    assert len(x) == 1 and y[0] == "asl_a"
    # Auto-selection fits raw features; saving must not add a second normalization.
    from sklearn.ensemble import RandomForestClassifier
    x = np.vstack([x, x + 2])
    model = RandomForestClassifier(n_estimators=5, random_state=1).fit(x, ["asl_a", "asl_b"])
    recognizer = StaticRecognizer(StaticRecognizerConfig())
    recognizer._model = model
    recognizer._classes = ["asl_a", "asl_b"]
    recognizer._label_to_idx = {"asl_a": 0, "asl_b": 1}
    recognizer.save(tmp_path / "model")
    loaded = StaticRecognizer.load(tmp_path / "model")
    assert loaded.predict_proba(x[0]) == dict(zip(model.classes_, model.predict_proba(x[:1])[0]))
