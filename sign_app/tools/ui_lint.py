#!/usr/bin/env python3
"""
UI Text-Fit Linter for Sign Language Learning App.
Checks for text clipping, overlapping widgets, and layout issues.
Run with: python tools/ui_lint.py --output docs/screenshots/lint
"""

import argparse
import os
import sys
from pathlib import Path

# Must be set before importing PySide6
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QFont, QFontMetrics

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from main import SignLanguageApp


class TextFitChecker:
    """Checks for text clipping and layout issues."""
    
    def __init__(self, app: QApplication):
        self.app = app
        self.failures = []
        self.warnings = []
        
    def check_widget(self, widget, path: str = "") -> list:
        """Recursively check a widget and its children for text clipping."""
        issues = []
        widget_path = f"{path}.{widget.objectName()}" if widget.objectName() else f"{path}[{type(widget).__name__}]"
        
        # Check QLabel text clipping
        if hasattr(widget, 'text') and callable(widget.text):
            text = widget.text()
            if text:
                issues.extend(self._check_label_clipping(widget, text, widget_path))
        
        # Check QPushButton text clipping
        if hasattr(widget, 'text') and callable(widget.text):
            text = widget.text()
            if text and widget.__class__.__name__ == 'QPushButton':
                if not widget.property("lint_ignore_clipped"):
                    issues.extend(self._check_button_clipping(widget, text, widget_path))
        
        # Check for fixed heights on text-containing widgets (skip QProgressBar and widgets with lint_ignore_fixed_height property)
        from PySide6.QtWidgets import QProgressBar
        if not isinstance(widget, QProgressBar) and not widget.property("lint_ignore_fixed_height") and widget.minimumHeight() > 0 and widget.maximumHeight() == widget.minimumHeight():
            if widget.height() > 0:
                issues.append({
                    'type': 'fixed_height',
                    'widget': widget_path,
                    'message': f"Widget has fixed height ({widget.height()}px) which may clip text",
                    'severity': 'warning'
                })
        
        # Check QScrollArea content clipping
        from PySide6.QtWidgets import QScrollArea
        if isinstance(widget, QScrollArea):
            issues.extend(self._check_scroll_area(widget, widget_path))
        
        # Check for overlapping siblings
        if widget.parent():
            issues.extend(self._check_overlapping(widget, widget_path))
        
        # Recurse into children
        from PySide6.QtWidgets import QWidget
        for child in widget.findChildren(QWidget):
            if child != widget:
                issues.extend(self.check_widget(child, widget_path))
        
        return issues
    
    def _check_label_clipping(self, label, text: str, path: str) -> list:
        """Check if label text is clipped."""
        issues = []
        # Only check QLabel widgets
        from PySide6.QtWidgets import QLabel
        if not isinstance(label, QLabel):
            return issues
        
        font = label.font()
        metrics = QFontMetrics(font)
        
        # Calculate required size
        if label.wordWrap():
            # Multi-line: need height for wrapped text
            avail_width = label.width()
            if avail_width > 0:
                bounding = metrics.boundingRect(0, 0, avail_width, 10000, Qt.TextWordWrap, text)
                required_height = bounding.height()
                actual_height = label.height()
                
                if required_height > actual_height + 2:  # Allow 2px tolerance
                    issues.append({
                        'type': 'text_clipped',
                        'widget': path,
                        'message': f"Label text clipped: needs {required_height}px height, has {actual_height}px",
                        'text_preview': text[:50] + ('...' if len(text) > 50 else ''),
                        'severity': 'error',
                        'needed_height': required_height,
                        'actual_height': actual_height
                    })
        else:
            # Single line: check width
            text_width = metrics.horizontalAdvance(text)
            if text_width > label.width() + 2:
                issues.append({
                    'type': 'text_clipped',
                    'widget': path,
                    'message': f"Label text clipped horizontally: needs {text_width}px width, has {label.width()}px",
                    'text_preview': text[:50] + ('...' if len(text) > 50 else ''),
                    'severity': 'error',
                    'needed_width': text_width,
                    'actual_width': label.width()
                })
        
        return issues
    
    def _check_button_clipping(self, button, text: str, path: str) -> list:
        """Check if button text is clipped."""
        issues = []
        font = button.font()
        metrics = QFontMetrics(font)
        text_width = metrics.horizontalAdvance(text)
        
        # Add padding for button
        padding = 24  # Typical button padding
        required_width = text_width + padding
        
        if required_width > button.width() + 2:
            issues.append({
                'type': 'button_clipped',
                'widget': path,
                'message': f"Button text clipped: needs {required_width}px width, has {button.width()}px",
                'text_preview': text[:50] + ('...' if len(text) > 50 else ''),
                'severity': 'error',
                'needed_width': required_width,
                'actual_width': button.width()
            })
        
        return issues
    
    def _check_scroll_area(self, scroll_area, path: str) -> list:
        """Check QScrollArea for content clipping."""
        issues = []
        widget = scroll_area.widget()
        if widget:
            content_height = widget.sizeHint().height()
            viewport_height = scroll_area.viewport().height()
            if content_height > viewport_height + 10:
                issues.append({
                    'type': 'scroll_content_clipped',
                    'widget': path,
                    'message': f"ScrollArea content ({content_height}px) exceeds viewport ({viewport_height}px) - needs scrolling",
                    'severity': 'warning'
                })
        return issues
    
    def _check_overlapping(self, widget, path: str) -> list:
        """Check for overlapping sibling widgets."""
        issues = []
        if not widget.parent():
            return issues
        
        from PySide6.QtWidgets import QStackedWidget
        
        # Skip if widget is a descendant of QStackedWidget (pages in stacked widget)
        ancestor = widget.parent()
        while ancestor:
            if isinstance(ancestor, QStackedWidget):
                return issues
            ancestor = ancestor.parent()
        
        parent = widget.parent()
        if isinstance(parent, QStackedWidget):
            # QStackedWidget intentionally stacks children - not an error
            return issues
        
        siblings = [w for w in parent.findChildren(widget.__class__) if w != widget]
        
        widget_rect = widget.geometry()
        for sibling in siblings:
            sibling_rect = sibling.geometry()
            if widget_rect.intersects(sibling_rect):
                # Allow small overlap (2px) for borders
                intersection = widget_rect.intersected(sibling_rect)
                if intersection.width() > 2 or intersection.height() > 2:
                    issues.append({
                        'type': 'overlapping_widgets',
                        'widget': path,
                        'message': f"Widget overlaps with {sibling.objectName() or sibling.__class__.__name__}: intersection {intersection.width()}x{intersection.height()}px",
                        'severity': 'warning'
                    })
        return issues


