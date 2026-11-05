#!/usr/bin/env python3
"""
Collect normalized landmark samples for ASL signs from the live camera.

Uses the shared CameraService and hand tracker to capture frames and extract
normalized landmarks, finger states, and joint angles.

Usage:
    python -m tools.collect_samples [--sign SIGN_ID] [--count N] [--output-dir DIR] [--list]
    
Examples:
    python -m tools.collect_samples --sign asl_a --count 50
    python -m tools.collect_samples --list
    python -m tools.collect_samples  # Interactive mode: goes through all scored signs
"""

import argparse
import csv
import json
import logging
import sys
import time
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.camera_service import CameraService, CameraFrame
from app.core.hand_tracker import HandTracker, HandLandmarks
from app.core.features import FeatureExtractor
from app.content.loader import initialize_content_packs
from app.data.db import init_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = PROJECT_ROOT / "data/samples/asl"

FEATURE_EXTRACTOR = FeatureExtractor(
    mirror_left_to_right=True,
    use_3d=True,
    include_angles=True,
    include_distances=True
)

LANDMARK_INDEX = {
    "WRIST": 0,
    "THUMB_CMC": 1, "THUMB_MCP": 2, "THUMB_IP": 3, "THUMB_TIP": 4,
    "INDEX_MCP": 5, "INDEX_PIP": 6, "INDEX_DIP": 7, "INDEX_TIP": 8,
    "MIDDLE_MCP": 9, "MIDDLE_PIP": 10, "MIDDLE_DIP": 11, "MIDDLE_TIP": 12,
    "RING_MCP": 13, "RING_PIP": 14, "RING_DIP": 15, "RING_TIP": 16,
    "PINKY_MCP": 17, "PINKY_PIP": 18, "PINKY_DIP": 19, "PINKY_TIP": 20,
}

FINGER_CHAINS = {
    "thumb": (4, 3, 2),   # tip, IP, MCP
    "index": (8, 6, 5),
    "middle": (12, 10, 9),
    "ring": (16, 14, 13),
    "pinky": (20, 18, 17),
}


@dataclass
class SampleData:
    frame_num: int
    handedness: str
    landmarks: np.ndarray  # (21, 3) normalized
    finger_states: Dict[str, str]
    joint_angles: Dict[str, float]


def normalize_landmarks(hand: HandLandmarks) -> np.ndarray:
    """Normalize: wrist at origin, scale by hand size, mirror left->right."""
    landmarks = hand.landmarks.copy()
    wrist = landmarks[0]
    landmarks = landmarks - wrist
    middle_mcp = landmarks[9]
    hand_scale = np.linalg.norm(middle_mcp[:2]) + 1e-6
    landmarks = landmarks / hand_scale
    if hand.handedness.value == "left":
        landmarks[:, 0] = -landmarks[:, 0]
    return landmarks.astype(np.float32)


def get_finger_states(landmarks: np.ndarray) -> Dict[str, str]:
    """Classify each finger as extended/curled/partial."""
    states = {}
    for name, (tip_idx, pip_idx, mcp_idx) in FINGER_CHAINS.items():
        tip = landmarks[tip_idx]
        pip = landmarks[pip_idx]
        mcp = landmarks[mcp_idx]
        tip_to_mcp = np.linalg.norm(tip[:2] - mcp[:2])
        pip_to_mcp = np.linalg.norm(pip[:2] - mcp[:2])
        if pip_to_mcp < 1e-6:
            states[name] = "unknown"
        else:
            ratio = tip_to_mcp / pip_to_mcp
            if ratio > 1.5:
                states[name] = "extended"
            elif ratio > 0.8:
                states[name] = "partial"
            else:
                states[name] = "curled"
    return states


