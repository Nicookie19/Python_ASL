"""
Python-QML Bridge for the Sign Language Learning App.
Connects Python backend (camera, hand tracking, pipeline) to QML frontend.
"""

import sys
import os
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
import numpy as np

from PySide6.QtCore import QObject, Signal, Slot, QTimer, QUrl, QRect, QPoint, QSize, QAbstractListModel, QModelIndex, Property, QVariant
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtQuick import QQuickView, QQuickItem
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType, QmlElement, QmlSingleton
from PySide6.QtCore import QObject, Signal, Slot, QTimer, QUrl, QRect, QPoint, QSize, QVariant

from app.core.pipeline import CorePipeline
from app.core.camera_service import CameraService
from app.core.camera_devices import CameraDevice
from app.content.loader import ContentPackLoader
from app.content.loader import initialize_content_packs
from app.data.db import init_db, UserRepository, User, SettingsRepository
from app.ui.theme import theme_manager, ThemeMode
from app.core.pipeline import CorePipeline
from app.core.camera_service import CameraService
from app.content.loader import ContentPackLoader
from app.data.db import init_db, UserRepository, User, SettingsRepository

logger = logging.getLogger(__name__)


@QmlElement
class CameraFrameProvider(QObject):
    """Provides camera frames to QML via QImage."""

    frameReady = Signal(QImage)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_frame = None
        self._timer = None

    @Slot(QImage)
    def setFrame(self, image: QImage):
        """Called from Python to update the frame."""
        self.frameReady.emit(image)

    @Property(QImage, notify=frameReady)
    def currentFrame(self):
        return self._current_frame

    @Slot(QImage)
    def setFrame(self, image: QImage):
        self._current_frame = image
        self.frameReady.emit(image)


@QmlElement
class CameraDeviceModel(QObject):
    """QML model for camera device list."""

    deviceChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._devices = []

    @Property(list, notify=deviceChanged)
    def devices(self):
        return self._devices

    @Slot(list)
    def setDevices(self, devices):
        self._devices = devices
        self.deviceChanged.emit()

    @Slot(result=str)
    def getActiveDeviceId(self):
        # Would be implemented to return active device ID
        return ""


@QmlElement
class SignListModel(QAbstractListModel):
    """Model for sign list in dictionary."""

    SignRole = Qt.UserRole + 1
    CategoryRole = Qt.UserRole + 2
    DifficultyRole = Qt.UserRole + 3
    MasteryRole = Qt.UserRole + 4
    ScoredRole = Qt.UserRole + 5

    def __init__(self, parent=None):
        super().__init__(parent)
        self._signs = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._signs)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._signs):
            return QVariant()
        sign = self._signs[index.row()]
        if role == self.SignRole:
            return sign.get("label", "")
        elif role == self.CategoryRole:
            return sign.get("category", "")
        elif role == self.DifficultyRole:
            return sign.get("difficulty", "")
        elif role == self.MasteryRole:
            return sign.get("mastery", 0.0)
        elif role == self.ScoredRole:
            return sign.get("scored", True)
        return QVariant()

    def roleNames(self):
        return {
            self.SignRole: b"label",
            self.CategoryRole: b"category",
            self.DifficultyRole: b"difficulty",
            self.MasteryRole: b"mastery",
            self.ScoredRole: b"scored"
        }

    @Slot(list)
    def setSigns(self, signs):
        self.beginResetModel()
        self._signs = signs
        self.endResetModel()


@QmlElement
class ModuleListModel(QAbstractListModel):
    """Model for module list in home screen."""

    ModuleRole = Qt.UserRole + 1
    ProgressRole = Qt.UserRole + 1
    CategoryRole = Qt.UserRole + 2
    DifficultyRole = Qt.UserRole + 3
    CompletedRole = Qt.UserRole + 4
    MasteredCountRole = Qt.UserRole + 5
    TotalCountRole = Qt.UserRole + 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self._modules = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._modules)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._modules):
            return QVariant()
        module = self._modules[index.row()]
        if role == self.ModuleRole:
            return module.get("name", "")
        elif role == self.ProgressRole:
            return module.get("progress", 0.0)
        elif role == self.CategoryRole:
            return module.get("category", "")
        elif role == self.DifficultyRole:
            return module.get("difficulty", "")
        elif role == self.CompletedRole:
            return module.get("completed", False)
        elif role == self.MasteredCountRole:
            return module.get("mastered", 0)
        elif role == self.TotalCountRole:
            return module.get("total", 0)
        return QVariant()

    def roleNames(self):
        return {
            self.ModuleRole: b"name",
            self.ProgressRole: b"progress",
            self.CategoryRole: b"category",
            self.DifficultyRole: b"difficulty",
            self.CompletedRole: b"completed",
            self.MasteredCountRole: b"mastered",
            self.TotalCountRole: b"total"
        }

    @Slot(list)
    def setModules(self, modules):
        self.beginResetModel()
        self._modules = modules
        self.endResetModel()


