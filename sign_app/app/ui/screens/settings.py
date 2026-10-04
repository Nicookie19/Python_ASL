"""
Settings screen - camera, theme, accessibility, privacy, language.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSlider, QSpinBox, QCheckBox, QScrollArea,
    QFrame, QDialog, QDialogButtonBox, QMessageBox, QFileDialog
)
from PySide6.QtGui import QFont
import logging

from app.ui.main_window import ScreenBase
from app.ui.widgets import Card
from app.ui.screens.welcome import CameraCheckWidget
from app.ui.theme import theme_manager, ThemeMode
from app.data.db import SettingsRepository, AppSettings, export_user_data, delete_user_data, UserRepository
from app.content.loader import ContentPackLoader, initialize_content_packs

logger = logging.getLogger(__name__)


class SettingsScreen(ScreenBase):
    """Application settings."""

    def __init__(self, main_window, pipeline, content_loader, camera_service):
        super().__init__(main_window)
        self._pipeline = pipeline
        self._content_loader = content_loader
        self.camera_service = camera_service
        self._settings: AppSettings = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(24)

        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Title
        title = QLabel("Settings")
        title.setProperty("class", "heading")
        content_layout.addWidget(title)

        # Camera section
        camera_card = self._create_camera_section()
        content_layout.addWidget(camera_card)

        # Display section
        display_card = self._create_display_section()
        content_layout.addWidget(display_card)

        # Recognition section
        recognition_card = self._create_recognition_section()
        content_layout.addWidget(recognition_card)

        # Interaction section
        interaction_card = self._create_interaction_section()
        content_layout.addWidget(interaction_card)

        # Language section
        language_card = self._create_language_section()
        content_layout.addWidget(language_card)

        # Privacy section
        privacy_card = self._create_privacy_section()
        content_layout.addWidget(privacy_card)

        # About section
        about_card = self._create_about_section()
        content_layout.addWidget(about_card)

        content_layout.addStretch()

    def _create_camera_section(self) -> QWidget:
        card = Card()
        layout = card.layout()

        title = QLabel("Camera")
        title.setProperty("class", "title")
        layout.addWidget(title)

        # Camera selection
        cam_layout = QHBoxLayout()
        cam_layout.addWidget(QLabel("Camera:"))

        self._camera_combo = QComboBox()
        self._refresh_cameras()
        self._camera_combo.currentIndexChanged.connect(self._on_camera_changed)
        cam_layout.addWidget(self._camera_combo)

        self._refresh_cam_btn = QPushButton("Refresh")
        self._refresh_cam_btn.setProperty("class", "secondary")
        self._refresh_cam_btn.setProperty("class", "small")
        self._refresh_cam_btn.clicked.connect(self._refresh_cameras)
        cam_layout.addWidget(self._refresh_cam_btn)

        cam_layout.addStretch()
        layout.addLayout(cam_layout)

        # Mirror toggle
        self._mirror_check = QCheckBox("Mirror camera (selfie view)")
        self._mirror_check.stateChanged.connect(self._on_mirror_changed)
        layout.addWidget(self._mirror_check)

        # Camera check widget
        self._camera_check = CameraCheckWidget(self._pipeline)
        layout.addWidget(self._camera_check)

        return card

    def _create_display_section(self) -> QWidget:
        card = Card()
        layout = card.layout()

        title = QLabel("Display")
        title.setProperty("class", "title")
        layout.addWidget(title)

        # Theme
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Theme:"))

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["Dark", "Light", "System"])
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_layout.addWidget(self._theme_combo)
        theme_layout.addStretch()
        layout.addLayout(theme_layout)

        # Text size
        text_layout = QHBoxLayout()
        text_layout.addWidget(QLabel("Text Size:"))

        self._text_size_slider = QSlider(Qt.Horizontal)
        self._text_size_slider.setRange(12, 24)
        self._text_size_slider.setValue(16)
        self._text_size_slider.valueChanged.connect(self._on_text_size_changed)
        text_layout.addWidget(self._text_size_slider)

        self._text_size_label = QLabel("16px")
        self._text_size_label.setFixedWidth(40)
        text_layout.addWidget(self._text_size_label)
        layout.addLayout(text_layout)

        return card

    def _create_recognition_section(self) -> QWidget:
        card = Card()
        layout = card.layout()

        title = QLabel("Recognition")
        title.setProperty("class", "title")
        layout.addWidget(title)

        # Confidence threshold
        conf_layout = QHBoxLayout()
        conf_layout.addWidget(QLabel("Confidence Threshold:"))

        self._confidence_slider = QSlider(Qt.Horizontal)
        self._confidence_slider.setRange(50, 95)
        self._confidence_slider.setValue(70)
        self._confidence_slider.valueChanged.connect(self._on_confidence_changed)
        conf_layout.addWidget(self._confidence_slider)

        self._confidence_label = QLabel("0.70")
        self._confidence_label.setFixedWidth(40)
        conf_layout.addWidget(self._confidence_label)
        layout.addLayout(conf_layout)

        # Smoothing frames
        smooth_layout = QHBoxLayout()
        smooth_layout.addWidget(QLabel("Smoothing Frames:"))

        self._smoothing_spin = QSpinBox()
        self._smoothing_spin.setRange(1, 15)
        self._smoothing_spin.setValue(5)
        self._smoothing_spin.valueChanged.connect(self._on_smoothing_changed)
        smooth_layout.addWidget(self._smoothing_spin)

        smooth_layout.addStretch()
        layout.addLayout(smooth_layout)

        # FPS overlay
        self._fps_check = QCheckBox("Show FPS overlay")
        self._fps_check.stateChanged.connect(self._on_fps_changed)
        layout.addWidget(self._fps_check)

        # Performance HUD
        self._hud_check = QCheckBox("Show Performance HUD (Ctrl+Shift+D)")
        self._hud_check.stateChanged.connect(self._on_hud_toggled)
        layout.addWidget(self._hud_check)

        return card

    def _create_interaction_section(self) -> QWidget:
        card = Card()
        layout = card.layout()

        title = QLabel("Interaction")
        title.setProperty("class", "title")
        layout.addWidget(title)

        # Hand dwell
        self._dwell_check = QCheckBox("Enable hand dwell (hover to click)")
        self._dwell_check.stateChanged.connect(self._on_dwell_changed)
        layout.addWidget(self._dwell_check)

        # Dwell duration
        dwell_layout = QHBoxLayout()
        dwell_layout.addWidget(QLabel("Dwell Duration:"))

        self._dwell_slider = QSlider(Qt.Horizontal)
        self._dwell_slider.setRange(1000, 5000)
        self._dwell_slider.setSingleStep(500)
        self._dwell_slider.setValue(2000)
        self._dwell_slider.valueChanged.connect(self._on_dwell_duration_changed)
        dwell_layout.addWidget(self._dwell_slider)

        self._dwell_label = QLabel("2.0s")
        self._dwell_label.setFixedWidth(40)
        dwell_layout.addWidget(self._dwell_label)
        layout.addLayout(dwell_layout)

        return card

    def _create_language_section(self) -> QWidget:
        card = Card()
        layout = card.layout()

        title = QLabel("Language Pack")
        title.setProperty("class", "title")
        layout.addWidget(title)

        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("Sign Language:"))

        self._language_combo = QComboBox()
        self._refresh_languages()
        self._language_combo.currentIndexChanged.connect(self._on_language_changed)
        lang_layout.addWidget(self._language_combo)
        lang_layout.addStretch()
        layout.addLayout(lang_layout)

        return card

    def _create_privacy_section(self) -> QWidget:
        card = Card()
        layout = card.layout()

        title = QLabel("Privacy & Data")
        title.setProperty("class", "title")
        layout.addWidget(title)

        info = QLabel(
            "All data is stored locally on your device. "
            "No data is sent to any server. "
            "In compliance with the Philippines Data Privacy Act of 2012 (RA 10173)."
        )
        info.setProperty("class", "body-small")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Export data
        self._export_btn = QPushButton("Export My Data")
        self._export_btn.setProperty("class", "secondary")
        self._export_btn.clicked.connect(self._export_data)
        layout.addWidget(self._export_btn)

        # Delete data
        self._delete_btn = QPushButton("Delete All My Data")
        self._delete_btn.setProperty("class", "danger")
        self._delete_btn.clicked.connect(self._confirm_delete_data)
        layout.addWidget(self._delete_btn)

        return card

    def _create_about_section(self) -> QWidget:
        card = Card()
        layout = card.layout()

        title = QLabel("About")
        title.setProperty("class", "title")
        layout.addWidget(title)

        version = QLabel("Sign Language Learning App v1.0.0")
        version.setProperty("class", "body")
        layout.addWidget(version)

        credits = QLabel(
            "Built with Python, OpenCV, MediaPipe, PySide6, scikit-learn.\n"
            "Hand tracking by MediaPipe (Google).\n"
            "ASL content based on standard fingerspelling charts."
        )
        credits.setProperty("class", "caption")
        credits.setWordWrap(True)
        layout.addWidget(credits)

        return card

    def _refresh_cameras(self):
        self._camera_combo.clear()
        cameras = self._pipeline.get_camera_devices()
        if not cameras:
            self._camera_combo.addItem("No camera found", "")
            self._camera_combo.setEnabled(False)
            return

        self._camera_combo.setEnabled(True)
        for camera in cameras:
            suffix = " (virtual)" if camera.is_virtual else ""
            self._camera_combo.addItem(f"{camera.name}{suffix}", camera.device_id)

        # Restore saved setting
        if self._settings:
            index = self._camera_combo.findData(self._settings.camera_device_id)
            if index >= 0:
                self._camera_combo.setCurrentIndex(index)

    def _refresh_languages(self):
        self._language_combo.clear()
        packs = self._content_loader._packs
        for pack_id, pack in packs.items():
            self._language_combo.addItem(pack.name, pack_id)

        if self._settings:
            index = self._language_combo.findData(self._settings.language_pack)
            if index >= 0:
                self._language_combo.setCurrentIndex(index)

    def on_show(self):
        if self._user:
            self._settings = SettingsRepository.get(self._user.id)
            self._load_settings()

    def set_user(self, user):
        self._user = user
        self._settings = SettingsRepository.get(user.id)
        self._load_settings()

    def _load_settings(self):
        if not self._settings:
            return

        self._mirror_check.setChecked(self._settings.mirror_camera)
        self._fps_check.setChecked(self._settings.show_fps)
        self._dwell_check.setChecked(self._settings.hand_dwell_enabled)

        self._text_size_slider.setValue(self._settings.text_size)
        self._text_size_label.setText(f"{self._settings.text_size}px")

        self._confidence_slider.setValue(int(self._settings.confidence_threshold * 100))
        self._confidence_label.setText(f"{self._settings.confidence_threshold:.2f}")

        self._smoothing_spin.setValue(self._settings.smoothing_frames)

        self._dwell_slider.setValue(self._settings.dwell_duration_ms)
        self._dwell_label.setText(f"{self._settings.dwell_duration_ms / 1000:.1f}s")

        # Theme
        theme_map = {"dark": 0, "light": 1, "system": 2}
        self._theme_combo.setCurrentIndex(theme_map.get(self._settings.theme, 0))

    def _on_camera_changed(self, index):
        if not self._settings:
            return
        cam_id = self._camera_combo.currentData()
        self._settings.camera_device_id = cam_id
        SettingsRepository.update(self._settings)
        self.camera_service.set_active_device(cam_id)

    def _on_mirror_changed(self, state):
        if not self._settings:
            return
        self._settings.mirror_camera = state == Qt.Checked
        SettingsRepository.update(self._settings)
        self.camera_service.set_mirror(self._settings.mirror_camera)

    def _on_theme_changed(self, index):
        theme_map = {0: "dark", 1: "light", 2: "system"}
        theme = theme_map.get(index, "dark")

        if theme == "system":
            # Detect system theme - simplified
            theme = "dark"

        theme_manager.mode = ThemeMode(theme)
        self._main_window.setStyleSheet(theme_manager.stylesheet())

        if self._settings:
            self._settings.theme = theme
            SettingsRepository.update(self._settings)

    def _on_text_size_changed(self, value):
        self._text_size_label.setText(f"{value}px")
        if self._settings:
            self._settings.text_size = value
            SettingsRepository.update(self._settings)
        # Apply font size globally
        self._main_window.setStyleSheet(theme_manager.stylesheet())

    def _on_confidence_changed(self, value):
        threshold = value / 100.0
        self._confidence_label.setText(f"{threshold:.2f}")
        if self._settings:
            self._settings.confidence_threshold = threshold
            SettingsRepository.update(self._settings)
        self._pipeline.set_confidence_threshold(threshold)

    def _on_smoothing_changed(self, value):
        if self._settings:
            self._settings.smoothing_frames = value
            SettingsRepository.update(self._settings)
        self._pipeline.set_smoothing_window(value)

    def _on_fps_changed(self, state):
        if self._settings:
            self._settings.show_fps = state == Qt.Checked
            SettingsRepository.update(self._settings)
        # FPS display handled in camera view

    def _on_hud_toggled(self, state):
        enabled = state == Qt.Checked
        if self._settings:
            self._settings.show_perf_hud = enabled
            SettingsRepository.update(self._settings)
        # Toggle HUD via manager
        from app.ui.widgets import PerfHUDManager
        if enabled:
            PerfHUDManager.get_instance(self).show_hud()
        else:
            PerfHUDManager.get_instance(self).hide_hud()

    def _on_dwell_changed(self, state):
        enabled = state == Qt.Checked
        if self._settings:
            self._settings.hand_dwell_enabled = enabled
            SettingsRepository.update(self._settings)
        self._pipeline.set_dwell_enabled(enabled)

    def _on_dwell_duration_changed(self, value):
        self._dwell_label.setText(f"{value / 1000:.1f}s")
        if self._settings:
            self._settings.dwell_duration_ms = value
            SettingsRepository.update(self._settings)
        self._pipeline.set_dwell_duration(value)

    def _on_language_changed(self, index):
        pack_id = self._language_combo.currentData()
        if self._content_loader.set_current_pack(pack_id):
            if self._settings:
                self._settings.language_pack = pack_id
                SettingsRepository.update(self._settings)
            # Sync new pack to database
            pack = self._content_loader.get_current_pack()
            if pack:
                self._content_loader.sync_to_database(pack)
            QMessageBox.information(self, "Language Changed",
                "Language pack changed. Please restart the app to fully apply.")

    def _export_data(self):
        if not self._user:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Data", f"sign_language_data_{self._user.name}.json", "JSON Files (*.json)"
        )
        if not path:
            return

        try:
            data = export_user_data(self._user.id)
            import json
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
            QMessageBox.information(self, "Export Complete", f"Data exported to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def _confirm_delete_data(self):
        if not self._user:
            return

        reply = QMessageBox.warning(
            self, "Delete All Data",
            "This will permanently delete ALL your data including:\n"
            "• Profile\n• Progress history\n• Practice attempts\n• Quiz results\n• Badges\n\n"
            "This action CANNOT be undone. Are you sure?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Double confirmation
            reply2 = QMessageBox.question(
                self, "Final Confirmation",
                "Type 'DELETE' to confirm:",
                QMessageBox.Yes | QMessageBox.No
            )
            # Simplified - in reality would show input dialog
            if reply2 == QMessageBox.Yes:
                delete_user_data(self._user.id)
                QMessageBox.information(self, "Data Deleted", "All your data has been deleted.")
                # Go back to welcome screen
                self._main_window._show_screen("welcome")

    def go_back(self):
        self._main_window._show_screen("home")
