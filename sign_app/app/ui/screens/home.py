"""
Home screen - main dashboard with module cards, progress, and quick actions.
"""

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QGridLayout, QProgressBar
)
from PySide6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor
import logging

from app.ui.main_window import ScreenBase
from app.ui.widgets import Card, Chip, ProgressRing
from app.ui.theme import theme_manager, ThemeMode
from app.data.db import (
    User, Module, UserProgress, ModuleRepository, ProgressRepository,
    ModuleCategory, Difficulty, UserRepository, BadgeRepository, UserBadge
)
from app.content.loader import ContentPackLoader

logger = logging.getLogger(__name__)


class ModuleCard(QFrame):
    """Card showing a learning module with progress."""

    clicked = Signal(str)  # module_id

    def __init__(self, module: Module, progress: UserProgress = None, pack=None, parent=None):
        super().__init__(parent)
        self._module = module
        self._progress = progress
        self._pack = pack
        self.setProperty("class", "card")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(200)
        self.setMinimumWidth(280)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header with category chip and difficulty
        header_layout = QHBoxLayout()

        category_chip = Chip(
            self._module.category.value.replace("_", " ").title(),
            f"category"
        )
        header_layout.addWidget(category_chip)

        difficulty_chip = Chip(
            self._module.difficulty.value.title(),
            f"difficulty-{self._module.difficulty.value}"
        )
        header_layout.addWidget(difficulty_chip)

        header_layout.addStretch()
        if self._progress and self._progress.completed:
            status = Chip("Completed", "success")
        elif self._progress and self._progress.attempts:
            status = Chip("In progress", "category")
        elif any((getattr(s, "metadata", None) or {}).get("motion_sign") for s in getattr(self._pack, "signs", {}).values()
                 if s.id in self._module.sign_ids):
            status = Chip("Watch & Learn", "warning")
        else:
            status = Chip("New", "difficulty-easy")
        header_layout.addWidget(status)
        layout.addLayout(header_layout)

        # Module name
        name_label = QLabel(self._module.name)
        name_label.setProperty("class", "title")
        name_label.setWordWrap(True)
        layout.addWidget(name_label)

        # Description - limit to 2 lines with ellipsis
        desc_label = QLabel(self._module.description)
        desc_label.setProperty("class", "body-small")
        desc_label.setWordWrap(True)
        desc_label.setMaximumHeight(40)  # ~2 lines
        layout.addWidget(desc_label)

        layout.addStretch()

        # Every card has an explicit progress affordance, including new cards.
        progress_layout = QHBoxLayout()

        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(int(self._progress.accuracy * 100) if self._progress else 0)
        progress_bar.setTextVisible(True)
        progress_bar.setFormat("%p%")
        progress_bar.setAlignment(Qt.AlignCenter)
        progress_bar.setFixedHeight(10)
        progress_bar.setProperty("showText", True)
        progress_layout.addWidget(progress_bar, 1)

        mastered = int(len(self._module.sign_ids) * (self._progress.accuracy if self._progress else 0))
        accuracy_label = QLabel(f"{mastered} / {len(self._module.sign_ids)} mastered")
        accuracy_label.setProperty("class", "caption")
        progress_layout.addWidget(accuracy_label)

        layout.addLayout(progress_layout)

        if self._progress and self._progress.completed:
            completed_label = QLabel("✓ Completed")
            completed_label.setProperty("class", "success")
            completed_label.setAlignment(Qt.AlignRight)
            layout.addWidget(completed_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._module.id)


