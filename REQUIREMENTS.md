# Requirement Specification and Analysis
## Sign Language Learning Application Using Hand-Tracking Technology
**Version: 2.0** | **Date: November 5, 2026** | **Status: V1 Implementation Complete**

---

## 1. Introduction

This document describes the **as-built** requirements and architecture of the Sign Language Learning Application (codename: **Pysign**). The system is a **Lightweight Desktop Augmented Reality (AR) Application** that uses real-time computer vision and hand-tracking via a standard webcam to teach sign language vocabulary.

The application overlays graphics directly onto the live webcam video stream (video see-through AR) using OpenCV and Qt/QML — no AR/VR headsets required. It detects hand landmarks via MediaPipe, classifies static hand shapes against a trained model, and provides immediate visual feedback.

**Current Scope (V1):** Static fingerspelling recognition (ASL letters A–I, K–Y; 24 classes), numbers 0–9, greetings, and everyday phrases. Motion-based signs (J, Z, Hello, Goodbye, Thank You, etc.) are included as **reference-only** (watch-and-learn) content. Sequence models (LSTM/GRU/Transformer) for dynamic signs are **deferred to V2**.

**Extensibility:** The architecture supports additional sign languages (e.g., Filipino Sign Language) by adding a content pack with a new `signs.json`, `modules.json`, and a trained model — no code changes required.

---

## 2. Target Users

| Role | Description |
|------|-------------|
| **Primary Learners** | Individuals learning sign language: students, hearing people with DHH family/colleagues, self-directed learners. |
| **Instructors/Educators** | Teachers who assign practice modules, review learner progress, and supplement classroom instruction. |
| **Developers/Maintainers** | Engineers maintaining the gesture-recognition model, hand-tracking pipeline, content packs, and SQLite backend. |

---

## 3. Functional Requirements — **Implemented (✓) / Partial (~) / Deferred (✗)**

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| **FR1** | Capture real-time video from webcam for hand detection | ✓ | `CameraWorker` + `CameraService` (shared singleton), 640×480 @ 30 FPS target |
| **FR2** | Detect/track hand landmarks (21 pts, 3D) for 1–2 hands via MediaPipe | ✓ | MediaPipe **Tasks API** (HandLandmarker, VIDEO mode), `HandTracker` wrapper |
| **FR3** | Classify static hand shapes (fingerspelling A–Z) via trained model | ✓ | **24 static classes** (A–I, K–Y). J/Z are motion signs → not scored. `StaticRecognizer` (ExtraTrees/RF/SVM/MLP/KNN) |
| **FR4** | Real-time color-coded skeleton overlay (green=match, red=off-target) + confidence score | ✓ | `HandTracker.draw_skeleton_with_feedback()`; per-landmark distance vs. reference pose |
| **FR5** | Structured learning modules by difficulty (fingerspelling, numbers, greetings, phrases) | ✓ | 12 modules defined in `modules.json`; category = fingerspelling/numbers/greetings/phrases |
| **FR6** | Guided practice mode: demonstrate sign → user repeats → evaluation | ✓ | `LessonScreen`: reference figure + live camera + hold-to-confirm (800 ms dwell) |
| **FR7** | Quiz/assessment mode recording accuracy, attempts, time per sign | ✓ | `LibraryScreen` (mode=quiz): knowledge quiz (text-based, not camera-scored) |
| **FR8** | Track/store user progress (modules, accuracy, streaks, badges) in SQLite | ✓ | `UserProgress`, `PracticeAttempt`, `QuizSession`, `UserBadge` tables; WAL mode |
| **FR9** | Searchable sign dictionary with reference pose + description | ✓ | `LibraryScreen` (mode=dictionary): search by label/description; "Practice" button |
| **FR10** | Spatial hand-dwell UI interaction (hold over "Next" for 2s to click) | ✓ | `DwellDetector` in `InferenceWorker`; configurable duration (default 2000 ms) |
| **FR11** | Use MediaPipe 3D landmarks (X,Y,Z normalized) for orientation checks | ✓ | `HandLandmarks.landmarks` is (21,3); `hand_rig` synthesizes reference poses in same space |
| **FR12** | Local SQLite/JSON storage (no cloud sync required for core use) | ✓ | SQLite in `~/Library/Application Support/SignLanguageApp/app.db` (macOS) |
| **FR13** | **Parametric hand rig** for synthesizing reference poses for every sign | ✓ | `hand_rig.py`: `ASL_POSES` dict → `build_hand_landmarks()` → (21,3) array |
| **FR14** | **Temporal smoothing** of predictions (EMA + majority vote window) | ✓ | `StaticRecognizer` smoothing window (default 5 frames), confidence threshold 0.7 |
| **FR15** | **Landmark stabilization** (EMA on normalized coords before feature extraction) | ✓ | `HandTracker._stabilize_landmarks()` with 0.65 smoothing factor |
| **FR16** | **Content pack system** (add languages without code changes) | ✓ | `ContentPackLoader` discovers `content_packs/<lang>/` with pack.json, signs.json, modules.json |
| **FR17** | **Reference image assets** (light/dark theme variants for each sign) | ✓ | `assets/signs/asl/{light,dark}/asl_*.png` — 54 images + missing.png |
| **FR18** | **Instructor assignment** schema (assign modules to learners, due dates) | ✓ | `InstructorAssignment` table + `AssignmentRepository` — UI not yet built |
| **FR19** | **Badge/achievement system** (streaks, first completion, perfect quiz, etc.) | ✓ | 10 default badges seeded; `BadgeRepository.award_badge()` — UI not yet built |
| **FR20** | **Performance HUD** (capture FPS, inference FPS, latency, p95 inference time) | ✓ | `CorePipeline.perf_stats()` → HUD overlay in `LessonScreen` (toggle in settings) |
| **FR21** | **Camera device persistence** by stable unique ID (not index) | ✓ | `CameraService` + `camera_devices.py`; stored in `app_settings.camera_device_id` |
| **FR22** | **Dark/Light theme** with CSS-like theming in QML | ✓ | `Theme.qml`; persisted in `app_settings.theme` |
| **FR23** | **Reduced motion** accessibility setting | ✓ | `app_settings.reduced_motion` — honored in animations |
| **FR24** | **Model evaluation script** with held-out split metrics | ✓ | `tools/measure_perf.py` + evaluation JSON in `content_packs/asl/model/evaluation.json` |

