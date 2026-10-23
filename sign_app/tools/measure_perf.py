#!/usr/bin/env python3
"""
Performance measurement harness.

Runs the real pipeline against the real camera and reports measured numbers:
capture FPS, display FPS, inference FPS, inference ms (avg/p95), UI emit ms,
capture->display latency, dropped frames and the UI-thread watchdog maximum.

Usage:
    python tools/measure_perf.py --seconds 10
    python tools/measure_perf.py --seconds 10 --hand-image path/to/hand.jpg

--hand-image feeds a still image containing a hand through the inference stage
so the hand-present inference cost can be measured on a machine where no hand is
in front of the camera. That is a real MediaPipe measurement on a real hand, but
it is NOT an end-to-end camera measurement and the report labels it as such.
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QCoreApplication


def percentiles(values, p):
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(len(ordered) * p))
    return ordered[idx]


def run_live(app, seconds: int, label: str) -> dict:
    """Drive the real camera pipeline and sample stats."""
    from app.core.pipeline import CorePipeline
    from app.core.camera_service import CameraService

    pipeline = CorePipeline()
    pipeline.initialize(use_fake_camera=False)
    service = CameraService.instance()

    print(f"[{label}] starting pipeline on {service.get_active_device().name if service.get_active_device() else 'no camera'}")

    samples = {"capture_fps": [], "display_fps": [], "inference_fps": [],
               "inference_avg_ms": [], "inference_p95_ms": [], "latency_ms": [],
               "ui_paint_ms": []}
    ui_lateness = []
    hands_seen = 0

    pipeline.start()
    # Let the pipeline settle before measuring.
    deadline = time.time() + 1.5
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.005)

    ui_lateness.append(0.0)
    deadline = time.time() + seconds
    last_tick = time.perf_counter()
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.005)
        now = time.perf_counter()
        lateness = max(0.0, (now - last_tick - 0.005) * 1000 - 5)
        ui_lateness.append(lateness)
        last_tick = now

        stats = pipeline.perf_stats()
        for key in samples:
            if key in stats:
                samples[key].append(stats[key])

    pipeline.stop()
    time.sleep(0.3)

    report = {"label": label, "seconds": seconds}
    for key, values in samples.items():
        if not values:
            continue
        report[key] = round(statistics.median(values), 2)
        report[key + "_p95"] = round(percentiles(values, 0.95), 2)

    worker = getattr(pipeline, "_inference_worker", None)
    if worker is not None:
        report["dropped_frames"] = worker.get_dropped_frames()

    report["ui_watchdog_max_ms"] = round(max(ui_lateness), 2)
    return report


def run_hand_image(app, seconds: int, image_path: str) -> dict:
    """Measure MediaPipe inference cost on a real hand, without a camera."""
    import cv2
    from app.core.hand_tracker import HandTracker

    frame = cv2.imread(image_path)
    if frame is None:
        print(f"could not read {image_path}")
        return {}

    tracker = HandTracker(max_hands=1, model_complexity=0)
    if not tracker.initialize():
        print("hand tracker failed to initialise")
        return {}

    # Warm up, then measure with the detector actually finding a hand.
    tracker.process(frame, timestamp_ms=1)
    times = []
    hands_found = 0
    ts = 100
    deadline = time.time() + seconds
    while time.time() < deadline:
        ts += 33
        start = time.perf_counter()
        result = tracker.process(frame, timestamp_ms=ts)
        times.append((time.perf_counter() - start) * 1000)
        if result.hands:
            hands_found += 1
        app.processEvents()

    tracker.close()

    report = {
        "label": "synthetic hand image (no camera)",
        "image": image_path,
        "frames": len(times),
        "inference_avg_ms": round(statistics.mean(times), 2),
        "inference_p95_ms": round(percentiles(times, 0.95), 2),
        "hand_detected": hands_found > 0,
        "hand_detection_rate": round(hands_found / max(1, len(times)), 3),
    }
    print(f"[{report['label']}] hand detected in {report['hand_detection_rate']:.0%} of frames")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure pipeline performance")
    parser.add_argument("--seconds", type=int, default=10)
    parser.add_argument("--hand-image", default=None)
    parser.add_argument("--label", default="live camera, no hand")
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    app = QCoreApplication(sys.argv)

    reports = [run_live(app, args.seconds, args.label)]
    if args.hand_image:
        reports.append(run_hand_image(app, args.seconds, args.hand_image))

    print("\n" + "=" * 68)
    print(" MEASURED PERFORMANCE")
    print("=" * 68)
    print(json.dumps(reports, indent=2))

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(reports, indent=2))
        print(f"\nsaved to {args.json_out}")

    from app.core.camera_service import CameraService
    CameraService.destroy_instance()
    return 0


if __name__ == "__main__":
    sys.exit(main())