class QMLBridge(QObject):
    """Main bridge between Python backend and QML frontend."""

    # Signals to QML
    cameraFrameReady = Signal('QVariant')  # QImage
    cameraStatusChanged = Signal(bool, str)  # running, message
    staticFeedDetected = Signal(str)
    inferenceResultReady = Signal('QVariant')  # InferenceResult dict
    inferenceFpsUpdate = Signal(float)
    cameraStatusChanged = Signal(bool, str)  # running, message
    cameraDevicesChanged = Signal()
    activeDeviceChanged = Signal(str, str)  # old, new
    modelLoaded = Signal(bool, str)
    errorOccurred = Signal(str)
    themeChanged = Signal()
    userChanged = Signal()
    screenChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Initialize components
        self._app = None
        self._engine = None
        self._pipeline = None
        self._camera_service = None
        self._content_loader = None
        self._current_user = None

        # Camera frame provider
        self._frame_provider = None

        # Settings
        self._theme = None

        # Performance HUD
        self._perf_hud = None

        # State
        self._current_user = None
        self._current_screen = "welcome"

        # Timer for frame updates
        self._frame_timer = None

    def initialize(self):
        """Initialize all components."""
        # Initialize database
        from app.data.db import init_db
        init_db()

        # Initialize content packs
        from app.content.loader import initialize_content_packs, ContentPackLoader
        project_root = Path(__file__).resolve().parents[3]
        packs_dir = project_root / "content_packs"
        self._content_loader = initialize_content_packs(Path(__file__).resolve().parents[3] / "content_packs")

        # Initialize database
        from app.data.db import init_db
        init_db()

        # Initialize content packs
        from app.content.loader import initialize_content_packs
        packs_dir = Path(__file__).resolve().parents[3] / "content_packs"
        self._content_loader = initialize_content_packs(packs_dir)

        # Create core pipeline
        from app.core.pipeline import CorePipeline
        self._pipeline = CorePipeline()
        self._pipeline.initialize(use_fake_camera=False)

        # Create camera service
        from app.core.camera_service import CameraService
        self._camera_service = CameraService.instance()

        # Connect camera service signals
        self._camera_service.frame_ready.connect(self._on_camera_frame)
        self._camera_service.error_occurred.connect(self._on_camera_error)
        self._camera_service.camera_status_changed.connect(self._on_camera_status)
        self._camera_service.static_feed_detected.connect(self.staticFeedDetected.emit)

        # Connect pipeline signals
        from app.core.pipeline import CorePipeline
        self._pipeline = CorePipeline()
        self._pipeline.initialize(use_fake_camera=False)

        self._pipeline.result_ready.connect(self._on_pipeline_result)
        self._pipeline.error_occurred.connect(self.errorOccurred.emit)
        self._pipeline.camera_status_changed.connect(self.cameraStatusChanged.emit)
        self._pipeline.model_loaded.connect(self.modelLoaded.emit)
        self._pipeline.inference_fps_update.connect(self.inferenceFpsUpdate.emit)

        # Create Performance HUD
        from app.ui.widgets.perf_hud import PerfHUDManager
        self._perf_hud = PerfHUDManager.get_instance(None)

        # Connect pipeline performance signals
        self._pipeline.inference_fps_update.connect(self.inferenceFpsUpdate.emit)

        # Create main QML engine
        self._engine = QQmlApplicationEngine()
        self._engine.rootContext().setContextProperty("bridge", self)

        # Register theme
        from app.ui.theme import theme_manager
        self._theme = theme_manager
        self._theme_changed = self.themeChanged

        # Load main QML
        qml_file = Path(__file__).parent / "main.qml"
        self._engine.load(QUrl.fromLocalFile(str(qml_file)))

        if self._engine.rootObjects():
            self._root = self._engine.rootObjects()[0]
            self._root.setProperty("bridge", self)

    @Slot()
    def initialize(self):
        """Initialize all components after QML is loaded."""
        pass

    @Slot()
    def _on_camera_frame(self, frame):
        """Handle frame from camera service."""
        # Convert numpy array to QImage
        # This would be implemented with proper QImage conversion
        pass

    @Slot(bool, str)
    def _on_camera_status(self, running: bool, message: str):
        """Handle camera status changes."""
        self.cameraStatusChanged.emit(running, message)

    @Slot(str)
    def _on_camera_error(self, message: str):
        """Handle camera errors."""
        self.errorOccurred.emit(message)

    @Slot(object)
    def _on_pipeline_result(self, result):
        """Handle pipeline result with inference."""
        # Emit to QML
        self.inferenceResultReady.emit(result)

    @Slot()
    def toggleTheme(self):
        """Toggle theme."""
        from app.ui.theme import theme_manager
        self._theme.toggle()
        self.themeChanged.emit()

    @Slot(str)
    def showScreen(self, screenName: str):
        """Show a screen by name."""
        self.screenChanged.emit(screenName)

    @Slot()
    def goBack(self):
        """Go back to previous screen."""
        pass

    def spaceAction(self):
        """Handle space key."""
        pass

    def navigateRelative(self, delta: int):
        pass

    def goBack(self):
        pass

    def spaceAction(self):
        pass

    def navigateRelative(self, delta: int):
        pass

    def togglePerfHud(self):
        """Toggle performance HUD."""
        if self._perf_hud:
            self._perf_hud.toggle()

    @Property(bool, notify=themeChanged)
    def isDarkTheme(self):
        from app.ui.theme import theme_manager
        return theme_manager.mode.value == "dark"

    @Slot()
    def toggleTheme(self):
        from app.ui.theme import theme_manager
        theme_manager.toggle()
        self.themeChanged.emit()

    @Slot(str)
    def setActiveCamera(self, deviceId: str):
        """Set active camera device."""
        if self._camera_service:
            self._camera_service.set_active_device(deviceId)

    @Slot(str)
    def setCameraMirror(self, mirror: bool):
        if self._camera_service:
            self._camera_service.set_mirror(mirror)

    @Slot(int)
    def setCameraResolution(self, width: int, height: int):
        if self._camera_service:
            self._camera_service.set_resolution(width, height)

    @Slot(int)
    def setCameraFps(self, fps: int):
        if self._camera_service:
            self._camera_service.set_fps(fps)

    @Slot(str)
    def loadModel(self, modelPath: str):
        """Load recognition model."""
        if self._pipeline:
            self._pipeline.load_model(modelPath)

    @Slot(str)
    def showScreen(self, screenName: str):
        """Show a screen by name."""
        self.screenChanged.emit(screenName)

    @Slot()
    def goBack(self):
        """Go back to previous screen."""
        pass

    def spaceAction(self):
        pass

    def navigateRelative(self, delta: int):
        pass

    def goBack(self):
        pass

    def spaceAction(self):
        pass

    def navigateRelative(self, delta: int):
        pass

    @Slot()
    def togglePerfHud(self):
        if self._perf_hud:
            self._perf_hud.toggle()


