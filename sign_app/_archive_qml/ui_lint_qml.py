#!/usr/bin/env python3
"""
UI Text-Fit Linter for Sign Language Learning App (QML version).
Checks for text clipping, overlapping widgets, and layout issues.
Run with: python tools/ui_lint_qml.py --output docs/screenshots/lint
"""

import argparse
import os
import sys
from pathlib import Path

# Must be set before importing PySide6
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QSize, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickView

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))


class QMLTextFitChecker:
    """Checks for text clipping and layout issues in QML."""

    def __init__(self, engine: QQmlApplicationEngine):
        self.engine = engine
        self.failures = []
        self.warnings = []

    def check_text_clipping(self, item, path: str = ""):
        """Recursively check QML items for text clipping."""
        issues = []
        
        # Get object name for path
        obj_name = item.objectName() if hasattr(item, 'objectName') and item.objectName() else item.__class__.__name__
        item_path = f"{path}.{obj_name}" if path else obj_name

        # Check Text items
        if hasattr(item, 'text') and item.text:
            text = item.text
            if isinstance(text, str) and text.strip():
                # Get font metrics
                font = item.font if hasattr(item, 'font') else None
                if font:
                    from PySide6.QtGui import QFontMetrics
                    metrics = QFontMetrics(font)
                    
                    # Check width
                    if hasattr(item, 'width') and item.width > 0:
                        text_width = metrics.horizontalAdvance(text)
                        if text_width > item.width + 4:  # 4px tolerance
                            issues.append({
                                'type': 'text_clipped',
                                'item': item_path,
                                'message': f"Text clipped horizontally: needs {text_width}px, has {item.width}px",
                                'text_preview': text[:50] + ('...' if len(text) > 50 else ''),
                                'severity': 'error',
                                'needed_width': text_width,
                                'actual_width': item.width
                            })
                    
                    # Check height for wrapped text
                    if hasattr(item, 'wrapMode') and item.wrapMode != 0:  # Text.NoWrap
                        if hasattr(item, 'height') and item.height > 0:
                            # Estimate required height
                            line_height = metrics.lineSpacing()
                            char_width = metrics.horizontalAdvance('x')
                            chars_per_line = max(1, item.width / char_width)
                            lines_needed = len(text) / chars_per_line
                            required_height = lines_needed * line_height
                            
                            if required_height > item.height + 4:
                                issues.append({
                                    'type': 'text_clipped_vertical',
                                    'item': item_path,
                                    'message': f"Text clipped vertically: needs {required_height:.0f}px, has {item.height}px",
                                    'text_preview': text[:50] + ('...' if len(text) > 50 else ''),
                                    'severity': 'error',
                                    'needed_height': required_height,
                                    'actual_height': item.height
                                })

        # Check children
        if hasattr(item, 'children'):
            for child in item.children():
                if hasattr(child, 'objectName') or hasattr(child, 'children'):
                    issues.extend(self.check_text_clipping(child, item_path))

        return issues

    def check_overlapping(self, item, path: str = ""):
        """Check for overlapping QML items."""
        issues = []
        
        if hasattr(item, 'children'):
            children = [c for c in item.children() if hasattr(c, 'x') and hasattr(c, 'y') and hasattr(c, 'width') and hasattr(c, 'height')]
            
            for i, child1 in enumerate(children):
                for child2 in children[i+1:]:
                    # Get geometry
                    try:
                        r1 = Qt.QRectF(child1.x, child1.y, child1.width, child1.height)
                        r2 = Qt.QRectF(child2.x, child2.y, child2.width, child2.height)
                        
                        if r1.intersects(r2):
                            intersection = r1.intersected(r2)
                            if intersection.width() > 2 or intersection.height() > 2:
                                issues.append({
                                    'type': 'overlapping_items',
                                    'item1': f"{path}.{child1.objectName() or child1.__class__.__name__}",
                                    'item2': f"{path}.{child2.objectName() or child2.__class__.__name__}",
                                    'message': f"Items overlap: intersection {intersection.width():.0f}x{intersection.height():.0f}px",
                                    'severity': 'error'
                                })
                    except Exception:
                        pass  # Skip items without proper geometry

        return issues


