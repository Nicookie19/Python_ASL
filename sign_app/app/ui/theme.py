"""
Design tokens and QSS stylesheet for the Sign Language Learning Application.
All visual styling is centralized here. No hard-coded styling in widgets.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class ThemeMode(Enum):
    DARK = "dark"
    LIGHT = "light"


@dataclass(frozen=True)
class ColorPalette:
    """Semantic color palette with accessibility considerations."""

    # Base colors
    background: str
    surface: str
    surface_variant: str
    surface_elevated: str

    # Text colors
    text_primary: str
    text_secondary: str
    text_disabled: str
    text_on_accent: str

    # Accent and semantic colors
    accent: str
    accent_hover: str
    accent_pressed: str

    success: str
    success_bg: str
    error: str
    error_bg: str
    warning: str
    warning_bg: str

    # Border and divider
    border: str
    border_focus: str
    divider: str

    # Camera overlay colors (for skeleton)
    skeleton_correct: str
    skeleton_incorrect: str
    skeleton_neutral: str
    skeleton_connections: str

    # Dwell progress ring
    dwell_ring_bg: str
    dwell_ring_fill: str


# Dark theme (default) - WCAG AA compliant
DARK_PALETTE = ColorPalette(
    background="#18181B",          # zinc-950
    surface="#27272A",             # zinc-900
    surface_variant="#3F3F46",     # zinc-800
    surface_elevated="#52525B",    # zinc-700

    text_primary="#FAFAFA",        # zinc-50
    text_secondary="#A1A1AA",      # zinc-400
    text_disabled="#71717A",       # zinc-500
    text_on_accent="#18181B",      # zinc-950

    accent="#22D3EE",              # cyan-400
    accent_hover="#06B6D4",        # cyan-500
    accent_pressed="#0891B2",      # cyan-600

    success="#4ADE80",             # green-400 (colorblind-safe)
    success_bg="#14532D",          # green-900
    error="#F87171",               # red-400
    error_bg="#7F1D1D",            # red-900
    warning="#FBBF24",             # amber-400
    warning_bg="#78350F",          # amber-900

    border="#3F3F46",              # zinc-800
    border_focus="#22D3EE",        # cyan-400
    divider="#3F3F46",             # zinc-800

    skeleton_correct="#4ADE80",    # green-400
    skeleton_incorrect="#F87171",  # red-400
    skeleton_neutral="#A1A1AA",    # zinc-400
    skeleton_connections="#52525B", # zinc-700

    dwell_ring_bg="#3F3F46",       # zinc-800
    dwell_ring_fill="#22D3EE",     # cyan-400
)

# Light theme
LIGHT_PALETTE = ColorPalette(
    background="#FAFAFA",          # zinc-50
    surface="#FFFFFF",             # white
    surface_variant="#F4F4F5",     # zinc-100
    surface_elevated="#E4E4E7",    # zinc-200

    text_primary="#18181B",        # zinc-950
    text_secondary="#52525B",      # zinc-700
    text_disabled="#A1A1AA",       # zinc-400
    text_on_accent="#FAFAFA",      # zinc-50

    accent="#06B6D4",              # cyan-500
    accent_hover="#0891B2",        # cyan-600
    accent_pressed="#0E7490",      # cyan-700

    success="#16A34A",             # green-600
    success_bg="#DCFCE7",          # green-100
    error="#DC2626",               # red-600
    error_bg="#FEF2F2",            # red-50
    warning="#D97706",             # amber-600
    warning_bg="#FFFBEB",          # amber-50

    border="#E4E4E7",              # zinc-200
    border_focus="#06B6D4",        # cyan-500
    divider="#E4E4E7",             # zinc-200

    skeleton_correct="#16A34A",    # green-600
    skeleton_incorrect="#DC2626",  # red-600
    skeleton_neutral="#71717A",    # zinc-500
    skeleton_connections="#D4D4D8", # zinc-300

    dwell_ring_bg="#E4E4E7",       # zinc-200
    dwell_ring_fill="#06B6D4",     # cyan-500
)


@dataclass(frozen=True)
class Spacing:
    """Spacing scale based on 4px base unit."""
    xs: int = 4
    sm: int = 8
    md: int = 16
    lg: int = 24
    xl: int = 32
    xxl: int = 48


@dataclass(frozen=True)
class Radius:
    """Border radius scale."""
    sm: int = 6
    md: int = 10
    lg: int = 16
    xl: int = 24
    full: int = 9999


@dataclass(frozen=True)
class Typography:
    """Font sizes and weights."""
    # Font family - system UI font stack
    # Qt's QSS font parser does not use CSS fallback lists reliably and emits
    # warnings while probing absent families. Helvetica is present on macOS and
    # Qt will use its platform fallback elsewhere.
    family: str = "Helvetica Neue"

    # Sizes in px
    xs: int = 12
    sm: int = 14
    base: int = 16
    lg: int = 18
    xl: int = 20
    xxl: int = 24
    xxxl: int = 32

    # Weights
    regular: int = 400
    medium: int = 500
    semibold: int = 600
    bold: int = 700


@dataclass(frozen=True)
class Shadows:
    """Box shadow definitions."""
    sm: str = "0 1px 2px rgba(0, 0, 0, 0.05)"
    md: str = "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)"
    lg: str = "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)"
    xl: str = "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)"


@dataclass(frozen=True)
class Transitions:
    """Transition durations."""
    fast: int = 100
    normal: int = 150
    slow: int = 250


@dataclass(frozen=True)
class DesignTokens:
    """Complete design token set."""
    spacing: Spacing = Spacing()
    radius: Radius = Radius()
    typography: Typography = Typography()
    shadows: Shadows = Shadows()
    transitions: Transitions = Transitions()

    # Component-specific tokens
    button_height: int = 56
    button_height_sm: int = 44
    button_padding_h: int = 24
    icon_size: int = 24
    icon_size_lg: int = 32

    # Camera view
    camera_min_width: int = 640
    camera_min_height: int = 480

    # Dwell interaction
    dwell_duration_ms: int = 2000
    dwell_cursor_size: int = 16
    dwell_ring_thickness: int = 4

    # Chart/Progress
    chart_height: int = 200
    heatmap_cell_size: int = 36


DARK_TOKENS = DesignTokens()
LIGHT_TOKENS = DesignTokens()


def get_palette(mode: ThemeMode) -> ColorPalette:
    return DARK_PALETTE if mode == ThemeMode.DARK else LIGHT_PALETTE


def get_tokens(mode: ThemeMode) -> DesignTokens:
    return DARK_TOKENS if mode == ThemeMode.DARK else LIGHT_TOKENS


def generate_qss(mode: ThemeMode = ThemeMode.DARK) -> str:
    """Generate the complete QSS stylesheet for the given theme mode."""
    palette = get_palette(mode)
    tokens = get_tokens(mode)
    t = tokens.typography
    s = tokens.spacing
    r = tokens.radius
    tr = tokens.transitions

    return f"""
