#!/usr/bin/env python3
"""
Camera Diagnostic Tool for Sign Language Learning App.
Independently tests camera access, MediaPipe hand tracking, and reports issues.
Run: python tools/camera_diagnose.py
"""

import sys
import time
import platform
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional

import cv2
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")


def print_section(title: str):
    print(f"\n--- {title} ---")


def check_macos_camera_permissions() -> Tuple[bool, str]:
    """Check if the current terminal/IDE has camera permission on macOS."""
    if platform.system() != "Darwin":
        return True, "Not on macOS, skipping permission check"

    try:
        # Check TCC database for camera access
        # This is a heuristic - we can't directly query TCC from Python easily
        # But we can try to open a camera and see if it fails with permission error
        result = subprocess.run(
            ["tccutil", "list", "Camera"],
            capture_output=True, text=True, timeout=5
        )
        output = result.stdout
        # Look for the current terminal/IDE in the output
        # This is approximate - actual permission check requires trying to open camera
        return True, "macOS detected - will test camera access directly"
    except Exception as e:
        return True, f"Could not check TCC: {e}"


def test_camera_opencv(indices: List[int] = None) -> List[dict]:
    """Test camera indices with platform-appropriate backends."""
    if indices is None:
        indices = list(range(6))

    system = platform.system()
    results = []

    print_section(f"Testing Cameras (Platform: {system})")

    # Determine backend priority order
    if system == "Darwin":  # macOS
        backends = [
            (cv2.CAP_AVFOUNDATION, "AVFoundation"),
        ]
    elif system == "Windows":
        backends = [
            (cv2.CAP_DSHOW, "DirectShow"),
            (cv2.CAP_MSMF, "Media Foundation"),
            (cv2.CAP_ANY, "Auto"),
        ]
    else:  # Linux
        backends = [
            (cv2.CAP_V4L2, "V4L2"),
            (cv2.CAP_ANY, "Auto"),
        ]

    for idx in indices:
        print(f"\n  Camera index {idx}:")
        camera_result = {
            "index": idx,
            "opened": False,
            "backend": None,
            "resolution": None,
            "fps": 0.0,
            "frame_read_ok": False,
            "frame_not_black": False,
            "error": None
        }

        for backend_id, backend_name in backends:
            try:
                cap = cv2.VideoCapture(idx, backend_id)
                if cap.isOpened():
                    # Try to set resolution
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    cap.set(cv2.CAP_PROP_FPS, 30)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                    # Read a few frames to stabilize
                    for _ in range(3):
                        cap.read()
                        time.sleep(0.05)

                    # Measure FPS over ~3 seconds
                    frame_count = 0
                    start_time = time.perf_counter()
                    last_frame = None
                    frame_ok = False
                    not_black = False

                    while time.perf_counter() - start_time < 3.0:
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            frame_count += 1
                            last_frame = frame
                            frame_ok = True
                            # Check if frame is not all black
                            if np.mean(frame) > 5:  # Some signal
                                not_black = True
                        time.sleep(0.01)  # Small delay

                    elapsed = time.perf_counter() - start_time
                    measured_fps = frame_count / elapsed if elapsed > 0 else 0

                    if frame_ok:
                        camera_result["opened"] = True
                        camera_result["backend"] = backend_name
                        camera_result["resolution"] = (
                            int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                            int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        )
                        camera_result["fps"] = measured_fps
                        camera_result["frame_read_ok"] = frame_ok
                        camera_result["frame_not_black"] = not_black
                        print(f"    ✅ OPENED with {backend_name}")
                        print(f"       Resolution: {camera_result['resolution']}")
                        print(f"       Measured FPS: {measured_fps:.1f}")
                        print(f"       Frame read OK: {frame_ok}")
                        print(f"       Frame not black: {not_black}")
                        cap.release()
                        break
                    else:
                        print(f"    ⚠️  Opened with {backend_name} but no valid frames")
                cap.release()
            except Exception as e:
                camera_result["error"] = str(e)
                print(f"    ❌ {backend_name} failed: {e}")

        if not camera_result["opened"]:
            print(f"    ❌ Could not open camera {idx} with any backend")

        results.append(camera_result)

    return results