def get_joint_angles(landmarks: np.ndarray) -> Dict[str, float]:
    """Compute key joint angles in radians."""
    angles = {}
    chains = {
        "thumb": (1, 2, 3, 4),
        "index": (5, 6, 7, 8),
        "middle": (9, 10, 11, 12),
        "ring": (13, 14, 15, 16),
        "pinky": (17, 18, 19, 20),
    }
    for name, (mcp, pip, dip, tip) in chains.items():
        # PIP angle
        v1 = landmarks[mcp] - landmarks[pip]
        v2 = landmarks[dip] - landmarks[pip]
        dot = np.dot(v1[:2], v2[:2])
        norm = np.linalg.norm(v1[:2]) * np.linalg.norm(v2[:2])
        if norm > 1e-6:
            angles[f"{name}_pip"] = float(np.arccos(np.clip(dot / norm, -1.0, 1.0)))
        # DIP angle
        v1 = landmarks[pip] - landmarks[dip]
        v2 = landmarks[tip] - landmarks[dip]
        dot = np.dot(v1[:2], v2[:2])
        norm = np.linalg.norm(v1[:2]) * np.linalg.norm(v2[:2])
        if norm > 1e-6:
            angles[f"{name}_dip"] = float(np.arccos(np.clip(dot / norm, -1.0, 1.0)))
    return angles


class SampleCollector:
    def __init__(self, output_dir: Path, target_hand: str = "both"):
        self.output_dir = output_dir
        self.target_hand = target_hand  # "right", "left", "both"
        self.hand_tracker = HandTracker(
            max_hands=2,
            min_detection_confidence=0.4,
            min_tracking_confidence=0.5,
            min_presence_confidence=0.5,
            model_complexity=0
        )
        self.camera_service = CameraService.instance()
        self._current_sign_id: Optional[str] = None
        self._current_csv_path: Optional[Path] = None
        self._csv_file = None
        self._csv_writer = None
        self._collected = 0
        self._target = 0
        self._frame_num = 0
        self._lock = threading.Lock()
        self._done_event = threading.Event()
        self._paused = False

    def initialize(self) -> bool:
        if not self.hand_tracker.initialize():
            logger.error("Failed to initialize hand tracker")
            return False
        # Initialize DB (for settings)
        init_db()
        return True

    def _frame_callback(self, frame: CameraFrame):
        if self._paused or self._done_event.is_set():
            return
        
        with self._lock:
            if self._done_event.is_set():
                return
            
            # Process frame with hand tracker
            tracker_result = self.hand_tracker.process(frame.frame, timestamp_ms=int(frame.timestamp_ms))
            
            if not tracker_result.hands:
                return
            
            # Select hand(s) based on target_hand
            hands_to_use = []
            for hand in tracker_result.hands:
                if self.target_hand == "both":
                    hands_to_use.append(hand)
                elif self.target_hand == "right" and hand.handedness.value == "right":
                    hands_to_use.append(hand)
                elif self.target_hand == "left" and hand.handedness.value == "left":
                    hands_to_use.append(hand)
            
            if not hands_to_use:
                return
            
            # Use the most confident hand
            best_hand = max(hands_to_use, key=lambda h: h.confidence)
            
            # Only accept high-confidence detections
            if best_hand.confidence < 0.6:
                return
            
            # Normalize and extract features
            norm_landmarks = normalize_landmarks(best_hand)
            finger_states = get_finger_states(norm_landmarks)
            joint_angles = get_joint_angles(norm_landmarks)
            
            # Write to CSV
            landmarks_flat = norm_landmarks.flatten().tolist()
            self._csv_writer.writerow([
                self._frame_num,
                best_hand.handedness.value,
                json.dumps(landmarks_flat),
                json.dumps(finger_states),
                json.dumps(joint_angles)
            ])
            self._csv_file.flush()
            
            self._frame_num += 1
            self._collected += 1
            
            if self._collected % 10 == 0:
                logger.info(f"  Collected {self._collected}/{self._target} samples...")
            
            if self._collected >= self._target:
                self._done_event.set()

    def collect_for_sign(self, sign_id: str, label: str, count: int) -> int:
        """Collect samples for one sign. Returns total samples after collection."""
        csv_path = self.output_dir / f"{sign_id}.csv"
        
        # Count existing
        existing = 0
        if csv_path.exists():
            with open(csv_path, "r") as f:
                existing = sum(1 for _ in f) - 1
        
        needed = max(0, count - existing)
        if needed == 0:
            logger.info(f"[{sign_id}] Already has {existing}/{count} samples")
            return existing
        
        # Open CSV for appending
        self._csv_file = open(csv_path, "a", newline="")
        self._csv_writer = csv.writer(self._csv_file)
        if existing == 0:
            self._csv_writer.writerow(["frame", "handedness", "landmarks", "finger_states", "joint_angles"])
        
        self._current_sign_id = sign_id
        self._current_csv_path = csv_path
        self._collected = 0
        self._target = needed
        self._frame_num = 0
        self._done_event.clear()
        self._paused = False
        
        logger.info(f"\n=== [{sign_id}] {label} ===")
        logger.info(f"Need {needed} more samples. Get ready...")
        
        # Countdown
        for i in range(3, 0, -1):
            logger.info(f"  {i}...")
            time.sleep(1)
        
        logger.info(f"  SHOW '{label}' NOW! (hold steady)")
        
        from PySide6.QtCore import QCoreApplication
        self.camera_service.frame_ready.connect(self._frame_callback)
        try:
            if not self.camera_service.acquire("collect_samples"):
                raise RuntimeError("No camera available for sample collection.")
            deadline = time.monotonic() + 120
            while not self._done_event.is_set():
                QCoreApplication.processEvents()
                if time.monotonic() > deadline:
                    raise RuntimeError("No complete sample set after 120 seconds. Check camera permission and hand visibility.")
                time.sleep(0.01)
        finally:
            self._done_event.set()
            self.camera_service.frame_ready.disconnect(self._frame_callback)
            self.camera_service.release("collect_samples")
            self._csv_file.close()
            self._csv_file = None
            self._csv_writer = None

        total = existing + self._collected
        logger.info(f"[{sign_id}] Done! Collected {self._collected} new samples (total: {total}/{count})")
        return total

    def cleanup(self):
        self.hand_tracker.close()
        CameraService.destroy_instance()