def run_lint(app: QApplication, output_dir: Path, sizes: list = None, themes: list = None) -> dict:
    """Run UI lint checks on all screens."""
    if sizes is None:
        sizes = [(1000, 650), (1280, 720), (1920, 1080)]
    if themes is None:
        themes = ['dark', 'light']
    
    # Use the passed app instance instead of creating a new one
    app_instance = SignLanguageApp.__new__(SignLanguageApp)
    app_instance.app = app
    app_instance.window = None
    app_instance.pipeline = None
    app_instance.content_loader = None
    app_instance.camera_service = None
    
    # Initialize components manually
    from app.data.db import init_db
    from app.content.loader import initialize_content_packs
    from app.core.pipeline import CorePipeline
    from app.core.camera_service import CameraService
    
    init_db()
    
    project_root = Path(__file__).resolve().parents[1]
    packs_dir = project_root / "content_packs"
    app_instance.content_loader = initialize_content_packs(packs_dir)
    
    app_instance.pipeline = CorePipeline()
    app_instance.pipeline.initialize(use_fake_camera=True)
    
    app_instance.camera_service = CameraService.instance()
    app_instance.camera_service.frame_ready.connect(app_instance.pipeline._on_frame_ready, Qt.DirectConnection)
    app_instance.camera_service.error_occurred.connect(app_instance.pipeline.error_occurred.emit)
    app_instance.camera_service.static_feed_detected.connect(
        lambda msg: app_instance.pipeline.camera_status_changed.emit(True, msg)
    )
    
    app_instance.window = None
    
    # Create screens manually without going through __init__
    from app.ui.main_window import MainWindow
    from app.ui.screens.welcome import WelcomeScreen
    from app.ui.screens.home import HomeScreen
    from app.ui.screens.lesson import LessonScreen
    from app.ui.screens.quiz import QuizScreen
    from app.ui.screens.dictionary import DictionaryScreen
    from app.ui.screens.progress import ProgressScreen
    from app.ui.screens.instructor import InstructorScreen
    from app.ui.screens.settings import SettingsScreen
    
    app_instance.window = MainWindow()
    app_instance.window.pipeline = app_instance.pipeline
    app_instance.window.camera_service = app_instance.camera_service
    
    screens = [
        ("welcome", WelcomeScreen(app_instance.window, app_instance.pipeline, app_instance.content_loader, app_instance.camera_service)),
        ("home", HomeScreen(app_instance.window, app_instance.content_loader, app_instance.camera_service)),
        ("lesson", LessonScreen(app_instance.window, app_instance.pipeline, app_instance.content_loader, app_instance.camera_service)),
        ("quiz", QuizScreen(app_instance.window, app_instance.pipeline, app_instance.content_loader, app_instance.camera_service)),
        ("dictionary", DictionaryScreen(app_instance.window, app_instance.pipeline, app_instance.content_loader, app_instance.camera_service)),
        ("progress", ProgressScreen(app_instance.window, app_instance.content_loader, app_instance.camera_service)),
        ("instructor", InstructorScreen(app_instance.window, app_instance.content_loader, app_instance.camera_service)),
        ("settings", SettingsScreen(app_instance.window, app_instance.pipeline, app_instance.content_loader, app_instance.camera_service)),
    ]
    
    for name, screen in screens:
        screen.set_main_window(app_instance.window)
        app_instance.window.register_screen(name, screen)
    
    app_instance.window.show()
    app.processEvents()
    
    all_results = {
        'passed': True,
        'total_checks': 0,
        'errors': 0,
        'warnings': 0,
        'results': {}
    }
    
    for theme_name in themes:
        from app.ui.theme import theme_manager, ThemeMode
        theme_mode = ThemeMode.DARK if theme_name == 'dark' else ThemeMode.LIGHT
        theme_manager.mode = theme_mode
        app.setStyleSheet(theme_manager.stylesheet())
        
        for width, height in sizes:
            app_instance.window.resize(width, height)
            app.processEvents()
            
            checker = TextFitChecker(app)
            all_issues = []
            
            # Check all screens
            for screen_name, screen in app_instance.window._screens.items():
                issues = checker.check_widget(screen, screen_name)
                all_issues.extend(issues)
            
            errors = [i for i in all_issues if i['severity'] == 'error']
            warnings = [i for i in all_issues if i['severity'] == 'warning']
            
            if errors or warnings:
                all_results['passed'] = False
            
            all_results['total_checks'] += len(all_issues)
            all_results['errors'] += len(errors)
            all_results['warnings'] += len(warnings)
            all_results['results'][f"{theme_name}_{width}x{height}"] = {
                'theme': theme_name,
                'size': f"{width}x{height}",
                'issues': all_issues,
                'error_count': len(errors),
                'warning_count': len(warnings)
            }
            
            if errors:
                print(f"  ❌ {len(errors)} errors found")
                for err in errors[:5]:
                    print(f"   - [{err['type']}] {err['widget']}: {err['message']}")
            if warnings:
                print(f"  ⚠️ {len(warnings)} warnings found")
                for warn in warnings[:3]:
                    print(f"   - [{warn['type']}] {warn['widget']}: {warn['message']}")
            if not errors and not warnings:
                print(f"  ✅ No issues")
    
    # Save detailed report
    import json
    report_path = output_dir / "lint_report.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print(f"\n📄 Report saved to {report_path}")
    print(f"\n📊 Summary: {all_results['total_checks']} checks, {all_results['errors']} errors, {all_results['warnings']} warnings")
    print(f"✅ PASSED" if all_results['passed'] else "❌ FAILED")
    
    return all_results


def main():
    parser = argparse.ArgumentParser(description="UI Text-Fit Linter")
    parser.add_argument("--output", default="docs/screenshots/lint", help="Output directory for reports")
    parser.add_argument("--sizes", nargs="+", type=str, default=["1000x650", "1280x720", "1920x1080"],
                        help="Screen sizes to test (WIDTHxHEIGHT)")
    parser.add_argument("--themes", nargs="+", default=["dark", "light"], help="Themes to test")
    args = parser.parse_args()
    
    output_dir = Path(args.output)
    sizes = [tuple(map(int, s.split('x'))) for s in args.sizes]
    
    app = QApplication.instance() or QApplication(sys.argv)
    
    try:
        results = run_lint(app, Path(args.output), sizes, args.themes)
        sys.exit(0 if results['passed'] else 1)
    finally:
        app.quit()


if __name__ == "__main__":
    main()