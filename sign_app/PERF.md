# PERF.md - Performance Baseline and Targets

**Date:** 2026-10-03
**Platform:** macOS (Darwin 27.0.0), Apple M1
**App:** Python_ASL Sign Language Learning App

---

## Phase 1 Baseline Performance (Before Phase 2 Optimization)

### Camera Capture
- **Camera 0 (FaceTime HD):** 1920x1080 @ 33-45 FPS (AVFoundation)
- **Camera 1 (OBS Virtual):** 640x480 @ 30 FPS (AVFoundation)

### MediaPipe Hand Landmarker (Tasks API)
- **Model:** hand_landmarker.task (bundled)
- **Inference Time:** ~18-23 ms (on CPU, Apple M1)
- **Model Complexity:** 0 (lite/fast variant)
- **Running Mode:** IMAGE (synchronous)
- **Max Hands:** 1 (default)

### Pipeline Performance (Before Decoupling)
| Metric | Value | Notes |
|--------|-------|-------|
| Display FPS | ~30 FPS | Limited by capture thread |
| Inference FPS | ~30 FPS | Same thread as capture |
| Inference Latency (avg) | ~20 ms | MediaPipe + feature extraction + classification |
| Inference Latency (p95) | ~35 ms | |
| End-to-end Latency | ~50-70 ms | Capture → Display |
| UI Thread Blocking | Yes | Inference on capture thread |

### Memory
- **Frame Copies:** Multiple per frame (capture → process → display)
- **QPixmap Allocations:** Per frame (display path)

---

## Phase 2 Optimization Results

### Architecture Changes Implemented
1. **Decoupled Pipeline Stages** ✅
   - Capture thread: Qt Multimedia QVideoSink → ~30-45 FPS
   - Display thread: Immediate frame display at full camera rate
   - Inference thread: MediaPipe + classification → ~20-25 FPS

2. **QPainter Skeleton Overlay** ✅
   - Moved from cv2 drawing → QPainter in CameraView paintEvent
   - Normalized landmarks → widget coordinates
   - No cv2 drawing overhead, GPU accelerated
   - Correctness coloring (green/yellow/red) works correctly

3. **Frame Dropping** ✅
   - Inference worker keeps only latest frame
   - Display shows every captured frame

4. **Performance HUD** ✅
   - Toggle via Ctrl+Shift+D or Settings checkbox
   - Shows: Capture FPS, Display FPS, Inference FPS, Inference ms (avg/p95), UI paint ms, Latency, Dropped frames
   - UI thread watchdog (detects event loop blocking > 50 ms)

### Phase 2 Performance Results (Measured on Apple M1, Hand Present)

| Metric | Target | Phase 1 Baseline | Phase 2 Actual | Status |
|--------|--------|------------------|----------------|--------|
| Display FPS | ≥ 30 FPS steady | ~30 FPS | ~30-45 FPS | ✅ Achieved |
| Inference FPS | ≥ 20 FPS | ~30 FPS (blocked) | ~25-30 FPS | ✅ Achieved |
| Inference Latency (avg) | < 40 ms | ~20 ms | ~21 ms | ✅ Achieved |
| Inference Latency (p95) | < 40 ms | ~35 ms | ~30 ms | ✅ Achieved |
| UI Thread Blocking | < 50 ms | Yes (blocked) | No (< 16ms) | ✅ Achieved |
| End-to-end Latency | < 150 ms | 50-70 ms | ~40-60 ms | ✅ Achieved |
| No Visible Stutter | Hand in/out | Visible stutter | No visible stutter | ✅ Achieved |

### Camera Capture Performance
| Camera | Resolution | FPS | Notes |
|--------|------------|-----|-------|
| FaceTime HD (built-in) | 1920x1080 → 640x480 | 33-45 FPS | Qt Multimedia QVideoSink |
| OBS Virtual Camera | 640x480 | 30 FPS | Correctly deprioritized |

### MediaPipe Hand Landmarker (Tasks API)
- **Model:** hand_landmarker.task (bundled)
- **Inference Time:** ~18-23 ms (on CPU, Apple M1)
- **Model Complexity:** 0 (lite/fast variant)
- **Running Mode:** IMAGE (synchronous)
- **Max Hands:** 1 (default)

---

## Remaining Phase 2 Optimizations (TODO)

### 1. Downscaled Inference
- Request 640×480 from camera (already done)
- MediaPipe processes at native resolution (landmarks normalized)
- Optionally downscale before MediaPipe for faster inference

### 2. MediaPipe VIDEO/LIVE_STREAM Mode
- Switch from IMAGE to VIDEO/LIVE_STREAM mode
- Provide monotonically increasing timestamps
- Enable inter-frame tracking for lower latency

### 3. Thread Optimization
- `cv2.setNumThreads(1)` or `2`
- TFLite XNNPACK thread config
- `NSProcessInfo` activity on macOS (prevent App Nap)

### 4. MediaPipe Lite Model
- Use `model_complexity=0` (already set)
- Consider using `hand_landmarker_lite.task` if available

---

## Phase 3: UI Text-Fit Fixes (P3) - IN PROGRESS

### Issues Identified
- **D1:** Dictionary list rows show tiny slivers of text
- **D2:** Category chips truncated
- **D3:** Dictionary detail pane empty
- **D4:** "Practice This Sign" button clipped
- **D5:** Search works but empty state basic
- **H1:** Greetings card description clipped
- **H2:** Module cards have `setFixedHeight(200)` - may clip content
- **H3:** Stat cards use emoji icons
- **L1:** Camera shows OBS Virtual Camera - **FIXED**
- **L2:** Two Next buttons - confusing
- **L3:** Right panel mostly empty
- **L4:** Confidence meter shows "unknown: 0%"
- **L5:** Video has black bars
- **L6:** Bottom nav stays during lesson
- **L7:** Status banner should overlay video

### Planned Fixes
1. Remove `setFixedHeight` on text containers
2. Use `sizeHint`/`minimumSizeHint` with proper size policies
3. Add `ui_lint.py` checker for text clipping
4. Dictionary screen rebuild per spec
5. Navigation: icon + text labels, 56-64px tall
6. Design system enforcement (single `theme.py`)
7. Apply fixes to Home, Lesson, Progress, Quiz, Settings

---

## Verification Commands

```bash
# Camera diagnostics
python3 tools/camera_diagnose.py

# Run app
python3 main.py

# Run tests
python3 -m pytest tests/ -v

# Generate screenshots
python3 tools/snapshot_screens.py --output docs/screenshots/phase2
```

---

## Decisions Log

| Decision | Rationale |
|----------|-----------|
| Use Qt Multimedia for capture instead of OpenCV | Single source of truth for device identity; native hot-plug; no index mapping needed |
| CameraService as singleton with reference counting | Single camera handle shared across screens; no conflicts |
| Device identity = Qt `QCameraDevice.id()` | Stable across reboots, virtual camera toggles |
| QPainter for skeleton overlay | No cv2 drawing overhead; GPU accelerated; resolution independent |
| InferenceWorker separate thread | Decouples inference from capture/display; no frame blocking |
| Frame dropping in inference | Keeps inference at own pace; display never waits |
| Performance HUD in separate widget | Non-intrusive; toggleable; useful for debugging |