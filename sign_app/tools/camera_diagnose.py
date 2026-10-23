#!/usr/bin/env python3
"""
Camera diagnostics.

Prints every camera the OS exposes - name, stable device ID, whether it is a
virtual or physical source, whether the feed is live or static, the resolution
actually delivered and the measured FPS.

All enumeration and capture goes through CameraService, so the identity reported
here is exactly the identity the app uses at runtime. (It deliberately does not
probe OpenCV indices: AVFoundation index order does not reliably match Qt's
device list, which is how a virtual camera could end up named one thing and
capturing another.)
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QCoreApplication, QTimer

from app.core.camera_service import CameraService
from app.core.camera_devices import discover_camera_devices, is_static_frame_sequence

SAMPLE_SECONDS = 2.0


def print_header(title: str) -> None:
    print(f"\n{'=' * 68}\n {title}\n{'=' * 68}")


def print_section(title: str) -> None:
    print(f"\n--- {title} ---")


def check_macos_camera_permissions():
    if sys.platform != "darwin":
        return True, "Not macOS - skipped"
    try:
        from AVFoundation import AVCaptureDevice
    except ImportError:
        return True, (
            "pyobjc not installed; macOS will prompt for camera access on first run."
        )
    status = AVCaptureDevice.authorizationStatusForMediaType_("vide")
    if status == 0:
        return True, "Authorized"
    if status == 2:
        return False, (
            "DENIED. Grant access in System Settings > Privacy & Security > Camera."
        )
    if status == 3:
        return True, "Not yet requested - macOS will prompt on first camera use."
    return True, f"Unknown status ({status})"


class _FrameTap:
    """Collects frames from CameraService for measurement."""

    def __init__(self):
        self.frames = []
        self.first_ts = None
        self.last_ts = None
        self.count = 0

    def on_frame(self, camera_frame):
        import numpy as np
        from app.core.camera_devices import CameraDevice  # noqa: F401

        frame = getattr(camera_frame, "frame", camera_frame)
        now = time.time()
        if self.first_ts is None:
            self.first_ts = now
        self.last_ts = now
        self.count += 1
        small = frame
        h, w = frame.shape[:2]
        if max(h, w) > 240:
            import cv2
            scale = 240.0 / max(h, w)
            small = cv2.resize(frame, (int(w * scale), int(h * scale)),
                               interpolation=cv2.INTER_AREA)
        self.frames.append(small)
        if len(self.frames) > 40:
            self.frames.pop(0)

    def measure(self):
        elapsed = (self.last_ts - self.first_ts) if (self.first_ts and self.last_ts) else 0
        fps = (self.count - 1) / elapsed if elapsed > 0.05 and self.count > 1 else 0.0
        static = is_static_frame_sequence(self.frames) if len(self.frames) >= 3 else False
        return fps, static


def probe_devices(app: QCoreApplication, show_virtual: bool = True) -> list[dict]:
    """Capture from each device in turn and measure it."""
    service = CameraService.instance()
    devices = discover_camera_devices()
    if not show_virtual:
        devices = [d for d in devices if not d.is_virtual]

    results = []
    for device in devices:
        print(f"\n  Probing: {device.name}")
        if not service.set_active_device(device.device_id):
            print("    could not activate this device")
            results.append({
                "name": device.name, "device_id": device.device_id,
                "virtual": device.is_virtual, "builtin": device.is_builtin,
                "resolution": (0, 0), "fps": 0.0, "static": False,
                "opened": False,
            })
            continue

        tap = _FrameTap()
        service.frame_ready.connect(tap.on_frame)
        service.acquire("diagnose")

        # Pump the Qt event loop so frame signals are delivered.
        deadline = time.time() + SAMPLE_SECONDS
        while time.time() < deadline:
            app.processEvents()
            time.sleep(0.005)

        # Capture FPS and resolution are measured inside the capture thread so
        # the reading is not limited by this script's event loop.
        fps = service.capture_fps()
        resolution = service.measured_resolution()

        service.release("diagnose")
        try:
            service.frame_ready.disconnect(tap.on_frame)
        except (TypeError, RuntimeError):
            pass

        _, static = tap.measure()
        results.append({
            "name": device.name,
            "device_id": device.device_id,
            "virtual": device.is_virtual,
            "builtin": device.is_builtin,
            "resolution": resolution,
            "fps": fps,
            "static": static,
            "opened": tap.count > 0,
        })

    # Leave the app on the preferred device.
    from app.core.camera_devices import preferred_camera
    pref = preferred_camera(devices)
    if pref:
        service.set_active_device(pref.device_id)
    return results


def check_mediapipe():
    print_section("MediaPipe Hand Landmarker")
    info = {"available": False, "inference_ms": 0.0}
    try:
        from app.core.hand_tracker import HandTracker
    except Exception as exc:
        print(f"  import failed: {exc}")
        return info

    tracker = HandTracker(max_hands=1, model_complexity=0)
    if not tracker.initialize():
        print("  HandTracker failed to initialize")
        tracker.close()
        return info

    import numpy as np
    info["available"] = True
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    tracker.process(frame, timestamp_ms=1)  # warm-up
    times = []
    for i in range(30):
        start = time.perf_counter()
        tracker.process(frame, timestamp_ms=100 + i)
        times.append((time.perf_counter() - start) * 1000)
    info["inference_ms"] = sum(times) / len(times)
    times.sort()
    info["p95_ms"] = times[int(len(times) * 0.95)]
    print(f"  initialised OK")
    print(f"  avg {info['inference_ms']:.1f} ms/frame | p95 {info['p95_ms']:.1f} ms (no hand in frame)")
    tracker.close()
    return info


def check_pipeline() -> bool:
    print_section("Pipeline integration")
    try:
        from app.core.pipeline import CorePipeline
    except Exception as exc:
        print(f"  import failed: {exc}")
        return False
    pipeline = CorePipeline()
    ok = pipeline.initialize(use_fake_camera=True)
    print(f"  initialize: {'OK' if ok else 'FAILED'}")
    pipeline.start()
    time.sleep(1.0)
    pipeline.stop()
    print("  start/stop clean")
    return ok


def main() -> int:
    app = QCoreApplication(sys.argv)

    print_header("Camera diagnostics")

    print_section("macOS permissions")
    allowed, message = check_macos_camera_permissions()
    print(f"  {'OK' if allowed else 'PROBLEM'}: {message}")

    print_section("Devices (as reported by CameraService)")
    results = probe_devices(app)

    print_section("Summary")
    header = f"{'DEVICE':<28} {'KIND':<9} {'FEED':<8} {'RESOLUTION':<12} {'FPS':>6}  ID"
    print(header)
    print("-" * len(header))
    for r in results:
        kind = "virtual" if r["virtual"] else ("built-in" if r["builtin"] else "physical")
        feed = "STATIC" if r["static"] else ("live" if r["opened"] else "no frames")
        res = f"{r['resolution'][0]}x{r['resolution'][1]}" if r["resolution"] != (0, 0) else "-"
        print(f"{r['name'][:27]:<28} {kind:<9} {feed:<8} {res:<12} {r['fps']:>6.1f}  {r['device_id']}")

    if not results:
        print("\n  No cameras found. Check System Settings > Privacy & Security > Camera.")

    mp = check_mediapipe()
    pipeline_ok = check_pipeline()

    print_header("Result")
    builtin = [r for r in results if r["builtin"] and not r["static"]]
    print(f"  built-in camera usable: {'YES' if builtin else 'NO'}")
    print(f"  MediaPipe: {'OK' if mp['available'] else 'UNAVAILABLE'}")
    print(f"  Pipeline: {'OK' if pipeline_ok else 'FAILED'}")
    service = CameraService.instance()
    active = service.get_active_device()
    print(f"  app will open: {active.name if active else '(none)'}")

    CameraService.destroy_instance()
    return 0


if __name__ == "__main__":
    sys.exit(main())