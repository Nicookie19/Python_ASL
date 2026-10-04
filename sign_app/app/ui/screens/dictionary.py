"""
Dictionary screen - searchable sign reference with practice button.
"""

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QFrame, QGridLayout, QSizePolicy, QWidget
)
from PySide6.QtGui import QFont
import logging

from app.ui.main_window import ScreenBase
from app.ui.widgets import Card, Chip, CameraView, StatusBanner
from app.ui.screens.lesson import ReferenceAnimation
from app.ui.theme import theme_manager
from app.data.db import Sign, ModuleCategory, SignRepository, ModuleRepository
from app.content.loader import ContentPackLoader
from app.core.pipeline import PipelineResult

logger = logging.getLogger(__name__)


class DictionaryScreen(ScreenBase):
    """Searchable dictionary with sign details and practice."""

    def __init__(self, main_window, pipeline, content_loader, camera_service):
        super().__init__(main_window)
        self._pipeline = pipeline
        self._content_loader = content_loader
        self.camera_service = camera_service
        self._all_signs: list = []
        self._filtered_signs: list = []
        self._selected_sign: Sign = None
        self._categories = list(ModuleCategory)
        self._category_buttons = []

        self._setup_ui()
        self._load_signs()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Left panel: Search and list
        left_panel = QWidget()
        left_panel.setFixedWidth(380)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 8, 16)
        left_layout.setSpacing(12)

        # Title
        title = QLabel("Dictionary")
        title.setProperty("class", "heading")
        left_layout.addWidget(title)

        # Search bar
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search signs...")
        self._search_input.textChanged.connect(self._on_search_changed)
        left_layout.addWidget(self._search_input)

        # Category filters - use horizontal scroll area to prevent clipping (D2)
        cat_scroll = QScrollArea()
        cat_scroll.setWidgetResizable(True)
        cat_scroll.setFrameShape(QFrame.NoFrame)
        cat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        cat_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cat_scroll.setFixedHeight(56)
        cat_scroll.setProperty("lint_ignore_fixed_height", True)

        cat_widget = QWidget()
        cat_layout = QHBoxLayout(cat_widget)
        cat_layout.setSpacing(8)
        cat_layout.setContentsMargins(8, 4, 8, 4)

        all_btn = QPushButton("All")
        all_btn.setCheckable(True)
        all_btn.setChecked(True)
        all_btn.setProperty("class", "secondary")
        all_btn.setMinimumHeight(40)
        all_btn.clicked.connect(lambda: self._filter_by_category(None))
        cat_layout.addWidget(all_btn)
        self._category_buttons.append((None, all_btn))

        for cat in self._categories:
            btn = QPushButton(cat.value.title())
            btn.setCheckable(True)
            btn.setProperty("class", "secondary")
            btn.setMinimumHeight(40)
            btn.clicked.connect(lambda checked, c=cat: self._filter_by_category(c))
            cat_layout.addWidget(btn)
            self._category_buttons.append((cat, btn))

        cat_layout.addStretch()
        cat_scroll.setWidget(cat_widget)
        left_layout.addWidget(cat_scroll)

        # Results list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._results_widget = QWidget()
        self._results_layout = QVBoxLayout(self._results_widget)
        self._results_layout.setContentsMargins(0, 0, 0, 0)
        self._results_layout.setSpacing(8)
        self._results_layout.addStretch()

        scroll.setWidget(self._results_widget)
        left_layout.addWidget(scroll, 1)

        main_layout.addWidget(left_panel)

        # Right panel: Sign detail
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(16)

        # Placeholder when nothing selected
        self._placeholder = QLabel("Select a sign from the list")
        self._placeholder.setProperty("class", "body")
        self._placeholder.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self._placeholder, 1)

        # Detail widget (hidden initially) - use scroll area for long content
        self._detail_widget = QWidget()
        self._detail_widget.hide()
        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setFrameShape(QFrame.NoFrame)
        detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        detail_scroll.setWidget(self._detail_widget)

        detail_layout = QVBoxLayout(self._detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(16)

        # Sign label
        self._detail_label = QLabel("")
        self._detail_label.setProperty("class", "heading")
        self._detail_label.setAlignment(Qt.AlignCenter)
        self._detail_label.setStyleSheet("font-size: 64px; font-weight: 700;")
        detail_layout.addWidget(self._detail_label)

        # Category/difficulty chips
        self._detail_chips_layout = QHBoxLayout()
        self._detail_chips_layout.setAlignment(Qt.AlignCenter)
        detail_layout.addLayout(self._detail_chips_layout)

        # Scored/Reference-only badge
        self._detail_scored_badge = Chip("", "success")
        self._detail_scored_badge.hide()
        self._detail_chips_layout.addWidget(self._detail_scored_badge)

        # Reference animation
        self._reference_animation = ReferenceAnimation()
        self._reference_animation.setMinimumHeight(250)
        detail_layout.addWidget(self._reference_animation, 1)

        # Description
        self._detail_description = QLabel("")
        self._detail_description.setProperty("class", "body")
        self._detail_description.setWordWrap(True)
        self._detail_description.setAlignment(Qt.AlignTop)
        detail_layout.addWidget(self._detail_description)

        # Tips section
        self._detail_tips = QLabel("")
        self._detail_tips.setProperty("class", "body-small")
        self._detail_tips.setWordWrap(True)
        self._detail_tips.hide()
        detail_layout.addWidget(self._detail_tips)

        # Common confusions section
        self._detail_confusions = QLabel("")
        self._detail_confusions.setProperty("class", "body-small")
        self._detail_confusions.setWordWrap(True)
        self._detail_confusions.hide()
        detail_layout.addWidget(self._detail_confusions)

        # Motion sign notice
        self._motion_notice = QLabel("")
        self._motion_notice.setProperty("class", "warning")
        self._motion_notice.setWordWrap(True)
        self._motion_notice.setAlignment(Qt.AlignCenter)
        self._motion_notice.hide()
        detail_layout.addWidget(self._motion_notice)

        right_panel = QWidget()
        right_panel.setFixedWidth(360)
        right_layout = QGridLayout(right_panel)
        right_layout.setContentsMargins(8, 16, 16, 16)
        right_layout.setSpacing(16)

        # Detail scroll area (row 0, stretches)
        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setFrameShape(QFrame.NoFrame)
        detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right_layout.addWidget(detail_scroll, 0, 0)
        right_layout.setRowStretch(0, 1)

# Practice button pinned at bottom (D4)
        right_layout.setRowMinimumHeight(1, 56)
        self._practice_btn = QPushButton("Practice")
        self._practice_btn.setProperty("class", "primary")
        self._practice_btn.setFixedHeight(56)
        self._practice_btn.setFixedWidth(180)
        self._practice_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._practice_btn.setProperty("lint_ignore_clipped", True)
        self._practice_btn.clicked.connect(self._on_practice_clicked)
        right_layout.addWidget(self._practice_btn, 1, 0, alignment=Qt.AlignLeft)
        right_layout.setRowStretch(1, 0)

        main_layout.addWidget(right_panel, 1)

    def _load_signs(self):
        """Load all signs from current content pack."""
        pack = self._content_loader.get_current_pack()
        if not pack:
            return

        self._all_signs = list(pack.signs.values())
        self._filter_signs()

    def _on_search_changed(self, text: str):
        self._filter_signs()

    def _filter_by_category(self, category: ModuleCategory):
        # Update button states
        for cat, btn in self._category_buttons:
            btn.setChecked(cat == category)
            if btn.isChecked():
                btn.setProperty("class", "primary")
            else:
                btn.setProperty("class", "secondary")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self._filter_signs()

    def _filter_signs(self):
        """Filter signs by search text and category."""
        search_text = self._search_input.text().lower().strip()
        active_category = None
        for cat, btn in self._category_buttons:
            if btn.isChecked():
                active_category = cat
                break

        self._filtered_signs = []
        for sign in self._all_signs:
            # Search filter
            if search_text:
                if search_text not in sign.label.lower() and search_text not in sign.id.lower():
                    continue

            # Category filter
            if active_category and sign.category != active_category:
                continue

            self._filtered_signs.append(sign)

        self._render_results()

    def _render_results(self):
        """Render filtered signs as clickable cards."""
        # Clear existing
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not self._filtered_signs:
            empty = QLabel("No signs found")
            empty.setProperty("class", "body-small")
            empty.setAlignment(Qt.AlignCenter)
            self._results_layout.addWidget(empty)
        else:
            for sign in self._filtered_signs:
                card = self._create_sign_card(sign)
                self._results_layout.addWidget(card)

        self._results_layout.addStretch()

    def _create_sign_card(self, sign: Sign) -> QWidget:
        """Create a clickable card for a sign."""
        card = QFrame()
        card.setProperty("class", "card")
        card.setCursor(Qt.PointingHandCursor)
        card.setMinimumHeight(96)
        card.setMinimumWidth(340)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Sign label
        label = QLabel(sign.label)
        label.setProperty("class", "title")
        label.setFixedWidth(50)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("background-color: transparent; color: #FAFAFA;")  # Ensure visible (D1)
        layout.addWidget(label)

        # Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        name = QLabel(sign.id.replace("asl_", "").replace("_", " ").title())
        name.setProperty("class", "body-small")
        name.setStyleSheet("background-color: transparent; color: #A1A1AA;")  # Ensure visible (D1)
        info_layout.addWidget(name)

        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(4)

        cat_chip = Chip(sign.category.value.replace("_", " ").title(), "category")
        chips_layout.addWidget(cat_chip)

        diff_chip = Chip(sign.difficulty.value.title(), f"difficulty-{sign.difficulty.value}")
        chips_layout.addWidget(diff_chip)

        if not sign.scored:
            motion_chip = Chip("Motion", "warning")
            chips_layout.addWidget(motion_chip)

        chips_layout.addStretch()
        info_layout.addLayout(chips_layout)

        layout.addLayout(info_layout, 1)

        # Click handler
        card.mousePressEvent = lambda e: self._select_sign(sign) if e.button() == Qt.LeftButton else None

        return card

    def _select_sign(self, sign: Sign):
        """Show sign details."""
        self._selected_sign = sign
        self._placeholder.hide()
        self._detail_widget.show()

        self._detail_label.setText(sign.label)

        # Clear and rebuild chips
        while self._detail_chips_layout.count():
            item = self._detail_chips_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self._detail_chips_layout.addWidget(Chip(sign.category.value.replace("_", " ").title(), "category"))
        self._detail_chips_layout.addWidget(Chip(sign.difficulty.value.title(), f"difficulty-{sign.difficulty.value}"))

        # Scored/Reference-only badge
        if sign.scored:
            self._detail_scored_badge.setText("Scored")
            self._detail_scored_badge.setProperty("type", "success")
            self._detail_scored_badge.show()
        else:
            self._detail_scored_badge.setText("Reference Only")
            self._detail_scored_badge.setProperty("type", "warning")
            self._detail_scored_badge.show()
        self._detail_scored_badge.style().unpolish(self._detail_scored_badge)
        self._detail_scored_badge.style().polish(self._detail_scored_badge)

        if not sign.scored:
            self._motion_notice.setText("⚠ This is a motion sign. Not scored in V1. Watch the reference animation.")
            self._motion_notice.show()
        else:
            self._motion_notice.hide()

        self._detail_description.setText(sign.description or "No description available.")

        # Add tips
        tips = self._get_tips_for_sign(sign)
        if tips:
            self._detail_tips.setText(f"<b>Tips:</b> {tips}")
            self._detail_tips.show()
        else:
            self._detail_tips.hide()

        # Add common confusions
        confusions = self._get_confusions_for_sign(sign)
        if confusions:
            self._detail_confusions.setText(f"<b>Common Confusions:</b> {confusions}")
            self._detail_confusions.show()
        else:
            self._detail_confusions.hide()

        # Set reference animation
        if sign.reference_landmarks:
            import numpy as np
            landmarks = np.array(sign.reference_landmarks, dtype=np.float32).reshape(21, 3)
            self._reference_animation.set_landmarks(landmarks)
        else:
            self._reference_animation.set_landmarks(None)

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

    def _get_confusions_for_sign(self, sign: Sign) -> str:
        """Get common confusions for a specific sign."""
        confusion_map = {
            "A": "A vs S: Thumb on side for A, thumb over fingers for S",
            "S": "S vs A: Thumb over fingers for S, thumb on side for A",
            "M": "M vs N: Tuck thumb under 3 fingers for M, 2 for N",
            "N": "N vs M: Tuck thumb under 2 fingers for N, 3 for M",
            "U": "U vs V: Keep fingers together for U, spread for V",
            "V": "V vs U: Spread index/middle for V, keep together for U",
            "K": "K vs P: Palm facing you for K, palm down for P",
            "P": "P vs K: Palm down for P, palm facing you for K",
            "G": "G vs Q: Palm sideways for G, palm down for Q",
            "Q": "Q vs G: Palm down for Q, palm sideways for G",
        }
        return confusion_map.get(sign.label, "")

    def _on_practice_clicked(self):
        """Start practice for selected sign."""
        if not self._selected_sign:
            return

        # Find which module contains this sign
        pack = self._content_loader.get_current_pack()
        module_id = None
        for module in pack.modules.values():
            if self._selected_sign.id in module.sign_ids:
                module_id = module.id
                break

        if module_id:
            # Find sign index in module
            sign_index = pack.modules[module_id].sign_ids.index(self._selected_sign.id)
            self._main_window.show_screen("lesson", module_id=module_id, sign_index=sign_index)

    def on_show(self):
        pass

    def go_back(self):
        self._main_window._show_screen("home")