class StatCard(QFrame):
    """Small stat card for streaks, badges, etc."""

    def __init__(self, title: str, value: str, icon: str = "", color: str = None, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setFixedSize(160, 100)
        self._icon_char = icon
        self._setup_ui(title, value, icon, color)

    def _setup_ui(self, title: str, value: str, icon: str, color: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        if icon:
            icon_label = QLabel()
            icon_label.setAlignment(Qt.AlignCenter)
            icon_label.setPixmap(self._create_icon_pixmap(icon, 32))
            layout.addWidget(icon_label)

        value_label = QLabel(value)
        value_label.setProperty("class", "heading")
        value_label.setAlignment(Qt.AlignCenter)
        if color:
            value_label.setStyleSheet(f"color: {color};")
        layout.addWidget(value_label)

        title_label = QLabel(title)
        title_label.setProperty("class", "caption")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

    def _create_icon_pixmap(self, char: str, size: int):
        """Create icon pixmap from character."""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setFont(QFont("Helvetica Neue", max(14, size // 2)))
        painter.setPen(QColor("#FAFAFA"))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, char)
        painter.end()
        return pixmap


class ContinueCard(QFrame):
    """Card for 'Continue where you left off'."""

    continue_requested = Signal(str)  # module_id

    def __init__(self, module: Module, progress: UserProgress, parent=None):
        super().__init__(parent)
        self._module = module
        self._progress = progress
        self.setProperty("class", "card-elevated")
        self.setCursor(Qt.PointingHandCursor)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Progress ring
        self._progress_ring = ProgressRing()
        self._progress_ring.set_progress(self._progress.accuracy)
        self._progress_ring.setFixedSize(80, 80)
        layout.addWidget(self._progress_ring)

        # Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        title = QLabel("Continue Learning")
        title.setProperty("class", "caption")
        info_layout.addWidget(title)

        name = QLabel(self._module.name)
        name.setProperty("class", "title")
        info_layout.addWidget(name)

        desc = QLabel(f"{int(self._progress.accuracy * 100)}% accuracy · {self._progress.attempts} attempts")
        desc.setProperty("class", "body-small")
        info_layout.addWidget(desc)

        info_layout.addStretch()

        btn = QPushButton("Continue")
        btn.setProperty("class", "primary")
        btn.setFixedWidth(120)
        btn.clicked.connect(lambda: self.continue_requested.emit(self._module.id))
        info_layout.addWidget(btn, alignment=Qt.AlignLeft)

        layout.addLayout(info_layout)


class HomeScreen(ScreenBase):
    """Main home/dashboard screen."""

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
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        layout.addWidget(scroll)

        # Content widget
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 100)  # Bottom padding for nav bar (H7)
        content_layout.setSpacing(32)

        scroll.setWidget(content)

        # Greeting section
        self._greeting_layout = QHBoxLayout()
        content_layout.addLayout(self._greeting_layout)

        # Continue card
        self._continue_card = None
        self._continue_container = QWidget()
        self._continue_layout = QVBoxLayout(self._continue_container)
        self._continue_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self._continue_container)

        # Modules by category
        self._modules_container = QWidget()
        self._modules_layout = QVBoxLayout(self._modules_container)
        self._modules_layout.setContentsMargins(0, 0, 0, 0)
        self._modules_layout.setSpacing(24)
        content_layout.addWidget(self._modules_container)

        # Stats row
        self._stats_container = QWidget()
        self._stats_layout = QHBoxLayout(self._stats_container)
        self._stats_layout.setContentsMargins(0, 0, 0, 0)
        self._stats_layout.setSpacing(16)
        content_layout.addWidget(self._stats_container)

        # Quick actions
        self._actions_container = QWidget()
        self._actions_layout = QHBoxLayout(self._actions_container)
        self._actions_layout.setContentsMargins(0, 0, 0, 0)
        self._actions_layout.setSpacing(12)
        content_layout.addWidget(self._actions_container)

        content_layout.addStretch()

    def on_show(self):
        """Refresh when shown."""
        self._refresh()

    def set_user(self, user: User):
        self._user = user
        self._refresh()

    def _refresh(self):
        if not self._user:
            return

        # Clear layouts
        self._clear_layout(self._greeting_layout)
        self._clear_layout(self._continue_layout)
        self._clear_layout(self._modules_layout)
        self._clear_layout(self._stats_layout)
        self._clear_layout(self._actions_layout)

        # Greeting
        greeting = QLabel(f"Welcome back, {self._user.name}!")
        greeting.setProperty("class", "heading")
        self._greeting_layout.addWidget(greeting)
        self._greeting_layout.addStretch()

        # Theme toggle - use icon button
        theme_btn = QPushButton()
        theme_btn.setProperty("class", "icon")
        theme_btn.setToolTip("Toggle theme")
        theme_btn.setIcon(self._create_theme_icon())
        theme_btn.clicked.connect(self._toggle_theme)
        self._greeting_layout.addWidget(theme_btn)

        # Continue where left off
        self._build_continue_section()

        # Modules by category
        self._build_modules_section()

        # Stats
        self._build_stats_section()

        # Quick actions
        self._build_actions_section()

    def _create_theme_icon(self):
        """Create theme toggle icon."""
        from PySide6.QtGui import QPixmap, QPainter, QFont, QColor
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setFont(QFont("Helvetica Neue", 14))
        painter.setPen(QColor("#FAFAFA"))
        char = "☀️" if theme_manager.mode == ThemeMode.DARK else "🌙"
        painter.drawText(pixmap.rect(), Qt.AlignCenter, char)
        painter.end()
        return QIcon(pixmap)

    def _build_continue_section(self):
        # Find most recently practiced incomplete module
        all_progress = ProgressRepository.get_all_progress(self._user.id)
        incomplete = [p for p in all_progress if not p.completed and p.attempts > 0]
        if incomplete:
            latest = max(incomplete, key=lambda p: p.last_practiced_at or "")
            module = ModuleRepository.get_by_id(latest.module_id)
            if module:
                self._continue_card = ContinueCard(module, latest)
                self._continue_card.continue_requested.connect(
                    lambda mid: self._main_window.show_screen("lesson", module_id=mid)
                )
                self._continue_layout.addWidget(self._continue_card)

    def _build_modules_section(self):
        pack = self._content_loader.get_current_pack()
        if not pack:
            return

        # Group modules by category
        categories = [
            (ModuleCategory.FINGERSPELLING, "Fingerspelling"),
            (ModuleCategory.NUMBERS, "Numbers"),
            (ModuleCategory.GREETINGS, "Greetings"),
            (ModuleCategory.PHRASES, "Phrases"),
        ]

        for category, label in categories:
            modules = [m for m in pack.modules.values() if m.category == category]
            
            # Category header
            cat_header = QWidget()
            cat_layout = QHBoxLayout(cat_header)
            cat_layout.setContentsMargins(0, 0, 0, 8)

            cat_label = QLabel(label)
            cat_label.setProperty("class", "subheading")
            cat_layout.addWidget(cat_label)

            cat_layout.addStretch()
            self._modules_layout.addWidget(cat_header)

            if not modules:
                # Empty state for categories with no modules (H6)
                empty_card = QFrame()
                empty_card.setProperty("class", "card")
                empty_layout = QVBoxLayout(empty_card)
                empty_layout.setAlignment(Qt.AlignCenter)
                empty_layout.setContentsMargins(24, 32, 24, 32)
                empty_layout.setSpacing(12)

                icon_label = QLabel("🚧")
                icon_label.setProperty("class", "heading")
                icon_label.setStyleSheet("font-size: 48px;")
                empty_layout.addWidget(icon_label)

                msg = QLabel(f"No {label.lower()} modules yet")
                msg.setProperty("class", "body")
                msg.setAlignment(Qt.AlignCenter)
                empty_layout.addWidget(msg)

                sub_msg = QLabel("Coming soon in a future update")
                sub_msg.setProperty("class", "caption")
                sub_msg.setAlignment(Qt.AlignCenter)
                empty_layout.addWidget(sub_msg)

                self._modules_layout.addWidget(empty_card)
                continue

            # Module grid - responsive: 3 cols wide, 2 medium, 1 narrow
            grid = QGridLayout()
            grid.setSpacing(16)
            for column in range(3):
                grid.setColumnStretch(column, 1)

            progress_map = {p.module_id: p for p in ProgressRepository.get_all_progress(self._user.id)}

            for i, module in enumerate(modules):
                progress = progress_map.get(module.id)
                card = ModuleCard(module, progress, pack)
                card.clicked.connect(
                    lambda mid: self._main_window.show_screen("lesson", module_id=mid)
                )
                # Responsive grid: 3 cols, but wrap to 2/1 as needed
                grid.addWidget(card, i // 3, i % 3)

            grid_widget = QWidget()
            grid_widget.setLayout(grid)
            self._modules_layout.addWidget(grid_widget)

    def _build_stats_section(self):
        # Get stats
        all_progress = ProgressRepository.get_all_progress(self._user.id)
        completed_count = sum(1 for p in all_progress if p.completed)
        total_attempts = sum(p.attempts for p in all_progress)

        # Calculate streak (simplified)
        streak = self._calculate_streak()

        # Badges
        badges = BadgeRepository.get_user_badges(self._user.id)

        stats = [
            ("Modules\nCompleted", str(completed_count), "📚", theme_manager.palette().accent),
            ("Practice\nAttempts", str(total_attempts), "🎯", theme_manager.palette().success),
            ("Current\nStreak", f"{streak} days", "🔥", theme_manager.palette().warning),
            ("Badges\nEarned", str(len(badges)), "🏆", theme_manager.palette().error),
        ]

        for title, value, icon_char, color in stats:
            card = StatCard(title, value, icon_char, color)
            self._stats_layout.addWidget(card)

    def _build_actions_section(self):
        actions = [
            ("📖", "Dictionary", "dictionary"),
            ("🧠", "Quiz", "quiz"),
            ("📈", "Progress", "progress"),
        ]

        for icon_char, text, screen in actions:
            btn = QPushButton()
            btn.setProperty("class", "secondary")
            btn.setMinimumHeight(56)
            btn.setIcon(self._create_action_icon(icon_char))
            btn.setIconSize(QSize(20, 20))
            btn.setToolTip(text)
            # Add text as accessible name
            btn.setAccessibleName(text)
            btn.clicked.connect(lambda checked, s=screen: self._main_window._show_screen(s))
            self._actions_layout.addWidget(btn)

    def _create_action_icon(self, char: str):
        """Create action button icon."""
        from PySide6.QtGui import QPixmap, QPainter, QFont, QColor
        pixmap = QPixmap(20, 20)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setFont(QFont("Helvetica Neue", 14))
        painter.setPen(QColor("#FAFAFA"))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, char)
        painter.end()
        return QIcon(pixmap)

    def _calculate_streak(self) -> int:
        """Calculate current streak in days."""
        # Simplified - in reality would check consecutive days with practice
        from app.data.db import PracticeAttempt
        from app.data.db import get_thread_connection
        from datetime import date, timedelta

        conn = get_thread_connection()
        rows = conn.execute("""
            SELECT DISTINCT date(timestamp) as practice_date
            FROM practice_attempts
            WHERE user_id = ?
            ORDER BY practice_date DESC
        """, (self._user.id,)).fetchall()

        if not rows:
            return 0

        streak = 0
        current_date = date.today()
        for row in rows:
            practice_date = date.fromisoformat(row['practice_date'])
            if practice_date == current_date or practice_date == current_date - timedelta(days=streak):
                streak += 1
                current_date = practice_date
            else:
                break
        return streak

    def _toggle_theme(self):
        theme_manager.toggle()
        self._main_window.setStyleSheet(theme_manager.stylesheet())
        # Save theme preference
        from app.data.db import SettingsRepository, AppSettings
        settings = SettingsRepository.get(self._user.id)
        settings.theme = theme_manager.mode.value
        SettingsRepository.update(settings)
        self._refresh()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