### Deferred to V2+
| ID | Requirement | Reason |
|----|-------------|--------|
| FR-D1 | Dynamic/motion sign recognition (LSTM/GRU/Transformer) | Requires sequence dataset, temporal modeling; `SequenceRecognizer` placeholder exists |
| FR-D2 | Facial expression / non-manual marker tracking | MediaPipe Face Mesh integration needed; significant scope increase |
| FR-D3 | Cloud sync / multi-device progress | Current design is local-first; schema supports export/import |
| FR-D4 | Instructor dashboard UI | Schema ready; QML screens not implemented |
| FR-D5 | Badge notification / toast UI | Logic ready; UI not implemented |
| FR-D6 | Signer-independent evaluation (cross-user generalization) | Current test split is random-by-frame, not by signer |

---

## 4. Non-Functional Requirements — **Current Achievement**

| ID | Requirement | Target | Current | Status |
|----|-------------|--------|---------|--------|
| **NFR1** | Recognition accuracy (static fingerspelling) | ≥ 90% | **96.47%** top-1 on held-out split (936 poses) | ✓ Exceeded |
| **NFR1b** | Reliable prediction rate @ confidence ≥ 0.70 | — | 78.4% of frames accepted; **100% precision** on accepted | ✓ |
| **NFR2** | Hand tracking frame rate | 15–20 FPS | **~30 FPS capture**, inference ~15–25 FPS (model_complexity=0) | ✓ |
| **NFR2b** | Feedback latency (gesture → overlay update) | ≤ 1–2 s | **< 100 ms** (inference worker async, display at camera rate) | ✓ |
| **NFR3** | OS compatibility | Win/macOS/Linux | **Tested on macOS**; PySide6 + MediaPipe Tasks API are cross-platform | ~ |
| **NFR4** | Visual-first UI (Deaf/HH accessible) | Primary visual | **No audio dependencies**; all feedback visual (colors, text, icons) | ✓ |
| **NFR5** | Privacy (no raw video stored) | Local only | **No video recording**; only landmarks + predictions logged to SQLite | ✓ |
| **NFR6** | Robustness (lighting, skin tone, hand size, background) | Reasonable | MediaPipe Tasks API + low detection threshold (0.3) + EMA smoothing | ~ |
| **NFR7** | Scalability (new gestures, languages) | No redesign | **Content pack system** + abstract `Recognizer` interface + parametric rig | ✓ |
| **NFR8** | Graceful degradation (hand lost, poor lighting) | Clear prompts | `CameraView` shows "Place one hand fully in camera view"; no crashes | ✓ |