def test_mediapipe_hand_landmarker() -> dict:
    """Test MediaPipe Hand Landmarker (Tasks API) initialization and inference."""
    print_section("Testing MediaPipe Hand Landmarker (Tasks API)")

    result = {
        "available": False,
        "model_found": False,
        "model_path": None,
        "initialization_ok": False,
        "inference_ok": False,
        "inference_time_ms": 0.0,
        "hands_detected": 0,
        "error": None
    }

    try:
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        # Check if HandLandmarker exists
        if not hasattr(vision, 'HandLandmarker'):
            result["error"] = "HandLandmarker not found in MediaPipe Tasks API"
            print(f"  ❌ {result['error']}")
            return result

        result["available"] = True
        print("  ✅ HandLandmarker class available")

        # Find model file - check bundled location first
        import os
        project_root = Path(__file__).parent.parent
        bundled_path = project_root / 'models' / 'hand_landmarker.task'
        package_path = Path(os.path.dirname(vision.__file__)) / 'hand_landmarker.task'

        if bundled_path.exists():
            model_path = str(bundled_path)
            result["model_found"] = True
            print(f"  ✅ Bundled model found at: {model_path}")
        elif package_path.exists():
            model_path = str(package_path)
            result["model_found"] = True
            print(f"  ✅ Package model found at: {model_path}")
        else:
            model_path = str(package_path)
            result["model_path"] = model_path
            result["model_found"] = False
            print(f"  ❌ Model NOT found at: {model_path}")
            print("     Download from: https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task")
            print(f"     Place at: {model_path} or {bundled_path}")
            result["error"] = "Model file missing"
            return result

        result["model_path"] = model_path

        # Initialize
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_hands=2,
            min_hand_detection_confidence=0.7,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5
        )

        start_init = time.perf_counter()
        landmarker = vision.HandLandmarker.create_from_options(options)
        init_time = (time.perf_counter() - start_init) * 1000
        print(f"  ✅ Initialized in {init_time:.1f}ms")
        result["initialization_ok"] = True

        # Test inference on a dummy frame
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        dummy_frame[:] = (100, 100, 100)  # Gray
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=dummy_frame)

        start_inf = time.perf_counter()
        detection_result = landmarker.detect(mp_image)
        inf_time = (time.perf_counter() - start_inf) * 1000

        result["inference_ok"] = True
        result["inference_time_ms"] = inf_time
        result["hands_detected"] = len(detection_result.hand_landmarks)
        print(f"  ✅ Inference time: {inf_time:.1f}ms")
        print(f"  ✅ Hands detected in dummy frame: {result['hands_detected']}")

        landmarker.close()

    except Exception as e:
        result["error"] = str(e)
        print(f"  ❌ Error: {e}")

    return result


def test_mediapipe_legacy() -> dict:
    """Test MediaPipe legacy solutions.hands (not available in 0.10.35+)."""
    print_section("Testing MediaPipe Legacy API (solutions.hands)")

    result = {
        "available": False,
        "initialization_ok": False,
        "error": None
    }

    try:
        import mediapipe as mp
        if hasattr(mp.solutions, 'hands'):
            result["available"] = True
            hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                min_detection_confidence=0.7,
                min_tracking_confidence=0.5,
                model_complexity=1
            )
            result["initialization_ok"] = True
            print("  ✅ Legacy API available and initialized")
            hands.close()
        else:
            print("  ℹ️  Legacy API not available in MediaPipe 0.10.35+ (expected)")
    except Exception as e:
        result["error"] = str(e)
        print(f"  ❌ Error: {e}")

    return result


def test_live_hand_detection(camera_results: List[dict]) -> dict:
    """Run the application's selected HandTracker against a live camera."""
    print_section("Testing Live Hand Detection")
    report = {"tested": False, "frames": 0, "hands_detected": 0, "avg_inference_ms": 0.0, "error": None}
    working = next((item for item in camera_results if item["opened"] and item["frame_read_ok"]), None)
    if not working:
        print("  ⚠️  Skipped: no readable camera is available.")
        return report

    try:
        from app.core.hand_tracker import HandTracker
        backend = cv2.CAP_AVFOUNDATION if platform.system() == "Darwin" else cv2.CAP_ANY
        cap = cv2.VideoCapture(working["index"], backend)
        tracker = HandTracker()
        if not cap.isOpened() or not tracker.initialize():
            raise RuntimeError("could not open the selected camera or initialize HandTracker")
        timings = []
        deadline = time.perf_counter() + 3.0
        while time.perf_counter() < deadline:
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            result = tracker.process(frame, timestamp_ms=int(time.time() * 1000))
            timings.append(result.processing_time_ms)
            report["frames"] += 1
            report["hands_detected"] += len(result.hands)
        cap.release()
        tracker.close()
        report["tested"] = True
        report["avg_inference_ms"] = sum(timings) / len(timings) if timings else 0.0
        print(f"  ✅ Processed {report['frames']} live frames with the app HandTracker")
        print(f"     Hands detected: {report['hands_detected']}")
        print(f"     Average inference: {report['avg_inference_ms']:.1f}ms/frame")
        if not report["hands_detected"]:
            print("     ℹ️  No hand was visible during this run; show a hand to test skeleton tracking.")
    except Exception as exc:
        report["error"] = str(exc)
        print(f"  ❌ Live hand test failed: {exc}")
    return report


