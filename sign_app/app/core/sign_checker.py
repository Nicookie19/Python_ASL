#!/usr/bin/env python3
"""
Sign Checker — Two-layer correctness validation for ASL signs.

Layer 1: Rule-based finger-state + joint-angle comparison against recorded reference
Layer 2: StaticRecognizer probability (ML model)

Output: is_correct, confidence (0-1), per-joint status, human-readable hint.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

from app.core.hand_tracker import HandLandmarks, Handedness
from app.core.features import FeatureExtractor
from app.core.recognizer import StaticRecognizer, RecognitionResult

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

FINGER_NAMES = ["thumb", "index", "middle", "ring", "pinky"]
FINGER_CHAINS = {
    "thumb": (4, 3, 2),
    "index": (8, 6, 5),
    "middle": (12, 10, 9),
    "ring": (16, 14, 13),
    "pinky": (20, 18, 17),
}

# Landmark indices for joints used in per-joint feedback
JOINT_NAMES = {
    0: "wrist",
    1: "thumb_cmc", 2: "thumb_mcp", 3: "thumb_ip", 4: "thumb_tip",
    5: "index_mcp", 6: "index_pip", 7: "index_dip", 8: "index_tip",
    9: "middle_mcp", 10: "middle_pip", 11: "middle_dip", 12: "middle_tip",
    13: "ring_mcp", 14: "ring_pip", 15: "ring_dip", 16: "ring_tip",
    17: "pinky_mcp", 18: "pinky_pip", 19: "pinky_dip", 20: "pinky_tip",
}

# Finger tip indices for coloring
FINGERTIP_INDICES = [4, 8, 12, 16, 20]


@dataclass
class JointStatus:
    """Per-joint correctness status."""
    index: int
    name: str
    distance: float
    status: str  # "correct", "close", "incorrect"
    hint: str = ""


@dataclass
class FingerStatus:
    """Per-finger correctness status."""
    name: str
    target_state: str  # "extended", "partial", "curled"
    actual_state: str
    match: bool
    hint: str = ""


@dataclass
class CheckResult:
    """Complete check result."""
    is_correct: bool
    confidence: float  # 0-1 combined confidence
    rule_confidence: float  # Layer 1 confidence
    ml_confidence: float    # Layer 2 confidence
    joint_statuses: List[JointStatus]
    finger_statuses: List[FingerStatus]
    hint: str  # Human-readable feedback
    ml_prediction: Optional[str] = None
    ml_scores: Dict[str, float] = field(default_factory=dict)


class SignChecker:
    """
    Two-layer sign correctness checker.
    
    Layer 1 (Rule-based): Compares normalized landmarks against recorded reference
    - Per-landmark distance vs tolerance
    - Finger state consensus (extended/partial/curled)
    - Joint angle deviations
    
    Layer 2 (ML): StaticRecognizer probability distribution
    
    Final decision: Both layers must agree above threshold.
    """
    
    def __init__(
        self,
        signs_data: Dict[str, Dict],
        recognizer: Optional[StaticRecognizer] = None,
        strictness: str = "normal"  # "easy", "normal", "strict"
    ):
        self.signs_data = signs_data
        self.recognizer = recognizer
        self.strictness = strictness
        
        # Strictness thresholds
        self.thresholds = {
            "easy": {
                "landmark_tolerance_mult": 1.5,
                "finger_state_required_match": 0.6,  # 60% of fingers must match
                "joint_angle_tolerance_deg": 25,
                "min_confidence": 0.55,
                "ml_weight": 0.4,
            },
            "normal": {
                "landmark_tolerance_mult": 1.0,
                "finger_state_required_match": 0.8,
                "joint_angle_tolerance_deg": 15,
                "min_confidence": 0.70,
                "ml_weight": 0.5,
            },
            "strict": {
                "landmark_tolerance_mult": 0.7,
                "finger_state_required_match": 1.0,
                "joint_angle_tolerance_deg": 10,
                "min_confidence": 0.80,
                "ml_weight": 0.6,
            },
        }
        
        self.feature_extractor = FeatureExtractor(
            mirror_left_to_right=True,
            use_3d=True,
            include_angles=True,
            include_distances=True
        )
    
    def set_strictness(self, strictness: str):
        if strictness in self.thresholds:
            self.strictness = strictness
            logger.info(f"SignChecker strictness set to: {strictness}")
        else:
            logger.warning(f"Unknown strictness: {strictness}")
    
    def _get_thresholds(self) -> Dict:
        return self.thresholds.get(self.strictness, self.thresholds["normal"])
    
    def _normalize_landmarks(self, hand: HandLandmarks) -> np.ndarray:
        """Normalize landmarks: wrist origin, scale by hand size, mirror left->right."""
        landmarks = hand.landmarks.copy()
        wrist = landmarks[0]
        landmarks = landmarks - wrist
        middle_mcp = landmarks[9]
        hand_scale = np.linalg.norm(middle_mcp[:2]) + 1e-6
        landmarks = landmarks / hand_scale
        if hand.handedness.value == "left":
            landmarks[:, 0] = -landmarks[:, 0]
        return landmarks.astype(np.float32)
    
    def _get_finger_state(self, landmarks: np.ndarray, finger: str) -> str:
        """Classify finger as extended/partial/curled."""
        tip_idx, pip_idx, mcp_idx = FINGER_CHAINS[finger]
        tip = landmarks[tip_idx]
        pip = landmarks[pip_idx]
        mcp = landmarks[mcp_idx]
        tip_to_mcp = np.linalg.norm(tip[:2] - mcp[:2])
        pip_to_mcp = np.linalg.norm(pip[:2] - mcp[:2])
        if pip_to_mcp < 1e-6:
            return "unknown"
        ratio = tip_to_mcp / pip_to_mcp
        if ratio > 1.5:
            return "extended"
        elif ratio > 0.8:
            return "partial"
        else:
            return "curled"
    
    def _get_joint_angles(self, landmarks: np.ndarray) -> Dict[str, float]:
        """Compute joint angles in radians."""
        angles = {}
        chains = {
            "thumb": (1, 2, 3, 4),
            "index": (5, 6, 7, 8),
            "middle": (9, 10, 11, 12),
            "ring": (13, 14, 15, 16),
            "pinky": (17, 18, 19, 20),
        }
        for name, (mcp, pip, dip, tip) in chains.items():
            v1 = landmarks[mcp] - landmarks[pip]
            v2 = landmarks[dip] - landmarks[pip]
            dot = np.dot(v1[:2], v2[:2])
            norm = np.linalg.norm(v1[:2]) * np.linalg.norm(v2[:2])
            if norm > 1e-6:
                angles[f"{name}_pip"] = float(np.arccos(np.clip(dot / norm, -1.0, 1.0)))
            v1 = landmarks[pip] - landmarks[dip]
            v2 = landmarks[tip] - landmarks[dip]
            dot = np.dot(v1[:2], v2[:2])
            norm = np.linalg.norm(v1[:2]) * np.linalg.norm(v2[:2])
            if norm > 1e-6:
                angles[f"{name}_dip"] = float(np.arccos(np.clip(dot / norm, -1.0, 1.0)))
        return angles
    
    def check(self, hand: HandLandmarks, target_sign_id: str) -> CheckResult:
        """
        Check if the hand matches the target sign.
        Returns CheckResult with all details.
        """
        sign_data = self.signs_data.get(target_sign_id)
        if not sign_data:
            return CheckResult(
                is_correct=False,
                confidence=0.0,
                rule_confidence=0.0,
                ml_confidence=0.0,
                joint_statuses=[],
                finger_statuses=[],
                hint=f"Unknown sign: {target_sign_id}"
            )
        
        reference = sign_data.get("reference")
        if not reference:
            return CheckResult(
                is_correct=False,
                confidence=0.0,
                rule_confidence=0.0,
                ml_confidence=0.0,
                joint_statuses=[],
                finger_statuses=[],
                hint=f"No reference data for {target_sign_id}"
            )
        
        thresholds = self._get_thresholds()
        
        # Normalize current hand
        norm_landmarks = self._normalize_landmarks(hand)
        
        # === LAYER 1: Rule-based checks ===
        
        # 1. Per-landmark distances
        ref_landmarks = np.array(reference["median_landmarks"], dtype=np.float32)  # (21, 3)
        ref_tolerances = np.array(reference.get("landmark_tolerances", []), dtype=np.float32)
        if len(ref_tolerances) == 0:
            # Fallback: use fixed tolerance
            ref_tolerances = np.full((21, 3), 0.03, dtype=np.float32)
        
        landmark_dists = np.linalg.norm(norm_landmarks - ref_landmarks, axis=1)  # (21,)
        tol_mult = thresholds["landmark_tolerance_mult"]
        joint_statuses = []
        
        for i in range(21):
            dist = float(landmark_dists[i])
            tolerance = float(ref_tolerances[i, :2].mean()) * tol_mult  # Use XY tolerance
            tolerance = max(tolerance, 0.02)  # Minimum tolerance
            
            if dist < tolerance * 0.5:
                status = "correct"
            elif dist < tolerance:
                status = "close"
            else:
                status = "incorrect"
            
            joint_name = JOINT_NAMES.get(i, f"joint_{i}")
            hint = ""
            if status != "correct":
                hint = self._generate_joint_hint(i, norm_landmarks, ref_landmarks)
            
            joint_statuses.append(JointStatus(
                index=i,
                name=joint_name,
                distance=dist,
                status=status,
                hint=hint
            ))
        
        # 2. Finger states
        ref_finger_states = reference.get("finger_states", {})
        finger_statuses = []
        finger_matches = 0
        
        for finger in FINGER_NAMES:
            target_state = ref_finger_states.get(finger, {}).get("state", "unknown")
            actual_state = self._get_finger_state(norm_landmarks, finger)
            match = (target_state == actual_state)
            if match:
                finger_matches += 1
            
            hint = ""
            if not match and target_state != "unknown":
                hint = f"{finger.capitalize()} should be {target_state}, not {actual_state}"
            
            finger_statuses.append(FingerStatus(
                name=finger,
                target_state=target_state,
                actual_state=actual_state,
                match=match,
                hint=hint
            ))
        
        finger_match_ratio = finger_matches / len(FINGER_NAMES)
        
        # 3. Joint angles (optional, for additional confidence)
        angle_score = 1.0
        ref_angles = reference.get("joint_angles", {})
        if ref_angles:
            actual_angles = self._get_joint_angles(norm_landmarks)
            angle_diffs = []
            for angle_name, ref_data in ref_angles.items():
                if angle_name in actual_angles:
                    diff_deg = abs(actual_angles[angle_name] - ref_data["median"]) * 180 / np.pi
                    tolerance_deg = thresholds["joint_angle_tolerance_deg"]
                    if diff_deg < tolerance_deg * 0.5:
                        angle_diffs.append(1.0)
                    elif diff_deg < tolerance_deg:
                        angle_diffs.append(0.7)
                    else:
                        angle_diffs.append(0.3)
            if angle_diffs:
                angle_score = np.mean(angle_diffs)
        
        # Layer 1 combined confidence
        landmark_correct_ratio = sum(1 for j in joint_statuses if j.status == "correct") / 21
        landmark_close_ratio = sum(1 for j in joint_statuses if j.status in ("correct", "close")) / 21
        
        rule_confidence = (
            0.4 * landmark_correct_ratio +
            0.3 * finger_match_ratio +
            0.2 * landmark_close_ratio +
            0.1 * angle_score
        )
        
        # === LAYER 2: ML Recognizer ===
        ml_confidence = 0.0
        ml_prediction = None
        ml_scores = {}
        
        if self.recognizer and self.recognizer.model_available:
            try:
                feature_vec = self.feature_extractor.extract(hand)
                recognition = self.recognizer.predict(feature_vec.features)
                ml_prediction = recognition.label
                ml_confidence = recognition.confidence
                ml_scores = recognition.all_scores
            except Exception as e:
                logger.warning(f"ML recognition failed: {e}")
        
        # === COMBINE ===
        ml_weight = thresholds["ml_weight"]
        rule_weight = 1.0 - ml_weight
        
        if self.recognizer and self.recognizer.model_available:
            combined_confidence = rule_weight * rule_confidence + ml_weight * ml_confidence
        else:
            combined_confidence = rule_confidence
            ml_confidence = 0.0
        
        # Decision: both layers must be above threshold (if ML available)
        min_conf = thresholds["min_confidence"]
        finger_required = thresholds["finger_state_required_match"]
        
        rule_pass = (rule_confidence >= min_conf) and (finger_match_ratio >= finger_required)
        ml_pass = True
        if self.recognizer and self.recognizer.model_available:
            ml_pass = (ml_confidence >= min_conf) and (ml_prediction == target_sign_id)
        
        is_correct = rule_pass and ml_pass
        
        # Generate human-readable hint
        hint = self._generate_hint(is_correct, joint_statuses, finger_statuses, ml_prediction, target_sign_id)
        
        return CheckResult(
            is_correct=is_correct,
            confidence=combined_confidence,
            rule_confidence=rule_confidence,
            ml_confidence=ml_confidence,
            joint_statuses=joint_statuses,
            finger_statuses=finger_statuses,
            hint=hint,
            ml_prediction=ml_prediction,
            ml_scores=ml_scores
        )
    
    def _generate_joint_hint(self, joint_idx: int, actual: np.ndarray, target: np.ndarray) -> str:
        """Generate specific hint for a misaligned joint."""
        joint_name = JOINT_NAMES.get(joint_idx, f"joint_{joint_idx}")
        diff = target[joint_idx] - actual[joint_idx]
        
        if joint_idx in FINGERTIP_INDICES:
            # Fingertip hints
            if abs(diff[0]) > abs(diff[1]):
                return f"Move {joint_name} {'right' if diff[0] > 0 else 'left'}"
            else:
                return f"Move {joint_name} {'up' if diff[1] < 0 else 'down'}"
        elif joint_idx in [2, 5, 9, 13, 17]:  # MCPs
            return f"Adjust {joint_name} position"
        else:
            return f"Adjust {joint_name}"
    
    def _generate_hint(
        self,
        is_correct: bool,
        joint_statuses: List[JointStatus],
        finger_statuses: List[FingerStatus],
        ml_prediction: Optional[str],
        target_sign_id: str
    ) -> str:
        """Generate human-readable feedback hint."""
        if is_correct:
            return "Correct! 🎉"
        
        hints = []
        
        # Priority 1: Finger state mismatches (most actionable)
        for fs in finger_statuses:
            if not fs.match and fs.hint:
                hints.append(fs.hint)
        
        # Priority 2: Major landmark errors (thumb, fingertips)
        major_joints = [j for j in joint_statuses if j.status == "incorrect" and 
                       (j.index in [1, 2, 4, 5, 8, 9, 12, 13, 16, 17, 20])]
        for j in major_joints[:3]:  # Top 3
            if j.hint:
                hints.append(j.hint)
        
        # ML prediction info
        if ml_prediction and ml_prediction != target_sign_id:
            hints.append(f"Model saw: {ml_prediction}")
        
        if not hints:
            return "Adjust your hand shape"
        
        return hints[0]  # Return most important hint
    
    def get_color_map(self, joint_statuses: List[JointStatus]) -> Dict[int, Tuple[int, int, int]]:
        """Get BGR color map for joint visualization (green/yellow/red)."""
        color_map = {}
        for js in joint_statuses:
            if js.status == "correct":
                color_map[js.index] = (0, 255, 0)      # Green
            elif js.status == "close":
                color_map[js.index] = (0, 255, 255)    # Yellow
            else:
                color_map[js.index] = (0, 0, 255)      # Red
        return color_map


def load_signs_with_references(pack_dir: Path) -> Dict[str, Dict]:
    """Load signs.json and return dict keyed by sign_id with reference data."""
    signs_path = pack_dir / "signs.json"
    with open(signs_path, "r", encoding="utf-8") as f:
        signs = json.load(f)
    return {s["id"]: s for s in signs}


def create_sign_checker(
    pack_dir: Path,
    recognizer: Optional[StaticRecognizer] = None,
    strictness: str = "normal"
) -> SignChecker:
    """Factory function to create SignChecker from content pack."""
    signs_data = load_signs_with_references(pack_dir)
    return SignChecker(signs_data, recognizer, strictness)