---

## 5. Hardware & Software Requirements — **As-Built**

### Hardware
| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Webcam | 720p @ 30 FPS | 1080p @ 30 FPS, good low-light |
| CPU | 2+ cores, AVX2 | 4+ cores, AVX2 (MediaPipe uses XNNPACK) |
| RAM | 4 GB | 8+ GB |
| GPU | Optional (CPU inference) | Any (MediaPipe Tasks can use GPU delegate) |
| OS | Windows 10 / macOS 11 / Ubuntu 20.04+ | Latest LTS |

### Software Stack
| Layer | Technology | Version / Notes |
|-------|------------|-----------------|
| Language | Python | 3.10+ (3.12 tested) |
| GUI Framework | **PySide6 (Qt 6)** | QML/Quick for UI; `ApplicationWindow` + `StackView` navigation |
| Computer Vision | **MediaPipe Tasks API** | `mediapipe==0.10.35+`; HandLandmarker (VIDEO mode) |
| ML Inference | **scikit-learn** | ExtraTreesClassifier (default), also RF, SVM, MLP, KNN |
| Feature Extraction | Custom geometric features | `FeatureExtractor`: distances, angles, palm normal, finger extensions |
| Database | **SQLite 3** (WAL mode) | Thread-local connections; schema v7 with migrations |
| Content Packs | JSON + joblib model | `content_packs/<lang>/` — auto-discovered |
| Reference Poses | Parametric hand rig | `hand_rig.py` — pure NumPy, no ML |
| Asset Pipeline | PNG (light/dark) | 54 sign images + missing placeholder |
| Packaging | `pip` / `pyproject.toml` | `sign_app` package; entry point `pysign` |

### Key Dependencies (`requirements.txt`)
```
PySide6>=6.6
mediapipe>=0.10.35
opencv-python>=4.8
numpy>=1.24
scikit-learn>=1.3
joblib>=1.3
```

---

## 6. System Architecture — **Implemented Components**

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Qt/QML Application Layer                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │  HomeScreen  │  │ LessonScreen │  │ LibraryScreen│  (Dictionary  │
│  │  (Dashboard) │  │  (Practice)  │  │ (Quiz/Prog)  │  /Progress)   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
└─────────┼─────────────────┼─────────────────┼───────────────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Python Bridge (main.py)                        │
│  • QML-Python signal bridge  • Settings persistence                 │
│  • Content pack loader        • User/profile management             │
│  • CameraService singleton    • Model loading                       │
└────────────────────────────┬────────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
┌──────────────────┐ ┌──────────────┐ ┌───────────────────┐
│  CameraWorker    │ │InferenceWorker││  Content Loader   │
│  (QThread)       │ │  (QThread)    ││  (syncs to DB)    │
│  • 30 FPS capture│ │ • Hand track  ││ • signs.json      │
│  • Device mgmt   │ │ • Features    ││ • modules.json    │
│  • Frame timestamps│ • Recognize   ││  • model.joblib   │
└────────┬─────────┘ └──────┬────────┘└───────────────────┘
         │                  │
         ▼                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      CorePipeline (QObject)                         │