/* ============================================================================
   BASE STYLES
   ============================================================================ */

* {{
    font-family: {t.family};
    font-size: {t.base}px;
    color: {palette.text_primary};
    background-color: transparent;
    border: none;
    outline: none;
}}

QWidget {{
    background-color: {palette.background};
    color: {palette.text_primary};
}}

/* Ensure QLabel backgrounds are transparent (fixes H1) */
QLabel {{
    background-color: transparent;
}}

/* Focus styles - visible for keyboard navigation on interactive widgets only */
QPushButton:focus,
QLineEdit:focus,
QTextEdit:focus,
QComboBox:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QSlider:focus,
QTabBar::tab:focus,
QListView:focus,
QTreeView:focus,
QTableView:focus {{
    border: 2px solid {palette.border_focus};
    border-radius: {r.sm}px;
    padding: 2px;
}}

/* ============================================================================
   MAIN WINDOW & CONTAINERS
   ============================================================================ */

QMainWindow {{
    background-color: {palette.background};
    min-width: 1000px;
    min-height: 650px;
}}

#centralWidget {{
    background-color: {palette.background};
}}

#contentStack {{
    background-color: {palette.background};
}}

QWidget[class="ScreenWidget"] {{
    background-color: {palette.background};
    border-radius: {r.lg}px;
}}

/* Scroll areas */
QScrollArea {{
    background-color: {palette.background};
    border: none;
}}

QScrollArea > QWidget > QWidget {{
    background-color: {palette.background};
}}

QScrollBar:vertical {{
    background: {palette.surface};
    width: 10px;
    border-radius: 5px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {palette.surface_elevated};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: {palette.border};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background: none;
}}

/* ============================================================================
   BUTTONS
   ============================================================================ */