def main():
    import sys
    import os
    import logging
    from logging.handlers import RotatingFileHandler
    from pathlib import Path

    # Add project root to path
    project_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(project_root))

    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt, QTimer, QUrl
    from PySide6.QtGui import QFont, QIcon
    from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType, qmlRegisterSingletonType
    from PySide6.QtQml import qmlRegisterSingletonType, QmlElement, QmlSingleton

    from app.ui.theme import theme_manager, ThemeMode
    from app.ui.main_window import MainWindow
    from app.ui.screens.welcome import WelcomeScreen
    from app.ui.screens.home import HomeScreen
    from app.ui.screens.lesson import LessonScreen
    from app.ui.screens.quiz import QuizScreen
    from app.ui.screens.dictionary import DictionaryScreen
    from app.ui.screens.progress import ProgressScreen
    from app.ui.screens.instructor import InstructorScreen
    from app.ui.screens.settings import SettingsScreen
    from app.core.pipeline import CorePipeline
    from app.core.camera_service import CameraService
    from app.content.loader import initialize_content_packs, ContentPackLoader
    from app.data.db import init_db, UserRepository, User, SettingsRepository
    from app.ui.widgets import PerfHUDManager

    # Configure logging
    log_dir = Path(__file__).resolve().parents[3] / "logs"
    log_dir.mkdir(exist_ok=True)
    _formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    _file_handler = RotatingFileHandler(log_dir / "app.log", maxBytes=1_000_000, backupCount=3)
    _file_handler.setLevel(logging.DEBUG)
    _file_handler.setFormatter(_formatter)
    _console_handler = logging.StreamHandler()
    _console_handler.setLevel(logging.DEBUG)
    _console_handler.setFormatter(_formatter)
    logging.basicConfig(level=logging.DEBUG, handlers=[_file_handler, _console_handler])
    logger = logging.getLogger(__name__)

    # QML imports
    from PySide6.QtCore import QUrl, QCoreApplication
    from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType, qmlRegisterSingletonType
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QIcon

    from app.ui.theme import theme_manager, ThemeMode
    from app.ui.main_window import MainWindow
    from app.ui.screens.welcome import WelcomeScreen
    from app.ui.screens.home import HomeScreen
    from app.ui.screens.lesson import LessonScreen
    from app.ui.screens.quiz import QuizScreen
    from app.ui.screens.dictionary import DictionaryScreen
    from app.ui.screens.progress import ProgressScreen
    from app.ui.screens.instructor import InstructorScreen
    from app.ui.screens.settings import SettingsScreen
    from app.core.pipeline import CorePipeline
    from app.core.camera_service import CameraService
    from app.content.loader import initialize_content_packs, ContentPackLoader
    from app.data.db import init_db, UserRepository, User, SettingsRepository
    from app.ui.widgets import PerfHUDManager

    # Configure logging
    log_dir = Path(__file__).resolve().parents[3] / "logs"
    log_dir.mkdir(exist_ok=True)
    _formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    _file_handler = RotatingFileHandler(log_dir / "app.log", maxBytes=1_000_000, backupCount=3)
    _file_handler.setLevel(logging.DEBUG)
    _file_handler.setFormatter(_formatter)
    _console_handler = logging.StreamHandler()
    _console_handler.setLevel(logging.DEBUG)
    _console_handler.setFormatter(_formatter)
    logging.basicConfig(level=logging.DEBUG, handlers=[_file_handler, _console_handler])
    logger = logging.getLogger(__name__)

    # Register QML types
    qmlRegisterType(QMLBridge, "SignLanguageApp", 1, 0, "Bridge")
    qmlRegisterType(CameraFrameProvider, "SignLanguageApp", 1, 0, "CameraFrameProvider")
    qmlRegisterType(CameraDeviceModel, "SignLanguageApp", 1, 0, "CameraDeviceModel")
    qmlRegisterType(SignListModel, "SignLanguageApp", 1, 0, "SignListModel")
    qmlRegisterType(ModuleListModel, "SignLanguageApp", 1, 0, "ModuleListModel")

    def main():
        # Handle macOS camera permissions
        if sys.platform == 'darwin':
            os.environ['QT_MAC_WANTS_LAYER'] = '1'

        # Create QApplication
        app = QApplication(sys.argv)
        app.setApplicationName("Sign Language Learning")
        app.setOrganizationName("SignLanguageApp")

        # Enable high DPI scaling
        app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

        # Set default font
        font = QFont("Helvetica Neue", 10)
        app.setFont(font)

        # Initialize database
        init_db()

        # Initialize content packs
        packs_dir = Path(__file__).resolve().parents[3] / "content_packs"
        content_loader = initialize_content_packs(packs_dir)

        # Create camera service
        camera_service = CameraService.instance()

        # Create core pipeline
        pipeline = CorePipeline()
        pipeline.initialize(use_fake_camera=False)

        # Create QML engine
        engine = QQmlApplicationEngine()

        # Create bridge
        bridge = QMLBridge()
        bridge.initialize()

        # Set context properties
        engine.rootContext().setContextProperty("bridge", bridge)
        engine.rootContext().setContextProperty("themeManager", theme_manager)
        engine.rootContext().setContextProperty("contentLoader", content_loader)
        engine.rootContext().setContextProperty("cameraService", CameraService.instance())
        engine.rootContext().setContextProperty("pipeline", pipeline)

        # Load main QML
        qml_file = Path(__file__).parent / "qml" / "main.qml"
        engine.load(QUrl.fromLocalFile(str(qml_file)))

        if not engine.rootObjects():
            logger.error("Failed to load QML")
            return -1

        # Create QML bridge after engine is loaded
        bridge = QMLBridge()
        bridge.initialize()

        # Set context properties on root object
        root = engine.rootObjects()[0]
        root.setProperty("bridge", bridge)
        root.setProperty("themeManager", theme_manager)
        root.setProperty("contentLoader", content_loader)

        return app.exec()

    if __name__ == "__main__":
        sys.exit(main())