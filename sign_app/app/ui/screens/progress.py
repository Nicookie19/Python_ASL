"""
Progress screen - accuracy charts, mastery heatmap, streaks, badges.
"""

from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGridLayout, QTabWidget, QComboBox
)
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QLinearGradient
import logging

from app.ui.main_window import ScreenBase
from app.ui.widgets import Card, Chip
from app.ui.theme import theme_manager
from app.data.db import (
    User, UserProgress, Module, Sign, Badge, UserBadge,
    ProgressRepository, ModuleRepository, SignRepository,
    BadgeRepository, AttemptRepository,
    ModuleCategory, Difficulty
)
from app.content.loader import ContentPackLoader

logger = logging.getLogger(__name__)


class AccuracyChart(QWidget):
    """Line chart showing accuracy over time."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []  # List of (date, accuracy)
        self.setMinimumHeight(200)

    def set_data(self, data: list):
        self._data = data
        self.update()

    def paintEvent(self, event):
        if not self._data:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        palette = theme_manager.palette()
        rect = self.rect().adjusted(40, 20, -20, -40)

        if not self._data:
            return

        # Find min/max
        accuracies = [d[1] for d in self._data]
        min_acc = min(accuracies) if accuracies else 0
        max_acc = max(accuracies) if accuracies else 1
        min_acc = max(0, min_acc - 0.1)
        max_acc = min(1, max_acc + 0.1)

        # Draw axes
        pen = QPen(QColor(palette.border))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())  # X axis
        painter.drawLine(rect.bottomLeft(), rect.topLeft())      # Y axis

        # Draw grid lines
        pen.setStyle(Qt.DotLine)
        pen.setColor(QColor(palette.divider))
        painter.setPen(pen)
        for i in range(5):
            y = rect.bottom() - i * rect.height() / 4
            painter.drawLine(rect.left(), y, rect.right(), y)

        # Draw line
        pen.setStyle(Qt.SolidLine)
        pen.setColor(QColor(palette.accent))
        pen.setWidth(3)
        painter.setPen(pen)

        points = []
        for i, (date, acc) in enumerate(self._data):
            x = rect.left() + (i / max(1, len(self._data) - 1)) * rect.width()
            y = rect.bottom() - ((acc - min_acc) / (max_acc - min_acc)) * rect.height()
            points.append((x, y))

        for i in range(len(points) - 1):
            painter.drawLine(int(points[i][0]), int(points[i][1]),
                           int(points[i+1][0]), int(points[i+1][1]))

        # Draw points
        painter.setBrush(QBrush(QColor(palette.accent)))
        for x, y in points:
            painter.drawEllipse(int(x) - 4, int(y) - 4, 8, 8)


class MasteryHeatmap(QWidget):
    """Heatmap grid showing mastery per letter/sign."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._signs = []  # List of (sign, accuracy)
        self._cell_size = 36
        self.setMinimumHeight(300)

    def set_data(self, signs: list):
        self._signs = signs
        self.update()

    def paintEvent(self, event):
        if not self._signs:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        palette = theme_manager.palette()
        tokens = theme_manager.tokens()

        cols = 8
        cell_size = self._cell_size
        spacing = 8

        for i, (sign, accuracy) in enumerate(self._signs):
            row = i // cols
            col = i % cols

            x = col * (cell_size + spacing) + spacing
            y = row * (cell_size + spacing) + spacing

            # Color based on accuracy
            if accuracy >= 0.8:
                color = QColor(palette.success)
            elif accuracy >= 0.6:
                color = QColor(palette.warning)
            elif accuracy > 0:
                color = QColor(palette.error)
            else:
                color = QColor(palette.surface_variant)

            # Draw cell
            rect = QRect(x, y, cell_size, cell_size)
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor(palette.border), 1))
            painter.drawRoundedRect(rect, tokens.radius.sm, tokens.radius.sm)

            # Draw letter
            font = QFont(tokens.typography.family, tokens.typography.base, tokens.typography.bold)
            painter.setFont(font)

            text_color = QColor(palette.text_on_accent) if accuracy > 0.5 else QColor(palette.text_primary)
            if accuracy == 0:
                text_color = QColor(palette.text_disabled)

            painter.setPen(text_color)
            painter.drawText(rect, Qt.AlignCenter, sign.label)

            # Accuracy tooltip would be nice but skip for now


