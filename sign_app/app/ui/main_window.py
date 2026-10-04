"""
Main application window with navigation stack.
"""

from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QIcon, QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QStackedWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QSizePolicy, QMessageBox, QApplication
)
import logging

from app.ui.theme import theme_manager, ThemeMode
from app.ui.widgets import CameraView, Card, Chip, StatusBanner, PerfHUDManager
from app.data.db import User, UserRole, UserRepository, SettingsRepository, AppSettings

logger = logging.getLogger(__name__)


class NavBar(QWidget):
    """Bottom navigation bar for main sections."""

    navigation_requested = Signal(str)  # screen name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons = {}
        self._active_screen = "home"
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        nav_items = [
            ("home", "🏠", "Home"),
            ("dictionary", "📖", "Dictionary"),
            ("progress", "📊", "Progress"),
            ("settings", "⚙️", "Settings"),
        ]

        for screen_id, icon, tooltip in nav_items:
            btn = QPushButton()
            btn.setToolTip(tooltip)
            btn.setCheckable(True)
            btn.setProperty("class", "nav")
            btn.setFixedSize(56, 56)
            btn.setIcon(self._create_icon(icon))
            btn.setIconSize(QSize(24, 24))
            btn.clicked.connect(lambda checked, s=screen_id: self._on_clicked(s))
            layout.addWidget(btn)
            self._buttons[screen_id] = btn

        self._update_active()

    def _create_icon(self, char: str):
        """Create a simple text-based icon. In production, use QIcon from SVG files."""
        from PySide6.QtGui import QPixmap, QPainter, QFont, QColor
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setFont(QFont("Helvetica Neue", 14))
        painter.setPen(QColor("#FAFAFA"))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, char)
        painter.end()
        return QIcon(pixmap)

    def _on_clicked(self, screen_id: str):
        if screen_id != self._active_screen:
            self._active_screen = screen_id
            self._update_active()
            self.navigation_requested.emit(screen_id)

    def _update_active(self):
        for screen_id, btn in self._buttons.items():
            btn.setChecked(screen_id == self._active_screen)
            btn.setProperty("active", screen_id == self._active_screen)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def set_active(self, screen_id: str):
        if screen_id in self._buttons:
            self._active_screen = screen_id
            self._update_active()


class MainWindow(QMainWindow):
    """
    Main application window.
    Uses a stacked widget for screen navigation.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sign Language Learning")
        self.setMinimumSize(1000, 650)
        self.resize(1200, 800)

        self._current_user: User = None
        self._screens = {}
        self._screen_stack = QStackedWidget()

        self._setup_ui()
        self._apply_theme()
        self._setup_shortcuts()

    def _setup_ui(self):
        # Central widget
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Screen stack
        self._screen_stack = QStackedWidget()
        self._screen_stack.setObjectName("contentStack")
        main_layout.addWidget(self._screen_stack, 1)

        # Navigation bar (hidden during lessons/quiz)
        self._nav_bar = NavBar()
        self._nav_bar.setObjectName("navBar")
        self._nav_bar.navigation_requested.connect(self._navigate_to)
        main_layout.addWidget(self._nav_bar)

    def _apply_theme(self):
        self.setStyleSheet(theme_manager.stylesheet())

    def _setup_shortcuts(self):
        # Global shortcuts
        shortcuts = {
            "Esc": self._go_back,
            "Space": self._space_action,
            "Left": lambda: self._navigate_relative(-1),
            "Right": lambda: self._navigate_relative(1),
            "Ctrl+Shift+D": self._toggle_perf_hud,
        }

        for key, slot in shortcuts.items():
            action = QAction(self)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(slot)
            self.addAction(action)

    def _go_back(self):
        current = self._screen_stack.currentWidget()
        if hasattr(current, 'go_back'):
            current.go_back()

    def _space_action(self):
        current = self._screen_stack.currentWidget()
        if hasattr(current, 'space_action'):
            current.space_action()

    def _navigate_relative(self, delta: int):
        current = self._screen_stack.currentWidget()
        if hasattr(current, 'navigate_relative'):
            current.navigate_relative(delta)

    def _toggle_perf_hud(self):
        """Toggle the performance HUD visibility."""
        PerfHUDManager.get_instance(self).toggle()

    def _navigate_to(self, screen_name: str):
        """Navigate to a main screen."""
        if screen_name in self._screens:
            self._show_screen(screen_name)

    def _show_screen(self, screen_name: str):
        """Show a screen by name."""
        if screen_name in self._screens:
            widget = self._screens[screen_name]
            self._screen_stack.setCurrentWidget(widget)
            self._nav_bar.set_active(screen_name)

            # Call on_show if exists
            if hasattr(widget, 'on_show'):
                widget.on_show()

    def register_screen(self, name: str, widget: QWidget):
        """Register a screen widget."""
        widget.setObjectName(f"screen_{name}")
        widget.setProperty("class", "ScreenWidget")
        self._screens[name] = widget
        self._screen_stack.addWidget(widget)

    def set_current_user(self, user: User):
        """Set the current user and update UI."""
        self._current_user = user
        # Preserve camera and accessibility preferences. Replacing the complete
        # settings record here silently reset the selected physical camera to 0
        # every time the app launched.
        settings = SettingsRepository.get(user.id)
        settings.theme = theme_manager.mode.value
        SettingsRepository.update(settings)

        # Update all screens with user info
        for widget in self._screens.values():
            if hasattr(widget, 'set_user'):
                widget.set_user(user)

    def get_current_user(self) -> User:
        return self._current_user

    def show_screen(self, screen_name: str, **kwargs):
        """Show a screen with optional parameters."""
        if screen_name in self._screens:
            widget = self._screens[screen_name]
            if hasattr(widget, 'prepare'):
                widget.prepare(**kwargs)
            self._show_screen(screen_name)

    def hide_nav_bar(self):
        self._nav_bar.hide()

    def show_nav_bar(self):
        self._nav_bar.show()

    def closeEvent(self, event):
        # Save settings
        if self._current_user:
            settings = SettingsRepository.get(self._current_user.id)
            settings.theme = theme_manager.mode.value
            SettingsRepository.update(settings)
        pipeline = getattr(self, "pipeline", None)
        if pipeline:
            pipeline.cleanup()
        event.accept()


class ScreenBase(QWidget):
    """Base class for all screens with common functionality."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._main_window: MainWindow = None
        self._user: User = None

    def set_main_window(self, main_window: MainWindow):
        self._main_window = main_window

    def set_user(self, user: User):
        self._user = user

    def on_show(self):
        """Called when screen becomes visible."""
        pass

    def prepare(self, **kwargs):
        """Called before showing with parameters."""
        pass

    def go_back(self):
        """Handle back navigation."""
        if self._main_window:
            self._main_window._show_screen("home")

    def space_action(self):
        """Handle space key."""
        pass

    def navigate_relative(self, delta: int):
        """Handle left/right navigation."""
        pass
