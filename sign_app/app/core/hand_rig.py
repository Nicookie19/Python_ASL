"""
Parametric hand rig for generating 21-point reference hand poses.

MediaPipe hand landmarks are produced by a neural network from real camera
imagery. This module instead synthesises anatomically-plausible poses from a
small set of pose parameters so the app can ship reference hand *figures* for
every sign without requiring recorded training data or a trained model.

Coordinate frame matches MediaPipe: normalised to the image, x right, y down,
z depth. Landmark indices are the standard MediaPipe ordering.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import numpy as np

# MediaPipe landmark indices
WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20

# Rest-pose geometry, normalised units (a hand spans roughly 0.2 of a frame).
_WRIST_POS = (0.500, 0.716)
_MCP_POS = {
    "index": (0.446, 0.548),
    "middle": (0.512, 0.528),
    "ring": (0.578, 0.542),
    "pinky": (0.634, 0.578),
}

# Proximal, middle, distal phalanx lengths.
_FINGER_LEN = {
    "index": (0.098, 0.062, 0.048),
    "middle": (0.108, 0.070, 0.052),
    "ring": (0.100, 0.066, 0.050),
    "pinky": (0.080, 0.052, 0.040),
}

# Rest direction of each finger (radians, -pi/2 points straight up).
_FINGER_BASE_ANGLE = -1.571

# Fan applied at spread=1.0: a natural, relaxed hand. `spread` scales this
# directly, so 0.0 draws fully closed fingers and 1.5 draws them wide apart.
_FINGER_FAN = {
    "index": -0.26,
    "middle": -0.02,
    "ring": 0.10,
    "pinky": 0.26,
}

_FINGER_ORDER = ("index", "middle", "ring", "pinky")

_THUMB_CMC = (0.436, 0.664)
_THUMB_LEN = (0.072, 0.058, 0.048)
_THUMB_BASE_ANGLE = -2.40

# Incremental flexion applied at the MCP/PIP/DIP joints as curl goes 0 -> 1.
# 1.85 rad at the PIP folds the finger over the palm; the further 1.20 rad
# brings the tip back down and inward, which is what a closed fist looks like.
# These are deltas added to the running direction angle, not absolute angles.
_CURL_STEPS = (0.0, 1.85, 1.20)

# How much the finger fan collapses as the fingers curl. A real fist pulls the
# fingers together; without this they splay outwards like a fan.
_CURL_CONVERGENCE = 0.65


@dataclass
class HandPose:
    """Pose parameters for a synthetic hand.

    curl        per-finger flexion 0 (straight) .. 1 (fully closed into palm)
    lateral     extra base-angle offset per finger, radians. Used for spread
                (V/W) and for crossing the fingers (R).
    thumb_angle base direction of the thumb chain, radians.
    thumb_curl  thumb flexion 0 .. 1.
    thumb_shift translation applied to the thumb root, normalised units.
    spread      scales the fan angle between fingers.
    rotation    whole-hand rotation about the wrist, radians.
    depth       per-finger z offset, used to separate overlapping fingers.
    """

    curl: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    lateral: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    thumb_angle: float = _THUMB_BASE_ANGLE
    thumb_curl: float = 0.0
    thumb_shift: Tuple[float, float] = (0.0, 0.0)
    spread: float = 1.0
    rotation: float = 0.0
    depth: Tuple[float, float, float, float] = (0.0, -0.02, 0.0, 0.02)


def _chain(
    origin: Tuple[float, float],
    base_angle: float,
    lengths: Tuple[float, float, float],
    curl: float,
) -> list:
    """Lay out a three-segment digit and return its 4 joint positions."""
    curl = float(np.clip(curl, 0.0, 1.0))
    points = [origin]
    x, y = origin
    angle = base_angle
    for i, length in enumerate(lengths):
        angle += curl * _CURL_STEPS[i]
        x += float(np.cos(angle)) * length
        y += float(np.sin(angle)) * length
        points.append((x, y))
    return points


def build_hand_landmarks(pose: Optional[HandPose] = None) -> np.ndarray:
    """Synthesise a (21, 3) normalised landmark array for the given pose."""
    pose = pose or HandPose()
    coords = np.zeros((21, 3), dtype=np.float32)

    # Fan the resting fingers apart or together.
    index_of = {name: i for i, name in enumerate(_FINGER_ORDER)}

    for finger in _FINGER_ORDER:
        i = index_of[finger]
        curl = pose.curl[i]
        lateral = pose.lateral[i]
        origin = _MCP_POS[finger]
        curl = float(np.clip(curl, 0.0, 1.0))
        fan = _FINGER_FAN[finger] * pose.spread * (1.0 - _CURL_CONVERGENCE * curl)
        angle = _FINGER_BASE_ANGLE + fan + lateral
        pts = _chain(origin, angle, _FINGER_LEN[finger], curl)
        base = finger_index_offset(finger)
        for j, (px, py) in enumerate(pts):
            coords[base + j, 0] = px
            coords[base + j, 1] = py
            coords[base + j, 2] = pose.depth[i]

    # Thumb
    thumb_origin = (
        _THUMB_CMC[0] + pose.thumb_shift[0],
        _THUMB_CMC[1] + pose.thumb_shift[1],
    )
    thumb_pts = _chain(thumb_origin, pose.thumb_angle, _THUMB_LEN, pose.thumb_curl)
    for j, (px, py) in enumerate(thumb_pts):
        coords[THUMB_CMC + j, 0] = px
        coords[THUMB_CMC + j, 1] = py
        coords[THUMB_CMC + j, 2] = -0.03

    coords[WRIST, 0], coords[WRIST, 1] = _WRIST_POS
    coords[WRIST, 2] = 0.02

    if pose.rotation:
        pivot = np.array(_WRIST_POS, dtype=np.float64)
        centred = coords[:, :2].astype(np.float64) - pivot
        c, s = np.cos(pose.rotation), np.sin(pose.rotation)
        rot = np.array([[c, -s], [s, c]], dtype=np.float64)
        rotated = centred @ rot.T + pivot
        coords[:, :2] = rotated.astype(np.float32)

    return _normalize(coords)


def finger_index_offset(finger: str) -> int:
    """Landmark index of a finger's MCP joint."""
    return {"index": INDEX_MCP, "middle": MIDDLE_MCP, "ring": RING_MCP, "pinky": PINKY_MCP}[finger]


