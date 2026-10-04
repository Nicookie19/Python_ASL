"""
Quiz screen - timed quiz with scoring and results.
"""

from PySide6.QtCore import Qt, Signal, QTimer, QTime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QProgressBar, QMessageBox, QSizePolicy
)
from PySide6.QtGui import QFont
import random
import logging

from app.ui.main_window import ScreenBase
from app.ui.widgets import CameraView, StatusBanner, ConfidenceMeter, ProgressRing, Chip
from app.ui.theme import theme_manager
from app.data.db import (
    Module, Sign, ModuleRepository, SignRepository, QuizRepository, QuizSession,
    QuizQuestion, AttemptRepository, PracticeAttempt, AttemptResult,
    UserProgress, ProgressRepository
)
from app.content.loader import ContentPackLoader
from app.core.pipeline import PipelineResult

logger = logging.getLogger(__name__)


class QuizScreen(ScreenBase):
    """
    Quiz mode: timed questions, random signs from module.
    Records accuracy, attempts, time per question.
    """

    def __init__(self, main_window, pipeline, content_loader, camera_service):
        super().__init__(main_window)
        self._pipeline = pipeline
        self._content_loader = content_loader
        self.camera_service = camera_service
        self._module: Module = None
        self._quiz_signs: list = []
        self._current_question = 0
        self._session: QuizSession = None
        self._question_start_time = 0
        self._question_time_limit = 15000  # 15 seconds per question
        self._timer = QTimer()
        self._timer.timeout.connect(self._on_timer_tick)
        self._hold_start_time = 0
        self._required_hold_ms = 1000

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Left: Camera view
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 8, 16)
        left_layout.setSpacing(12)

        # Quiz header
        header_layout = QHBoxLayout()
        self._quiz_title = QLabel("Quiz")
        self._quiz_title.setProperty("class", "heading")
        header_layout.addWidget(self._quiz_title)

        header_layout.addStretch()

        # Timer
        self._timer_label = QLabel("15s")
        self._timer_label.setProperty("class", "heading")
        self._timer_label.setStyleSheet("color: #F87171;")
        header_layout.addWidget(self._timer_label)

        left_layout.addLayout(header_layout)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setProperty("lint_ignore_fixed_height", True)
        left_layout.addWidget(self._progress_bar)

        # Question counter
        self._question_label = QLabel("Question 1 of 10")
        self._question_label.setProperty("class", "body")
        left_layout.addWidget(self._question_label)

        # Camera view
        self._camera_view = CameraView()
        self._camera_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_layout.addWidget(self._camera_view, 1)

        # Confidence meter
        self._confidence_meter = ConfidenceMeter()
        left_layout.addWidget(self._confidence_meter)

        # Target letter (large)
        self._target_label = QLabel("?")
        self._target_label.setProperty("class", "heading")
        self._target_label.setAlignment(Qt.AlignCenter)
        self._target_label.setStyleSheet("font-size: 96px; font-weight: 700;")
        left_layout.addWidget(self._target_label)

        main_layout.addWidget(left_panel, 7)

        # Right: Score panel
        right_panel = QWidget()
        right_panel.setFixedWidth(300)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(16)

        # Score display
        score_card = QFrame()
        score_card.setProperty("class", "card")
        score_layout = QVBoxLayout(score_card)
        score_layout.setAlignment(Qt.AlignCenter)
        score_layout.setSpacing(8)

        self._score_label = QLabel("Score: 0")
        self._score_label.setProperty("class", "heading")
        self._score_label.setAlignment(Qt.AlignCenter)
        score_layout.addWidget(self._score_label)

        self._accuracy_label = QLabel("Accuracy: 0%")
        self._accuracy_label.setProperty("class", "body")
        self._accuracy_label.setAlignment(Qt.AlignCenter)
        score_layout.addWidget(self._accuracy_label)

        right_layout.addWidget(score_card)

        # Question results
        self._results_label = QLabel("")
        self._results_label.setProperty("class", "body-small")
        self._results_label.setWordWrap(True)
        right_layout.addWidget(self._results_label)

        right_layout.addStretch()

        # End quiz button
        self._end_btn = QPushButton("End Quiz")
        self._end_btn.setProperty("class", "danger")
        self._end_btn.clicked.connect(self._confirm_end_quiz)
        right_layout.addWidget(self._end_btn)

        main_layout.addWidget(right_panel, 3)

    def prepare(self, module_id: str = None):
        """Start a new quiz for the given module."""
        self._module = ModuleRepository.get_by_id(module_id)
        if not self._module:
            return

        # Get scored signs from module
        pack = self._content_loader.get_current_pack()
        all_signs = []
        for sign_id in self._module.sign_ids:
            sign = SignRepository.get_by_id(sign_id)
            if sign and sign.scored:
                all_signs.append(sign)

        # Select 10 random signs (or fewer if not enough)
        num_questions = min(10, len(all_signs))
        self._quiz_signs = random.sample(all_signs, num_questions)

        # Start quiz session
        user = self._main_window.get_current_user()
        self._session = QuizRepository.start_session(user.id, self._module.id)

        self._current_question = 0
        self._load_question()
        self._pipeline.start()

    def _load_question(self):
        """Load current question."""
        if self._current_question >= len(self._quiz_signs):
            self._finish_quiz()
            return

        sign = self._quiz_signs[self._current_question]

        # Update UI
        self._quiz_title.setText(f"Quiz: {self._module.name}")
        self._question_label.setText(f"Question {self._current_question + 1} of {len(self._quiz_signs)}")
        self._target_label.setText(sign.label)
        self._progress_bar.setValue(int((self._current_question) / len(self._quiz_signs) * 100))

        # Set target for pipeline
        if sign.reference_landmarks:
            landmarks = np.array(sign.reference_landmarks, dtype=np.float32).reshape(21, 3)
            self._pipeline.set_target_sign(sign.id, landmarks)
        else:
            self._pipeline.set_target_sign(sign.id, None)

        # Start timer
        self._question_start_time = QTime.currentTime().msecsSinceStartOfDay()
        self._timer.start(100)  # Update every 100ms
        self._hold_start_time = 0

        self._results_label.setText("")

    def _on_timer_tick(self):
        """Update timer display."""
        elapsed = QTime.currentTime().msecsSinceStartOfDay() - self._question_start_time
        remaining = max(0, self._question_time_limit - elapsed)
        seconds = remaining / 1000
        self._timer_label.setText(f"{seconds:.1f}s")

        # Color code
        if remaining < 3000:
            self._timer_label.setStyleSheet("color: #F87171;")
        elif remaining < 6000:
            self._timer_label.setStyleSheet("color: #FBBF24;")
        else:
            self._timer_label.setStyleSheet("color: #4ADE80;")

        if remaining <= 0:
            self._on_timeout()

    def _on_pipeline_result(self, result: PipelineResult):
        """Handle pipeline result during quiz."""
        self._camera_view.set_frame(result.frame)

        # Update confidence meter
        label, confidence = result.confidence_meter
        is_stable = result.smoothed.is_stable if result.smoothed else False
        self._confidence_meter.set_values(label, confidence, is_stable)

        if self._current_question >= len(self._quiz_signs):
            return

        sign = self._quiz_signs[self._current_question]
        target_label = sign.label

        if result.recognition and result.recognition.is_reliable:
            predicted = result.recognition.label

            if predicted.upper() == target_label.upper():
                self._hold_start_time = getattr(self, '_hold_start_time', 0)
                import time
                now = time.time() * 1000

                if self._hold_start_time == 0:
                    self._hold_start_time = now
                elif now - self._hold_start_time >= self._required_hold_ms:
                    self._record_answer(sign, True, result.recognition.confidence)
            else:
                self._hold_start_time = 0

    def _record_answer(self, sign: Sign, correct: bool, confidence: float):
        """Record answer and move to next question."""
        self._timer.stop()

        elapsed = QTime.currentTime().msecsSinceStartOfDay() - self._question_start_time

        user = self._main_window.get_current_user()
        result = AttemptResult.CORRECT if correct else AttemptResult.INCORRECT

        # Record quiz question
        question = QuizQuestion(
            id=0,
            session_id=self._session.id,
            sign_id=sign.id,
            result=result,
            confidence=confidence,
            predicted_label=sign.label if correct else "wrong",
            time_ms=elapsed,
            sequence=self._current_question
        )
        QuizRepository.record_question(question)

        # Also record as practice attempt
        from datetime import datetime
        attempt = PracticeAttempt(
            id=0,
            user_id=user.id,
            sign_id=sign.id,
            module_id=self._module.id,
            result=result,
            confidence=confidence,
            predicted_label=sign.label if correct else "wrong",
            target_label=sign.label,
            duration_ms=elapsed,
            timestamp=datetime.now()
        )
        AttemptRepository.record(attempt)

        # Update session
        self._session.total_questions += 1
        if correct:
            self._session.correct_count += 1

        # Update UI
        self._update_score_display()

        # Show result briefly
        if correct:
            self._results_label.setText(f"✓ Correct! ({elapsed}ms)")
            self._results_label.setProperty("state", "success")
        else:
            self._results_label.setText(f"✗ Incorrect. Target: {sign.label}")
            self._results_label.setProperty("state", "error")

        # Move to next after brief delay
        QTimer.singleShot(1000, self._next_question)

    def _on_timeout(self):
        """Handle question timeout."""
        self._timer.stop()

        sign = self._quiz_signs[self._current_question]
        elapsed = self._question_time_limit

        # Record as timeout
        question = QuizQuestion(
            id=0,
            session_id=self._session.id,
            sign_id=sign.id,
            result=AttemptResult.TIMEOUT,
            confidence=0.0,
            predicted_label=None,
            time_ms=elapsed,
            sequence=self._current_question
        )
        QuizRepository.record_question(question)

        self._session.total_questions += 1

        self._results_label.setText(f"⏱ Time's up! Target: {sign.label}")
        self._results_label.setProperty("state", "warning")

        QTimer.singleShot(1000, self._next_question)

    def _next_question(self):
        self._current_question += 1
        self._load_question()

    def _update_score_display(self):
        if self._session.total_questions > 0:
            accuracy = self._session.correct_count / self._session.total_questions
            self._score_label.setText(f"Score: {self._session.correct_count}/{self._session.total_questions}")
            self._accuracy_label.setText(f"Accuracy: {int(accuracy * 100)}%")

    def _finish_quiz(self):
        """Finish quiz and show results."""
        self._timer.stop()
        self._pipeline.stop()
        self._pipeline.clear_target()

        # Calculate final stats
        total = self._session.total_questions
        correct = self._session.correct_count
        accuracy = correct / total if total > 0 else 0

        # Get question times for average
        from app.data.db import get_thread_connection
        conn = get_thread_connection()
        rows = conn.execute("""
            SELECT time_ms FROM quiz_questions WHERE session_id = ?
        """, (self._session.id,)).fetchall()

        avg_time = sum(r['time_ms'] for r in rows) / len(rows) if rows else 0

        # Find weakest signs
        weak_signs = []
        for row in rows:
            if row['result'] != 'correct':
                sign = SignRepository.get_by_id(row['sign_id'])
                if sign:
                    weak_signs.append(sign.label)

        self._session.completed_at = datetime.now()
        self._session.score = accuracy * 100
        self._session.avg_time_ms = avg_time
        self._session.weakest_signs = weak_signs[:3]

        QuizRepository.complete_session(self._session)

        # Update module progress
        self._update_module_progress()

        # Show results screen
        self._show_results_screen()

    def _update_module_progress(self):
        """Update module progress with quiz results."""
        from datetime import datetime
        user = self._main_window.get_current_user()
        progress = ProgressRepository.get_progress(user.id, self._module.id)

        if not progress:
            progress = UserProgress(
                user_id=user.id,
                module_id=self._module.id,
                completed=False,
                completed_at=None,
                accuracy=self._session.correct_count / self._session.total_questions,
                attempts=self._session.total_questions,
                best_streak=0,
                current_streak=0,
                last_practiced_at=datetime.now()
            )
        else:
            total_attempts = progress.attempts + self._session.total_questions
            total_correct = progress.accuracy * progress.attempts + self._session.correct_count
            progress.accuracy = total_correct / total_attempts if total_attempts > 0 else 0
            progress.attempts = total_attempts
            progress.last_practiced_at = datetime.now()

        ProgressRepository.update_progress(progress)

    def _show_results_screen(self):
        """Show quiz results overlay."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox

        dialog = QDialog(self)
        dialog.setWindowTitle("Quiz Complete!")
        dialog.setModal(True)
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(16)

        # Score
        score_card = QFrame()
        score_card.setProperty("class", "card-elevated")
        score_layout = QVBoxLayout(score_card)
        score_layout.setAlignment(Qt.AlignCenter)

        accuracy = self._session.score
        score_label = QLabel(f"{int(accuracy)}%")
        score_label.setProperty("class", "heading")
        score_label.setStyleSheet(f"font-size: 64px; color: {theme_manager.palette().success if accuracy >= 70 else theme_manager.palette().warning if accuracy >= 50 else theme_manager.palette().error};")
        score_label.setAlignment(Qt.AlignCenter)
        score_layout.addWidget(score_label)

        detail = QLabel(f"{self._session.correct_count} of {self._session.total_questions} correct")
        detail.setProperty("class", "body")
        detail.setAlignment(Qt.AlignCenter)
        score_layout.addWidget(detail)

        avg_time = self._session.avg_time_ms / 1000
        time_label = QLabel(f"Average time: {avg_time:.1f}s per question")
        time_label.setProperty("class", "caption")
        time_label.setAlignment(Qt.AlignCenter)
        score_layout.addWidget(time_label)

        layout.addWidget(score_card)

        # Weak signs
        if self._session.weakest_signs:
            weak_label = QLabel("Practice these:")
            weak_label.setProperty("class", "title")
            layout.addWidget(weak_label)

            for sign_label in self._session.weakest_signs:
                chip = Chip(sign_label, "error")
                layout.addWidget(chip, alignment=Qt.AlignCenter)

            retry_btn = QPushButton("Retry Weak Signs")
            retry_btn.setProperty("class", "primary")
            retry_btn.clicked.connect(lambda: self._retry_weak_signs(dialog))
            layout.addWidget(retry_btn)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)

        dialog.exec()

    def _retry_weak_signs(self, dialog):
        dialog.accept()
        # Filter quiz signs to only weak ones
        weak_sign_ids = []
        for sign in self._quiz_signs:
            if sign.label in self._session.weakest_signs:
                weak_sign_ids.append(sign.id)

        # Could create a custom quiz with just these signs
        # For now, just restart the quiz
        self.prepare(self._module.id)

    def _confirm_end_quiz(self):
        reply = QMessageBox.question(
            self, "End Quiz?",
            "Are you sure you want to end the quiz early?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._finish_quiz()

    def go_back(self):
        self._timer.stop()
        self._pipeline.stop()
        self._pipeline.clear_target()
        self._main_window._show_screen("home")

    def on_show(self):
        pass