QPushButton {{
    background-color: {palette.accent};
    color: {palette.text_on_accent};
    border-radius: {r.md}px;
    padding: {s.sm}px {tokens.button_padding_h}px;
    min-height: {tokens.button_height}px;
    font-size: {t.base}px;
    font-weight: {t.medium};
}}

QPushButton:hover {{
    background-color: {palette.accent_hover};
}}

QPushButton:pressed {{
    background-color: {palette.accent_pressed};
}}

QPushButton:disabled {{
    background-color: {palette.surface_elevated};
    color: {palette.text_disabled};
}}

QPushButton:checked {{
    background-color: {palette.accent_pressed};
    border: 2px solid {palette.border_focus};
}}

/* Secondary button variant */
QPushButton[class="secondary"] {{
    background-color: {palette.surface_variant};
    color: {palette.text_primary};
    border: 1px solid {palette.border};
}}

QPushButton[class="secondary"]:hover {{
    background-color: {palette.surface_elevated};
    border-color: {palette.border_focus};
}}

QPushButton[class="secondary"]:pressed {{
    background-color: {palette.border};
}}

/* Ghost button variant */
QPushButton[class="ghost"] {{
    background-color: transparent;
    color: {palette.text_primary};
    border: 1px solid transparent;
}}

QPushButton[class="ghost"]:hover {{
    background-color: {palette.surface_variant};
}}

/* Danger button variant */
QPushButton[class="danger"] {{
    background-color: {palette.error_bg};
    color: {palette.error};
    border: 1px solid {palette.error};
}}

QPushButton[class="danger"]:hover {{
    background-color: {palette.error};
    color: {palette.text_on_accent};
}}

/* Small button */
QPushButton[class="small"] {{
    min-height: {tokens.button_height_sm}px;
    padding: {s.xs}px {s.md}px;
    font-size: {t.sm}px;
}}

/* Icon button */
QPushButton[class="icon"] {{
    min-width: {tokens.button_height}px;
    min-height: {tokens.button_height}px;
    max-width: {tokens.button_height}px;
    max-height: {tokens.button_height}px;
    padding: 0;
    border-radius: {r.full}px;
}}

/* Nav bar buttons - compact icon-only buttons */
QPushButton[class="nav"] {{
    background-color: transparent;
    border: none;
    border-radius: {r.md}px;
    padding: 0;
    min-width: {tokens.button_height}px;
    min-height: {tokens.button_height}px;
    max-width: {tokens.button_height}px;
    max-height: {tokens.button_height}px;
}}

QPushButton[class="nav"]:hover {{
    background-color: {palette.surface_variant};
}}

QPushButton[class="nav"]:checked,
QPushButton[class="nav"][active="true"] {{
    background-color: {palette.accent};
    color: {palette.text_on_accent};
}}

/* ============================================================================
   LABELS
   ============================================================================ */

QLabel {{
    color: {palette.text_primary};
}}

QLabel[class="heading"] {{
    font-size: {t.xxxl}px;
    font-weight: {t.bold};
    color: {palette.text_primary};
}}

QLabel[class="subheading"] {{
    font-size: {t.xxl}px;
    font-weight: {t.semibold};
    color: {palette.text_primary};
}}

QLabel[class="title"] {{
    font-size: {t.xl}px;
    font-weight: {t.semibold};
    color: {palette.text_primary};
}}

QLabel[class="body"] {{
    font-size: {t.base}px;
    font-weight: {t.regular};
    color: {palette.text_primary};
    line-height: 1.5;
}}

QLabel[class="body-small"] {{
    font-size: {t.sm}px;
    font-weight: {t.regular};
    color: {palette.text_secondary};
}}

QLabel[class="caption"] {{
    font-size: {t.xs}px;
    font-weight: {t.regular};
    color: {palette.text_disabled};
}}

QLabel[class="accent"] {{
    color: {palette.accent};
    font-weight: {t.medium};
}}

QLabel[class="success"] {{
    color: {palette.success};
    font-weight: {t.medium};
}}

QLabel[class="error"] {{
    color: {palette.error};
    font-weight: {t.medium};
}}

QLabel[class="warning"] {{
    color: {palette.warning};
    font-weight: {t.medium};
}}

/* ============================================================================
   INPUT FIELDS
   ============================================================================ */

QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {palette.surface};
    border: 2px solid {palette.border};
    border-radius: {r.md}px;
    padding: {s.sm}px {s.md}px;
    font-size: {t.base}px;
    color: {palette.text_primary};
    min-height: {tokens.button_height}px;
    selection-background-color: {palette.accent};
}}

QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {palette.border_focus};
}}

QLineEdit:disabled, QTextEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    background-color: {palette.surface_variant};
    color: {palette.text_disabled};
    border-color: {palette.border};
}}

QComboBox::drop-down {{
    border: none;
    width: 32px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {palette.text_secondary};
    width: 0;
    height: 0;
    margin-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {r.md}px;
    selection-background-color: {palette.accent};
    selection-color: {palette.text_on_accent};
    padding: {s.xs}px;
    outline: none;
}}

/* ============================================================================
   CARDS & PANELS
   ============================================================================ */

QFrame[class="card"] {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {r.lg}px;
    padding: {s.lg}px;
}}

QFrame[class="card-elevated"] {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {r.lg}px;
    padding: {s.lg}px;
}}

QFrame[class="panel"] {{
    background-color: {palette.surface_variant};
    border-radius: {r.lg}px;
    padding: {s.md}px;
}}

/* ============================================================================
   PROGRESS BARS
   ============================================================================ */

QProgressBar {{
    background-color: {palette.surface_variant};
    border: 1px solid {palette.border};
    border-radius: {r.full}px;
    height: 10px;
    text-align: center;
    color: {palette.text_on_accent};
    font-size: {t.xs}px;
    font-weight: {t.medium};
}}

QProgressBar::chunk {{
    background-color: {palette.accent};
    border-radius: {r.full}px;
}}

/* Progress bar with text - for mastered count */
QProgressBar[showText="true"] {{
    text-align: center;
    color: {palette.text_on_accent};
    font-size: {t.xs}px;
    font-weight: {t.medium};
}}

/* ============================================================================
   SLIDERS
   ============================================================================ */

QSlider::groove:horizontal {{
    background: {palette.surface_variant};
    height: 6px;
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background: {palette.accent};
    border: none;
    width: 20px;
    height: 20px;
    margin: -7px 0;
    border-radius: 10px;
}}

QSlider::handle:horizontal:hover {{
    background: {palette.accent_hover};
}}

QSlider::sub-page:horizontal {{
    background: {palette.accent};
    border-radius: 3px;
}}

/* ============================================================================
   TABS
   ============================================================================ */

QTabWidget::pane {{
    border: 1px solid {palette.border};
    border-radius: {r.md}px;
    background: {palette.surface};
    margin-top: -1px;
}}

QTabBar::tab {{
    background: transparent;
    color: {palette.text_secondary};
    padding: {s.sm}px {s.lg}px;
    border-radius: {r.md}px;
    font-size: {t.base}px;
    font-weight: {t.medium};
    min-width: 80px;
}}

QTabBar::tab:selected {{
    background: {palette.accent};
    color: {palette.text_on_accent};
}}

QTabBar::tab:hover:!selected {{
    background: {palette.surface_variant};
    color: {palette.text_primary};
}}

/* ============================================================================
   LIST & TREE VIEWS
   ============================================================================ */

QListView, QTreeView, QTableView {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {r.md}px;
    outline: none;
    show-decoration-selected: 1;
}}

QListView::item, QTreeView::item {{
    padding: {s.sm}px {s.md}px;
    border-radius: {r.sm}px;
    margin: {s.xs}px {s.sm}px;
}}

QListView::item:selected, QTreeView::item:selected {{
    background-color: {palette.accent};
    color: {palette.text_on_accent};
}}

QListView::item:hover:!selected, QTreeView::item:hover:!selected {{
    background-color: {palette.surface_variant};
}}

/* ============================================================================
   DIALOGS & MESSAGE BOXES
   ============================================================================ */

QDialog {{
    background-color: {palette.surface};
    border-radius: {r.xl}px;
}}

QMessageBox {{
    background-color: {palette.surface};
}}

QMessageBox QLabel {{
    color: {palette.text_primary};
    font-size: {t.base}px;
}}

QMessageBox QPushButton {{
    min-width: 80px;
}}

/* ============================================================================
   TOOLTIPS
   ============================================================================ */

QToolTip {{
    background-color: {palette.surface_elevated};
    color: {palette.text_primary};
    border: 1px solid {palette.border};
    border-radius: {r.md}px;
    padding: {s.sm}px {s.md}px;
    font-size: {t.sm}px;
}}