def main():
    parser = argparse.ArgumentParser(description="Collect ASL sign samples from camera")
    parser.add_argument("--sign", help="Specific sign ID to collect (e.g., asl_a)")
    parser.add_argument("--count", type=int, default=50, help="Target samples per sign")
    parser.add_argument("--output-dir", default=str(SAMPLE_DIR), help="Output directory")
    parser.add_argument("--list", action="store_true", help="List available signs and sample counts")
    parser.add_argument("--hands", choices=["right", "left", "both"], default="both", help="Which hand(s) to collect")
    parser.add_argument("--skip-motion", action="store_true", default=True, help="Skip motion signs (J, Z, greetings, phrases)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load content pack
    loader = initialize_content_packs(PROJECT_ROOT / "content_packs")
    pack = loader.get_current_pack()
    if not pack:
        logger.error("No content pack loaded")
        return 1

    # Get signs to collect
    if args.sign:
        if args.sign not in pack.signs:
            logger.error(f"Unknown sign: {args.sign}")
            return 1
        signs_to_collect = [(args.sign, pack.signs[args.sign])]
    else:
        signs_to_collect = [(s.id, s) for s in pack.signs.values() if s.scored]
        if args.skip_motion:
            signs_to_collect = [(sid, s) for sid, s in signs_to_collect if not s.metadata.get("motion_sign")]

    if args.list:
        print(f"\n{'Sign ID':<15} {'Label':<12} {'Category':<15} {'Motion':<6} {'Samples'}")
        print("-" * 70)
        for sign_id, sign in pack.signs.items():
            csv_path = output_dir / f"{sign_id}.csv"
            count = 0
            if csv_path.exists():
                with open(csv_path, "r") as f:
                    count = sum(1 for _ in f) - 1
            motion = "yes" if sign.metadata.get("motion_sign") else "no"
            print(f"{sign_id:<15} {sign.label:<12} {sign.category.value:<15} {motion:<6} {count}")
        return 0

    from PySide6.QtGui import QGuiApplication
    application = QGuiApplication.instance() or QGuiApplication([])

    # Initialize collector
    collector = SampleCollector(output_dir, target_hand=args.hands)
    if not collector.initialize():
        return 1

    logger.info(f"Will collect for {len(signs_to_collect)} sign(s), {args.count} samples each")
    logger.info(f"Hand preference: {args.hands}")
    logger.info("Press Ctrl+C to stop early\n")

    try:
        for sign_id, sign in signs_to_collect:
            collector.collect_for_sign(sign_id, sign.label, args.count)
            # Brief pause between signs
            time.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
    
    finally:
        collector.cleanup()
    
    logger.info("\nAll done!")
    return 0


if __name__ == "__main__":
    sys.exit(main())