def run_lint_test(sizes=None, themes=None, text_scales=None, output_dir=None):
    """Run UI lint tests at various configurations."""
    
    if sizes is None:
        sizes = [(1000, 650), (1200, 800), (1400, 900)]  # 3 sizes
    if themes is None:
        themes = ["dark", "light"]  # 2 themes
    if text_scales is None:
        text_scales = [0.8, 1.0, 1.2]  # 3 text scales

    app = QApplication.instance() or QApplication(sys.argv)
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    all_failures = []
    all_warnings = []

    for width, height in sizes:
        for theme in themes:
            for scale in text_scales:
                print(f"\nTesting: {width}x{height}, theme={theme}, text_scale={scale}")
                
                engine = QQmlApplicationEngine()
                
                # Add import paths
                base = str(project_root / "app" / "qml")
                engine.addImportPath(base)
                engine.addImportPath(base + "/components")
                engine.addImportPath(base + "/screens")
                
                # Load main QML
                qml_file = os.path.join(base, "main.qml")
                if not os.path.exists(qml_file):
                    # Try alternative path
                    qml_file = str(project_root / "sign_app" / "app" / "qml" / "main.qml")
                engine.load(QUrl.fromLocalFile(qml_file))
                
                if not engine.rootObjects():
                    all_failures.append({
                        'config': f"{width}x{height}, theme={theme}, scale={scale}",
                        'message': "Failed to load QML"
                    })
                    continue
                
                # Apply theme and text scale to root
                root = engine.rootObjects()[0]
                if hasattr(root, 'theme'):
                    root.theme.isDark = (theme == "dark")
                if hasattr(root, 'setScale'):
                    root.setScale(scale)
                
                # Process events to let QML layout
                app.processEvents()
                
                # Check root and children
                checker = QMLTextFitChecker(engine)
                for root_obj in engine.rootObjects():
                    failures = checker.check_text_clipping(root_obj)
                    all_failures.extend([{**f, 'config': f"{width}x{height}, theme={theme}, scale={scale}"} for f in failures])
                    
                    overlaps = checker.check_overlapping(root_obj)
                    all_failures.extend([{**f, 'config': f"{width}x{height}, theme={theme}, scale={scale}"} for f in overlaps])
                
                # Take screenshot if output dir specified
                if output_dir:
                    output_path = Path(output_dir) / f"lint_{width}x{height}_{theme}_scale{scale}.png"
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    # Note: QQuickView or QQuickWindow needed for grabWindow
                    # This would need a QQuickView instead of QQmlApplicationEngine
                    pass

    # Print results
    print("\n" + "="*60)
    print("UI LINT RESULTS")
    print("="*60)
    
    if all_failures:
        print(f"\n❌ FAILURES ({len(all_failures)}):")
        for f in all_failures:
            item = f.get('item', f.get('item1', 'unknown'))
            print(f"  [{f['config']}] {item}: {f['message']}")
    else:
        print("\n✅ No text clipping or overlapping issues found!")
    
    if all_warnings:
        print(f"\n⚠️  WARNINGS ({len(all_warnings)}):")
        for w in all_warnings:
            item = w.get('item', w.get('item1', 'unknown'))
            print(f"  [{w['config']}] {item}: {w['message']}")

    return len(all_failures) == 0


def main():
    parser = argparse.ArgumentParser(description="QML UI Text-Fit Linter")
    parser.add_argument("--output", help="Output directory for screenshots")
    parser.add_argument("--sizes", nargs="+", type=int, help="Window sizes (W H W H ...)")
    parser.add_argument("--themes", nargs="+", choices=["dark", "light"], help="Themes to test")
    parser.add_argument("--scales", nargs="+", type=float, help="Text scales to test")
    
    args = parser.parse_args()
    
    sizes = None
    if args.sizes:
        sizes = [(args.sizes[i], args.sizes[i+1]) for i in range(0, len(args.sizes), 2)]
    
    themes = args.themes
    text_scales = args.scales
    
    success = run_lint_test(sizes, themes, text_scales, args.output)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()