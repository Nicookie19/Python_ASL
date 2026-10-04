"""
Custom UI widgets for the Sign Language Learning Application.
"""

from PySide6.QtCore import Qt, Signal, QRect, QPoint, QTimer, QPropertyAnimation, QEasingCurve, QSize, Property
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPixmap, QImage, QLinearGradient
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QProgressBar, QFrame, QSizePolicy, QGraphicsOpacityEffect
)
import numpy as np
import cv2

from app.ui.theme import theme_manager, ThemeMode


class CameraView(QWidget):
    """
    Widget for displaying camera feed with optional overlays.
    Handles mirrored display, aspect ratio preservation, and overlay rendering.
    Supports drawing hand skeleton overlay via QPainter from normalized landmarks.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._frame: np.ndarray = None
        self._mirror = False
        self._aspect_ratio = 4/3
        self._status_text = ""
        self._status_state = "info"
        self._show_fps = False
        self._fps = 0.0
        
        # Skeleton overlay data
        self._hands = []
        self._target_landmarks = None
        self._connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),
            (0, 5), (5, 6), (6, 7), (7, 8),
            (0, 9), (9, 10), (10, 11), (11, 12),
            (0, 13), (13, 14), (14, 15), (15, 16),
            (0, 17), (17, 18), (18, 19), (19, 20),
            (5, 9), (9, 13), (13, 17)
        ]

        self.setMinimumSize(640, 480)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("background-color: #000000; border-radius: 16px;")

    def set_frame(self, frame: np.ndarray) -> None:
        """Set the camera frame (BGR numpy array)."""
        self._frame = frame
        self.update()

    def set_hands(self, hands, target_landmarks=None) -> None:
        """Set hand landmarks for skeleton overlay."""
        self._hands = hands
        self._target_landmarks = target_landmarks
        self.update()

    def set_mirror(self, mirror: bool) -> None:
        self._mirror = mirror

    def set_status(self, text: str, state: str = "info") -> None:
        """Set status banner text and state."""
        self._status_text = text
        self._status_state = state
        self.update()

    def set_fps(self, fps: float, show: bool = True) -> None:
        self._fps = fps
        self._show_fps = show
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Fill background
        painter.fillRect(self.rect(), QColor(0, 0, 0))

        if self._frame is not None:
            self._draw_frame(painter)

        # Draw skeleton overlay
        if self._hands:
            self._draw_skeleton(painter)

        # Draw status banner
        if self._status_text:
            self._draw_status_banner(painter)

        # Draw FPS
        if self._show_fps and self._fps > 0:
            self._draw_fps(painter)

    def _draw_frame(self, painter: QPainter) -> None:
        """Draw the camera frame preserving aspect ratio."""
        h, w = self._frame.shape[:2]
        widget_rect = self.rect()

        # Calculate scaled size preserving aspect ratio
        scale_w = widget_rect.width() / w
        scale_h = widget_rect.height() / h
        scale = min(scale_w, scale_h)

        draw_w = int(w * scale)
        draw_h = int(h * scale)

        # Center in widget
        x = (widget_rect.width() - draw_w) // 2
        y = (widget_rect.height() - draw_h) // 2

        # Convert BGR to RGB for QImage
        if self._mirror:
            frame = cv2.flip(self._frame, 1)
        else:
            frame = self._frame

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg.copy())

        painter.drawPixmap(x, y, draw_w, draw_h, pixmap)

    def _draw_skeleton(self, painter: QPainter) -> None:
        """Draw hand skeleton overlay using QPainter from normalized landmarks."""
        if not self._hands:
            return

        palette = theme_manager.palette()
        widget_rect = self.rect()
        
        # Get the frame dimensions and position to map normalized coords
        if self._frame is None:
            return
        h, w = self._frame.shape[:2]
        widget_rect = self.rect()
        
        scale_w = widget_rect.width() / w
        scale_h = widget_rect.height() / h
        scale = min(scale_w, scale_h)
        
        draw_w = int(w * scale)
        draw_h = int(h * scale)
        x = (widget_rect.width() - draw_w) // 2
        y = (widget_rect.height() - draw_h) // 2
        
        # For mirror mode, the frame is flipped horizontally
        # So we need to flip the x coordinates
        flip_x = self._mirror

        for hand in self._hands:
            # Convert normalized landmarks to widget coordinates
            coords = hand.landmarks.copy()
            coords[:, 0] *= draw_w
            coords[:, 1] *= draw_h
            
            # Apply mirror flip if needed
            if flip_x:
                coords[:, 0] = draw_w - coords[:, 0]
            
            # Offset to widget position
            coords[:, 0] += x
            coords[:, 1] += y
            
            # Determine colors based on correctness
            colors = {}
            if self._target_landmarks is not None:
                target_coords = self._target_landmarks.copy()
                target_coords[:, 0] *= draw_w
                target_coords[:, 1] *= draw_h
                
                if flip_x:
                    target_coords[:, 0] = draw_w - target_coords[:, 0]
                
                target_coords[:, 0] += x
                target_coords[:, 1] += y
                
                for i in range(21):
                    if i < len(coords) and i < len(target_coords):
                        dist = np.linalg.norm(coords[i, :2] - target_coords[i, :2])
                        norm_dist = dist / max(draw_w, draw_h)
                        if norm_dist < 0.05:
                            colors[i] = QColor(palette.skeleton_correct)
                        elif norm_dist < 0.12:
                            colors[i] = QColor(palette.warning)
                        else:
                            colors[i] = QColor(palette.skeleton_incorrect)
            else:
                for i in range(21):
                    colors[i] = QColor(palette.skeleton_neutral)

            # Draw connections
            pen = QPen(QColor(palette.skeleton_connections))
            pen.setWidth(3)
            painter.setPen(pen)

            connections = [
                (0, 1), (1, 2), (2, 3), (3, 4),
                (0, 5), (5, 6), (6, 7), (7, 8),
                (0, 9), (9, 10), (10, 11), (11, 12),
                (0, 13), (13, 14), (14, 15), (15, 16),
                (0, 17), (17, 18), (18, 19), (19, 20),
                (5, 9), (9, 13), (13, 17)
            ]

            for start, end in connections:
                if start < len(coords) and end < len(coords):
                    # Average color for connection
                    c1 = colors.get(start, QColor(palette.skeleton_neutral))
                    c2 = colors.get(end, QColor(palette.skeleton_neutral))
                    avg_color = QColor(
                        (c1.red() + c2.red()) // 2,
                        (c1.green() + c2.green()) // 2,
                        (c1.blue() + c2.blue()) // 2
                    )
                    pen.setColor(avg_color)
                    painter.setPen(pen)

                    p1 = QPoint(int(coords[start, 0]), int(coords[start, 1]))
                    p2 = QPoint(int(coords[end, 0]), int(coords[end, 1]))
                    painter.drawLine(p1, p2)

            # Draw landmark points
            for i in range(21):
                if i < len(coords):
                    color = colors.get(i, QColor(palette.skeleton_neutral))
                    painter.setBrush(QBrush(color))
                    painter.setPen(QPen(QColor(0, 0, 0), 2))
                    center = QPoint(int(coords[i, 0]), int(coords[i, 1]))
                    painter.drawEllipse(center, 6, 6)

    def _draw_status_banner(self, painter: QPainter) -> None:
        """Draw status banner at top of camera view."""
        palette = theme_manager.palette()
        tokens = theme_manager.tokens()

        # Color based on state
        state_colors = {
            "info": palette.accent,
            "success": palette.success,
            "warning": palette.warning,
            "error": palette.error
        }
        bg_color = QColor(state_colors.get(self._status_state, palette.accent))
        bg_color.setAlpha(220)

        font = QFont(tokens.typography.family, tokens.typography.base, tokens.typography.medium)
        painter.setFont(font)

        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(self._status_text)
        padding = tokens.spacing.md
        banner_width = min(text_width + 2 * padding, widget_rect.width() - 2 * padding)
        banner_height = metrics.height() + 2 * (padding // 2)

        x = (widget_rect.width() - banner_width) // 2
        y = padding

        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(x, y, banner_width, banner_height, tokens.radius.md, tokens.radius.md)

        painter.setPen(QColor(palette.text_on_accent))
        painter.drawText(x, y, banner_width, banner_height, Qt.AlignCenter, self._status_text)

    def _draw_fps(self, painter: QPainter) -> None:
        """Draw FPS counter in corner."""
        palette = theme_manager.palette()
        tokens = theme_manager.tokens()

        font = QFont(tokens.typography.family, tokens.typography.xs, tokens.typography.medium)
        painter.setFont(font)
        painter.setPen(QColor(palette.text_secondary))

        fps_text = f"{self._fps:.1f} FPS"
        painter.drawText(self.rect().adjusted(tokens.spacing.md, tokens.spacing.md, -tokens.spacing.md, 0),
                        Qt.AlignRight | Qt.AlignTop, fps_text)


class SkeletonOverlay(QWidget):
    """
    Transparent overlay widget for drawing hand skeleton on top of camera view.
    Separated for performance - only redraws when landmarks change.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self._hands = []
        self._target_landmarks = None
        self._connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),
            (0, 5), (5, 6), (6, 7), (7, 8),
            (0, 9), (9, 10), (10, 11), (11, 12),
            (0, 13), (13, 14), (14, 15), (15, 16),
            (0, 17), (17, 18), (18, 19), (19, 20),
            (5, 9), (9, 13), (13, 17)
        ]

    def set_hands(self, hands, target_landmarks=None):
        self._hands = hands
        self._target_landmarks = target_landmarks
        self.update()

    def paintEvent(self, event):
        if not self._hands:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        palette = theme_manager.palette()
        w, h = self.width(), self.height()

        for hand in self._hands:
            # Convert normalized landmarks to widget coordinates
            coords = hand.landmarks.copy()
            coords[:, 0] *= w
            coords[:, 1] *= h

            # Determine colors based on correctness
            colors = {}
            if self._target_landmarks is not None:
                target_coords = self._target_landmarks.copy()
                target_coords[:, 0] *= w
                target_coords[:, 1] *= h

                for i in range(21):
                    if i < len(coords) and i < len(target_coords):
                        dist = np.linalg.norm(coords[i, :2] - target_coords[i, :2])
                        norm_dist = dist / max(w, h)
                        if norm_dist < 0.05:
                            colors[i] = QColor(palette.skeleton_correct)
                        elif norm_dist < 0.12:
                            colors[i] = QColor(palette.warning)
                        else:
                            colors[i] = QColor(palette.skeleton_incorrect)
            else:
                for i in range(21):
                    colors[i] = QColor(palette.skeleton_neutral)

            # Draw connections
            pen = QPen(QColor(palette.skeleton_connections))
            pen.setWidth(3)
            painter.setPen(pen)

            for start, end in self._connections:
                if start < len(coords) and end < len(coords):
                    # Average color for connection
                    c1 = colors.get(start, QColor(palette.skeleton_neutral))
                    c2 = colors.get(end, QColor(palette.skeleton_neutral))
                    avg_color = QColor(
                        (c1.red() + c2.red()) // 2,
                        (c1.green() + c2.green()) // 2,
                        (c1.blue() + c2.blue()) // 2
                    )
                    pen.setColor(avg_color)
                    painter.setPen(pen)

                    p1 = QPoint(int(coords[start, 0]), int(coords[start, 1]))
                    p2 = QPoint(int(coords[end, 0]), int(coords[end, 1]))
                    painter.drawLine(p1, p2)

            # Draw landmark points
            for i in range(21):
                if i < len(coords):
                    color = colors.get(i, QColor(palette.skeleton_neutral))
                    painter.setBrush(QBrush(color))
                    painter.setPen(QPen(QColor(0, 0, 0), 2))
                    center = QPoint(int(coords[i, 0]), int(coords[i, 1]))
                    painter.drawEllipse(center, 6, 6)


