#!/usr/bin/env python3
"""
Data Collection Tool for Sign Language Learning App.
Records hand landmarks for training the classifier.
Run: python tools/collect_data.py
"""

import sys
import csv
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Optional

import cv2
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.hand_tracker import HandTracker
from app.core.features import FeatureExtractor
from app.data.db import ModuleCategory, Difficulty


class DataCollector:
    """Collects hand landmark data for training."""

    def __init__(self, output_dir: Path, camera_device_id: str | None = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Cameras are identified by stable device ID, never by index.
        self.camera_device_id = camera_device_id
        self.tracker = HandTracker()
        self.extractor = FeatureExtractor()

        self._latest_frame = None
        self._service = None

        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.person_id = "collector_1"  # Could be made configurable

        # CSV file for landmarks
        self.csv_path = self.output_dir / f"landmarks_{self.session_id}.csv"
        self._init_csv()

        # JSON metadata
        self.meta_path = self.output_dir / f"session_{self.session_id}.json"
        self.metadata = {
            "session_id": self.session_id,
            "person_id": self.person_id,
            "timestamp": datetime.now().isoformat(),
            "camera_device_id": camera_device_id or "",
            "labels": [],
            "samples_per_label": {}
        }

    def _start_camera(self):
        """Open the shared camera via CameraService."""
        from app.core.camera_service import CameraService

        self._service = CameraService.instance()
        if self.camera_device_id:
            self._service.set_active_device(self.camera_device_id)
        self._service.frame_ready.connect(self._on_frame)
        self._service.acquire("collect_data")
        device = self._service.get_active_device()
        if device is None:
            return False
        self.metadata["camera_device_id"] = device.device_id
        self.metadata["camera_name"] = device.name
        print(f"Using camera: {device.name} (id={device.device_id})")
        return True

    def _on_frame(self, camera_frame):
        self._latest_frame = getattr(camera_frame, "frame", camera_frame)

    def _next_frame(self, timeout: float = 1.0):
        """Return the most recent frame, or None if none arrives in time."""
        deadline = time.time() + timeout
        while self._latest_frame is None and time.time() < deadline:
            time.sleep(0.005)
        frame = self._latest_frame
        self._latest_frame = None
        return frame

    def _stop_camera(self):
        if self._service is not None:
            try:
                self._service.frame_ready.disconnect(self._on_frame)
            except (TypeError, RuntimeError):
                pass
            self._service.release("collect_data")

    def _init_csv(self):
        """Initialize CSV with headers."""
        headers = ["session_id", "person_id", "timestamp", "label"]
        # 21 landmarks * 3 coordinates = 63 features
        for i in range(21):
            headers.extend([f"x{i}", f"y{i}", f"z{i}"])
        # Add handedness and confidence
        headers.extend(["handedness", "hand_confidence"])

        self.csv_file = open(self.csv_path, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(headers)

    def collect_for_label(
        self,
        label: str,
        num_samples: int = 50,
        countdown: int = 3,
        show_preview: bool = True
    ) -> int:
        """
        Collect samples for a specific label.
        Returns number of samples collected.
        """
        print(f"\n=== Collecting for label: {label} ===")
        print(f"Get ready to sign '{label}'...")
        print(f"Will collect {num_samples} samples after {countdown}s countdown.")

        if not self.tracker.initialize():
            print("ERROR: Failed to initialize hand tracker")
            return 0

        if not self._start_camera():
            print("ERROR: Could not open a camera through CameraService")
            return 0

        # Countdown
        for i in range(countdown, 0, -1):
            frame = self._next_frame()
            if frame is not None:
                frame = frame.copy()
                cv2.putText(frame, f"Starting in {i}...", (50, 100),
                           cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 255), 3)
                cv2.putText(frame, f"Sign: {label}", (50, 200),
                           cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 2)
                if show_preview:
                    cv2.imshow("Data Collection", frame)
                    cv2.waitKey(1000)

        collected = 0
        last_save_time = 0
        min_interval = 0.1  # Minimum 100ms between samples

        print("Collecting... Press 'q' to stop early.")

        while collected < num_samples:
            frame = self._next_frame()
            if frame is None:
                continue

            result = self.tracker.process(frame, timestamp_ms=int(time.time() * 1000))

            # Draw landmarks on preview
            if result.hands:
                annotated = self.tracker.draw_landmarks(frame.copy(), result.hands)
            else:
                annotated = frame

            # Status overlay
            cv2.putText(annotated, f"Label: {label}", (20, 40),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(annotated, f"Collected: {collected}/{num_samples}", (20, 80),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(annotated, "Press 'q' to quit", (20, 120),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)

            if show_preview:
                cv2.imshow("Data Collection", annotated)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("Stopped by user")
                break

            # Save sample if hand detected
            if result.hands:
                now = time.time()
                if now - last_save_time >= min_interval:
                    best_hand = max(result.hands, key=lambda h: h.confidence)
                    self._save_sample(label, best_hand)
                    collected += 1
                    last_save_time = now

                    # Brief flash
                    cv2.circle(annotated, (30, 150), 15, (0, 255, 0), -1)
                    if show_preview:
                        cv2.imshow("Data Collection", annotated)
                        cv2.waitKey(50)

        self._stop_camera()
        if show_preview:
            cv2.destroyAllWindows()

        # Update metadata
        self.metadata["labels"].append(label)
        self.metadata["samples_per_label"][label] = collected
        self._save_metadata()

        print(f"Collected {collected} samples for {label}")
        return collected

    def _save_sample(self, label: str, hand):
        """Save a single landmark sample to CSV."""
        timestamp = datetime.now().isoformat()
        landmarks = hand.landmarks.flatten()  # 63 values

        row = [self.session_id, self.person_id, timestamp, label]
        row.extend(landmarks.tolist())
        row.extend([hand.handedness.value, hand.confidence])

        self.csv_writer.writerow(row)

    def _save_metadata(self):
        """Save session metadata."""
        with open(self.meta_path, 'w') as f:
            json.dump(self.metadata, f, indent=2)

    def close(self):
        """Clean up."""
        if hasattr(self, 'csv_file'):
            self.csv_file.close()
        self.tracker.close()


def main():
    parser = argparse.ArgumentParser(description="Collect hand landmark data for ASL training")
    parser.add_argument("--output", "-o", default="data/collected",
                       help="Output directory for collected data")
    parser.add_argument("--camera", "-c", default=None,
                       help="Camera device ID (default: best available). "
                            "Run tools/camera_diagnose.py to list IDs.")
    parser.add_argument("--samples", "-n", type=int, default=50,
                       help="Samples per label")
    parser.add_argument("--labels", "-l", nargs="+",
                       help="Labels to collect (default: all ASL letters)")
    parser.add_argument("--countdown", "-d", type=int, default=3,
                       help="Countdown seconds before collection")

    args = parser.parse_args()

    # Default ASL labels (scored letters only)
    default_labels = [
        "A", "B", "C", "D", "E", "F", "G", "H", "I",
        "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T",
        "U", "V", "W", "X", "Y",
        "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"
    ]

    labels = args.labels if args.labels else default_labels

    print("=" * 60)
    print("ASL Data Collection Tool")
    print("=" * 60)
    print(f"Output directory: {args.output}")
    print(f"Camera device id: {args.camera or 'auto (built-in preferred)'}")
    print(f"Samples per label: {args.samples}")
    print(f"Labels: {', '.join(labels)}")
    print("=" * 60)

    # Consent notice
    print("\n⚠️  CONSENT NOTICE")
    print("This tool collects hand landmark data (NOT images) for training.")
    print("Data is stored locally only. No video or images are saved.")
    print("By continuing, you consent to this data collection.")
    response = input("Continue? (y/N): ").strip().lower()
    if response != 'y':
        print("Cancelled.")
        return

    collector = DataCollector(args.output, args.camera)

    try:
        for label in labels:
            print(f"\nNext label: {label}")
            input("Press Enter when ready...")

            collector.collect_for_label(
                label=label,
                num_samples=args.samples,
                countdown=args.countdown
            )

            # Ask to continue
            if label != labels[-1]:
                cont = input("Continue to next label? (Y/n): ").strip().lower()
                if cont == 'n':
                    break

    finally:
        collector.close()

    print(f"\n✅ Data collection complete!")
    print(f"CSV: {collector.csv_path}")
    print(f"Metadata: {collector.meta_path}")
    print(f"\nNext step: python tools/train_model.py --data {args.output}")


if __name__ == "__main__":
    main()