/* ============================================================================
   SEPARATORS
   ============================================================================ */

QFrame[class="separator"] {{
    background-color: {palette.divider};
    max-height: 1px;
    min-height: 1px;
    margin: {s.md}px 0;
}}

QFrame[class="separator-vertical"] {{
    background-color: {palette.divider};
    max-width: 1px;
    min-width: 1px;
    margin: 0 {s.md}px;
}}

/* ============================================================================
   CAMERA VIEW SPECIFIC
   ============================================================================ */

CameraView {{
    background-color: #000000;
    border-radius: {r.lg}px;
}}

CameraView[class="preview"] {{
    border: 2px solid {palette.border};
}}

CameraView[class="preview"][state="good"] {{
    border-color: {palette.success};
}}

CameraView[class="preview"][state="warning"] {{
    border-color: {palette.warning};
}}

CameraView[class="preview"][state="error"] {{
    border-color: {palette.error};
}}

/* Status banner */
QLabel[class="status-banner"] {{
    background-color: rgba(0, 0, 0, 0.7);
    color: {palette.text_primary};
    padding: {s.sm}px {s.md}px;
    border-radius: {r.md}px;
    font-size: {t.base}px;
    font-weight: {t.medium};
}}

QLabel[class="status-banner"][state="info"] {{
    background-color: rgba({int(palette.accent[1:3], 16)}, {int(palette.accent[3:5], 16)}, {int(palette.accent[5:7], 16)}, 0.9);
}}

QLabel[class="status-banner"][state="success"] {{
    background-color: rgba({int(palette.success[1:3], 16)}, {int(palette.success[3:5], 16)}, {int(palette.success[5:7], 16)}, 0.9);
}}

QLabel[class="status-banner"][state="error"] {{
    background-color: rgba({int(palette.error[1:3], 16)}, {int(palette.error[3:5], 16)}, {int(palette.error[5:7], 16)}, 0.9);
}}

QLabel[class="status-banner"][state="warning"] {{
    background-color: rgba({int(palette.warning[1:3], 16)}, {int(palette.warning[3:5], 16)}, {int(palette.warning[5:7], 16)}, 0.9);
}}

/* ============================================================================
   CONFIDENCE METER
   ============================================================================ */

ConfidenceMeter {{
    background-color: transparent;
}}

/* ============================================================================
   DWELL BUTTON
   ============================================================================ */

DwellButton {{
    background-color: transparent;
    border-radius: {r.full}px;
}}

DwellButton[class="primary"] {{
    background-color: {palette.accent};
}}

DwellButton[class="primary"]:hover {{
    background-color: {palette.accent_hover};
}}

/* ============================================================================
   BADGES / CHIPS
   ============================================================================ */

QLabel[class="chip"] {{
    background-color: {palette.surface_variant};
    color: {palette.text_secondary};
    padding: {s.xs}px {s.sm}px;
    border-radius: {r.full}px;
    font-size: {t.xs}px;
    font-weight: {t.medium};
}}

QLabel[class="chip"][type="difficulty-easy"] {{
    background-color: {palette.success_bg};
    color: {palette.success};
}}

QLabel[class="chip"][type="difficulty-medium"] {{
    background-color: {palette.warning_bg};
    color: {palette.warning};
}}

QLabel[class="chip"][type="difficulty-hard"] {{
    background-color: {palette.error_bg};
    color: {palette.error};
}}

QLabel[class="chip"][type="category"] {{
    background-color: {palette.accent};
    color: {palette.text_on_accent};
}}

/* ============================================================================
   ANIMATIONS (via QPropertyAnimation on properties)
   ============================================================================ */

/* Screen transitions handled in code via QStackedWidget animations */
"""


class ThemeManager:
    """Manages application theme state and stylesheet application."""

    _instance = None
    _mode: ThemeMode = ThemeMode.DARK

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def mode(self) -> ThemeMode:
        return self._mode

    @mode.setter
    def mode(self, value: ThemeMode):
        self._mode = value

    def toggle(self):
        self._mode = ThemeMode.LIGHT if self._mode == ThemeMode.DARK else ThemeMode.DARK

    def stylesheet(self) -> str:
        return generate_qss(self._mode)

    def palette(self) -> ColorPalette:
        return get_palette(self._mode)

    def tokens(self) -> DesignTokens:
        return get_tokens(self._mode)


# Global theme manager instance
theme_manager = ThemeManager()
