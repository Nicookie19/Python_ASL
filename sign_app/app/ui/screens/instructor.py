"""
Instructor dashboard - view learner progress and assign modules.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QDialog, QDialogButtonBox, QFormLayout, QDateEdit,
    QMessageBox, QFileDialog
)
from PySide6.QtGui import QFont
import csv
import logging
from datetime import date, datetime

from app.ui.main_window import ScreenBase
from app.ui.widgets import Card
from app.ui.theme import theme_manager
from app.data.db import (
    User, UserRole, Module, UserProgress,
    UserRepository, ModuleRepository, ProgressRepository,
    AssignmentRepository, InstructorAssignment
)

logger = logging.getLogger(__name__)


class AssignModuleDialog(QDialog):
    """Dialog for assigning a module to a learner."""

    def __init__(self, learners, modules, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Assign Module")
        self.setModal(True)
        self.setMinimumWidth(400)

        layout = QFormLayout(self)
        layout.setSpacing(16)

        self._learner_combo = QComboBox()
        for learner in learners:
            self._learner_combo.addItem(learner.name, learner.id)
        layout.addRow("Learner:", self._learner_combo)

        self._module_combo = QComboBox()
        for module in modules:
            self._module_combo.addItem(f"{module.name} ({module.category.value})", module.id)
        layout.addRow("Module:", self._module_combo)

        self._due_date = QDateEdit()
        self._due_date.setCalendarPopup(True)
        self._due_date.setDate(date.today())
        self._due_date.setSpecialValueText("No due date")
        layout.addRow("Due Date:", self._due_date)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_assignment(self):
        return {
            "learner_id": self._learner_combo.currentData(),
            "module_id": self._module_combo.currentData(),
            "due_date": self._due_date.date().toPython() if self._due_date.date().isValid() else None
        }


class InstructorScreen(ScreenBase):
    """Instructor dashboard showing learner progress and assignment tools."""

    def __init__(self, main_window, content_loader, camera_service):
        super().__init__(main_window)
        self._content_loader = content_loader
        self.camera_service = camera_service
        self._learners = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)

        # Title and actions
        header = QHBoxLayout()
        title = QLabel("Instructor Dashboard")
        title.setProperty("class", "heading")
        header.addWidget(title)

        header.addStretch()

        self._assign_btn = QPushButton("Assign Module")
        self._assign_btn.setProperty("class", "primary")
        self._assign_btn.clicked.connect(self._show_assign_dialog)
        header.addWidget(self._assign_btn)

        self._export_btn = QPushButton("Export CSV")
        self._export_btn.setProperty("class", "secondary")
        self._export_btn.clicked.connect(self._export_csv)
        header.addWidget(self._export_btn)

        layout.addLayout(header)

        # Learner table
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels([
            "Learner", "Modules Completed", "Overall Accuracy",
            "Current Streak", "Last Active", "Assignments"
        ])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.verticalHeader().setVisible(False)

        layout.addWidget(self._table, 1)

        # Assignments section
        assign_card = Card()
        assign_layout = assign_card.layout()

        assign_title = QLabel("Current Assignments")
        assign_title.setProperty("class", "title")
        assign_layout.addWidget(assign_title)

        self._assignments_table = QTableWidget()
        self._assignments_table.setColumnCount(5)
        self._assignments_table.setHorizontalHeaderLabels([
            "Learner", "Module", "Assigned", "Due Date", "Status"
        ])
        self._assignments_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._assignments_table.verticalHeader().setVisible(False)
        assign_layout.addWidget(self._assignments_table)

        layout.addWidget(assign_card)

    def on_show(self):
        self._refresh()

    def set_user(self, user: User):
        self._user = user
        if user.role != UserRole.INSTRUCTOR:
            # Hide instructor features for non-instructors
            self._assign_btn.hide()
            self._export_btn.hide()

    def _refresh(self):
        self._load_learners()
        self._load_assignments()

    def _load_learners(self):
        self._learners = UserRepository.get_learners()
        self._table.setRowCount(len(self._learners))

        for row, learner in enumerate(self._learners):
            # Get progress
            progress_list = ProgressRepository.get_all_progress(learner.id)
            completed = sum(1 for p in progress_list if p.completed)
            total = len(ModuleRepository.get_all())

            avg_accuracy = sum(p.accuracy for p in progress_list) / len(progress_list) if progress_list else 0
            streak = self._calculate_streak(learner.id)

            # Last active
            from app.data.db import get_thread_connection
            conn = get_thread_connection()
            last_row = conn.execute("""
                SELECT MAX(timestamp) as last FROM practice_attempts WHERE user_id = ?
            """, (learner.id,)).fetchone()
            last_active = "Never"
            if last_row and last_row['last']:
                last_active = last_row['last'][:10]

            # Assignments count
            assignments = AssignmentRepository.get_for_learner(learner.id)
            active_assignments = sum(1 for a in assignments if not a.completed)

            self._table.setItem(row, 0, QTableWidgetItem(learner.name))
            self._table.setItem(row, 1, QTableWidgetItem(f"{completed}/{total}"))
            self._table.setItem(row, 2, QTableWidgetItem(f"{int(avg_accuracy * 100)}%"))
            self._table.setItem(row, 3, QTableWidgetItem(f"{streak} days"))
            self._table.setItem(row, 4, QTableWidgetItem(last_active))
            self._table.setItem(row, 5, QTableWidgetItem(str(active_assignments)))

    def _load_assignments(self):
        assignments = AssignmentRepository.get_for_instructor(self._user.id)
        self._assignments_table.setRowCount(len(assignments))

        for row, assignment in enumerate(assignments):
            learner = UserRepository.get_by_id(assignment.learner_id)
            module = ModuleRepository.get_by_id(assignment.module_id)

            learner_name = learner.name if learner else "Unknown"
            module_name = module.name if module else "Unknown"

            due = assignment.due_date.isoformat() if assignment.due_date else "No due date"
            status = "Completed" if assignment.completed else "Pending"

            self._assignments_table.setItem(row, 0, QTableWidgetItem(learner_name))
            self._assignments_table.setItem(row, 1, QTableWidgetItem(module_name))
            self._assignments_table.setItem(row, 2, QTableWidgetItem(assignment.assigned_at[:10]))
            self._assignments_table.setItem(row, 3, QTableWidgetItem(due))
            self._assignments_table.setItem(row, 4, QTableWidgetItem(status))

    def _calculate_streak(self, user_id: int) -> int:
        from app.data.db import get_thread_connection
        from datetime import date, timedelta

        conn = get_thread_connection()
        rows = conn.execute("""
            SELECT DISTINCT date(timestamp) as d
            FROM practice_attempts
            WHERE user_id = ?
            ORDER BY d DESC
        """, (user_id,)).fetchall()

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

    def _show_assign_dialog(self):
        modules = ModuleRepository.get_all()
        dialog = AssignModuleDialog(self._learners, modules, self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_assignment()
            assignment = InstructorAssignment(
                id=0,
                instructor_id=self._user.id,
                learner_id=data["learner_id"],
                module_id=data["module_id"],
                assigned_at=datetime.now(),
                due_date=data["due_date"],
                completed=False
            )
            AssignmentRepository.create(assignment)
            self._refresh()

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Progress Report", "progress_report.csv", "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Learner", "Modules Completed", "Total Modules",
                    "Overall Accuracy", "Total Attempts",
                    "Current Streak", "Last Active", "Active Assignments"
                ])

                for learner in self._learners:
                    progress_list = ProgressRepository.get_all_progress(learner.id)
                    completed = sum(1 for p in progress_list if p.completed)
                    total = len(ModuleRepository.get_all())
                    avg_accuracy = sum(p.accuracy for p in progress_list) / len(progress_list) if progress_list else 0

                    from app.data.db import get_thread_connection
                    conn = get_thread_connection()
                    row = conn.execute("""
                        SELECT COUNT(*) as attempts, MAX(timestamp) as last
                        FROM practice_attempts WHERE user_id = ?
                    """, (learner.id,)).fetchone()

                    total_attempts = row['attempts'] if row else 0
                    last_active = row['last'][:10] if row and row['last'] else "Never"

                    assignments = AssignmentRepository.get_for_learner(learner.id)
                    active_assignments = sum(1 for a in assignments if not a.completed)

                    writer.writerow([
                        learner.name, completed, total,
                        f"{avg_accuracy:.1%}", total_attempts,
                        f"{self._calculate_streak(learner.id)} days",
                        last_active, active_assignments
                    ])

            QMessageBox.information(self, "Export Complete", f"Report saved to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def go_back(self):
        self._main_window._show_screen("home")