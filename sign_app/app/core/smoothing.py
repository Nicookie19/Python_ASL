"""
Temporal smoothing for recognition results.
Prevents flicker by requiring consistent predictions over time.
"""

from collections import deque
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
import numpy as np
import time


@dataclass
class SmoothedPrediction:
    """Result of temporal smoothing."""
    label: str
    confidence: float
    is_stable: bool
    stability_score: float  # 0-1, how consistent recent predictions are
    all_recent: List[Tuple[str, float]]  # Recent (label, confidence) pairs


class TemporalSmoother:
    """
    Smooths recognition predictions over time using a sliding window.
    Requires consistent predictions above confidence threshold for N frames.
    """

    def __init__(
        self,
        window_size: int = 5,
        min_confidence: float = 0.7,
        stability_threshold: float = 0.6,  # Fraction of window that must agree
        min_frames_for_stable: int = 3
    ):
        self.window_size = window_size
        self.min_confidence = min_confidence
        self.stability_threshold = stability_threshold
        self.min_frames_for_stable = min_frames_for_stable

        self._buffer: deque[Tuple[str, float, float]] = deque(maxlen=window_size)  # (label, confidence, timestamp)
        self._last_stable_label: Optional[str] = None
        self._stable_start_time: Optional[float] = None

    def update(self, label: str, confidence: float) -> SmoothedPrediction:
        """
        Update with new prediction and return smoothed result.
        """
        now = time.time()
        self._buffer.append((label, confidence, now))

        # Filter to high-confidence predictions only
        high_conf = [(l, c) for l, c, _ in self._buffer if c >= self.min_confidence]

        if not high_conf:
            return SmoothedPrediction(
                label="unknown",
                confidence=0.0,
                is_stable=False,
                stability_score=0.0,
                all_recent=list(self._buffer)
            )

        # Count labels
        label_counts: Dict[str, int] = {}
        label_confidences: Dict[str, List[float]] = {}
        for l, c in high_conf:
            label_counts[l] = label_counts.get(l, 0) + 1
            label_confidences.setdefault(l, []).append(c)

        # Find most common label
        most_common_label = max(label_counts, key=label_counts.get)
        count = label_counts[most_common_label]
        avg_confidence = np.mean(label_confidences[most_common_label])

        # Stability score: fraction of high-conf predictions that agree
        stability_score = count / len(high_conf) if high_conf else 0.0

        # Check if stable
        is_stable = (
            count >= self.min_frames_for_stable and
            stability_score >= self.stability_threshold and
            avg_confidence >= self.min_confidence
        )

        if is_stable:
            self._last_stable_label = most_common_label
            if self._stable_start_time is None:
                self._stable_start_time = now
        else:
            self._stable_start_time = None

        return SmoothedPrediction(
            label=most_common_label if is_stable else "unknown",
            confidence=avg_confidence if is_stable else 0.0,
            is_stable=is_stable,
            stability_score=stability_score,
            all_recent=[(l, c) for l, c, _ in self._buffer]
        )

    def reset(self) -> None:
        """Clear the buffer."""
        self._buffer.clear()
        self._last_stable_label = None
        self._stable_start_time = None

    def get_stable_duration(self) -> float:
        """Get duration (seconds) that current label has been stable."""
        if self._stable_start_time is not None:
            return time.time() - self._stable_start_time
        return 0.0


class ConfidenceMeter:
    """
    Visual confidence meter with smoothing for UI display.
    Provides a smoothed confidence value that doesn't jump around.
    """

    def __init__(self, smoothing_factor: float = 0.3):
        self.smoothing_factor = smoothing_factor
        self._smoothed_confidence: float = 0.0
        self._current_label: str = "unknown"

    def update(self, label: str, confidence: float, is_stable: bool) -> Tuple[str, float]:
        """
        Update meter and return display values.
        """
        if is_stable and label != "unknown":
            # Smooth the confidence for stable predictions
            self._smoothed_confidence = (
                self.smoothing_factor * confidence +
                (1 - self.smoothing_factor) * self._smoothed_confidence
            )
            self._current_label = label
        else:
            # Decay confidence when not stable
            self._smoothed_confidence *= 0.9
            if self._smoothed_confidence < 0.1:
                self._current_label = "unknown"

        return self._current_label, self._smoothed_confidence

    def reset(self) -> None:
        self._smoothed_confidence = 0.0
        self._current_label = "unknown"


class DwellDetector:
    """
    Detects dwell (hover) for hand-driven UI.
    Tracks index fingertip position and triggers after hold duration.
    """

    def __init__(
        self,
        dwell_time_ms: int = 2000,
        max_movement_px: int = 30
    ):
        self.dwell_time_ms = dwell_time_ms
        self.max_movement_px = max_movement_px

        self._start_pos: Optional[Tuple[float, float]] = None
        self._start_time: Optional[float] = None
        self._is_active = False
        self._progress = 0.0
        self._target_widget: Optional[str] = None

    def update(self, fingertip_pos: Tuple[float, float], widget_id: Optional[str]) -> Tuple[bool, float]:
        """
        Update dwell state with new fingertip position.
        Returns (triggered, progress 0-1).
        """
        now = time.time() * 1000  # ms

        # If widget changed or no widget, reset
        if widget_id != self._target_widget or widget_id is None:
            self._reset()
            self._target_widget = widget_id
            if widget_id is not None:
                self._start_pos = fingertip_pos
                self._start_time = now
            return False, 0.0

        # First time on this widget
        if self._start_time is None:
            self._start_pos = fingertip_pos
            self._start_time = now
            return False, 0.0

        # Check movement
        if self._start_pos is not None:
            dx = fingertip_pos[0] - self._start_pos[0]
            dy = fingertip_pos[1] - self._start_pos[1]
            movement = np.sqrt(dx*dx + dy*dy)

            if movement > self.max_movement_px:
                self._reset()
                self._start_pos = fingertip_pos
                self._start_time = now
                return False, 0.0

        # Calculate progress
        elapsed = now - self._start_time
        self._progress = min(elapsed / self.dwell_time_ms, 1.0)

        triggered = False
        if self._progress >= 1.0:
            triggered = True
            self._reset()

        return triggered, self._progress

    def _reset(self) -> None:
        self._start_pos = None
        self._start_time = None
        self._progress = 0.0

    def get_progress(self) -> float:
        return self._progress

    def is_active(self) -> bool:
        return self._start_time is not None