# Pysign

A local desktop application for practicing American Sign Language with a webcam, built with PySide6/QML and MediaPipe.

## Run

Use Python 3.11 or 3.12 for a fresh installation with the pinned dependencies. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r sign_app/requirements.txt
python sign_app/app/qml/main.py
```

On Windows, activate with `.venv\Scripts\activate`. On macOS, allow camera access for the application or terminal in System Settings → Privacy & Security → Camera. Do not run the app with sudo.

For a synthetic preview without opening a webcam:

```bash
python sign_app/app/qml/main.py --demo
```

## Available features

- Nine lessons and 45 sign entries, including fingerspelling, numbers and self-guided motion signs.
- Live camera preview and hand skeleton, with inference on a separate worker.
- Searchable dictionary with direct sign practice.
- Ten-question description-to-sign knowledge quizzes with immediate feedback and a final score.
- Persistent local learner profile, lesson coverage, practice time, streak and per-sign statistics.
- Camera selection using stable device IDs, mirror preference, and saved light/dark theme.
- Reset learning progress in Settings while keeping the learner profile and app preferences.
- Keyboard navigation: Escape goes back; Left/Right select lesson signs; Space continues.

Use Settings to change your learner name and camera preferences. The camera starts when entering practice and stops when leaving it. References remain usable without a working camera.

## Recognition and progress

**A trained landmark classifier for 24 static letters (A–I, K–Y) and its CC BY 4.0 training samples are bundled. MediaPipe supplies hand tracking; the bundled classifier maps each detected pose to one of those letters. Static lessons can be scored automatically when the model is available. Numbers, J/Z motion, and phrases remain self-guided. Compare those signs with the description/reference, then select **Mark reviewed**. References include generated diagrams; these are learning aids, not a substitute for instruction from a fluent signer.

When a compatible model is present, the app automatically loads it at startup. Supported static signs require a reliable prediction held continuously for approximately 800 ms to advance. Removing the hand, losing fresh feedback, or switching targets resets the hold. Signs absent from the trained model stay self-guided.

Lesson coverage counts signs reviewed or attempted. Recognition accuracy excludes self-reviews. Knowledge quizzes are separate from camera recognition and their scores last for the current quiz session. Instructor dashboards, badges, and video lessons are not implemented in the active QML interface.

## Collect samples and train

Use the matching sample collector and trainer (the older `collect_data.py` uses a different CSV format):

```bash
python sign_app/tools/collect_samples.py --list
python sign_app/tools/collect_samples.py --sign asl_a --count 50
python sign_app/tools/collect_samples.py --sign asl_b --count 50
python sign_app/tools/train_model.py --model-type random_forest
```

The collector uses the shared camera service and stores derived landmarks, finger states and joint angles under `sign_app/data/samples/asl`. Train at least two classes with varied examples. Train all desired signs for broader coverage. Restart the app after training.

The bundled model and transformed landmark data can be retrained without network access with `python sign_app/tools/prepare_public_asl.py --offline`. To refresh the source data and retrain, run `python sign_app/tools/prepare_public_asl.py`; downloads are pinned and checked against SHA-256 hashes. For collection of your own samples, the existing trainer writes `model.joblib` and `model.json` under `sign_app/content_packs/asl/model`. Load only model files you trust: joblib models are executable Python serialization. The provided dataset split groups random frames, not signers or sessions. Its test result can therefore overstate performance on new people.

## Local data

Learner settings and attempts are stored in `SignLanguageApp/app.db` under the platform data directory: Application Support on macOS, APPDATA on Windows, or XDG_DATA_HOME / `~/.local/share` on Linux. Setting `XDG_DATA_HOME` overrides the location on every platform. The app does not save camera video. The sample collection tool saves landmarks only. Tests use temporary databases and do not alter your learner profile.

## Verification

```bash
python -m pytest sign_app/tests -q
python -m ruff check sign_app/app sign_app/tools --select E9,F63,F7,F82
```

Tests cover database repairs, persistence, content loading, camera ownership, stale inference rejection, model save/load, and QML screen navigation. The bundled model reports 96.47% accuracy on the upstream held-out frame split, with 78.4% of examples above its confidence threshold and 100% accuracy among those accepted. This split is not signer-independent, and actual webcam performance still needs evaluation with new signers.

The active frontend is `sign_app/app/qml/main.py`. `_archive_qml/` contains historical screens, not active features. See `AUDIT.md` for the repair notes and original camera audit.
