"""
Lesson/Practice screen - core learning interface.
Split layout: camera view with skeleton overlay + reference panel.
"""

from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation, QEasingCurve, QRect, QPoint
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QStackedWidget, QSizePolicy, QProgressBar
)
from PySide6.QtGui import QFont, QPixmap, QPainter, QColor, QPen, QBrush
import numpy as np
import logging

from app.ui.main_window import ScreenBase
from app.ui.widgets import CameraView, StatusBanner, DwellButton, ConfidenceMeter, Chip, ProgressRing
from app.ui.theme import theme_manager
from app.data.db import Module, Sign, ModuleRepository, SignRepository, ModuleCategory, Difficulty
from app.content.loader import ContentPackLoader
from app.core.pipeline import PipelineResult

logger = logging.getLogger(__name__)


class ReferenceAnimation(QWidget):
    """
    Animated reference skeleton for target sign.
    Cycles through key frames or shows static pose.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._landmarks: np.ndarray = None  # (21, 3) normalized
        self._frame_index = 0
        self._animation_timer = QTimer()
        self._animation_timer.timeout.connect(self._next_frame)
        self._animation_timer.setInterval(1000)  # 1 FPS for static poses
        self.setMinimumSize(200, 200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_landmarks(self, landmarks: np.ndarray):
        """Set reference landmarks (static pose)."""
        self._landmarks = landmarks
        self._frame_index = 0
        self._animation_timer.stop()
        self.update()

    def set_animation_frames(self, frames: list):
        """Set animation frames (list of landmark arrays)."""
        self._animation_frames = frames
        self._frame_index = 0
        if len(frames) > 1:
            self._animation_timer.start()
        else:
            self._animation_timer.stop()
        self.update()

    def _next_frame(self):
        if hasattr(self, '_animation_frames') and self._animation_frames:
            self._frame_index = (self._frame_index + 1) % len(self._animation_frames)
            self.update()

    def paintEvent(self, event):
        if self._landmarks is None and not hasattr(self, '_animation_frames'):
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        palette = theme_manager.palette()

        # Determine which landmarks to draw
        landmarks = self._landmarks
        if hasattr(self, '_animation_frames') and self._animation_frames:
            landmarks = self._animation_frames[self._frame_index]

        if landmarks is None:
            return

        w, h = self.width(), self.height()
        coords = landmarks.copy()
        coords[:, 0] *= w
        coords[:, 1] *= h

        connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),
            (0, 5), (5, 6), (6, 7), (7, 8),
            (0, 9), (9, 10), (10, 11), (11, 12),
            (0, 13), (13, 14), (14, 15), (15, 16),
            (0, 17), (17, 18), (18, 19), (19, 20),
            (5, 9), (9, 13), (13, 17)
        ]

        # Draw connections
        pen = QPen(QColor(palette.skeleton_connections))
        pen.setWidth(3)
        painter.setPen(pen)

        for start, end in connections:
            if start < len(coords) and end < len(coords):
                p1 = QPoint(int(coords[start, 0]), int(coords[start, 1]))
                p2 = QPoint(int(coords[end, 0]), int(coords[end, 1]))
                painter.drawLine(p1, p2)

        # Draw landmarks
        for i in range(21):
            if i < len(coords):
                painter.setBrush(QBrush(QColor(palette.accent)))
                painter.setPen(QPen(QColor(palette.text_on_accent), 2))
                center = QPoint(int(coords[i, 0]), int(coords[i, 1]))
                painter.drawEllipse(center, 8, 8)

        # Label
        painter.setPen(QColor(palette.text_secondary))
        painter.setFont(QFont("Helvetica Neue", 10))
        painter.drawText(10, 20, "Reference")


class LessonScreen(ScreenBase):
    """
    Main lesson/practice screen.
    Left: Camera view with skeleton overlay and feedback
    Right: Target sign reference, description, progress
    """

    def __init__(self, main_window, pipeline, content_loader, camera_service):
        super().__init__(main_window)
        self._pipeline = pipeline
        self._content_loader = content_loader
        self.camera_service = camera_service
        self._current_module: Module = None
        self._current_sign_index = 0
        self._signs: list = []
        self._attempt_count = 0
        self._success_count = 0
        self._hold_start_time = 0
        self._required_hold_ms = 800  # Hold steady for 800ms

        self._setup_ui()
        self._connect_pipeline()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Left panel: Camera view (70%)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 8, 16)
        left_layout.setSpacing(12)

        # Status banner - will overlay on camera view
        self._status_banner = StatusBanner()
        self._status_banner.setText("Loading lesson...")
        self._status_banner.setProperty("state", "info")
        left_layout.addWidget(self._status_banner)

        # Camera view - with rounded 16:9 container (L5)
        self._camera_view = CameraView()
        self._camera_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._camera_view.setMinimumSize(640, 360)  # 16:9 minimum
        self._camera_view.setProperty("class", "preview")
        self._camera_view.setProperty("state", "good")
        left_layout.addWidget(self._camera_view, 1)

        # Confidence meter (L4 - improved)
        self._confidence_meter = ConfidenceMeter()
        left_layout.addWidget(self._confidence_meter)

        main_layout.addWidget(left_panel, 7)

        # Right panel: Reference (30%)
        right_panel = QWidget()
        right_panel.setFixedWidth(360)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 16, 16, 16)
        right_layout.setSpacing(16)

        # Target letter display - large glyph (L3)
        self._target_label = QLabel("—")
        self._target_label.setProperty("class", "heading")
        self._target_label.setAlignment(Qt.AlignCenter)
        self._target_label.setStyleSheet("font-size: 96px; font-weight: 700;")
        self._target_label.setMinimumHeight(120)
        right_layout.addWidget(self._target_label)

        # Reference animation
        self._reference_animation = ReferenceAnimation()
        self._reference_animation.setMinimumHeight(280)
        right_layout.addWidget(self._reference_animation, 1)

        # Description
        self._description = QLabel("")
        self._description.setProperty("class", "body")
        self._description.setWordWrap(True)
        self._description.setAlignment(Qt.AlignTop)
        right_layout.addWidget(self._description)

        # Tips
        self._tips_label = QLabel("")
        self._tips_label.setProperty("class", "body-small")
        self._tips_label.setWordWrap(True)
        self._tips_label.setStyleSheet("color: #A1A1AA;")
        self._tips_label.hide()
        right_layout.addWidget(self._tips_label)

        # Attempt counter
        self._attempt_label = QLabel("Attempts: 0")
        self._attempt_label.setProperty("class", "caption")
        self._attempt_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self._attempt_label)

        # Progress dots
        self._progress_container = QWidget()
        self._progress_layout = QHBoxLayout(self._progress_container)
        self._progress_layout.setContentsMargins(0, 0, 0, 0)
        self._progress_layout.setSpacing(8)
        self._progress_layout.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self._progress_container)

        # Navigation buttons (L2 - single Next button in right panel)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self._back_btn = QPushButton("← Back")
        self._back_btn.setProperty("class", "secondary")
        self._back_btn.clicked.connect(self._go_previous)
        btn_layout.addWidget(self._back_btn)

        self._skip_btn = QPushButton("Skip")
        self._skip_btn.setProperty("class", "ghost")
        self._skip_btn.clicked.connect(self._go_next)
        btn_layout.addWidget(self._skip_btn)

        self._next_btn = QPushButton("Next →")
        self._next_btn.setProperty("class", "primary")
        self._next_btn.clicked.connect(self._go_next)
        self._next_btn.setEnabled(False)
        btn_layout.addWidget(self._next_btn)

        right_layout.addLayout(btn_layout)

        main_layout.addWidget(right_panel, 3)

    def _connect_pipeline(self):
        self._pipeline.result_ready.connect(self._on_pipeline_result)
        self._pipeline.error_occurred.connect(self._on_camera_error)
        self._pipeline.camera_status_changed.connect(self._on_camera_status)

    def _on_camera_error(self, message: str):
        self._status_banner.setText(f"Camera unavailable: {message}. Check Settings and try again.")
        self._status_banner.setProperty("state", "error")

    def _on_camera_status(self, running: bool, message: str):
        if "still image" in message:
            self._status_banner.setText(message)
            self._status_banner.setProperty("state", "warning")
        elif not running:
            self._status_banner.setText(message)
            self._status_banner.setProperty("state", "warning")

    def prepare(self, module_id: str = None, sign_index: int = 0):
        """Prepare lesson for a specific module."""
        # Hide nav bar during lesson (L6)
        self._main_window.hide_nav_bar()
        
        self._current_module = ModuleRepository.get_by_id(module_id)
        if not self._current_module:
            logger.error(f"Module not found: {module_id}")
            return

        # Get signs for this module
        pack = self._content_loader.get_current_pack()
        self._signs = []
        for sign_id in self._current_module.sign_ids:
            sign = SignRepository.get_by_id(sign_id)
            if sign:
                self._signs.append(sign)

        self._current_sign_index = max(0, min(sign_index, len(self._signs) - 1))
        self._attempt_count = 0
        self._success_count = 0

        self._build_progress_dots()
        self._load_current_sign()
        if not self._pipeline.model_available:
            self._status_banner.setText("Model not trained — Watch & Learn mode. Collect samples and train to score practice.")
            self._status_banner.setProperty("state", "warning")
        self._pipeline.start()

    def _load_current_sign(self):
        """Load the current target sign."""
        if not self._signs or self._current_sign_index >= len(self._signs):
            return

        sign = self._signs[self._current_sign_index]

        # Update UI
        self._target_label.setText(sign.label)

        # Check if motion sign (not scored)
        is_motion = sign.metadata.get("motion_sign", False) if sign.metadata else False
        if is_motion:
            self._target_label.setText(f"{sign.label}")
            self._status_banner.setText(f"Watch & Learn: {sign.label} (motion sign)")
            self._status_banner.setProperty("state", "info")
            self._next_btn.setEnabled(True)
        else:
            self._status_banner.setText(f"Show me: {sign.label}")
            self._status_banner.setProperty("state", "info")
            self._next_btn.setEnabled(False)

        self._description.setText(sign.description or "No description available.")
        
        # Add tips (L3)
        tips = self._get_tips_for_sign(sign)
        if tips:
            self._tips_label.setText(f"💡 {tips}")
            self._tips_label.show()
        else:
            self._tips_label.hide()

        self._attempt_label.setText(f"Attempts: {self._attempt_count}")

        # Set reference landmarks if available
        if sign.reference_landmarks:
            landmarks = np.array(sign.reference_landmarks, dtype=np.float32).reshape(21, 3)
            self._reference_animation.set_landmarks(landmarks)
            self._pipeline.set_target_sign(sign.id, landmarks)
        else:
            self._pipeline.set_target_sign(sign.id, None)

        self._update_progress_dots()

    def _get_tips_for_sign(self, sign: Sign) -> str:
        """Get tips for a specific sign."""
        tips_map = {
            "A": "Make a tight fist with thumb resting against the side of the index finger.",
            "B": "Hold fingers together and straight up, thumb tucked across palm.",
            "C": "Curve fingers and thumb into a C shape.",
            "D": "Index finger up, other fingers curled, thumb touching middle finger.",
            "E": "Fingers curled down, thumb tucked under fingertips.",
            "F": "Index finger and thumb touching in a circle, other fingers up and spread.",
            "G": "Index finger and thumb extended sideways, other fingers curled.",
            "H": "Index and middle fingers extended sideways, thumb tucked.",
            "I": "Pinky finger up, other fingers curled, thumb tucked.",
            "K": "Index and middle fingers up in V, thumb between them.",
            "L": "Index finger and thumb extended in L shape, other fingers curled.",
            "M": "Thumb tucked under first three fingers.",
            "N": "Thumb tucked under first two fingers.",
            "O": "Fingers curved to touch thumb in O shape.",
            "P": "Like K but palm facing down, thumb between index and middle.",
            "Q": "Like G but palm facing down.",
            "R": "Index and middle fingers crossed, others curled.",
            "S": "Fist with thumb over fingers.",
            "T": "Thumb tucked between index and middle fingers, fist.",
            "U": "Index and middle fingers up together, others curled.",
            "V": "Index and middle fingers in V shape.",
            "W": "Index, middle, ring fingers up in W shape.",
            "X": "Index finger hooked, others curled.",
            "Y": "Thumb and pinky extended, other fingers curled.",
            "0": "Fingers curved to form O shape (same as O).",
            "1": "Index finger up, others curled.",
            "2": "Index and middle fingers up.",
            "3": "Thumb, index, middle up (like 3).",
            "4": "Four fingers up, thumb tucked.",
            "5": "All five fingers spread.",
            "6": "Pinky, ring, middle up; index and thumb touching.",
            "7": "Ring, middle, index up; pinky and thumb touching.",
            "8": "Middle, index, thumb up; pinky and ring curled.",
            "9": "Index up, thumb and pinky touching, others curled.",
        }
        return tips_map.get(sign.label, "")

    def _build_progress_dots(self):
        """Build progress indicator dots."""
        self._clear_layout(self._progress_layout)
        self._progress_dots = []

        for i, sign in enumerate(self._signs):
            dot = QFrame()
            dot.setFixedSize(12, 12)
            dot.setProperty("class", "card")
            self._progress_layout.addWidget(dot)
            self._progress_dots.append(dot)

    def _update_progress_dots(self):
        for i, dot in enumerate(self._progress_dots):
            if i < self._current_sign_index:
                dot.setStyleSheet("background-color: #4ADE80; border-radius: 6px;")
            elif i == self._current_sign_index:
                dot.setStyleSheet("background-color: #22D3EE; border-radius: 6px;")
            else:
                dot.setStyleSheet("background-color: #3F3F46; border-radius: 6px;")

    def _on_pipeline_result(self, result: PipelineResult):
        """Handle pipeline result."""
        # Update camera view with frame (no overlay)
        if result.frame is not None:
            self._camera_view.set_frame(result.frame)
        
        # Update camera view with hands for skeleton overlay
        if result.hands:
            self._camera_view.set_hands(result.hands, result.target_landmarks)
        else:
            self._camera_view.set_hands([])

        # Update confidence meter (L4 - improved display)
        label, confidence = result.confidence_meter
        is_stable = result.smoothed.is_stable if result.smoothed else False
        
        # When no hand detected, show waiting state
        if not result.hands:
            self._confidence_meter.set_values("Waiting for hand...", 0.0, False)
        elif label == "unknown" or confidence < 0.1:
            self._confidence_meter.set_values("Show your hand", 0.0, False)
        else:
            self._confidence_meter.set_values(f"Detected: {label}", confidence, is_stable)

        # Check for successful match
        current_sign = self._signs[self._current_sign_index] if self._signs else None
        if current_sign and not current_sign.metadata.get("motion_sign", False):
            self._check_match(result, current_sign)

    def _check_match(self, result: PipelineResult, target_sign: Sign):
        """Check if user's sign matches target."""
        if result.recognition and result.recognition.is_reliable:
            predicted = result.recognition.label
            target = target_sign.id.replace("asl_", "").upper()

            # Map sign ID to label
            target_label = target_sign.label

            if predicted.upper() == target_label.upper():
                # Correct!
                self._hold_start_time = getattr(self, '_hold_start_time', 0)
                import time
                now = time.time() * 1000

                if self._hold_start_time == 0:
                    self._hold_start_time = now
                    self._status_banner.setText("Hold steady...")
                    self._status_banner.setProperty("state", "warning")
                elif now - self._hold_start_time >= self._required_hold_ms:
                    self._on_success(target_sign)
            else:
                # Incorrect - give specific feedback
                self._hold_start_time = 0
                self._give_feedback(predicted, target_label, result.recognition.all_scores)
        else:
            self._hold_start_time = 0
            if result.hands:
                self._status_banner.setText("Show me the sign...")
                self._status_banner.setProperty("state", "info")
            else:
                self._status_banner.setText("No hand detected - show your hand to camera")
                self._status_banner.setProperty("state", "warning")

    def _give_feedback(self, predicted: str, target: str, all_scores: dict):
        """Give specific constructive feedback."""
        self._attempt_count += 1
        self._attempt_label.setText(f"Attempts: {self._attempt_count}")

        # Find common confusions
        feedback_map = {
            ("M", "N"): "M vs N: Tuck thumb under 3 fingers for M, 2 for N",
            ("N", "M"): "N vs M: Tuck thumb under 2 fingers for N, 3 for M",
            ("U", "V"): "U vs V: Keep fingers together for U, spread for V",
            ("V", "U"): "V vs U: Spread index/middle for V, keep together for U",
            ("A", "S"): "A vs S: Thumb on side for A, thumb over fingers for S",
            ("S", "A"): "S vs A: Thumb over fingers for S, thumb on side for A",
            ("K", "P"): "K vs P: Palm facing you for K, palm down for P",
            ("P", "K"): "P vs K: Palm down for P, palm facing you for K",
            ("G", "Q"): "G vs Q: Palm sideways for G, palm down for Q",
            ("Q", "G"): "Q vs G: Palm down for Q, palm sideways for G",
        }

        key = (predicted.upper(), target.upper())
        if key in feedback_map:
            msg = feedback_map[key]
        else:
            msg = f"Detected: {predicted} — Target: {target}"

        self._status_banner.setText(msg)
        self._status_banner.setProperty("state", "error")

    def _on_success(self, sign: Sign):
        """Handle successful sign recognition."""
        self._hold_start_time = 0
        self._success_count += 1

        self._status_banner.setText(f"✓ Great! That's {sign.label}!")
        self._status_banner.setProperty("state", "success")

        # Enable next
        self._next_btn.setEnabled(True)
        self._dwell_next.setEnabled(True)

        # Record attempt
        from app.data.db import AttemptRepository, PracticeAttempt, AttemptResult
        from datetime import datetime

        attempt = PracticeAttempt(
            id=0,
            user_id=self._main_window.get_current_user().id,
            sign_id=sign.id,
            module_id=self._current_module.id,
            result=AttemptResult.CORRECT,
            confidence=1.0,
            predicted_label=sign.label,
            target_label=sign.label,
            duration_ms=0,
            timestamp=datetime.now()
        )
        AttemptRepository.record(attempt)

        # Brief celebration animation
        self._celebrate()

    def _celebrate(self):
        """Show brief celebration."""
        # Flash the target label green
        original_style = self._target_label.styleSheet()
        self._target_label.setStyleSheet("color: #4ADE80; font-size: 72px; font-weight: 700;")

        QTimer.singleShot(500, lambda: self._target_label.setStyleSheet(original_style))

    def _go_next(self):
        if self._current_sign_index < len(self._signs) - 1:
            self._current_sign_index += 1
            self._load_current_sign()
        else:
            # Module complete
            self._complete_module()

    def _go_previous(self):
        if self._current_sign_index > 0:
            self._current_sign_index -= 1
            self._load_current_sign()

    def _complete_module(self):
        """Mark module as complete and update progress."""
        from app.data.db import ProgressRepository, UserProgress
        from datetime import datetime

        user = self._main_window.get_current_user()
        progress = ProgressRepository.get_progress(user.id, self._current_module.id)

        if not progress:
            progress = UserProgress(
                user_id=user.id,
                module_id=self._current_module.id,
                completed=True,
                completed_at=datetime.now(),
                accuracy=1.0,
                attempts=self._attempt_count,
                best_streak=self._success_count,
                current_streak=self._success_count,
                last_practiced_at=datetime.now()
            )
        else:
            progress.completed = True
            progress.completed_at = datetime.now()
            progress.attempts += self._attempt_count
            progress.last_practiced_at = datetime.now()

        ProgressRepository.update_progress(progress)

        # Check for badges
        self._check_badges()

        # Go back to home
        self._main_window._show_screen("home")

    def _check_badges(self):
        """Check and award badges."""
        from app.data.db import BadgeRepository
        user = self._main_window.get_current_user()

        # First completion badge
        all_progress = ProgressRepository.get_all_progress(user.id)
        completed = sum(1 for p in all_progress if p.completed)
        if completed == 1:
            BadgeRepository.award_badge(user.id, "first_letter")

    def _on_dwell_next(self):
        """Handle dwell activation on Next button."""
        if self._next_btn.isEnabled():
            self._go_next()

    def on_show(self):
        pass

    def go_back(self):
        # Show nav bar when leaving lesson (L6)
        self._main_window.show_nav_bar()
        self._pipeline.stop()
        self._pipeline.clear_target()
        self._main_window._show_screen("home")

    def space_action(self):
        if self._next_btn.isEnabled():
            self._go_next()

    def navigate_relative(self, delta: int):
        if delta > 0:
            self._go_next()
        else:
            self._go_previous()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