class DwellButton(QPushButton):
    """
    Button that supports hand-dwell activation (hover for 2 seconds).
    Shows a circular progress ring during dwell.
    """

    dwell_activated = Signal()

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCheckable(False)
        self._progress = 0.0
        self._is_dwelling = False
        self._dwell_duration = 2000  # ms
        self._ring_thickness = 4
        self._cursor_pos = None

        # Animation for progress ring
        self._progress_animation = QPropertyAnimation(self, b"progress")
        self._progress_animation.setDuration(self._dwell_duration)
        self._progress_animation.setEasingCurve(QEasingCurve.Linear)
        self._progress_animation.finished.connect(self._on_dwell_complete)

    def _on_dwell_complete(self):
        self._progress = 0.0
        self._is_dwelling = False
        self.dwell_activated.emit()
        self.update()

    def start_dwell(self, cursor_pos: QPoint):
        """Start dwell timer at cursor position."""
        if self._is_dwelling:
            return
        self._is_dwelling = True
        self._cursor_pos = cursor_pos
        self._progress_animation.start()
        self.update()

    def cancel_dwell(self):
        """Cancel dwell timer."""
        self._progress_animation.stop()
        self._progress = 0.0
        self._is_dwelling = False
        self._cursor_pos = None
        self.update()

    def set_progress(self, progress: float):
        self._progress = progress
        self.update()

    def get_progress(self) -> float:
        return self._progress

    progress = Property(float, get_progress, set_progress)

    def set_dwell_duration(self, ms: int):
        self._dwell_duration = ms
        self._progress_animation.setDuration(ms)

    def paintEvent(self, event):
        super().paintEvent(event)

        if self._is_dwelling and self._cursor_pos:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)

            palette = theme_manager.palette()

            # Draw progress ring around cursor
            center = self._cursor_pos
            radius = 24

            # Background ring
            bg_pen = QPen(QColor(palette.dwell_ring_bg))
            bg_pen.setWidth(self._ring_thickness)
            painter.setPen(bg_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(center, radius, radius)

            # Progress ring
            if self._progress > 0:
                progress_pen = QPen(QColor(palette.dwell_ring_fill))
                progress_pen.setWidth(self._ring_thickness)
                progress_pen.setCapStyle(Qt.RoundCap)
                painter.setPen(progress_pen)

                # Draw arc from -90 degrees (top) clockwise
                span_angle = int(-self._progress * 360 * 16)  # 1/16 degree units
                painter.drawArc(
                    center.x() - radius, center.y() - radius,
                    radius * 2, radius * 2,
                    90 * 16,  # Start at top (90 degrees * 16)
                    span_angle
                )


class ConfidenceMeter(QWidget):
    """
    Visual confidence meter showing recognition confidence.
    Horizontal bar with color gradient and label.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._label = "unknown"
        self._confidence = 0.0
        self._is_stable = False
        self.setMinimumHeight(40)
        self.setMinimumWidth(200)

    def set_values(self, label: str, confidence: float, is_stable: bool):
        self._label = label
        self._confidence = confidence
        self._is_stable = is_stable
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        palette = theme_manager.palette()
        tokens = theme_manager.tokens()

        rect = self.rect()
        margin = tokens.spacing.sm
        bar_rect = rect.adjusted(margin, margin, -margin, -margin)

        # Background track
        track_rect = QRect(bar_rect.left(), bar_rect.center().y() - 6, bar_rect.width(), 12)
        painter.setBrush(QColor(palette.surface_variant))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(track_rect, 6, 6)

        # Confidence fill
        if self._confidence > 0:
            fill_width = int(track_rect.width() * self._confidence)
            fill_rect = QRect(track_rect.left(), track_rect.top(), fill_width, track_rect.height())

            # Color based on confidence level
            if self._confidence >= 0.8:
                color = QColor(palette.success)
            elif self._confidence >= 0.6:
                color = QColor(palette.warning)
            else:
                color = QColor(palette.error)

            painter.setBrush(color)
            painter.drawRoundedRect(fill_rect, 6, 6)

        # Label text
        font = QFont(tokens.typography.family, tokens.typography.sm, tokens.typography.medium)
        painter.setFont(font)
        painter.setPen(QColor(palette.text_primary))

        text = f"{self._label}: {int(self._confidence * 100)}%"
        if self._is_stable:
            text += " ✓"

        painter.drawText(bar_rect, Qt.AlignLeft | Qt.AlignVCenter, text)


class ProgressRing(QWidget):
    """
    Circular progress indicator for lesson progress, quiz timer, etc.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 0.0  # 0-1
        self._thickness = 8
        self._show_text = True
        self.setMinimumSize(64, 64)
        self.setMaximumSize(128, 128)

    def set_progress(self, progress: float):
        self._progress = max(0.0, min(1.0, progress))
        self.update()

    def set_thickness(self, thickness: int):
        self._thickness = thickness
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        palette = theme_manager.palette()
        tokens = theme_manager.tokens()

        rect = self.rect()
        size = min(rect.width(), rect.height())
        center = rect.center()
        radius = (size - self._thickness) // 2

        # Background ring
        bg_pen = QPen(QColor(palette.surface_variant))
        bg_pen.setWidth(self._thickness)
        bg_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(bg_pen)
        painter.drawEllipse(center, radius, radius)

        # Progress ring
        if self._progress > 0:
            progress_pen = QPen(QColor(palette.accent))
            progress_pen.setWidth(self._thickness)
            progress_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(progress_pen)

            span = int(-self._progress * 360 * 16)
            painter.drawArc(
                center.x() - radius, center.y() - radius,
                radius * 2, radius * 2,
                90 * 16, span
            )

        # Center text
        if self._show_text:
            font = QFont(tokens.typography.family, tokens.typography.xl, tokens.typography.bold)
            painter.setFont(font)
            painter.setPen(QColor(palette.text_primary))
            text = f"{int(self._progress * 100)}%"
            painter.drawText(rect, Qt.AlignCenter, text)


class Chip(QWidget):
    """Small colored chip/tag for categories, difficulties, etc."""

    def __init__(self, text: str, chip_type: str = "default", parent=None):
        super().__init__(parent)
        self._text = text
        self._chip_type = chip_type
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        palette = theme_manager.palette()
        tokens = theme_manager.tokens()

        # Colors by type
        type_colors = {
            "default": (palette.surface_variant, palette.text_secondary),
            "difficulty-easy": (palette.success_bg, palette.success),
            "difficulty-medium": (palette.warning_bg, palette.warning),
            "difficulty-hard": (palette.error_bg, palette.error),
            "category": (palette.accent, palette.text_on_accent),
            "success": (palette.success_bg, palette.success),
            "error": (palette.error_bg, palette.error),
        }
        bg_color, text_color = type_colors.get(self._chip_type, type_colors["default"])

        rect = self.rect()
        painter.setBrush(QColor(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, tokens.radius.full, tokens.radius.full)

        font = QFont(tokens.typography.family, tokens.typography.xs, tokens.typography.medium)
        painter.setFont(font)
        painter.setPen(QColor(text_color))

        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(self._text)
        self.setFixedWidth(text_width + tokens.spacing.md * 2)

        painter.drawText(rect, Qt.AlignCenter, self._text)


class Card(QFrame):
    """Elevated card container with consistent styling."""

    def __init__(self, parent=None, elevated=False):
        super().__init__(parent)
        self.setProperty("class", "card-elevated" if elevated else "card")
        self.setContentsMargins(0, 0, 0, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)


class StatusBanner(QLabel):
    """Top banner showing current status with icon."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "status-banner")
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self.setMinimumHeight(48)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
