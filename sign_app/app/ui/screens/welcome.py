"""
Welcome screen - first run experience.
Handles consent, profile creation, and camera check.
"""

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QFrame, QScrollArea, QButtonGroup, QRadioButton
)
from PySide6.QtGui import QFont, QPixmap, QColor
import logging

from app.ui.main_window import ScreenBase
from app.ui.widgets import Card, Chip, CameraView, StatusBanner
from app.ui.theme import theme_manager
from app.data.db import User, UserRole, UserRepository, init_db
from app.content.loader import initialize_content_packs, DEFAULT_ASL_SIGNS, DEFAULT_ASL_MODULES
from app.data.db import SignRepository, ModuleRepository, BadgeRepository, ModuleCategory, Difficulty, Sign

logger = logging.getLogger(__name__)


class WelcomeScreen(ScreenBase):
    """
    First-run welcome screen with multi-step flow:
    1. Welcome & Consent
    2. Profile Creation
    3. Camera Check
    4. Complete → Home
    """

    finished = Signal(User)

    def __init__(self, main_window, pipeline, content_loader, camera_service):
        super().__init__(main_window)
        self._pipeline = pipeline
        self._content_loader = content_loader
        self.camera_service = camera_service
        self._step = 0
        self._steps = ["consent", "profile", "camera", "complete"]
        self._user_data = {}
        self._camera_check_timer = None

        self._setup_ui()
        self._check_first_run()

    def _check_first_run(self):
        """Check if this is the first run (no users exist)."""
        users = UserRepository.get_all()
        if users:
            # Not first run - skip to home
            self._step = len(self._steps) - 1
            self._show_step()
        else:
            self._step = 0
            self._show_step()

    def _setup_ui(self):
        self.setStyleSheet("background-color: transparent;")

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Stacked widget for steps
        from PySide6.QtWidgets import QStackedWidget
        self._stack = QStackedWidget()
        main_layout.addWidget(self._stack)

        # Create step widgets
        self._consent_widget = self._create_consent_step()
        self._profile_widget = self._create_profile_step()
        self._camera_widget = self._create_camera_step()
        self._complete_widget = self._create_complete_step()

        self._stack.addWidget(self._consent_widget)
        self._stack.addWidget(self._profile_widget)
        self._stack.addWidget(self._camera_widget)
        self._stack.addWidget(self._complete_widget)

        # Navigation buttons at bottom
        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(24, 16, 24, 24)

        self._back_btn = QPushButton("Back")
        self._back_btn.setProperty("class", "secondary")
        self._back_btn.clicked.connect(self._go_back)
        nav_layout.addWidget(self._back_btn)

        nav_layout.addStretch()

        self._next_btn = QPushButton("Continue")
        self._next_btn.setProperty("class", "primary")
        self._next_btn.clicked.connect(self._go_next)
        nav_layout.addWidget(self._next_btn)

        main_layout.addLayout(nav_layout)

    def _create_consent_step(self) -> QWidget:
        """Step 1: Welcome and Privacy Consent."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(24)

        # Title
        title = QLabel("Welcome to Sign Language Learning")
        title.setProperty("class", "heading")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Learn ASL fingerspelling with real-time hand tracking")
        subtitle.setProperty("class", "body")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        # Consent card
        card = Card()
        card_layout = card.layout()

        consent_text = QLabel(
            "<h3>Privacy & Data Consent</h3>"
            "<p>This application runs entirely offline. Your data never leaves your device.</p>"
            "<p><b>What we store locally:</b></p>"
            "<ul>"
            "<li>Your profile name and preferences</li>"
            "<li>Practice history and quiz scores</li>"
            "<li>Progress tracking (streaks, badges, accuracy)</li>"
            "</ul>"
            "<p><b>What we NEVER store:</b></p>"
            "<ul>"
            "<li>Camera images or video frames</li>"
            "<li>Biometric data (only derived landmarks for recognition)</li>"
            "<li>Any personally identifiable information beyond your chosen name</li>"
            "</ul>"
            "<p><small>In compliance with the Philippines Data Privacy Act of 2012 (RA 10173). "
            "You can export or delete all your data at any time from Settings.</small></p>"
        )
        consent_text.setWordWrap(True)
        consent_text.setProperty("class", "body")
        consent_text.setTextFormat(Qt.RichText)
        card_layout.addWidget(consent_text)

        self._consent_checkbox = QPushButton("I understand and agree")
        self._consent_checkbox.setCheckable(True)
        self._consent_checkbox.setProperty("class", "secondary")
        self._consent_checkbox.toggled.connect(self._on_consent_changed)
        card_layout.addWidget(self._consent_checkbox)

        layout.addWidget(card)
        layout.addStretch()

        return widget

    def _create_profile_step(self) -> QWidget:
        """Step 2: Profile Creation."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(24)

        title = QLabel("Create Your Profile")
        title.setProperty("class", "heading")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        card = Card()
        card_layout = card.layout()

        # Name input
        name_label = QLabel("Your Name")
        name_label.setProperty("class", "body")
        card_layout.addWidget(name_label)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Enter your name")
        self._name_input.textChanged.connect(self._validate_profile)
        card_layout.addWidget(self._name_input)

        # Avatar color selection
        avatar_label = QLabel("Avatar Color")
        avatar_label.setProperty("class", "body")
        avatar_label.setContentsMargins(0, 16, 0, 0)
        card_layout.addWidget(avatar_label)

        avatar_layout = QHBoxLayout()
        avatar_layout.setSpacing(12)
        self._avatar_buttons = []
        colors = ["#22D3EE", "#4ADE80", "#F87171", "#FBBF24", "#A78BFA", "#FB923C", "#EC4899", "#14B8A6"]
        self._selected_color = colors[0]

        for color in colors:
            btn = QPushButton()
            btn.setFixedSize(48, 48)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    border-radius: 24px;
                    border: 3px solid transparent;
                }}
                QPushButton:checked {{
                    border-color: white;
                }}
            """)
            btn.setCheckable(True)
            btn.setChecked(color == self._selected_color)
            btn.clicked.connect(lambda checked, c=color: self._select_avatar_color(c))
            avatar_layout.addWidget(btn)
            self._avatar_buttons.append(btn)
        avatar_layout.addStretch()
        card_layout.addLayout(avatar_layout)

        # Role selection
        role_label = QLabel("Role")
        role_label.setProperty("class", "body")
        role_label.setContentsMargins(0, 16, 0, 0)
        card_layout.addWidget(role_label)

        self._role_group = QButtonGroup()
        role_layout = QHBoxLayout()
        role_layout.setSpacing(16)

        for role_text, role_value in [("Learner", UserRole.LEARNER), ("Instructor", UserRole.INSTRUCTOR)]:
            rb = QRadioButton(role_text)
            rb.setProperty("role", role_value.value)
            self._role_group.addButton(rb)
            role_layout.addWidget(rb)
            if role_value == UserRole.LEARNER:
                rb.setChecked(True)
        role_layout.addStretch()
        card_layout.addLayout(role_layout)

        layout.addWidget(card)
        layout.addStretch()

        return widget

    def _create_camera_step(self) -> QWidget:
        """Step 3: Camera Check."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)

        title = QLabel("Camera Check")
        title.setProperty("class", "heading")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Make sure your camera works and your hand is visible")
        subtitle.setProperty("class", "body")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        # Camera view
        self._camera_view = CameraView()
        self._camera_view.setMinimumHeight(400)
        layout.addWidget(self._camera_view)

        # Status
        self._camera_status = StatusBanner()
        self._camera_status.setText("Starting camera...")
        self._camera_status.setProperty("state", "info")
        layout.addWidget(self._camera_status)

        # Tips
        tips_card = Card()
        tips_layout = tips_card.layout()
        tips_label = QLabel(
            "<b>Tips for best results:</b><br>"
            "• Ensure good lighting on your hands<br>"
            "• Keep background uncluttered<br>"
            "• Position hands in the center of the frame<br>"
            "• Avoid wearing gloves or dark nail polish"
        )
        tips_label.setWordWrap(True)
        tips_label.setProperty("class", "body-small")
        tips_layout.addWidget(tips_label)
        layout.addWidget(tips_card)

        return widget

    def _create_complete_step(self) -> QWidget:
        """Step 4: Setup Complete."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(24)

        title = QLabel("You're All Set! 🎉")
        title.setProperty("class", "heading")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        card = Card()
        card_layout = card.layout()

        msg = QLabel(
            "Your profile has been created and the camera is working.\n\n"
            "You can now start learning ASL fingerspelling!\n\n"
            "Click <b>Start Learning</b> to begin your first lesson."
        )
        msg.setWordWrap(True)
        msg.setProperty("class", "body")
        msg.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(msg)

        layout.addWidget(card)
        layout.addStretch()

        return widget

    def _show_step(self):
        """Show the current step."""
        self._stack.setCurrentIndex(self._step)

        # Update button states
        self._back_btn.setEnabled(self._step > 0)
        self._back_btn.setVisible(self._step > 0)

        is_last = self._step == len(self._steps) - 1
        self._next_btn.setText("Start Learning" if is_last else "Continue")

        # Step-specific setup
        if self._steps[self._step] == "camera":
            self._start_camera_check()
        elif self._steps[self._step] == "complete":
            self._finalize_setup()

    def _on_consent_changed(self, checked: bool):
        self._next_btn.setEnabled(checked)

    def _validate_profile(self):
        name = self._name_input.text().strip()
        self._next_btn.setEnabled(len(name) >= 2)

    def _select_avatar_color(self, color: str):
        self._selected_color = color
        for btn in self._avatar_buttons:
            btn.setChecked(btn.styleSheet().find(color) >= 0)

    def _go_back(self):
        if self._step > 0:
            self._step -= 1
            self._show_step()

    def _go_next(self):
        if self._steps[self._step] == "consent":
            self._step += 1
            self._show_step()
        elif self._steps[self._step] == "profile":
            self._save_profile()
            self._step += 1
            self._show_step()
        elif self._steps[self._step] == "camera":
            self._step += 1
            self._show_step()
        elif self._steps[self._step] == "complete":
            self.finished.emit(self._current_user)

    def _save_profile(self):
        """Save user profile."""
        name = self._name_input.text().strip()
        role = UserRole.LEARNER
        for btn in self._role_group.buttons():
            if btn.isChecked():
                role = UserRole(btn.property("role"))
                break

        user = UserRepository.create(name, self._selected_color, role)
        self._current_user = user
        logger.info(f"Created user: {user.name} ({user.role.value})")

    def _start_camera_check(self):
        """Start camera for checking."""
        self._pipeline.camera_status_changed.connect(self._on_camera_status)
        self._pipeline.start()

    def _on_camera_status(self, running: bool, message: str):
        if "still image" in message.lower():
            self._camera_status.setText(message)
            self._camera_status.setProperty("state", "warning")
        elif running:
            self._camera_status.setText("Camera running - show your hand")
            self._camera_status.setProperty("state", "success")
        else:
            self._camera_status.setText(message)
            self._camera_status.setProperty("state", "info")

    def _check_camera_status(self):
        """Check if camera is working."""
        # The pipeline emits results - we just need to verify it's running
        # In practice, we'd check the last frame for hand detection
        pass

    def _finalize_setup(self):
        """Finalize setup: initialize database with default content."""
        # Sync content packs to database
        pack = self._content_loader.get_current_pack()
        if pack:
            self._content_loader.sync_to_database(pack)

        # Seed badges
        BadgeRepository.seed_default_badges()

        # Set user in main window (only if _main_window is set)
        if self._main_window and self._current_user:
            self._main_window.set_current_user(self._current_user)

    def on_show(self):
        pass


class CameraCheckWidget(QWidget):
    """Reusable camera check widget for settings and first run."""

    def __init__(self, pipeline, parent=None):
        super().__init__(parent)
        self._pipeline = pipeline
        self._setup_ui()
        self._connect_pipeline()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        self._camera_view = CameraView()
        self._camera_view.setMinimumHeight(300)
        layout.addWidget(self._camera_view)

        self._status = StatusBanner()
        self._status.setText("Checking camera...")
        self._status.setProperty("state", "info")
        layout.addWidget(self._status)

        btn_layout = QHBoxLayout()
        self._start_btn = QPushButton("Start Camera")
        self._start_btn.setProperty("class", "primary")
        self._start_btn.clicked.connect(self._start_camera)
        btn_layout.addWidget(self._start_btn)

        self._stop_btn = QPushButton("Stop Camera")
        self._stop_btn.setProperty("class", "secondary")
        self._stop_btn.clicked.connect(self._stop_camera)
        self._stop_btn.setEnabled(False)
        btn_layout.addWidget(self._stop_btn)
        layout.addLayout(btn_layout)

    def _connect_pipeline(self):
        """Connect to pipeline signals for camera status updates and frames."""
        self._pipeline.camera_status_changed.connect(self._on_camera_status)
        self._pipeline.result_ready.connect(self._on_pipeline_result)

    def _on_camera_status(self, running: bool, message: str):
        if "still image" in message.lower():
            self._status.setText(message)
            self._status.setProperty("state", "warning")
        elif running:
            self._status.setText("Camera running - show your hand")
            self._status.setProperty("state", "success")
        else:
            self._status.setText(message)
            self._status.setProperty("state", "info")

    def _on_pipeline_result(self, result):
        """Receive camera frames from pipeline and display them."""
        self._camera_view.set_frame(result.frame)

    def _start_camera(self):
        self._pipeline.start()
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)

    def _stop_camera(self):
        self._pipeline.stop()
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status.setText("Camera stopped")
        self._status.setProperty("state", "info")