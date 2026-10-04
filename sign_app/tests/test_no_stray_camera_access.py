#!/usr/bin/env python3
"""
Guard test: fails if cv2.VideoCapture or QCamera appears outside the camera service module.
This ensures all camera access goes through the single CameraService.
"""

import ast
import os
import sys
from pathlib import Path


def find_stray_camera_access(root: Path) -> list[tuple[str, int, str]]:
    """
    Scan Python files for direct camera access outside the camera service.
    Returns list of (file_path, line_number, code_snippet).
    """
    violations = []
    camera_service_path = Path("app/core/camera_service.py")
    
    for py_file in root.rglob("*.py"):
        # Skip test files and the camera service itself
        if "test_" in py_file.name or py_file == camera_service_path:
            continue
        if "__pycache__" in str(py_file):
            continue
            
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except Exception:
            continue
            
        for node in ast.walk(tree):
            # Check for cv2.VideoCapture calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if (isinstance(node.func.value, ast.Name) and 
                        node.func.value.id == "cv2" and 
                        node.func.attr == "VideoCapture"):
                        violations.append((
                            str(py_file.relative_to(root)),
                            node.lineno,
                            ast.get_source_segment(content, node) or ""
                        ))
                    # Check for QCamera instantiation
                    elif (isinstance(node.func.value, ast.Name) and
                          node.func.value.id == "QCamera"):
                        violations.append((
                            str(py_file.relative_to(root)),
                            node.lineno,
                            ast.get_source_segment(content, node) or ""
                        ))
                    # Check for QMediaCaptureSession instantiation
                    elif (isinstance(node.func.value, ast.Name) and
                          node.func.value.id == "QMediaCaptureSession"):
                        violations.append((
                            str(py_file.relative_to(root)),
                            node.lineno,
                            ast.get_source_segment(content, node) or ""
                        ))
    
    return violations


def main():
    root = Path(__file__).resolve().parents[1] / "sign_app"
    camera_service_path = root / "app" / "core" / "camera_service.py"
    
    violations = find_stray_camera_access(root)
    
    if violations:
        print("❌ STRAY CAMERA ACCESS DETECTED:")
        for file_path, line_no, snippet in violations:
            print(f"  {file_path}:{line_no}: {snippet.strip()}")
        print(f"\nTotal violations: {len(violations)}")
        print("\nAll camera access must go through CameraService in app/core/camera_service.py")
        return 1
    
    print("✅ No stray camera access detected. All camera access goes through CameraService.")
    return 0


if __name__ == "__main__":
    sys.exit(main())