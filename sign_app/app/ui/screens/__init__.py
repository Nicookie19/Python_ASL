"""
Screen modules
"""

from app.ui.screens.welcome import WelcomeScreen, CameraCheckWidget
from app.ui.screens.home import HomeScreen, ModuleCard, ContinueCard, StatCard
from app.ui.screens.lesson import LessonScreen, ReferenceAnimation
from app.ui.screens.quiz import QuizScreen
from app.ui.screens.dictionary import DictionaryScreen
from app.ui.screens.progress import ProgressScreen, AccuracyChart, MasteryHeatmap, StreakCalendar
from app.ui.screens.instructor import InstructorScreen, AssignModuleDialog
from app.ui.screens.settings import SettingsScreen

__all__ = [
    "WelcomeScreen",
    "CameraCheckWidget",
    "HomeScreen",
    "ModuleCard",
    "ContinueCard",
    "StatCard",
    "LessonScreen",
    "ReferenceAnimation",
    "QuizScreen",
    "DictionaryScreen",
    "ProgressScreen",
    "AccuracyChart",
    "MasteryHeatmap",
    "StreakCalendar",
    "InstructorScreen",
    "AssignModuleDialog",
    "SettingsScreen",
]