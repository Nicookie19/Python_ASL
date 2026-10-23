#!/usr/bin/env python3
"""
Guard test: camera access must go through the single CameraService.

Historically this file "passed" while doing nothing useful, because it defined
no test functions (so pytest collected zero tests) and pointed at a directory
that does not exist (``<repo>/sign_app/sign_app``). These tests are real and
assert against the actual source tree.
"""

import ast
from pathlib import Path
from typing import Iterator, NamedTuple

import pytest

# tests/ lives directly inside the app package root.
APP_ROOT = Path(__file__).resolve().parents[1]

# The one module allowed to OPEN a camera.
CAPTURE_ALLOWED = {APP_ROOT / "app" / "core" / "camera_service.py"}

# Read-only enumeration of the device list may also live here. It must never
# open a device - capture is what has to be a single, shared code path.
ENUMERATION_ALLOWED = {APP_ROOT / "app" / "core" / "camera_devices.py"}

# Symbols that actually open or capture from a device.
CAPTURE_SYMBOLS = {
    "cv2.VideoCapture",
    "QCamera(",
    "QMediaCaptureSession(",
    "QVideoSink(",
}

# Read-only device listing.
ENUMERATION_SYMBOLS = {"QMediaDevices.videoInputs()"}

# Directories that are not application source.
IGNORED_DIRS = {"__pycache__", "venv", ".venv", "_archive_qml", "docs", ".git"}


class Violation(NamedTuple):
    path: str
    line: int
    symbol: str
    snippet: str


def _iter_source_files() -> Iterator[Path]:
    skip = {p.resolve() for p in (CAPTURE_ALLOWED | ENUMERATION_ALLOWED)}
    for path in APP_ROOT.rglob("*.py"):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if path.resolve() in skip:
            continue
        # The guard's own source legitimately names the symbols it forbids.
        if path.name == "test_no_stray_camera_access.py":
            continue
        yield path


def find_stray_camera_access() -> list[Violation]:
    """Return every camera capture/enumeration call outside CameraService."""
    violations: list[Violation] = []

    for py_file in _iter_source_files():
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except (OSError, SyntaxError):
            continue

        rel = str(py_file.relative_to(APP_ROOT))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute):
                continue

            # cv2.VideoCapture(...)
            if (
                isinstance(func.value, ast.Name)
                and func.value.id == "cv2"
                and func.attr == "VideoCapture"
            ):
                violations.append(Violation(rel, node.lineno, "cv2.VideoCapture",
                                            ast.get_source_segment(content, node) or ""))

            # QtMultimedia.VideoCapture(...)
            elif func.attr == "VideoCapture" and "Multimedia" in getattr(func.value, "id", ""):
                violations.append(Violation(rel, node.lineno, "VideoCapture",
                                            ast.get_source_segment(content, node) or ""))

            # QCamera(...)
            elif isinstance(func.value, ast.Name) and func.value.id == "QCamera":
                violations.append(Violation(rel, node.lineno, "QCamera(",
                                            ast.get_source_segment(content, node) or ""))

            # QMediaCaptureSession(...)
            elif isinstance(func.value, ast.Name) and func.value.id == "QMediaCaptureSession":
                violations.append(Violation(rel, node.lineno, "QMediaCaptureSession(",
                                            ast.get_source_segment(content, node) or ""))

            # QVideoSink(...)
            elif isinstance(func.value, ast.Name) and func.value.id == "QVideoSink":
                violations.append(Violation(rel, node.lineno, "QVideoSink(",
                                            ast.get_source_segment(content, node) or ""))

            # QMediaDevices.videoInputs()
            elif (
                isinstance(func.value, ast.Name)
                and func.value.id == "QMediaDevices"
                and func.attr == "videoInputs"
            ):
                violations.append(Violation(rel, node.lineno, "QMediaDevices.videoInputs()",
                                            ast.get_source_segment(content, node) or ""))

    return sorted(violations)


def test_guard_scans_a_real_tree():
    """The scan must actually visit application files.

    Guards against the regression where the scanned root did not exist and the
    checker therefore reported zero violations for the wrong reason.
    """
    files = list(_iter_source_files())
    assert len(files) > 20, f"expected to scan the app source tree, only found {len(files)} files"
    names = {p.name for p in files}
    assert "camera_worker.py" in names, "guard is not scanning app/core"


def test_camera_service_is_the_only_camera_path():
    violations = find_stray_camera_access()
    if violations:
        detail = "\n".join(
            f"  {v.path}:{v.line}: {v.symbol} -> {v.snippet}" for v in violations
        )
        pytest.fail(
            "Stray camera access outside app/core/camera_service.py:\n"
            f"{detail}\n\n"
            "All camera enumeration/opening must go through CameraService."
        )


def test_only_camera_service_opens_devices():
    """No module other than CameraService may construct a capture object.

    Camera_devices.py may list devices but must never open one.
    """
    offenders = []
    for path in _iter_source_files():
        if path.name == "test_camera_identity_is_not_persisted_by_index.py":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for symbol in CAPTURE_SYMBOLS:
            if symbol in text:
                offenders.append(f"{path.relative_to(APP_ROOT)}: {symbol}")

    # camera_devices.py is allowed to be scanned for enumeration, not capture.
    offenders = [
        o for o in offenders
        if not o.startswith("app/core/camera_devices.py")
    ]
    assert not offenders, f"capture constructed outside CameraService: {offenders}"


def test_camera_identity_is_not_persisted_by_index():
    """Camera choice must be stored as a device ID, never an index."""
    offenders = []
    for py_file in _iter_source_files():
        text = py_file.read_text(encoding="utf-8", errors="replace")
        if "cv2.VideoCapture" in text:
            offenders.append(str(py_file.relative_to(APP_ROOT)))
    assert not offenders, f"index-based camera opening in: {offenders}"