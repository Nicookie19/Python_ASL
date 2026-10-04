# AUDIT.md - Camera and Performance Audit

## Executive Summary
- **Camera Issue**: Some screens use OBS Virtual Camera (index 1) instead of FaceTime HD Camera (index 0)
- **Stutter Issue**: Video stutters when hand is in frame - likely due to MediaPipe running in same thread as capture/display
- **Root Cause**: Multiple camera access paths, index-based selection, inference on capture thread

---

## Camera Audit

### Camera Enumeration (from camera_diagnose.py)
| Index | Device | Resolution | FPS | Backend | Type |
|-------|--------|------------|-----|---------|------|
| 0 | FaceTime HD Camera | 1920x1080 | 34.2 | AVFoundation | Built-in |
| 1 | OBS Virtual Camera | 640x480 | 21.8 | AVFoundation | Virtual |
| 2-5 | N/A | N/A | N/A | N/A | N/A |

### Current Camera Selection Logic Issues
1. **Index-based selection**: CameraWorker uses `camera_index` (int) - breaks when virtual cameras shift indices
2. **Multiple code paths** using cameras:
   - `CameraWorker` (OpenCV, `app/core/camera_worker.py`)
   - `CameraService` (Qt Multimedia, `app/core/camera_service.py`)
   - `CameraWorker` in pipeline
   - `CameraCheckWidget` (welcome screen, settings)
   - `tools/collect_data.py` - standalone tool
   - `tools/camera_diagnose.py` - diagnostic
3. **Settings store camera_index** (int) not device name/ID
4. **Qt Multimedia available** but `CameraWorker` uses OpenCV directly

### Current Camera Selection Logic (`camera_devices.py`)
- `discover_camera_devices()` - uses `QMediaDevices.videoInputs()` ✓
- `preferred_camera()` - prefers built-in, deprioritizes virtual ✓
- BUT: `CameraWorker` still uses `camera_index` (int) not device ID

---

## Stutter Issue Analysis

### Current Pipeline Architecture (`app/core/pipeline.py`)
```
CameraWorker (QThread) 
  → frame_ready (DirectConnection) 
  → Pipeline._process_frame() [SAME THREAD]
    → HandTracker.process() [MediaPipe]
    → FeatureExtractor.extract()
    → StaticRecognizer.predict()
    → TemporalSmoother.update()
    → ConfidenceMeter.update()
    → DwellDetector.update()
    → HandTracker.draw_landmarks() [cv2 on full-res frame]
    → result_ready.emit() [UI thread via queued connection]
```

### Problems Identified:
1. **All inference on capture thread** - MediaPipe + classification + drawing blocks frame capture
2. **cv2 drawing on full-res frames** - Then converted to QImage/QPixmap for UI
3. **Full-resolution frames** (1920x1080) processed by MediaPipe
4. **No frame dropping** - Inference blocks capture
4. **cv2 drawing on BGR frames** → QImage → QPixmap → QLabel (slow path)

### MediaPipe Configuration
- Using Tasks API `HandLandmarker` in `IMAGE` mode (not `LIVE_STREAM`)
- `model_complexity=0` (lite) - GOOD
- But: `running_mode=IMAGE` processes each frame independently (no tracking)
- No `LIVE_STREAM` mode with timestamp tracking

### MediaPipe Inference Performance (from diagnostics)
- 22ms/frame average (83 frames, no hand)
- 28.5ms initialization
- With hand: likely higher

---

## Current Architecture Problems

### Multiple Camera Access Paths
| Component | Camera Access Method | Issues |
|-----------|---------------------|--------|
| `CameraWorker` | OpenCV `cv2.VideoCapture(index)` | Index-based, no device identity |
| `CameraService` | Qt Multimedia `QCamera` + `QVideoSink` | Good but not used by pipeline |
| `CameraCheckWidget` | Uses pipeline's camera worker | Indirect |
| `tools/collect_data.py` | Direct `cv2.VideoCapture(index)` | Standalone, index-based |
| `tools/camera_diagnose.py` | Direct `cv2.VideoCapture` | Diagnostic only |

