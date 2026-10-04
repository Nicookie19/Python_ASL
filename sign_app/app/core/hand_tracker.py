"""
Hand tracking using MediaPipe.
Wraps both legacy and Tasks API behind a unified interface.
"""

import cv2
import numpy as np
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict, Any
from enum import Enum
import logging
import time

logger = logging.getLogger(__name__)


class Handedness(Enum):
    LEFT = "left"
    RIGHT = "right"
    UNKNOWN = "unknown"


@dataclass
class HandLandmarks:
    """Normalized 3D hand landmarks (21 points, x,y,z in [0,1] relative to image)."""
    landmarks: np.ndarray  # Shape (21, 3) - x, y, z normalized
    handedness: Handedness
    confidence: float
    image_width: int
    image_height: int

    def to_pixel_coords(self) -> np.ndarray:
        """Convert normalized landmarks to pixel coordinates."""
        coords = self.landmarks.copy()
        coords[:, 0] *= self.image_width
        coords[:, 1] *= self.image_height
        return coords

    def get_wrist(self) -> np.ndarray:
        """Get wrist landmark (index 0)."""
        return self.landmarks[0]

    def get_fingertips(self) -> Dict[str, np.ndarray]:
        """Get fingertip landmarks by name."""
        return {
            'thumb': self.landmarks[4],
            'index': self.landmarks[8],
            'middle': self.landmarks[12],
            'ring': self.landmarks[16],
            'pinky': self.landmarks[20]
        }

    def get_mcp_joints(self) -> Dict[str, np.ndarray]:
        """Get MCP (knuckle) landmarks."""
        return {
            'thumb': self.landmarks[2],
            'index': self.landmarks[5],
            'middle': self.landmarks[9],
            'ring': self.landmarks[13],
            'pinky': self.landmarks[17]
        }


@dataclass
class HandTrackerResult:
    """Result from hand tracking."""
    hands: List[HandLandmarks]
    annotated_frame: Optional[np.ndarray] = None
    processing_time_ms: float = 0.0
    fps: float = 0.0


