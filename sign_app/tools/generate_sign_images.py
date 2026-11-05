#!/usr/bin/env python3
"""
Generate ASL sign reference images from the parametric hand rig.

This creates clean, consistent, theme-matching images for every sign
without external dependencies or licensing concerns.

Usage:
    python -m tools.generate_sign_images [--output-dir OUTPUT_DIR] [--size SIZE] [--theme THEME]
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.hand_rig import reference_landmarks_for, ASL_POSES, build_hand_landmarks

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_SIZE = 512
THEMES = {
    "dark": {
        "bg": (0x0A, 0x0E, 0x1A, 0x00),      # transparent
        "line": (0x00, 0xE5, 0xC7, 0xFF),     # accent cyan
        "joint": (0x00, 0xE5, 0xC7, 0xFF),
        "tip": (0xF1, 0xF5, 0xFF, 0xFF),      # text color
        "label": (0x8B, 0x9D, 0xC3, 0xFF),    # textMuted
    },
    "light": {
        "bg": (0xF8, 0xFA, 0xFC, 0x00),       # transparent
        "line": (0x00, 0xB8, 0x9C, 0xFF),     # accent
        "joint": (0x00, 0xB8, 0x9C, 0xFF),
        "tip": (0x0F, 0x1A, 0x2E, 0xFF),      # text
        "label": (0x5E, 0x6E, 0x8A, 0xFF),    # textMuted
    }
}

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),      # Thumb
    (0, 5), (5, 6), (6, 7), (7, 8),      # Index
    (0, 9), (9, 10), (10, 11), (11, 12), # Middle
    (0, 13), (13, 14), (14, 15), (15, 16), # Ring
    (0, 17), (17, 18), (18, 19), (19, 20), # Pinky
    (5, 9), (9, 13), (13, 17)             # Palm
]

FINGERTIPS = [4, 8, 12, 16, 20]


def render_hand(landmarks: np.ndarray, size: int, theme: dict, line_width: float = 3.0) -> Image.Image:
    """Render hand landmarks to a PIL Image."""
    img = Image.new("RGBA", (size, size), theme["bg"])
    draw = ImageDraw.Draw(img)
    
    # Convert normalized landmarks (0-1) to pixel coordinates
    pts = [(lm[0] * size, lm[1] * size) for lm in landmarks]
    
    # Draw connections
    line_w = max(1, int(line_width))
    for start, end in HAND_CONNECTIONS:
        draw.line([pts[start], pts[end]], fill=theme["line"], width=line_w, joint="curve")
    
    # Draw joints
    joint_radius = max(4, int(size * 0.018))
    for i, pt in enumerate(pts):
        r = int(joint_radius * 1.3) if i in FINGERTIPS else joint_radius
        x, y = int(pt[0]), int(pt[1])
        draw.ellipse([x-r, y-r, x+r, y+r], fill=theme["joint"])
        
        # White highlight on fingertips
        if i in FINGERTIPS:
            hr = int(r * 0.4)
            draw.ellipse([x-hr, y-hr, x+hr, y+hr], fill=theme["tip"])
    
    return img


def add_label(img: Image.Image, label: str, theme: dict) -> Image.Image:
    """Add sign label below the hand."""
    draw = ImageDraw.Draw(img)
    size = img.width
    
    # Try to find a reasonable font
    font_size = max(24, size // 16)
    font = None
    for font_path in [
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]:
        try:
            font = ImageFont.truetype(font_path, font_size)
            break
        except:
            continue
    
    if font is None:
        font = ImageFont.load_default()
    
    # Draw label
    bbox = draw.textbbox((0, 0), label, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) // 2
    y = size - text_h - size // 20
    
    draw.text((x, y), label, fill=theme["label"], font=font)
    return img


def generate_sign_image(sign_id: str, label: str, size: int, theme_name: str) -> Image.Image:
    """Generate a single sign image."""
    # Try exact match first, then uppercase
    landmarks = reference_landmarks_for(label)
    if landmarks is None:
        landmarks = reference_landmarks_for(label.upper())
    if landmarks is None:
        logger.warning(f"No reference pose for {label}, using default")
        landmarks = build_hand_landmarks()
    
    theme = THEMES[theme_name]
    img = render_hand(landmarks, size, theme)
    img = add_label(img, label, theme)
    return img


def main():
    parser = argparse.ArgumentParser(description="Generate ASL sign reference images from hand rig")
    parser.add_argument("--output-dir", default="assets/signs/asl", help="Output directory")
    parser.add_argument("--size", type=int, default=DEFAULT_SIZE, help="Image size (square)")
    parser.add_argument("--theme", choices=["dark", "light", "both"], default="both", help="Theme variant")
    parser.add_argument("--force", action="store_true", help="Regenerate existing images")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine which signs to generate from content_packs/asl/signs.json
    signs_path = Path("content_packs/asl/signs.json")
    if signs_path.exists():
        with open(signs_path, "r", encoding="utf-8") as f:
            signs_data = json.load(f)
        signs = [(s["id"], s["label"]) for s in signs_data]
    else:
        # Fallback: generate from ASL_POSES
        signs = [(f"asl_{k.lower()}", k) for k in ASL_POSES.keys()]

    logger.info(f"Generating {len(signs)} sign images...")

    themes = ["dark", "light"] if args.theme == "both" else [args.theme]
    
    for theme_name in themes:
        theme_dir = output_dir / theme_name
        theme_dir.mkdir(exist_ok=True)
        
        for sign_id, label in signs:
            output_path = theme_dir / f"{sign_id}.png"
            
            if output_path.exists() and not args.force:
                logger.info(f"  [{sign_id}] Skipped (exists)")
                continue
            
            try:
                img = generate_sign_image(sign_id, label, args.size, theme_name)
                img.save(output_path, "PNG")
                logger.info(f"  [{sign_id}] Generated ({theme_name})")
            except Exception as e:
                logger.error(f"  [{sign_id}] Failed: {e}")

    # Also generate a "missing" placeholder
    for theme_name in themes:
        theme_dir = output_dir / theme_name
        placeholder_path = theme_dir / "missing.png"
        if not placeholder_path.exists() or args.force:
            img = Image.new("RGBA", (args.size, args.size), THEMES[theme_name]["bg"])
            draw = ImageDraw.Draw(img)
            # Draw a simple placeholder: circle with question mark
            cx, cy = args.size // 2, args.size // 2
            r = args.size // 3
            draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=THEMES[theme_name]["line"], width=3)
            draw.text((cx-10, cy-15), "?", fill=THEMES[theme_name]["label"], font=ImageFont.load_default())
            img.save(placeholder_path, "PNG")

    logger.info("Done!")
    return 0


if __name__ == "__main__":
    sys.exit(main())