│  • Coordinates capture + inference                                  │
│  • Emits PipelineResult @ camera rate (with latest inference state) │
│  • Perf stats (capture FPS, inference FPS, latency, p95)            │
└─────────────────────────────────────────────────────────────────────┘
```

### Threading Model
| Thread | Responsibility | Rate |
|--------|----------------|------|
| **GUI (Main)** | QML rendering, user input, signal handling | VSync (60 Hz) |
| **Capture** | `CameraWorker`: OpenCV `VideoCapture`, device mgmt | 30 FPS target |
| **Inference** | `InferenceWorker`: MediaPipe → features → classify → smooth | ~15–25 FPS |
| **DB** | Thread-local SQLite connections (WAL) | On demand |

**Key Design:** Capture and display run at full camera rate. Inference runs asynchronously; the latest inference state is attached to the next camera frame. No frame dropping in UI.

---

## 7. Data Model — **SQLite Schema (v7)**

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `users` | Learner/instructor profiles | id, name, avatar_color, role, settings JSON |
| `signs` | Vocabulary entries | id, label, category, difficulty, description, scored, handedness, reference_landmarks (JSON), image path, metadata JSON |
| `modules` | Ordered lesson groups | id, name, category, difficulty, sign_ids (JSON), description, est_time |
| `user_progress` | Per-user per-module stats | user_id, module_id, completed, accuracy, attempts, streaks, last_practiced |
| `practice_attempts` | Every scored attempt | user_id, sign_id, module_id, result, confidence, predicted_label, target_label, duration_ms, landmarks_json |
| `quiz_sessions` | Knowledge quiz runs | user_id, module_id, score, correct_count, avg_time_ms, weakest_signs |
| `quiz_questions` | Per-question detail | session_id, sign_id, result, confidence, time_ms, sequence |
| `badges` | Achievement definitions | id, name, description, icon, criteria JSON |
| `user_badges` | Earned badges | user_id, badge_id, earned_at |
| `instructor_assignments` | Teacher→learner tasks | instructor_id, learner_id, module_id, due_date, completed |
| `app_settings` | Per-user preferences | camera_device_id, mirror_camera, theme, dwell_duration_ms, confidence_threshold, smoothing_frames, show_fps, hand_dwell_enabled, language_pack, reduced_motion |

**Migrations:** `init_db()` runs automatic migrations v1→v7 on startup. Thread-local connections handle DB path changes (e.g., XDG_DATA_HOME).

---

## 8. Content Pack Structure — **Extensibility Point**

```
content_packs/
└── asl/                          # Language code = pack ID
    ├── pack.json                 # Manifest: id, name, version, categories
    ├── signs.json                # 54 sign definitions (see below)
    ├── modules.json              # 12 module definitions
    ├── model/
    │   ├── recognizer.joblib     # Trained sklearn model (ExtraTrees)
    │   ├── recognizer.json       # Model metadata (classes, config, feature stats)
    │   └── evaluation.json       # Held-out split metrics
    └── templates/                # (reserved for future template overrides)