def _normalize(coords: np.ndarray, margin: float = 0.08) -> np.ndarray:
    """Scale and centre a pose into the unit square so it always fits the view."""
    xy = coords[:, :2]
    lo = xy.min(axis=0)
    hi = xy.max(axis=0)
    span = hi - lo
    span[span < 1e-6] = 1.0
    scale = (1.0 - 2 * margin) / float(span.max())
    centred = (xy - (lo + hi) / 2.0) * scale
    coords[:, :2] = centred + 0.5
    return coords


# --------------------------------------------------------------------------
# ASL fingerspelling and counting poses
# --------------------------------------------------------------------------

_OPEN = (0.0, 0.0, 0.0, 0.0)
_FIST = (1.0, 1.0, 1.0, 1.0)


def _pose(
    curl=_OPEN,
    lateral=(0.0, 0.0, 0.0, 0.0),
    thumb_angle=_THUMB_BASE_ANGLE,
    thumb_curl=0.0,
    thumb_shift=(0.0, 0.0),
    spread=1.0,
    rotation=0.0,
    depth=(0.0, -0.02, 0.0, 0.02),
) -> HandPose:
    return HandPose(
        curl=tuple(curl),
        lateral=tuple(lateral),
        thumb_angle=thumb_angle,
        thumb_curl=thumb_curl,
        thumb_shift=thumb_shift,
        spread=spread,
        rotation=rotation,
        depth=tuple(depth),
    )