class StreakCalendar(QWidget):
    """GitHub-style contribution calendar for practice streaks."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._practice_dates = set()  # Set of date strings "YYYY-MM-DD"
        self.setMinimumHeight(150)

    def set_dates(self, dates: set):
        self._practice_dates = dates
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        palette = theme_manager.palette()

        cell_size = 12
        spacing = 2
        weeks = 52  # Show 52 weeks

        from datetime import date, timedelta
        today = date.today()
        start_date = today - timedelta(weeks=weeks)

        for week in range(weeks):
            for day in range(7):
                current_date = start_date + timedelta(weeks=week, days=day)
                if current_date > today:
                    break

                date_str = current_date.isoformat()
                x = week * (cell_size + spacing)
                y = day * (cell_size + spacing)

                rect = QRect(x, y, cell_size, cell_size)

                if date_str in self._practice_dates:
                    color = QColor(palette.success)
                else:
                    color = QColor(palette.surface_variant)

                painter.setBrush(QBrush(color))
                painter.setPen(QPen(QColor(palette.border), 1))
                painter.drawRoundedRect(rect, 2, 2)


class ProgressScreen(ScreenBase):
    """Progress dashboard with charts and statistics."""

    def __init__(self, main_window, content_loader, camera_service):
        super().__init__(main_window)
        self._content_loader = content_loader
        self.camera_service = camera_service
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scroll area
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
        title = QLabel("Your Progress")
        title.setProperty("class", "heading")
        content_layout.addWidget(title)

        # Tabs
        self._tabs = QTabWidget()
        content_layout.addWidget(self._tabs)

        # Overview tab
        self._overview_tab = self._create_overview_tab()
        self._tabs.addTab(self._overview_tab, "Overview")

        # Letters tab
        self._letters_tab = self._create_letters_tab()
        self._tabs.addTab(self._letters_tab, "Letters")

        # Badges tab
        self._badges_tab = self._create_badges_tab()
        self._tabs.addTab(self._badges_tab, "Badges")

    def _create_overview_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(24)

        # Stats cards
        self._stats_layout = QHBoxLayout()
        self._stats_layout.setSpacing(16)
        layout.addLayout(self._stats_layout)

        # Accuracy chart
        chart_card = Card()
        chart_layout = chart_card.layout()
        chart_title = QLabel("Accuracy Over Time")
        chart_title.setProperty("class", "title")
        chart_layout.addWidget(chart_title)

        self._accuracy_chart = AccuracyChart()
        self._accuracy_chart.setMinimumHeight(250)
        chart_layout.addWidget(self._accuracy_chart)

        layout.addWidget(chart_card)

        # Streak calendar
        streak_card = Card()
        streak_layout = streak_card.layout()
        streak_title = QLabel("Practice Streak")
        streak_title.setProperty("class", "title")
        streak_layout.addWidget(streak_title)

        self._streak_calendar = StreakCalendar()
        self._streak_calendar.setMinimumHeight(180)
        streak_layout.addWidget(self._streak_calendar)

        layout.addWidget(streak_card)

        layout.addStretch()
        return widget

    def _create_letters_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Category filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Category:"))

        self._category_combo = QComboBox()
        self._category_combo.addItems(["All", "Fingerspelling", "Numbers", "Greetings", "Phrases"])
        self._category_combo.currentTextChanged.connect(self._refresh_letters)
        filter_layout.addWidget(self._category_combo)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Heatmap
        heatmap_card = Card()
        heatmap_layout = heatmap_card.layout()

        self._heatmap = MasteryHeatmap()
        self._heatmap.setMinimumHeight(400)
        heatmap_layout.addWidget(self._heatmap)

        layout.addWidget(heatmap_card)
        layout.addStretch()
        return widget

    def _create_badges_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Badge grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        self._badges_widget = QWidget()
        self._badges_layout = QGridLayout(self._badges_widget)
        self._badges_layout.setSpacing(16)

        scroll.setWidget(self._badges_widget)
        layout.addWidget(scroll)
        return widget

    def on_show(self):
        self._refresh()

    def set_user(self, user: User):
        self._user = user
        self._refresh()

    def _refresh(self):
        if not hasattr(self, '_user') or not self._user:
            return

        # Stats cards
        self._refresh_stats()
        self._refresh_chart()
        self._refresh_streak()
        self._refresh_letters()
        self._refresh_badges()

    def _refresh_stats(self):
        self._clear_layout(self._stats_layout)

        user = self._user
        all_progress = ProgressRepository.get_all_progress(user.id)
        completed = sum(1 for p in all_progress if p.completed)
        total_modules = len(ModuleRepository.get_all())

        # Total practice attempts
        from app.data.db import get_thread_connection
        conn = get_thread_connection()
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM practice_attempts WHERE user_id = ?",
            (user.id,)
        ).fetchone()
        total_attempts = row['cnt'] if row else 0

        # Average accuracy
        avg_acc = sum(p.accuracy for p in all_progress) / len(all_progress) if all_progress else 0

        # Current streak
        streak = self._calculate_streak()

        stats = [
            ("Modules\nCompleted", f"{completed}/{total_modules}", "📚", theme_manager.palette().accent),
            ("Practice\nAttempts", str(total_attempts), "🎯", theme_manager.palette().success),
            ("Average\nAccuracy", f"{int(avg_acc * 100)}%", "📊", theme_manager.palette().warning),
            ("Current\nStreak", f"{streak} days", "🔥", theme_manager.palette().error),
        ]

        for title, value, icon, color in stats:
            card = Card()
            card.setFixedSize(160, 100)
            card_layout = card.layout()
            card_layout.setAlignment(Qt.AlignCenter)
            card_layout.setSpacing(8)

            icon_label = QLabel(icon)
            icon_label.setProperty("class", "heading")
            icon_label.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(icon_label)

            value_label = QLabel(value)
            value_label.setProperty("class", "heading")
            value_label.setAlignment(Qt.AlignCenter)
            value_label.setStyleSheet(f"color: {color};")
            card_layout.addWidget(value_label)

            title_label = QLabel(title)
            title_label.setProperty("class", "caption")
            title_label.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(title_label)

            self._stats_layout.addWidget(card)

    def _refresh_chart(self):
        """Load accuracy history for chart."""
        from app.data.db import get_thread_connection
        from datetime import date, timedelta

        conn = get_thread_connection()
        rows = conn.execute("""
            SELECT date(timestamp) as d, AVG(CASE WHEN result = 'correct' THEN 1.0 ELSE 0.0 END) as acc
            FROM practice_attempts
            WHERE user_id = ?
            GROUP BY date(timestamp)
            ORDER BY d
        """, (self._user.id,)).fetchall()

        data = [(row['d'], row['acc']) for row in rows]
        self._accuracy_chart.set_data(data)

    def _refresh_streak(self):
        """Load practice dates for streak calendar."""
        from app.data.db import get_thread_connection

        conn = get_thread_connection()
        rows = conn.execute("""
            SELECT DISTINCT date(timestamp) as d
            FROM practice_attempts
            WHERE user_id = ?
        """, (self._user.id,)).fetchall()

        dates = {row['d'] for row in rows}
        self._streak_calendar.set_dates(dates)

    def _refresh_letters(self):
        """Refresh mastery heatmap."""
        category_text = self._category_combo.currentText()

        pack = self._content_loader.get_current_pack()
        if not pack:
            return

        # Get signs for category
        signs = []
        if category_text == "All":
            signs = [s for s in pack.signs.values() if s.scored]
        else:
            cat_map = {
                "Fingerspelling": ModuleCategory.FINGERSPELLING,
                "Numbers": ModuleCategory.NUMBERS,
                "Greetings": ModuleCategory.GREETINGS,
                "Phrases": ModuleCategory.PHRASES,
            }
            cat = cat_map.get(category_text)
            if cat:
                signs = [s for s in pack.signs.values() if s.category == cat and s.scored]

        # Get accuracy for each sign
        sign_data = []
        for sign in signs:
            stats = AttemptRepository.get_accuracy_stats(self._user.id, sign.id)
            sign_data.append((sign, stats['accuracy']))

        self._heatmap.set_data(sign_data)

    def _refresh_badges(self):
        """Refresh badge grid."""
        self._clear_layout(self._badges_layout)

        all_badges = BadgeRepository.get_all()
        earned_badges = {ub.badge_id for ub in BadgeRepository.get_user_badges(self._user.id)}

        for i, badge in enumerate(all_badges):
            earned = badge.id in earned_badges
            badge_widget = self._create_badge_widget(badge, earned)
            self._badges_layout.addWidget(badge_widget, i // 4, i % 4)

    def _create_badge_widget(self, badge: Badge, earned: bool) -> QWidget:
        widget = QFrame()
        widget.setProperty("class", "card" if earned else "card")
        widget.setFixedSize(140, 140)

        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)

        # Icon
        icon_label = QLabel(badge.icon)
        icon_label.setProperty("class", "heading")
        icon_label.setStyleSheet(f"font-size: 48px;")
        icon_label.setAlignment(Qt.AlignCenter)
        if not earned:
            icon_label.setStyleSheet("font-size: 48px; color: #71717A;")
        layout.addWidget(icon_label)

        # Name
        name_label = QLabel(badge.name)
        name_label.setProperty("class", "body")
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setWordWrap(True)
        if not earned:
            name_label.setStyleSheet("color: #71717A;")
        layout.addWidget(name_label)

        # Description
        desc_label = QLabel(badge.description)
        desc_label.setProperty("class", "caption")
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        if not earned:
            widget.setStyleSheet("opacity: 0.5;")

        return widget

    def _calculate_streak(self) -> int:
        from app.data.db import get_thread_connection
        from datetime import date, timedelta

        conn = get_thread_connection()
        rows = conn.execute("""
            SELECT DISTINCT date(timestamp) as d
            FROM practice_attempts
            WHERE user_id = ?
            ORDER BY d DESC
        """, (self._user.id,)).fetchall()

        if not rows:
            return 0

        streak = 0
        current_date = date.today()
        for row in rows:
            d = date.fromisoformat(row['d'])
            if d == current_date or d == current_date - timedelta(days=streak):
                streak += 1
                current_date = d
            else:
                break
        return streak

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())