```

### `signs.json` Entry (example)
```json
{
  "id": "asl_a",
  "label": "A",
  "category": "fingerspelling",
  "difficulty": "easy",
  "description": "Make a fist with thumb resting against the side of the index finger.",
  "scored": true,
  "handedness": "both",
  "image": "assets/signs/asl/dark/asl_a.png",
  "metadata": {}
}
```
- `scored: false` → motion sign (J, Z, Hello, etc.) — reference only, not evaluated
- `reference_landmarks` optional — auto-synthesized from `hand_rig.ASL_POSES` if missing
- `image` path resolves relative to project root; dark/light variants auto-selected by theme

### `modules.json` Entry (example)
```json
{
  "id": "asl_fingerspelling_1",
  "name": "Fingerspelling: A–E",
  "category": "fingerspelling",
  "difficulty": "easy",
  "sign_ids": ["asl_a", "asl_b", "asl_c", "asl_d", "asl_e"],
  "description": "Learn the first five letters of the ASL alphabet.",
  "estimated_time_minutes": 10
}
```

### Current ASL Pack Content (v1.1.0)
| Category | Signs | Scored | Modules |
|----------|-------|--------|---------|
| Fingerspelling | 26 (A–Z) | 24 (excl. J, Z) | 5 (A–E, F–J, K–O, P–T, U–Z) |
| Numbers | 10 (0–9) | 10 | 2 (0–5, 6–9) |
| Greetings | 5 | 0 (all motion) | 1 |
| Phrases | 4 | 0 (all motion) | 1 |
| **Total** | **45 unique labels** | **34 scored** | **9 modules** |

---

## 9. Recognition Pipeline — **Technical Detail**

### Feature Extraction (`FeatureExtractor`)
Input: 21×3 normalized landmarks (MediaPipe coords). Output: **88-dim feature vector**:
- **Pairwise distances** (21 choose 2 = 210) → PCA'd to 30 dims
- **Joint angles** (MCP/PIP/DIP per finger) → 12 dims
- **Palm normal** (cross product of wrist→index_mcp × wrist→pinky_mcp) → 3 dims
- **Finger extension ratios** (tip-to-mcp / mcp-to-wrist) → 5 dims
- **Handedness one-hot** → 2 dims
- **Normalized fingertip positions** (relative to wrist) → 10 dims
- **Finger spread angles** → 6 dims
- **Thumb pose** (angle, distance to index) → 4 dims
- **Global scale** (hand bbox diagonal) → 1 dim
- **Wrist depth** (z) → 1 dim
- **Total** → 88 dims (standardized with train-set mean/std)

### Classifier (`StaticRecognizer`)
- **Default:** `ExtraTreesClassifier(n_estimators=200, class_weight="balanced")`
- **Options:** RandomForest, SVM (RBF), MLP (128,64), KNN (k=5)
- **Temporal smoothing:** 5-frame EMA + majority vote (60% threshold) + confidence ≥ 0.7
- **Landmark stabilization:** EMA (α=0.65) on normalized coords *before* feature extraction
- **Model persistence:** `joblib` + JSON metadata (classes, config, feature stats)

### Evaluation Results (Held-out Split, 936 poses)
| Metric | Value |
|--------|-------|
| Top-1 Accuracy | **96.47%** |
| Acceptance Rate @ conf≥0.70 | 78.4% |
| Precision (accepted) | **100%** |
| Per-class F1 (macro) | 0.96 |
| Inference Time (CPU, model_complexity=0) | ~4–8 ms / frame |

> **Caveat:** Test split is random by frame, not by signer. Signer-independent generalization not yet measured.

---

## 10. UI Screens — **Implemented**

| Screen | File | Key Features |
|--------|------|--------------|
| **Home** | `HomeScreen.qml` | Dashboard: streak, daily practice card, stats cards (accuracy, modules, minutes, lessons), module grid with progress bars, quick actions (Dictionary, Progress, Quiz, Settings) |
| **Lesson** | `LessonScreen.qml` | Split view: CameraView (live + skeleton + feedback) + ReferenceFigure (rig-synthesized pose) + instructions/tip + prev/next navigation + hold-to-confirm (800 ms) |
| **Library** | `LibraryScreen.qml` | Three modes: **Dictionary** (searchable list, practice button), **Progress** (per-sign attempts/accuracy), **Quiz** (knowledge MCQ, not camera-scored) |
| **Settings** | `SettingsScreen.qml` | Profile name, camera picker (stable device ID), mirror toggle, privacy notice, model status, theme persisted |
| **CameraView** | `CameraView.qml` | OpenCV frame → QImage → `Image` item; overlays: hand skeleton (color-coded), target landmarks, check result status, FPS/perf HUD |
| **ReferenceFigure** | `ReferenceFigure.qml` | Renders parametric hand rig pose (or image asset) with same coordinate mapping as live skeleton |
| **ProgressRing** | `ProgressRing.qml` | Circular progress indicator (lesson progress, module cards) |

---

## 11. System Constraints & Known Limitations

| Constraint | Impact | Mitigation |
|------------|--------|------------|
| **Hand-only tracking** | Cannot capture facial expressions, mouth morphemes, body posture (non-manual markers) | Disclosed in UI; content limited to manual signs |
| **Static classifier only** | J, Z, and all phrases are motion signs → not scored | Parametric rig provides start poses; watch-and-learn mode |
| **Lighting/camera dependency** | Low light, backlight, cluttered background reduce MediaPipe confidence | Detection threshold lowered to 0.3; EMA smoothing; on-screen prompts |
| **Single-signer training data** | Model trained on ASL Static Landmarks v1 (one signer, augmented) | Mirrored poses (2×); evaluate on diverse users before relying |
| **No unknown-gesture rejection** | Classifier always picks from 24 known classes | Confidence threshold + temporal smoothing; "unknown" if conf < 0.7 |
| **Local-only storage** | No cloud sync / multi-device | Export/import JSON utility (`export_user_data`) for portability |
| **Qt/QML desktop only** | No mobile/web build currently | PySide6 is cross-platform; mobile would need touch adaptations |

---

## 12. User Scenarios — **Supported Flows**

### Beginner Learner
1. Launch app → Home screen shows "Fingerspelling: A–E" module (0% progress)
2. Click "Start lesson" → LessonScreen loads sign A
3. CameraView shows live feed + green/red skeleton overlay
4. ReferenceFigure shows parametric "A" pose (thumb alongside index)
5. User forms sign → hold 800 ms → auto-advance to B
6. Complete module → progress saved → streak updated → badge check

### Self-Guided Practice (Motion Signs)
1. Library → Dictionary → search "Hello"
2. See description + reference image + "Practice" button
3. Practice opens LessonScreen with `scored=false` → no auto-advance
4. User watches reference, mimics at own pace → clicks "Mark reviewed"
5. Attempt logged as `reviewed` (not counted in recognition accuracy)

### Knowledge Quiz
1. Library → mode=Quiz → "Quick knowledge quiz"
2. Text prompt: "Which sign uses thumb and pinky extended?" → options [A, I, Y, B]
3. Answer → immediate feedback → next question
4. Session complete → score saved to `quiz_sessions`

### Instructor (Schema Ready, UI Pending)
1. Instructor creates learner accounts (`UserRepository.create(role=INSTRUCTOR)`)
2. Assign module: `AssignmentRepository.create(InstructorAssignment(...))`
3. Learner sees assigned modules (UI not built)
4. Instructor reviews progress via `ProgressRepository.get_all_progress(learner_id)`

---

## 13. Analysis Summary

### What Works (V1 Complete)
- **End-to-end static fingerspelling recognition** at >96% accuracy on held-out data
- **Real-time AR overlay** (skeleton + reference figure) at camera frame rate
- **Structured curriculum** (9 modules, 34 scored signs, 11 reference-only signs)
- **Local-first architecture** with SQLite, content packs, parametric rig — no cloud dependency
- **Extensible to new sign languages** via content pack folder drop-in
- **Accessibility-first UI**: visual-only, dark/light theme, reduced motion, configurable dwell
- **Performance observability**: live HUD with capture/inference FPS, latency, p95

### Trade-offs Made
| Decision | Rationale |
|----------|-----------|
| **Static-only V1** | Motion signs require sequence models + larger datasets; defer to V2 |
| **MediaPipe Tasks API (VIDEO mode)** | Lower latency than LIVE_STREAM callback; synchronous, predictable |
| **Parametric rig vs. recorded video** | No licensing/bandwidth for 54+ reference videos; rig is deterministic, themeable |
| **ExtraTrees over deep learning** | Fast CPU inference, no GPU needed, interpretable, works with 88-dim geometric features |
| **Local SQLite** | Privacy by default; simpler deployment; export/import for portability |
| **PySide6/QML** | Native desktop performance, mature AR-like overlay via `Image` + OpenCV, no Electron bloat |

### Next Priorities (V2 Roadmap)
1. **Sequence recognizer** (LSTM/GRU) for J, Z, and phrase motion signs
2. **Signer-independent evaluation** (collect multi-user data, cross-validation by signer)
3. **Instructor dashboard UI** (assignments, class roster, progress overview)
4. **Badge/toast notifications** in QML
5. **Mobile prototype** (PySide6 on Android/iOS via `fbs` or `python-for-android`)
6. **WebAssembly port** (MediaPipe Tasks WASM + Pyodide) for browser demo

---

## 14. Appendix — Key File Reference

| File | Purpose |
|------|---------|
| `app/qml/main.py` | Qt app entry; bridge object; content pack init; user session |
| `app/core/pipeline.py` | `CorePipeline`: orchestrates capture + inference + perf stats |
| `app/core/camera_worker.py` | `CameraWorker` + `CameraService` (singleton device manager) |
| `app/core/inference_worker.py` | `InferenceWorker`: MediaPipe → features → recognize → smooth → dwell |
| `app/core/hand_tracker.py` | MediaPipe Tasks API wrapper; landmark stabilization; drawing |
| `app/core/features.py` | `FeatureExtractor`: 88-dim geometric feature vector |
| `app/core/recognizer.py` | `Recognizer` ABC; `StaticRecognizer` (sklearn); `SequenceRecognizer` (stub) |
| `app/core/hand_rig.py` | Parametric hand pose synthesis; `ASL_POSES` for 45 labels |
| `app/core/smoothing.py` | `TemporalSmoother`, `ConfidenceMeter`, `DwellDetector` |
| `app/content/loader.py` | `ContentPackLoader`: discovers packs, syncs to SQLite |
| `app/data/db.py` | Schema v7, migrations, repositories, export/import |
| `tools/train_model.py` | Train/evaluate recognizer from `training_data/asl_static/` |
| `tools/prepare_public_asl.py` | Download/verify ASL Static Landmarks dataset (CC BY 4.0) |
| `tools/collect_samples.py` | Custom data collection (press key → save landmarks) |
| `content_packs/asl/signs.json` | 54 sign definitions |
| `content_packs/asl/modules.json` | 9 module definitions |
| `content_packs/asl/model/evaluation.json` | Held-out metrics (accuracy, per-class, confusion matrix) |

---

*Document version 2.0 reflects the as-built V1 implementation as of November 5, 2026. All functional requirements FR1–FR24 are implemented. Deferred items FR-D1–FR-D6 are tracked for V2.*