ASL_POSES: Dict[str, HandPose] = {
    # --- Fingerspelling -----------------------------------------------------
    # A: closed fist, thumb resting alongside the index finger.
    "A": _pose(curl=_FIST, thumb_angle=-1.78, thumb_curl=0.12, thumb_shift=(-0.022, -0.034)),
    # B: four fingers extended and together, thumb folded across the palm.
    "B": _pose(spread=0.25, thumb_angle=-0.34, thumb_curl=0.28, thumb_shift=(0.012, 0.010)),
    # C: whole hand curved into an open C.
    "C": _pose(curl=(0.46, 0.46, 0.46, 0.46), thumb_angle=-1.95, thumb_curl=0.14),
    # D: index up, thumb touching the middle finger to close a loop.
    "D": _pose(curl=(0.0, 1.0, 1.0, 1.0), thumb_angle=-0.95, thumb_curl=0.58),
    # E: fingertips curled down onto the tucked thumb.
    "E": _pose(curl=(0.92, 0.95, 0.95, 0.95), thumb_angle=-0.28, thumb_curl=0.52,
               thumb_shift=(0.010, 0.006)),
    # F: index and thumb touching in a ring, other three extended.
    "F": _pose(curl=(0.34, 0.0, 0.0, 0.0), thumb_angle=-0.78, thumb_curl=0.52),
    # G: index and thumb extended together, pointing sideways.
    "G": _pose(curl=(0.0, 1.0, 1.0, 1.0), lateral=(-0.34, 0.0, 0.0, 0.0),
               thumb_angle=-1.74, thumb_curl=0.10, rotation=0.52),
    # H: index and middle extended together, pointing sideways.
    "H": _pose(curl=(0.0, 0.0, 1.0, 1.0), spread=0.08, rotation=0.52),
    # I: pinky extended.
    "I": _pose(curl=(1.0, 1.0, 1.0, 0.0), thumb_angle=-0.30, thumb_curl=0.45),
    # J: pinky extended. The sign itself is drawn with a J motion; this is the
    # start position a learner holds before tracing the curve.
    "J": _pose(curl=(1.0, 1.0, 1.0, 0.0), thumb_angle=-0.30, thumb_curl=0.45),
    # K: index up with the middle finger opened to a V, thumb between them.
    "K": _pose(curl=(0.0, 0.18, 1.0, 1.0), lateral=(0.0, 0.42, 0.0, 0.0),
               thumb_angle=-1.92, thumb_curl=0.12),
    # L: thumb and index at a right angle.
    "L": _pose(curl=(0.0, 1.0, 1.0, 1.0), thumb_angle=-1.88, thumb_curl=0.08),
    # M: three fingers draped over the thumb.
    "M": _pose(curl=(0.82, 0.90, 0.96, 1.0), thumb_angle=-0.62, thumb_curl=0.38),
    # N: two fingers draped over the thumb.
    "N": _pose(curl=(0.82, 0.96, 1.0, 1.0), thumb_angle=-0.58, thumb_curl=0.34),
    # O: all fingertips meet the thumb to close a ring.
    "O": _pose(curl=(0.70, 0.75, 0.78, 0.80), thumb_angle=-1.02, thumb_curl=0.34),
    # P: the K shape, rotated to point downward. Only the rotation differs from
    # K, so the thumb keeps K's angle and simply travels with the hand.
    "P": _pose(curl=(0.0, 0.18, 1.0, 1.0), lateral=(0.0, 0.42, 0.0, 0.0),
               thumb_angle=-1.92, thumb_curl=0.12, rotation=-0.85),
    # Q: the G shape, rotated to point downward.
    "Q": _pose(curl=(0.0, 1.0, 1.0, 1.0), lateral=(-0.34, 0.0, 0.0, 0.0),
               thumb_angle=-1.74, thumb_curl=0.10, rotation=-0.85),
    # R: index and middle crossed over one another.
    "R": _pose(curl=(0.0, 0.0, 1.0, 1.0), lateral=(0.24, -0.24, 0.0, 0.0),
               spread=0.45, thumb_angle=-0.34, thumb_curl=0.28),
    # S: fist with the thumb laid across the front of the fingers.
    "S": _pose(curl=_FIST, thumb_angle=-0.16, thumb_curl=0.46, thumb_shift=(0.014, -0.040)),
    # T: thumb wedged between the index and middle fingers.
    "T": _pose(curl=(0.74, 0.78, 1.0, 1.0), thumb_angle=-1.82, thumb_curl=0.10,
               thumb_shift=(-0.030, -0.030)),
    # U: index and middle together, pointing up.
    "U": _pose(curl=(0.0, 0.0, 1.0, 1.0), spread=0.06, thumb_angle=-0.34, thumb_curl=0.28),
    # V: index and middle spread apart.
    "V": _pose(curl=(0.0, 0.0, 1.0, 1.0), spread=1.55, thumb_angle=-0.34, thumb_curl=0.28),
    # W: index, middle and ring spread apart.
    "W": _pose(curl=(0.0, 0.0, 0.0, 1.0), spread=1.42, thumb_angle=-0.34, thumb_curl=0.28),
    # X: index finger hooked into a curve.
    "X": _pose(curl=(0.58, 1.0, 1.0, 1.0), thumb_angle=-0.30, thumb_curl=0.58),
    # Y: thumb and pinky extended wide.
    "Y": _pose(curl=(1.0, 1.0, 1.0, 0.0), thumb_angle=-2.22, thumb_curl=0.08),
    # Z: index extended, held in the Z start position (the sign itself is motion).
    "Z": _pose(curl=(0.0, 1.0, 1.0, 1.0), thumb_angle=-0.20, thumb_curl=0.50,
               thumb_shift=(0.020, 0.010)),
    # --- Numbers ------------------------------------------------------------
    "0": _pose(curl=(0.70, 0.75, 0.78, 0.80), thumb_angle=-1.02, thumb_curl=0.34),
    "1": _pose(curl=(0.0, 1.0, 1.0, 1.0), thumb_angle=-0.34, thumb_curl=0.40),
    "2": _pose(curl=(0.0, 0.0, 1.0, 1.0), spread=1.45, thumb_angle=-0.34, thumb_curl=0.28),
    "3": _pose(curl=(0.0, 0.0, 1.0, 1.0), spread=0.60, thumb_angle=-1.46, thumb_curl=0.14),
    "4": _pose(spread=0.48, thumb_angle=-0.52, thumb_curl=0.34),
    "5": _pose(spread=1.05, thumb_angle=-2.52, thumb_curl=0.08),
    "6": _pose(curl=(1.0, 1.0, 1.0, 0.0), thumb_angle=-0.62, thumb_curl=0.30),
    "7": _pose(curl=(0.0, 0.0, 1.0, 1.0), thumb_angle=-0.92, thumb_curl=0.34),
    "8": _pose(curl=(1.0, 0.0, 1.0, 1.0), thumb_angle=-1.34, thumb_curl=0.20),
    "9": _pose(curl=(0.40, 0.0, 0.0, 0.0), thumb_angle=-0.74, thumb_curl=0.50),
}


def reference_landmarks_for(label: str) -> Optional[np.ndarray]:
    """Return (21, 3) reference landmarks for a sign label, or None."""
    pose = ASL_POSES.get(str(label).strip().upper())
    if pose is None:
        return None
    return build_hand_landmarks(pose)


def is_static_sign(label: str) -> bool:
    """True when a pose figure can be drawn for this label."""
    return str(label).strip().upper() in ASL_POSES