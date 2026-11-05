# Image Attributions

All sign reference images in this application are **procedurally generated** from the app's built-in parametric hand rig (`app/core/hand_rig.py`). They are not sourced from external image libraries or websites.

## Generation Method

Each sign image is synthesized by:
1. Defining the hand pose parameters for each ASL sign (finger curl, thumb position, spread, rotation)
2. Computing 21 MediaPipe-compatible hand landmarks from these parameters
3. Rendering the landmarks as a clean vector skeleton (bones + joints) with the app's theme colors
4. Exporting as 512×512 PNG with transparent background

## License

Since all images are generated from the application's own code:
- **No external licenses apply**
- **No attribution required** for the images themselves
- The hand rig code is part of the Python_ASL project (MIT License)

## Signs Covered

| Category | Signs | Count |
|----------|-------|-------|
| Fingerspelling | A–Z (including J, Z motion signs) | 26 |
| Numbers | 0–9 | 10 |
| Greetings | Hello, Goodbye, Thank You, Please, Sorry | 5 |
| Phrases | Hospital, Help, Yes, No | 4 |
| **Total** | | **45** |

## Theme Variants

Images are generated in two theme variants:
- **Dark** (`assets/signs/asl/dark/`) — Cyan-mint accent on transparent background
- **Light** (`assets/signs/asl/light/`) — Teal accent on transparent background

Both variants use the same hand poses; only the color palette changes to match `Theme.qml`.

## Regenerating Images

To regenerate all sign images (e.g., after updating hand poses or theme colors):

```bash
python -m tools.generate_sign_images --size 512 --theme both --force
```

This will overwrite all images in `assets/signs/asl/dark/` and `assets/signs/asl/light/`.

## Motion Signs

J, Z, and all greetings/phrases are **motion signs** — the static image shows the starting handshape only. The actual sign involves movement (tracing a letter, waving, etc.). These are marked with `"motion_sign": true` in `content_packs/asl/signs.json` and display a "Motion" badge in the UI.