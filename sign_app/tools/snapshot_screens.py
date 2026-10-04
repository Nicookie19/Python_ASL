#!/usr/bin/env python3
"""Capture deterministic UI snapshots without opening a webcam.

Run from ``sign_app``:
    python tools/snapshot_screens.py --output docs/screenshots/after
"""

import argparse
import os
import sys
from pathlib import Path

# Must be set before importing PySide6.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import QCoreApplication
from main import SignLanguageApp
from app.ui.theme import ThemeMode, theme_manager


SIZES = ((1000, 650), (1280, 720), (1920, 1080))
SCREENS = ("home", "dictionary", "progress", "settings", "lesson", "quiz")


def show_screen(application: SignLanguageApp, name: str) -> None:
    if name in {"lesson", "quiz"}:
        application.window.show_screen(name, module_id="asl_fingerspelling_1")
    else:
        application.window.show_screen(name)
    QCoreApplication.processEvents()


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture all application screens using FakeCamera")
    parser.add_argument("--output", default="docs/screenshots/after", help="Destination relative to project root")
    args = parser.parse_args()
    output = (PROJECT_ROOT / args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    application = SignLanguageApp(use_fake_camera=True)
    application.window.show()

    try:
        for mode in (ThemeMode.DARK, ThemeMode.LIGHT):
            theme_manager.mode = mode
            application.app.setStyleSheet(theme_manager.stylesheet())
            for width, height in SIZES:
                application.window.resize(width, height)
                for screen in SCREENS:
                    show_screen(application, screen)
                    QCoreApplication.processEvents()
                    path = output / f"{screen}_{width}x{height}_{mode.value}.png"
                    application.window.grab().save(str(path), "PNG")
                    print(path.relative_to(PROJECT_ROOT))
    finally:
        application.pipeline.cleanup()
        application.window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
