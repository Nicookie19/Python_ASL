"""
Performance HUD widget for real-time performance monitoring.
Toggle with Ctrl+Shift+D or from Settings.
"""

import time
from collections import deque
from PySide6.QtCore import Qt, Signal, QTimer, QRect
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox

from app.ui.theme import theme_manager


class PerfHUD(QWidget):
    """
    Performance HUD overlay showing real-time performance metrics.
    Toggle with Ctrl+Shift+D or from Settings.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        
        # Data sources (updated externally)
        self._capture_fps = 0.0
        self._display_fps = 0.0
        self._inference_fps = 0.0
        self._inference_avg_ms = 0.0
        self._inference_p95_ms = 0.0
        self._ui_paint_ms = 0.0
        self._latency_ms = 0.0
        self._dropped_frames = 0
        
        # UI thread watchdog
        self._watchdog_max_lateness = 0.0
        self._watchdog_timer = QTimer(self)
        self._watchdog_timer.timeout.connect(self._watchdog_tick)
        self._watchdog_timer.start(16)  # 60 Hz
        self._last_watchdog = time.perf_counter()
        
        # Layout
        self._setup_ui()
        
        # Hide by default
        self.hide()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        
        # Title bar
        title_layout = QHBoxLayout()
        title = QLabel("⚡ Performance HUD")
        title.setStyleSheet("font-weight: bold; color: #22D3EE;")
        title_layout.addWidget(title)
        title_layout.addStretch()
        
        close_btn = QLabel("✕")
        close_btn.setStyleSheet("color: #71717A; font-size: 14px;")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.mousePressEvent = lambda e: self.hide()
        title_layout.addWidget(close_btn)
        self.layout().addLayout(title_layout)
        
        # Metrics grid
        self._metrics_labels = {}
        metrics = [
            ("Capture FPS", "_capture_fps", "{:.1f}"),
            ("Display FPS", "_display_fps", "{:.1f}"),
            ("Inference FPS", "_inference_fps", "{:.1f}"),
            ("Inference Avg (ms)", "_inference_avg_ms", "{:.1f}"),
            ("Inference P95 (ms)", "_inference_p95_ms", "{:.1f}"),
            ("UI Paint (ms)", "_ui_paint_ms", "{:.1f}"),
            ("Latency (ms)", "_latency_ms", "{:.1f}"),
            ("Dropped Frames", "_dropped_frames", "{}"),
            ("Max UI Lateness (ms)", "_watchdog_max_lateness", "{:.1f}"),
        ]
        
        for label, attr, fmt in metrics:
            row = QHBoxLayout()
            row.setSpacing(8)
            
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #A1A1AA; font-size: 12px;")
            row.addWidget(lbl)
            row.addStretch()
            
            val = QLabel("—")
            val.setStyleSheet("color: #FAFAFA; font-size: 12px; font-weight: bold; font-family: monospace;")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(val)
            self._metrics_labels[attr] = (val, fmt)
            self.layout().addLayout(row)
        
        # Styling
        self.setStyleSheet("""
            PerfHUD {
                background-color: rgba(24, 24, 27, 0.95);
                border: 1px solid #3F3F46;
                border-radius: 12px;
            }
        """)
        
        self.setFixedWidth(280)
        
    def _watchdog_tick(self):
        """UI thread watchdog - detects event loop blocking."""
        now = time.perf_counter()
        elapsed = (now - self._last_watchdog) * 1000  # ms
        expected = 16.67  # 60 Hz = 16.67ms
        lateness = max(0, elapsed - expected * 1.5)  # Allow 1.5x margin
        if lateness > self._watchdog_max_lateness:
            self._watchdog_max_lateness = lateness
        self._last_watchdog = now
        
    def update_metrics(self, **kwargs):
        """Update displayed metrics."""
        for key, value in kwargs.items():
            if key in self._metrics_labels:
                label, fmt = self._metrics_labels[key]
                setattr(self, key, value)
                label.setText(fmt.format(value))
                
                # Color coding for critical metrics
                if key == "_display_fps" and value < 25:
                    label.setStyleSheet("color: #F87171; font-size: 12px; font-weight: bold; font-family: monospace;")
                elif key == "_inference_avg_ms" and value > 50:
                    label.setStyleSheet("color: #F87171; font-size: 12px; font-weight: bold; font-family: monospace;")
                elif key == "_watchdog_max_lateness" and value > 50:
                    label.setStyleSheet("color: #F87171; font-size: 12px; font-weight: bold; font-family: monospace;")
                else:
                    label.setStyleSheet("color: #FAFAFA; font-size: 12px; font-weight: bold; font-family: monospace;")
    
    def show_hud(self):
        """Show HUD at top-right of parent."""
        if self.parent():
            parent_rect = self.parent().rect()
            global_pos = self.parent().mapToGlobal(self.parent().rect().topRight())
            self.move(global_pos.x() - self.width() - 20, global_pos.y() + 20)
        self.show()
        self.raise_()
        
    def hide_hud(self):
        self.hide()
        
    def toggle(self):
        if self.isVisible():
            self.hide()
        else:
            self.show_hud()


class PerfHUDManager:
    """Manages the PerfHUD singleton and keyboard shortcut."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls, parent=None):
        if cls._instance is None:
            cls._instance = PerfHUD(parent)
        return cls._instance
    
    @classmethod
    def toggle(cls):
        if cls._instance:
            cls._instance.toggle()
        else:
            # Can't toggle if not created yet
            pass