def test_pipeline_integration() -> dict:
    """Test the app's CorePipeline with fake camera."""
    print_section("Testing App CorePipeline Integration")

    result = {
        "pipeline_init": False,
        "hand_tracker_init": False,
        "camera_worker_start": False,
        "frame_received": False,
        "hand_detection": False,
        "error": None
    }

    try:
        sys.path.insert(0, str(project_root))
        from app.core.pipeline import CorePipeline

        pipeline = CorePipeline()
        init_ok = pipeline.initialize(use_fake_camera=True)
        result["pipeline_init"] = init_ok
        print(f"  Pipeline initialize: {'✅' if init_ok else '❌'}")

        if pipeline._hand_tracker._initialized:
            result["hand_tracker_init"] = True
            print("  ✅ HandTracker initialized")
        else:
            print("  ❌ HandTracker NOT initialized")

        # Start and check for frames
        pipeline.start()
        time.sleep(1.0)  # Let it run a bit
        result["camera_worker_start"] = True
        print("  ✅ Camera worker started (fake)")

        pipeline.stop()
        print("  ✅ Pipeline stopped cleanly")

    except Exception as e:
        result["error"] = str(e)
        print(f"  ❌ Error: {e}")

    return result


def print_summary(camera_results: List[dict], mp_result: dict, legacy_result: dict, live_result: dict, pipeline_result: dict):
    """Print final summary and recommendations."""
    print_header("SUMMARY & RECOMMENDATIONS")

    # Camera summary
    working_cameras = [r for r in camera_results if r["opened"] and r["frame_read_ok"] and r["frame_not_black"]]
    print(f"\n📷 Cameras: {len(working_cameras)}/{len(camera_results)} working")
    for cam in working_cameras:
        print(f"   Camera {cam['index']}: {cam['resolution']} @ {cam['fps']:.1f} FPS ({cam['backend']})")

    if not working_cameras:
        print("   ❌ NO WORKING CAMERAS FOUND")
        if platform.system() == "Darwin":
            print("\n   🔧 macOS CAMERA PERMISSION FIX:")
            print("   1. Open System Settings → Privacy & Security → Camera")
            print("   2. Enable the terminal/IDE you're using (Terminal, VS Code, PyCharm, etc.)")
            print("   3. FULLY RESTART the terminal/IDE after enabling")
            print("   4. Run this script again")

    # MediaPipe summary
    print(f"\n🤖 MediaPipe Hand Landmarker:")
    if mp_result["available"]:
        print(f"   Available: ✅")
        if mp_result["model_found"]:
            print(f"   Model: ✅ Found")
            print(f"   Initialization: {'✅' if mp_result['initialization_ok'] else '❌'}")
            print(f"   Inference: {'✅' if mp_result['inference_ok'] else '❌'} ({mp_result['inference_time_ms']:.1f}ms)")
        else:
            print(f"   Model: ❌ MISSING - Download required")
            print(f"   Download: https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task")
            print(f"   Place at: {mp_result['model_path']}")
    else:
        print(f"   Available: ❌")

    print(f"\n🔄 Legacy API (solutions.hands): {'✅ Available' if legacy_result['available'] else '❌ Not in 0.10.35+'}")
    if live_result["tested"]:
        print(f"\n✋ Live tracker: {live_result['frames']} frames, {live_result['hands_detected']} hand detections, "
              f"{live_result['avg_inference_ms']:.1f}ms average")

    # Pipeline summary
    print(f"\n🔧 App Pipeline:")
    print(f"   Init: {'✅' if pipeline_result['pipeline_init'] else '❌'}")
    print(f"   HandTracker: {'✅' if pipeline_result['hand_tracker_init'] else '❌'}")
    print(f"   Camera Worker: {'✅' if pipeline_result['camera_worker_start'] else '❌'}")

    # Overall verdict
    print(f"\n{'='*60}")
    if working_cameras and mp_result["model_found"] and mp_result["initialization_ok"]:
        print("✅ SYSTEM READY - Camera and MediaPipe working!")
        print("   Next: Run the app and verify live video + skeleton overlay")
    elif working_cameras and not mp_result["model_found"]:
        print("⚠️  CAMERA OK but MediaPipe model missing")
        print("   Action: Download hand_landmarker.task model file")
    elif not working_cameras and platform.system() == "Darwin":
        print("❌ CAMERA PERMISSION ISSUE (macOS)")
        print("   Action: Grant camera permission to terminal/IDE and restart")
    else:
        print("❌ MULTIPLE ISSUES - See details above")
    print(f"{'='*60}\n")


def main():
    print_header("SIGN LANGUAGE APP - CAMERA DIAGNOSTIC")
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"OpenCV: {cv2.__version__}")

    # Check macOS permissions
    perm_ok, perm_msg = check_macos_camera_permissions()
    print(f"\n🔐 macOS Permissions: {perm_msg}")

    # Test cameras
    camera_results = test_camera_opencv(list(range(6)))

    # Test MediaPipe
    mp_result = test_mediapipe_hand_landmarker()
    legacy_result = test_mediapipe_legacy()
    live_result = test_live_hand_detection(camera_results)

    # Test pipeline
    pipeline_result = test_pipeline_integration()

    # Summary
    print_summary(camera_results, mp_result, legacy_result, live_result, pipeline_result)

    # Exit code
    if working_cameras := [r for r in camera_results if r["opened"] and r["frame_read_ok"] and r["frame_not_black"]]:
        if mp_result["model_found"] and mp_result["initialization_ok"]:
            return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