class HandTracker:
    """
    Unified hand tracker supporting both MediaPipe legacy and Tasks API.
    Automatically detects which API is available.
    """

    # MediaPipe hand landmark connections for drawing skeleton
    HAND_CONNECTIONS = [
        (0, 1), (1, 2), (2, 3), (3, 4),      # Thumb
        (0, 5), (5, 6), (6, 7), (7, 8),      # Index
        (0, 9), (9, 10), (10, 11), (11, 12), # Middle
        (0, 13), (13, 14), (14, 15), (15, 16), # Ring
        (0, 17), (17, 18), (18, 19), (19, 20), # Pinky
        (5, 9), (9, 13), (13, 17)             # Palm
    ]

    def __init__(
        self,
        max_hands: int = 2,
        min_detection_confidence: float = 0.7,
        min_tracking_confidence: float = 0.5,
        model_complexity: int = 1
    ):
        self.max_hands = max_hands
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.model_complexity = model_complexity

        self._tracker = None
        self._use_tasks_api = False
        self._initialized = False
        self._last_timestamp = 0

        # For FPS calculation
        self._frame_times: List[float] = []

    def initialize(self) -> bool:
        """Initialize the hand tracker. Returns True if successful."""
        if self._initialized:
            return True

        # Use Tasks API (only option in MediaPipe 0.10.35+)
        if self._try_init_tasks_api():
            self._use_tasks_api = True
            logger.info("HandTracker initialized with MediaPipe Tasks API")
            self._initialized = True
            return True

        logger.error("Failed to initialize MediaPipe hand tracking")
        return False

    def _try_init_tasks_api(self) -> bool:
        """Try to initialize MediaPipe Tasks API HandLandmarker."""
        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            # Check if HandLandmarker exists (Tasks API)
            if not hasattr(vision, 'HandLandmarker'):
                return False

            base_options = python.BaseOptions(model_asset_path=self._get_model_path())
            # LIVE_STREAM mode enables tracking across frames with timestamps
            options = vision.HandLandmarkerOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.LIVE_STREAM,
                num_hands=self.max_hands,
                min_hand_detection_confidence=self.min_detection_confidence,
                min_hand_presence_confidence=self.min_tracking_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
                result_callback=self._tasks_callback,
            )
            self._tracker = vision.HandLandmarker.create_from_options(options)
            self._tasks_result = None
            return True
        except Exception as e:
            logger.debug(f"Tasks API initialization failed: {e}")
            return False

    def _try_init_legacy_api(self) -> bool:
        """Try to initialize MediaPipe legacy solutions.hands."""
        try:
            import mediapipe as mp
            self._tracker = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=self.max_hands,
                min_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
                model_complexity=self.model_complexity
            )
            self._mp_drawing = mp.solutions.drawing_utils
            self._mp_hands = mp.solutions.hands
            return True
        except Exception as e:
            logger.debug(f"Legacy API initialization failed: {e}")
            return False

    def _get_model_path(self) -> str:
        """Get path to MediaPipe hand landmarker model."""
        # First check bundled model in project
        import os
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        bundled_path = os.path.join(project_root, 'models', 'hand_landmarker.task')
        if os.path.exists(bundled_path):
            return bundled_path

        # Fallback to MediaPipe package location
        try:
            from mediapipe.tasks.python import vision
            model_path = os.path.join(os.path.dirname(vision.__file__), 'hand_landmarker.task')
            if os.path.exists(model_path):
                return model_path
        except Exception as e:
            logger.warning(f"Could not get model path from MediaPipe package: {e}")

        logger.error("MediaPipe hand_landmarker.task model not found. Download from https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task")
        return ""

    def _tasks_callback(self, result, output_image, timestamp_ms):
        """Callback for Tasks API async results."""
        self._tasks_result = result

    def process(self, frame: np.ndarray) -> HandTrackerResult:
        """
        Process a frame and return hand landmarks.
        Frame should be BGR (OpenCV format).
        """
        if not self._initialized:
            if not self.initialize():
                return HandTrackerResult(hands=[])

        start_time = time.perf_counter()
        h, w = frame.shape[:2]

        if self._use_tasks_api:
            result = self._process_tasks(frame, w, h)
        else:
            result = self._process_legacy(frame, w, h)

        # Calculate FPS
        processing_time = (time.perf_counter() - start_time) * 1000
        self._frame_times.append(time.perf_counter())
        if len(self._frame_times) > 30:
            self._frame_times.pop(0)
        fps = len(self._frame_times) / (self._frame_times[-1] - self._frame_times[0]) if len(self._frame_times) > 1 else 0

        result.processing_time_ms = processing_time
        result.fps = fps

        return result

    def process(self, frame: np.ndarray, timestamp_ms: int = 0) -> HandTrackerResult:
        """
        Process a frame and return hand landmarks.
        Frame should be BGR (OpenCV format).
        timestamp_ms: optional timestamp in milliseconds for LIVE_STREAM mode
        """
        if not self._initialized:
            if not self.initialize():
                return HandTrackerResult(hands=[])

        start_time = time.perf_counter()
        h, w = frame.shape[:2]

        if self._use_tasks_api:
            result = self._process_tasks(frame, w, h, timestamp_ms)
        else:
            result = self._process_legacy(frame, w, h)

        # Calculate FPS
        processing_time = (time.perf_counter() - start_time) * 1000
        self._frame_times.append(time.perf_counter())
        if len(self._frame_times) > 30:
            self._frame_times.pop(0)
        fps = len(self._frame_times) / (self._frame_times[-1] - self._frame_times[0]) if len(self._frame_times) > 1 else 0

        result.processing_time_ms = processing_time
        result.fps = fps

        return result

    def _process_tasks(self, frame: np.ndarray, w: int, h: int, timestamp_ms: int = 0) -> HandTrackerResult:
        """Process using Tasks API in LIVE_STREAM mode."""
        import mediapipe as mp

        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        # LIVE_STREAM mode: submit frame for async processing
        # The result will be delivered via _tasks_callback
        if timestamp_ms == 0:
            timestamp_ms = int(time.time() * 1000)
        self._tasks_result = None
        self._tracker.detect_async(mp_image, timestamp_ms)

        # Wait for result (with timeout)
        timeout = 0.1  # 100ms max wait
        start_wait = time.time()
        while self._tasks_result is None and (time.time() - start_wait) < timeout:
            time.sleep(0.001)

        hands = []
        if self._tasks_result and self._tasks_result.hand_landmarks:
            for i, (landmarks, handedness) in enumerate(zip(
                self._tasks_result.hand_landmarks,
                self._tasks_result.handedness
            )):
                # Convert to numpy array
                lm_array = np.array([[lm.x, lm.y, lm.z] for lm in landmarks], dtype=np.float32)

                # Get handedness
                hand_label = handedness[0].category_name.lower() if handedness else "unknown"
                hand_enum = Handedness.LEFT if hand_label == "left" else Handedness.RIGHT

                hands.append(HandLandmarks(
                    landmarks=lm_array,
                    handedness=hand_enum,
                    confidence=handedness[0].score if handedness else 1.0,
                    image_width=w,
                    image_height=h
                ))

        # Create annotated frame
        annotated = frame.copy()
        if hands:
            annotated = self.draw_landmarks(annotated, hands)

        return HandTrackerResult(hands=hands, annotated_frame=annotated)

    def _process_legacy(self, frame: np.ndarray, w: int, h: int) -> HandTrackerResult:
        """Process using legacy API."""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._tracker.process(rgb_frame)

        hands = []
        if results.multi_hand_landmarks:
            for i, (landmarks, handedness) in enumerate(zip(
                results.multi_hand_landmarks,
                results.multi_handedness
            )):
                lm_array = np.array([[lm.x, lm.y, lm.z] for lm in landmarks.landmark], dtype=np.float32)

                hand_label = handedness.classification[0].label.lower()
                hand_enum = Handedness.LEFT if hand_label == "left" else Handedness.RIGHT
                confidence = handedness.classification[0].score

                hands.append(HandLandmarks(
                    landmarks=lm_array,
                    handedness=hand_enum,
                    confidence=confidence,
                    image_width=w,
                    image_height=h
                ))

        annotated = frame.copy()
        if hands:
            annotated = self.draw_landmarks(annotated, hands)

        return HandTrackerResult(hands=hands, annotated_frame=annotated)

    def draw_landmarks(
        self,
        frame: np.ndarray,
        hands: List[HandLandmarks],
        connections: Optional[List[Tuple[int, int]]] = None,
        color_by_correctness: Optional[Dict[int, Tuple[int, int, int]]] = None
    ) -> np.ndarray:
        """
        Draw hand skeleton on frame.
        If color_by_correctness is provided, maps landmark index to BGR color.
        """
        annotated = frame.copy()
        conns = connections or self.HAND_CONNECTIONS

        for hand in hands:
            pixel_coords = hand.to_pixel_coords().astype(int)

            # Draw connections
            for start_idx, end_idx in conns:
                if start_idx < len(pixel_coords) and end_idx < len(pixel_coords):
                    pt1 = tuple(pixel_coords[start_idx])
                    pt2 = tuple(pixel_coords[end_idx])

                    # Determine color
                    if color_by_correctness:
                        # Average color of the two landmarks
                        c1 = color_by_correctness.get(start_idx, (255, 255, 255))
                        c2 = color_by_correctness.get(end_idx, (255, 255, 255))
                        color = tuple((np.array(c1) + np.array(c2)) // 2)
                    else:
                        color = (100, 200, 100)  # Default greenish

                    cv2.line(annotated, pt1, pt2, color, 2)

            # Draw landmark points
            for i, pt in enumerate(pixel_coords):
                if color_by_correctness and i in color_by_correctness:
                    color = color_by_correctness[i]
                else:
                    color = (255, 255, 255)  # White default

                cv2.circle(annotated, tuple(pt), 4, color, -1)
                cv2.circle(annotated, tuple(pt), 6, (0, 0, 0), 1)  # Black outline

        return annotated

    def draw_skeleton_with_feedback(
        self,
        frame: np.ndarray,
        hands: List[HandLandmarks],
        target_sign_landmarks: Optional[np.ndarray] = None,
        correctness_threshold: float = 0.7
    ) -> np.ndarray:
        """
        Draw skeleton colored by correctness compared to target sign.
        Green = matches target, Red = off-target, White = neutral/no target.
        """
        if target_sign_landmarks is None:
            return self.draw_landmarks(frame, hands)

        color_map = {}
        for hand in hands:
            pixel_coords = hand.to_pixel_coords()
            target_pixel = target_sign_landmarks * np.array([hand.image_width, hand.image_height, 1.0])

            # Compute per-landmark distance
            for i in range(21):
                if i < len(pixel_coords) and i < len(target_pixel):
                    dist = np.linalg.norm(pixel_coords[i, :2] - target_pixel[i, :2])
                    normalized_dist = dist / max(hand.image_width, hand.image_height)

                    if normalized_dist < (1.0 - correctness_threshold):
                        color_map[i] = (0, 255, 0)  # Green - correct
                    elif normalized_dist < 0.15:
                        color_map[i] = (0, 255, 255)  # Yellow - close
                    else:
                        color_map[i] = (0, 0, 255)  # Red - incorrect

        return self.draw_landmarks(frame, hands, color_by_correctness=color_map)

    def close(self) -> None:
        """Release resources."""
        if self._tracker and not self._use_tasks_api:
            self._tracker.close()
        elif self._tracker and self._use_tasks_api:
            self._tracker.close()
        self._tracker = None
        self._initialized = False


# MediaPipe landmark indices reference
class LandmarkIndex:
    """MediaPipe hand landmark indices."""
    WRIST = 0
    THUMB_CMC = 1
    THUMB_MCP = 2
    THUMB_IP = 3
    THUMB_TIP = 4
    INDEX_MCP = 5
    INDEX_PIP = 6
    INDEX_DIP = 7
    INDEX_TIP = 8
    MIDDLE_MCP = 9
    MIDDLE_PIP = 10
    MIDDLE_DIP = 11
    MIDDLE_TIP = 12
    RING_MCP = 13
    RING_PIP = 14
    RING_DIP = 15
    RING_TIP = 16
    PINKY_MCP = 17
    PINKY_PIP = 18
    PINKY_DIP = 19
    PINKY_TIP = 20

    # Fingertip indices
    FINGERTIPS = [THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP]
    # MCP joints
    MCPS = [THUMB_MCP, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP]
    # PIP joints
    PIPS = [THUMB_IP, INDEX_PIP, MIDDLE_PIP, RING_PIP, PINKY_PIP]