### Settings Storage (`app/data/db.py`)
- `AppSettings.camera_index` - stores integer index (BAD)
- Should store: `camera_device_id` (Qt device ID string)

---

## Performance Targets (from requirements)
| Metric | Target | Current (est.) |
|--------|--------|----------------|
| Display FPS | ≥ 30 | ~30 (stutters with hand) |
| Inference FPS | ≥ 20 | ~15-20 (with hand) |
| p95 Inference Latency | < 40ms | ~50-80ms (est.) |
| UI Thread Blocking | < 50ms | Exceeds (blocks on inference) |
| End-to-end Latency | < 150ms | >200ms (est.) |
| Stutter on hand entry | None | Visible stutter |

---

## Fix Plan

### Phase 1: CameraService Unification (TASK 1)
1. **Remove all direct `cv2.VideoCapture` usage** except in `CameraCaptureWorker`
2. **Use `CameraService` as single camera authority**:
   - Single `CameraCaptureWorker` (Qt Multimedia preferred, OpenCV fallback)
   - Reference counting: `acquire(owner)` / `release(owner)`
   - Device identity = `QCameraDevice.id()` string
2. **Device identity = Qt `QCameraDevice.id()`** (stable UUID)
3. **Ranking**: Built-in > Physical USB > Virtual (hidden by default)
4. **Settings**: Store `camera_device_id` (string), not index
5. **Hot-plug**: `QMediaDevices.videoInputsChanged` → re-enumerate
8. **Static feed detection**: >2s near-zero variance → warn + fallback

### TASK 2: Stutter Fix
1. **Instrument**: Performance HUD (Ctrl+Shift+D) showing:
   - Capture FPS, Display FPS, Inference FPS
   - Inference ms (avg/p95), UI paint ms, dropped frames
   - UI thread watchdog (16ms timer)
2. **Decoupled Pipeline**:
   - Capture thread → latest frame buffer (drop old)
   - Display thread: immediate paint, never waits for inference
   - Inference thread: consumes latest frame, publishes results at own pace
   - UI paints from latest frame + latest landmarks (QPainter overlay)
3. **MediaPipe Optimization**:
   - `HandLandmarker` in `LIVE_STREAM` mode with timestamps
   - `model_complexity=0`, `num_hands=1`
   - Downscale inference frames to 480px max dimension
   - QPainter overlay from normalized landmarks (no cv2 drawing)
4. **Thread Management**:
   - `cv2.setNumThreads(2)`
   - Inference on separate `QThread`
   - UI paint: QPainter on `QVideoFrame`/`QImage` (FastTransformation)

---

## Action Items

### Immediate (Phase 1 - Camera Service)
- [ ] Write `AUDIT.md` with findings
- [ ] Create `CameraService` as single camera authority
- [ ] Migrate all camera access to `CameraService`
- [ ] Add `cv2-enumerate-cameras` for device enumeration by name
- [ ] Migrate settings to `camera_device_id` (string)
- [ ] Write `test_no_stray_camera_access.py`

### Phase 2: Stutter Fix
- [ ] Add Performance HUD (Settings toggle + Ctrl+Shift+D)
- [ ] Create `InferenceWorker` thread
- [ ] Decouple pipeline: Capture → Display (immediate) + Inference (async)
- [ ] MediaPipe `LIVE_STREAM` mode with timestamps
- [ ] Downscale inference frames to 480p max
- [ ] QPainter skeleton overlay from normalized landmarks
- [ ] Performance HUD toggle (Settings + Ctrl+Shift+D)

---

## Next Steps
1. Write `AUDIT.md` with findings
2. Start Phase 1 implementation
3. Verify each step with `camera_diagnose.py` and app run