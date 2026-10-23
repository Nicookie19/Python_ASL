"""
Content pack loader for sign language modules.
Each sign language is a folder with signs.json, model/, and templates/.
Adding a new language requires no code changes.
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import logging

from app.data.db import (
    Sign, Module, ModuleCategory, Difficulty,
    SignRepository, ModuleRepository
)

logger = logging.getLogger(__name__)


def _resolve_reference_landmarks(stored: Optional[Any], label: str) -> Optional[List[float]]:
    """Return stored reference landmarks, or synthesise them for known signs.

    Content packs ship descriptions but no landmark templates, which left the
    reference figure panel and the live skeleton comparison with nothing to
    draw. Fall back to the parametric hand rig for any sign it recognises.
    """
    if stored:
        return stored
    try:
        from app.core.hand_rig import reference_landmarks_for
        landmarks = reference_landmarks_for(label)
    except Exception as exc:  # pragma: no cover - rig is pure numpy
        logger.warning(f"Could not build reference landmarks for '{label}': {exc}")
        return None
    if landmarks is None:
        return None
    return landmarks.reshape(-1).tolist()


@dataclass
class ContentPack:
    """Represents a loaded content pack (sign language)."""
    id: str
    name: str
    version: str
    description: str
    author: str
    supported_categories: List[ModuleCategory]
    signs: Dict[str, Sign] = field(default_factory=dict)
    modules: Dict[str, Module] = field(default_factory=dict)
    model_path: Optional[Path] = None
    labels_path: Optional[Path] = None
    templates_path: Optional[Path] = None


class ContentPackLoader:
    """Loads and manages content packs from the content_packs directory."""

    def __init__(self, packs_dir: Path):
        self.packs_dir = Path(packs_dir)
        self._packs: Dict[str, ContentPack] = {}
        self._current_pack_id: Optional[str] = None

    def discover_packs(self) -> List[ContentPack]:
        """Discover all valid content packs in the packs directory."""
        packs = []
        if not self.packs_dir.exists():
            logger.warning(f"Content packs directory not found: {self.packs_dir}")
            return packs

        for pack_dir in self.packs_dir.iterdir():
            if not pack_dir.is_dir():
                continue

            manifest_path = pack_dir / "pack.json"
            if not manifest_path.exists():
                # Try legacy signs.json
                manifest_path = pack_dir / "signs.json"
                if not manifest_path.exists():
                    logger.warning(f"No manifest found in {pack_dir}, skipping")
                    continue

            try:
                pack = self._load_pack(pack_dir)
                packs.append(pack)
                self._packs[pack.id] = pack
                logger.info(f"Loaded content pack: {pack.name} ({pack.id})")
            except Exception as e:
                logger.error(f"Failed to load pack from {pack_dir}: {e}")

        return packs

    def _load_pack(self, pack_dir: Path) -> ContentPack:
        """Load a single content pack from its directory."""
        manifest_path = pack_dir / "pack.json"
        if manifest_path.exists():
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
        else:
            # Legacy support: signs.json only
            with open(pack_dir / "signs.json", 'r', encoding='utf-8') as f:
                signs_data = json.load(f)
            manifest = {
                "id": pack_dir.name,
                "name": pack_dir.name.upper(),
                "version": "1.0.0",
                "description": "",
                "author": "",
                "supported_categories": [c.value for c in ModuleCategory]
            }

        pack = ContentPack(
            id=manifest["id"],
            name=manifest["name"],
            version=manifest.get("version", "1.0.0"),
            description=manifest.get("description", ""),
            author=manifest.get("author", ""),
            supported_categories=[ModuleCategory(c) for c in manifest.get("supported_categories", [c.value for c in ModuleCategory])],
        )

        # Load signs
        signs_path = pack_dir / "signs.json"
        if signs_path.exists():
            with open(signs_path, 'r', encoding='utf-8') as f:
                signs_data = json.load(f)
            for sign_data in signs_data:
                sign = Sign(
                    id=sign_data["id"],
                    label=sign_data["label"],
                    category=ModuleCategory(sign_data["category"]),
                    difficulty=Difficulty(sign_data["difficulty"]),
                    description=sign_data.get("description", ""),
                    scored=sign_data.get("scored", True),
                    handedness=sign_data.get("handedness", "both"),
                    reference_landmarks=_resolve_reference_landmarks(
                        sign_data.get("reference_landmarks"), sign_data["label"]
                    ),
                    metadata=sign_data.get("metadata", {})
                )
                pack.signs[sign.id] = sign

        # Load modules
        modules_path = pack_dir / "modules.json"
        if modules_path.exists():
            with open(modules_path, 'r', encoding='utf-8') as f:
                modules_data = json.load(f)
            for module_data in modules_data:
                module = Module(
                    id=module_data["id"],
                    name=module_data["name"],
                    category=ModuleCategory(module_data["category"]),
                    difficulty=Difficulty(module_data["difficulty"]),
                    sign_ids=module_data["sign_ids"],
                    description=module_data.get("description", ""),
                    estimated_time_minutes=module_data.get("estimated_time_minutes", 10)
                )
                pack.modules[module.id] = module

        # Model and template paths
        model_path = pack_dir / "model" / "model.joblib"
        if model_path.exists():
            pack.model_path = model_path

        labels_path = pack_dir / "model" / "labels.json"
        if labels_path.exists():
            pack.labels_path = labels_path

        templates_path = pack_dir / "templates"
        if templates_path.exists():
            pack.templates_path = templates_path

        return pack

    def get_pack(self, pack_id: str) -> Optional[ContentPack]:
        """Get a loaded content pack by ID."""
        return self._packs.get(pack_id)

    def get_current_pack(self) -> Optional[ContentPack]:
        """Get the currently active content pack."""
        if self._current_pack_id:
            return self._packs.get(self._current_pack_id)
        return None

    def set_current_pack(self, pack_id: str) -> bool:
        """Set the active content pack."""
        if pack_id in self._packs:
            self._current_pack_id = pack_id
            return True
        return False

    def sync_to_database(self, pack: ContentPack) -> None:
        """Sync content pack data to the database."""
        # Sync signs
        for sign in pack.signs.values():
            SignRepository.upsert(sign)

        # Sync modules
        for module in pack.modules.values():
            ModuleRepository.upsert(module)

        logger.info(f"Synced content pack {pack.id} to database: {len(pack.signs)} signs, {len(pack.modules)} modules")

    def get_signs_for_module(self, module_id: str) -> List[Sign]:
        """Get all signs for a module in the current pack."""
        pack = self.get_current_pack()
        if not pack or module_id not in pack.modules:
            return []

        module = pack.modules[module_id]
        return [pack.signs[sid] for sid in module.sign_ids if sid in pack.signs]

    def get_scored_signs(self) -> List[Sign]:
        """Get all scored signs from the current pack."""
        pack = self.get_current_pack()
        if not pack:
            return []
        return [s for s in pack.signs.values() if s.scored]


# Default ASL content pack definition
DEFAULT_ASL_SIGNS = [
    # Fingerspelling A-I, K-Y (24 letters, excluding J and Z which are motion)
    {"id": "asl_a", "label": "A", "category": "fingerspelling", "difficulty": "easy", "description": "Make a fist with thumb resting against the side of the index finger.", "scored": True, "handedness": "both"},
    {"id": "asl_b", "label": "B", "category": "fingerspelling", "difficulty": "easy", "description": "Hold fingers together and straight up, thumb tucked across palm.", "scored": True, "handedness": "both"},
    {"id": "asl_c", "label": "C", "category": "fingerspelling", "difficulty": "easy", "description": "Curve fingers and thumb into a C shape.", "scored": True, "handedness": "both"},
    {"id": "asl_d", "label": "D", "category": "fingerspelling", "difficulty": "easy", "description": "Index finger up, other fingers curled, thumb touching middle finger.", "scored": True, "handedness": "both"},
    {"id": "asl_e", "label": "E", "category": "fingerspelling", "difficulty": "easy", "description": "Fingers curled down, thumb tucked under fingertips.", "scored": True, "handedness": "both"},
    {"id": "asl_f", "label": "F", "category": "fingerspelling", "difficulty": "medium", "description": "Index finger and thumb touching in a circle, other fingers up.", "scored": True, "handedness": "both"},
    {"id": "asl_g", "label": "G", "category": "fingerspelling", "difficulty": "medium", "description": "Index finger and thumb extended sideways, other fingers curled.", "scored": True, "handedness": "both"},
    {"id": "asl_h", "label": "H", "category": "fingerspelling", "difficulty": "medium", "description": "Index and middle fingers extended sideways, thumb tucked.", "scored": True, "handedness": "both"},
    {"id": "asl_i", "label": "I", "category": "fingerspelling", "difficulty": "easy", "description": "Pinky finger up, other fingers curled, thumb tucked.", "scored": True, "handedness": "both"},
    {"id": "asl_k", "label": "K", "category": "fingerspelling", "difficulty": "medium", "description": "Index and middle fingers up in V, thumb between them.", "scored": True, "handedness": "both"},
    {"id": "asl_l", "label": "L", "category": "fingerspelling", "difficulty": "easy", "description": "Index finger and thumb extended in L shape, other fingers curled.", "scored": True, "handedness": "both"},
    {"id": "asl_m", "label": "M", "category": "fingerspelling", "difficulty": "medium", "description": "Thumb tucked under first three fingers.", "scored": True, "handedness": "both"},
    {"id": "asl_n", "label": "N", "category": "fingerspelling", "difficulty": "medium", "description": "Thumb tucked under first two fingers.", "scored": True, "handedness": "both"},
    {"id": "asl_o", "label": "O", "category": "fingerspelling", "difficulty": "easy", "description": "Fingers curved to touch thumb in O shape.", "scored": True, "handedness": "both"},
    {"id": "asl_p", "label": "P", "category": "fingerspelling", "difficulty": "medium", "description": "Like K but palm facing down, thumb between index and middle.", "scored": True, "handedness": "both"},
    {"id": "asl_q", "label": "Q", "category": "fingerspelling", "difficulty": "medium", "description": "Like G but palm facing down.", "scored": True, "handedness": "both"},
    {"id": "asl_r", "label": "R", "category": "fingerspelling", "difficulty": "medium", "description": "Index and middle fingers crossed, others curled.", "scored": True, "handedness": "both"},
    {"id": "asl_s", "label": "S", "category": "fingerspelling", "difficulty": "easy", "description": "Fist with thumb over fingers.", "scored": True, "handedness": "both"},
    {"id": "asl_t", "label": "T", "category": "fingerspelling", "difficulty": "medium", "description": "Thumb tucked between index and middle fingers, fist.", "scored": True, "handedness": "both"},
    {"id": "asl_u", "label": "U", "category": "fingerspelling", "difficulty": "easy", "description": "Index and middle fingers up together, others curled.", "scored": True, "handedness": "both"},
    {"id": "asl_v", "label": "V", "category": "fingerspelling", "difficulty": "easy", "description": "Index and middle fingers in V shape.", "scored": True, "handedness": "both"},
    {"id": "asl_w", "label": "W", "category": "fingerspelling", "difficulty": "medium", "description": "Index, middle, ring fingers up in W shape.", "scored": True, "handedness": "both"},
    {"id": "asl_x", "label": "X", "category": "fingerspelling", "difficulty": "medium", "description": "Index finger hooked, others curled.", "scored": True, "handedness": "both"},
    {"id": "asl_y", "label": "Y", "category": "fingerspelling", "difficulty": "easy", "description": "Thumb and pinky extended, other fingers curled.", "scored": True, "handedness": "both"},

    # J and Z - Motion signs (reference only, not scored)
    {"id": "asl_j", "label": "J", "category": "fingerspelling", "difficulty": "medium", "description": "Motion sign: Trace a J in the air with pinky finger. Not scored in V1.", "scored": False, "handedness": "both", "metadata": {"motion_sign": True}},
    {"id": "asl_z", "label": "Z", "category": "fingerspelling", "difficulty": "medium", "description": "Motion sign: Trace a Z in the air with index finger. Not scored in V1.", "scored": False, "handedness": "both", "metadata": {"motion_sign": True}},

    # Numbers 0-9
    {"id": "asl_0", "label": "0", "category": "numbers", "difficulty": "easy", "description": "Fingers curved to form O shape (same as O).", "scored": True, "handedness": "both"},
    {"id": "asl_1", "label": "1", "category": "numbers", "difficulty": "easy", "description": "Index finger up, others curled.", "scored": True, "handedness": "both"},
    {"id": "asl_2", "label": "2", "category": "numbers", "difficulty": "easy", "description": "Index and middle fingers up.", "scored": True, "handedness": "both"},
    {"id": "asl_3", "label": "3", "category": "numbers", "difficulty": "easy", "description": "Thumb, index, middle up (like 3).", "scored": True, "handedness": "both"},
    {"id": "asl_4", "label": "4", "category": "numbers", "difficulty": "easy", "description": "Four fingers up, thumb tucked.", "scored": True, "handedness": "both"},
    {"id": "asl_5", "label": "5", "category": "numbers", "difficulty": "easy", "description": "All five fingers spread.", "scored": True, "handedness": "both"},
    {"id": "asl_6", "label": "6", "category": "numbers", "difficulty": "medium", "description": "Pinky, ring, middle up; index and thumb touching.", "scored": True, "handedness": "both"},
    {"id": "asl_7", "label": "7", "category": "numbers", "difficulty": "medium", "description": "Ring, middle, index up; pinky and thumb touching.", "scored": True, "handedness": "both"},
    {"id": "asl_8", "label": "8", "category": "numbers", "difficulty": "medium", "description": "Middle, index, thumb up; pinky and ring curled.", "scored": True, "handedness": "both"},
    {"id": "asl_9", "label": "9", "category": "numbers", "difficulty": "medium", "description": "Index up, thumb and pinky touching, others curled.", "scored": True, "handedness": "both"},

    # Greetings (mostly motion - reference only)
    {"id": "asl_hello", "label": "Hello", "category": "greetings", "difficulty": "easy", "description": "Wave hand from side of head outward. Motion sign - watch and learn.", "scored": False, "handedness": "both", "metadata": {"motion_sign": True, "phrase": True}},
    {"id": "asl_goodbye", "label": "Goodbye", "category": "greetings", "difficulty": "easy", "description": "Wave hand back and forth. Motion sign - watch and learn.", "scored": False, "handedness": "both", "metadata": {"motion_sign": True, "phrase": True}},
    {"id": "asl_thank_you", "label": "Thank You", "category": "greetings", "difficulty": "easy", "description": "Touch chin with fingertips, move hand forward and down. Motion sign.", "scored": False, "handedness": "both", "metadata": {"motion_sign": True, "phrase": True}},
    {"id": "asl_please", "label": "Please", "category": "greetings", "difficulty": "easy", "description": "Flat hand circles on chest. Motion sign.", "scored": False, "handedness": "both", "metadata": {"motion_sign": True, "phrase": True}},
    {"id": "asl_sorry", "label": "Sorry", "category": "greetings", "difficulty": "easy", "description": "Fist circles on chest. Motion sign.", "scored": False, "handedness": "both", "metadata": {"motion_sign": True, "phrase": True}},

    # Everyday Phrases (motion - reference only)
    {"id": "asl_hospital", "label": "Hospital", "category": "phrases", "difficulty": "medium", "description": "H sign taps opposite arm. Motion sign.", "scored": False, "handedness": "both", "metadata": {"motion_sign": True, "phrase": True}},
    {"id": "asl_help", "label": "Help", "category": "phrases", "difficulty": "easy", "description": "Fist on flat hand, both move up. Motion sign.", "scored": False, "handedness": "both", "metadata": {"motion_sign": True, "phrase": True}},
    {"id": "asl_yes", "label": "Yes", "category": "phrases", "difficulty": "easy", "description": "Fist nods up and down. Motion sign.", "scored": False, "handedness": "both", "metadata": {"motion_sign": True, "phrase": True}},
    {"id": "asl_no", "label": "No", "category": "phrases", "difficulty": "easy", "description": "Index and middle tap thumb. Motion sign.", "scored": False, "handedness": "both", "metadata": {"motion_sign": True, "phrase": True}},
]

DEFAULT_ASL_MODULES = [
    # Fingerspelling groups (~4-6 letters each)
    {"id": "asl_fingerspelling_1", "name": "Fingerspelling: A–E", "category": "fingerspelling", "difficulty": "easy", "sign_ids": ["asl_a", "asl_b", "asl_c", "asl_d", "asl_e"], "description": "Learn the first five letters of the ASL alphabet.", "estimated_time_minutes": 10},
    {"id": "asl_fingerspelling_2", "name": "Fingerspelling: F–J", "category": "fingerspelling", "difficulty": "medium", "sign_ids": ["asl_f", "asl_g", "asl_h", "asl_i", "asl_j"], "description": "Letters F through J. Note: J is a motion sign (reference only).", "estimated_time_minutes": 12},
    {"id": "asl_fingerspelling_3", "name": "Fingerspelling: K–O", "category": "fingerspelling", "difficulty": "medium", "sign_ids": ["asl_k", "asl_l", "asl_m", "asl_n", "asl_o"], "description": "Letters K through O. M and N are similar - pay attention to thumb position.", "estimated_time_minutes": 12},
    {"id": "asl_fingerspelling_4", "name": "Fingerspelling: P–T", "category": "fingerspelling", "difficulty": "medium", "sign_ids": ["asl_p", "asl_q", "asl_r", "asl_s", "asl_t"], "description": "Letters P through T. P and Q are similar orientations.", "estimated_time_minutes": 12},
    {"id": "asl_fingerspelling_5", "name": "Fingerspelling: U–Z", "category": "fingerspelling", "difficulty": "medium", "sign_ids": ["asl_u", "asl_v", "asl_w", "asl_x", "asl_y", "asl_z"], "description": "Letters U through Z. Note: Z is a motion sign (reference only).", "estimated_time_minutes": 12},

    # Numbers
    {"id": "asl_numbers_1", "name": "Numbers: 0–5", "category": "numbers", "difficulty": "easy", "sign_ids": ["asl_0", "asl_1", "asl_2", "asl_3", "asl_4", "asl_5"], "description": "Learn to sign numbers zero through five.", "estimated_time_minutes": 8},
    {"id": "asl_numbers_2", "name": "Numbers: 6–9", "category": "numbers", "difficulty": "medium", "sign_ids": ["asl_6", "asl_7", "asl_8", "asl_9"], "description": "Numbers six through nine use thumb contact patterns.", "estimated_time_minutes": 10},

    # Greetings (watch & learn)
    {"id": "asl_greetings", "name": "Greetings & Politeness", "category": "greetings", "difficulty": "easy", "sign_ids": ["asl_hello", "asl_goodbye", "asl_thank_you", "asl_please", "asl_sorry"], "description": "Common greetings and polite phrases. These are motion signs - watch the reference animation.", "estimated_time_minutes": 10},

    # Everyday Phrases (watch & learn)
    {"id": "asl_phrases", "name": "Everyday Phrases", "category": "phrases", "difficulty": "easy", "sign_ids": ["asl_hospital", "asl_help", "asl_yes", "asl_no"], "description": "Useful everyday signs. Motion signs - watch and learn.", "estimated_time_minutes": 8},
]


def create_default_asl_pack(packs_dir: Path) -> None:
    """Create the default ASL content pack if it doesn't exist."""
    pack_dir = packs_dir / "asl"
    pack_dir.mkdir(parents=True, exist_ok=True)

    # pack.json manifest
    pack_json = {
        "id": "asl",
        "name": "American Sign Language",
        "version": "1.0.0",
        "description": "ASL fingerspelling, numbers, greetings, and everyday phrases.",
        "author": "Sign Language Learning App",
        "supported_categories": [c.value for c in ModuleCategory]
    }
    with open(pack_dir / "pack.json", 'w', encoding='utf-8') as f:
        json.dump(pack_json, f, indent=2)

    # signs.json
    with open(pack_dir / "signs.json", 'w', encoding='utf-8') as f:
        json.dump(DEFAULT_ASL_SIGNS, f, indent=2)

    # modules.json
    with open(pack_dir / "modules.json", 'w', encoding='utf-8') as f:
        json.dump(DEFAULT_ASL_MODULES, f, indent=2)

    # Create model and templates directories
    (pack_dir / "model").mkdir(exist_ok=True)
    (pack_dir / "templates").mkdir(exist_ok=True)

    logger.info(f"Created default ASL content pack at {pack_dir}")


def initialize_content_packs(packs_dir: Path) -> ContentPackLoader:
    """Initialize content packs, creating defaults if needed."""
    loader = ContentPackLoader(packs_dir)

    # Create default ASL pack if no packs exist or if ASL pack is missing files
    asl_dir = packs_dir / "asl"
    needs_default = False
    if not any(packs_dir.iterdir()):
        needs_default = True
    elif not (asl_dir / "pack.json").exists() or not (asl_dir / "signs.json").exists() or not (asl_dir / "modules.json").exists():
        needs_default = True

    if needs_default:
        create_default_asl_pack(packs_dir)

    # Discover and load all packs
    loader.discover_packs()

    # Set ASL as default if available
    if "asl" in loader._packs:
        loader.set_current_pack("asl")

    return loader