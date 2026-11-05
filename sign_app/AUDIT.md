# Audit and repair notes — 2026-11-05

## Current status

The app now includes a trained static ASL alphabet classifier and adapted landmark samples. It recognizes 24 static letters, A–I and K–Y. J and Z require motion; numbers and phrases are not covered by this classifier.

The training source is **ASL Static Landmarks v1** by Neel Ulysses Roda (Siruyy), licensed CC BY 4.0. The training data manifest and attribution are in `training_data/asl_static/`. Source release is pinned and downloads are SHA-256 checked. `tools/prepare_public_asl.py --offline` retrains from the bundled data.

Model evaluation on the dataset's provided held-out frame split:

- 3,744 source training poses, mirrored for 7,488 training examples.
- 936 held-out poses; 96.47% top-label accuracy.
- At confidence >= 0.70, 78.4% of held-out poses are accepted; accepted predictions were 100% accurate on that split.
- Test split is random by frame rather than by signer/session. No signer-independent accuracy claim is made.

The classifier always chooses among known letters; its confidence threshold is not a general unknown-gesture detector. Please evaluate on new users and real camera poses before relying on it. Recognition does not measure ASL fluency or validate motion signs.

## Earlier repairs

- Restored the missing database migration and repaired databases stamped at v7 without required columns. Thread-local connections follow database location changes.
- Initialized the local learner and synchronized content before saving attempts; fixed user IDs, attempt IDs and visible errors.
- Connected dashboard progress to SQLite and separated reviews from recognition accuracy.
- Added dictionary, knowledge quiz and persisted settings.
- Fixed lesson timer and stale inference handling; stop the camera when leaving lessons.
- Fixed classifier label mapping, normalization, source paths and sample collector event handling.

Core model loading and an offscreen lesson launch with all 24 scored letters were verified after bundling. Physical camera performance and generalization remain to be verified.
