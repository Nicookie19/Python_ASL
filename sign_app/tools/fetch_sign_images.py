#!/usr/bin/env python3
"""
Download and normalize ASL sign images from sources.csv.

Usage:
    python -m tools.fetch_sign_images [--sources SOURCES_CSV] [--output-dir OUTPUT_DIR] [--size SIZE]
"""

import argparse
import csv
import logging
import ssl
import sys
from io import BytesIO
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from PIL import Image, ImageOps
import cairosvg

# Create SSL context that doesn't verify certificates (for macOS default Python)
ssl._create_default_https_context = ssl._create_unverified_context

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_SIZE = 512
DEFAULT_PADDING = 0.1  # 10% padding around the hand


def normalize_image(img: Image.Image, size: int = DEFAULT_SIZE, padding: float = DEFAULT_PADDING) -> Image.Image:
    """
    Normalize an image to a square canvas with consistent padding.
    - Converts to RGBA
    - Makes background transparent (removes near-white/gray backgrounds)
    - Centers the content with consistent padding
    - Resizes to target size
    """
    # Convert to RGBA
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    # Remove near-white/light-gray backgrounds (common in SVG renders)
    datas = img.getdata()
    new_data = []
    for item in datas:
        # If pixel is very light (close to white), make it transparent
        if item[0] > 240 and item[1] > 240 and item[2] > 240:
            new_data.append((255, 255, 255, 0))
        # If pixel is light gray, also make transparent
        elif item[0] > 200 and item[1] > 200 and item[2] > 200 and abs(item[0] - item[1]) < 15 and abs(item[1] - item[2]) < 15:
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append(item)
    img.putdata(new_data)

    # Find bounding box of non-transparent pixels
    bbox = img.getbbox()
    if bbox:
        # Crop to content
        img = img.crop(bbox)

    # Create square canvas with padding
    w, h = img.size
    max_dim = max(w, h)
    padded_dim = int(max_dim * (1 + 2 * padding))

    # Create transparent square canvas
    canvas = Image.new("RGBA", (padded_dim, padded_dim), (0, 0, 0, 0))

    # Center the image
    x = (padded_dim - w) // 2
    y = (padded_dim - h) // 2
    canvas.paste(img, (x, y), img)

    # Resize to target size with high-quality resampling
    canvas = canvas.resize((size, size), Image.Resampling.LANCZOS)

    return canvas


def download_svg(url: str, timeout: int = 30) -> bytes:
    """Download an SVG file from a URL."""
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Python ASL Image Fetcher)"})
    with urlopen(req, timeout=timeout) as response:
        return response.read()


def svg_to_png(svg_data: bytes, output_width: int = 1024, output_height: int = 1024) -> Image.Image:
    """Convert SVG bytes to PIL Image using cairosvg."""
    png_data = cairosvg.svg2png(
        bytestring=svg_data,
        output_width=output_width,
        output_height=output_height,
        background_color="white"  # Will be made transparent later
    )
    return Image.open(BytesIO(png_data))


def main():
    parser = argparse.ArgumentParser(description="Download and normalize ASL sign images")
    parser.add_argument("--sources", default="assets/signs/sources.csv", help="Path to sources.csv")
    parser.add_argument("--output-dir", default="assets/signs/asl", help="Output directory for images")
    parser.add_argument("--size", type=int, default=DEFAULT_SIZE, help="Target image size (square)")
    parser.add_argument("--padding", type=float, default=DEFAULT_PADDING, help="Padding fraction around content")
    parser.add_argument("--force", action="store_true", help="Re-download even if file exists")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be downloaded without doing it")
    args = parser.parse_args()

    sources_path = Path(args.sources)
    if not sources_path.exists():
        logger.error(f"Sources file not found: {sources_path}")
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Read sources.csv
    with open(sources_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    logger.info(f"Found {len(rows)} signs to process")

    success = 0
    failed = 0
    skipped = 0

    for row in rows:
        sign = row["sign"]
        url = row["url"]
        output_path = output_dir / f"{sign}.png"

        if output_path.exists() and not args.force:
            logger.info(f"  [{sign}] Skipped (exists, use --force to re-download)")
            skipped += 1
            continue

        if args.dry_run:
            logger.info(f"  [{sign}] Would download from {url}")
            continue

        try:
            logger.info(f"  [{sign}] Downloading SVG...")
            svg_data = download_svg(url)

            logger.info(f"  [{sign}] Converting to PNG...")
            img = svg_to_png(svg_data, output_width=1024, output_height=1024)

            logger.info(f"  [{sign}] Normalizing...")
            normalized = normalize_image(img, size=args.size, padding=args.padding)

            normalized.save(output_path, "PNG")
            logger.info(f"  [{sign}] Saved to {output_path}")
            success += 1

        except HTTPError as e:
            logger.error(f"  [{sign}] HTTP error: {e.code} {e.reason}")
            failed += 1
        except URLError as e:
            logger.error(f"  [{sign}] URL error: {e.reason}")
            failed += 1
        except Exception as e:
            logger.error(f"  [{sign}] Unexpected error: {e}")
            failed += 1

    logger.info(f"Done: {success} downloaded, {skipped} skipped, {failed} failed")

    if failed > 0:
        logger.warning("Some images failed to download. Check URLs in sources.csv.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())