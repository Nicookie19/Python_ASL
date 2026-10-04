"""
Main entry point for the Sign Language Learning Application.
"""

import sys
import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
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

# Configure logging before application services are constructed. A rotating log
# is deliberately kept in the project for camera/backend diagnostics.
log_dir = project_root / "logs"
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


class SignLanguageApp:
    """Main application controller."""

    def __init__(self, use_fake_camera: bool = False):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Sign Language Learning")
        self.app.setOrganizationName("SignLanguageApp")

        # Enable high DPI scaling
        self.app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        self.app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

        # Set default font
        font = QFont("Helvetica Neue", 10)
        self.app.setFont(font)

        # Initialize database
        init_db()

        # Initialize content packs
        packs_dir = project_root / "content_packs"
        self.content_loader = initialize_content_packs(packs_dir)

        # Create camera service (singleton)
        self.camera_service = CameraService.instance()
        if use_fake_camera:
            # For testing - we'll use the fake camera worker in the pipeline
            pass

        # Create core pipeline
        self.pipeline = CorePipeline()
        self.pipeline.initialize(use_fake_camera=use_fake_camera)

        # Connect camera service signals to pipeline
        self.camera_service.error_occurred.connect(self.pipeline.error_occurred.emit)
        self.camera_service.static_feed_detected.connect(
            lambda msg: self.pipeline.camera_status_changed.emit(True, msg)
        )

        # Create main window
        self.window = MainWindow()
        self.window.pipeline = self.pipeline
        self.window.camera_service = self.camera_service

        # Create Performance HUD
        self.perf_hud = PerfHUDManager.get_instance(self.window)

        # Connect pipeline performance signals to HUD
        self.pipeline.inference_fps_update.connect(
            lambda fps: self.perf_hud.update_metrics(_inference_fps=fps)
        )

        # Create screens
        self._create_screens()

        # Check for existing user (auto-login for now)
        self._check_existing_user()
        
        # For testing: auto-skip welcome if user exists
        if self.window.get_current_user():
            self.window._show_screen("home")

        # Apply globally so dialogs and dynamically-created cards use the same
        # design system.
        self.app.setStyleSheet(theme_manager.stylesheet())

    def _create_screens(self):
        """Create and register all screens."""
        screens = [
            ("welcome", WelcomeScreen(self.window, self.pipeline, self.content_loader, self.camera_service)),
            ("home", HomeScreen(self.window, self.content_loader, self.camera_service)),
            ("lesson", LessonScreen(self.window, self.pipeline, self.content_loader, self.camera_service)),
            ("quiz", QuizScreen(self.window, self.pipeline, self.content_loader, self.camera_service)),
            ("dictionary", DictionaryScreen(self.window, self.pipeline, self.content_loader, self.camera_service)),
            ("progress", ProgressScreen(self.window, self.content_loader, self.camera_service)),
            ("instructor", InstructorScreen(self.window, self.content_loader, self.camera_service)),
            ("settings", SettingsScreen(self.window, self.pipeline, self.content_loader, self.camera_service)),
        ]

        for name, screen in screens:
            screen.set_main_window(self.window)
            self.window.register_screen(name, screen)

    def _check_existing_user(self):
        """Check for existing users and auto-login the first one."""
        users = UserRepository.get_all()
        if users:
            # Auto-login first user for convenience
            user = users[0]
            self.window.set_current_user(user)
            # The worker is created before the user is known. Apply the saved
            # physical-camera choice before any lesson or quiz can start.
            settings = SettingsRepository.get(user.id)
            self.camera_service.set_active_device(settings.camera_device_id)
            self.camera_service.set_mirror(settings.mirror_camera)
            self.pipeline.set_confidence_threshold(settings.confidence_threshold)
            self.pipeline.set_smoothing_window(settings.smoothing_frames)
            self.window._show_screen("home")
        else:
            # First run - show welcome
            self.window._show_screen("welcome")

    def run(self):
        """Run the application."""
        self.window.show()
        return self.app.exec()


def main():
    """Main entry point."""
    # Handle macOS camera permissions
    if sys.platform == 'darwin':
        # Ensure we have camera permission prompt
        os.environ['QT_MAC_WANTS_LAYER'] = '1'

    app = SignLanguageApp()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
