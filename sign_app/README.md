# Sign Language Learning Application

A desktop application for learning American Sign Language (ASL) fingerspelling using real-time hand tracking via webcam.

## Features

- **Real-time hand tracking** using MediaPipe (up to 2 hands)
- **Static ASL classification** for 24 letters (A-I, K-Y) and numbers 0-9
- **Interactive lessons** with guided practice and reference animations
- **Quiz mode** with timed questions and scoring
- **Searchable dictionary** with sign reference and practice
- **Progress tracking** with accuracy charts, mastery heatmap, streaks, and badges
- **Instructor dashboard** for assigning modules and viewing learner progress
- **Hand-driven UI** with dwell-to-click (2s hover) + full keyboard/mouse support
- **Fully offline** - all data stored locally in SQLite
- **Cross-platform** - Windows, macOS, Linux
- **Extensible** - content pack architecture for adding new sign languages

## Quick Start

### Prerequisites

- Python 3.11 (recommended) or 3.10-3.12
- Webcam
- macOS: Grant camera permission in System Settings → Privacy & Security → Camera

### Installation

```bash
# Clone and enter directory
cd sign_app

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app (QML "Sign Spark" UI)
python app/qml/main.py
```

### First Run

1. **Welcome & Consent** - Review privacy policy (Data Privacy Act of 2012 compliant)
2. **Create Profile** - Enter name, choose avatar color, select role (Learner/Instructor)
3. **Camera Check** - Verify webcam works and lighting is good
4. **Start Learning** - Begin with "Fingerspelling: A-E" module

## Project Structure

```
sign_app/
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── app/
│   ├── core/              # Camera, hand tracking, features, recognition
│   │   ├── camera_worker.py
│   │   ├── hand_tracker.py
│   │   ├── features.py
│   │   ├── recognizer.py
│   │   ├── smoothing.py
│   │   └── pipeline.py
│   ├── qml/               # QML "Sign Spark" GUI
│   │   ├── main.py        # QML entry point
│   │   ├── main.qml       # Root QML component
│   │   ├── theme/         # Theme system
│   │   ├── components/    # Reusable QML components
│   │   └── screens/       # HomeScreen, LessonScreen
│   ├── data/              # SQLite database
│   │   └── db.py
│   └── content/           # Content pack loader
│       └── loader.py
├── content_packs/
│   └── asl/               # ASL content pack
│       ├── pack.json
│       ├── signs.json
│       ├── modules.json
│       ├── model/         # Trained model (after training)
│       └── templates/     # Reference landmarks
├── tools/
│   ├── collect_data.py    # Data collection tool
│   └── train_model.py     # Model training tool
└── tests/                 # Unit tests
```

## Data Collection & Training

The app includes tools to collect your own training data and train a custom model.

### Collect Data

```bash
# Collect 50 samples per label for all ASL letters/numbers
python tools/collect_data.py --samples 50

# Collect for specific labels only
python tools/collect_data.py --labels A B C D E --samples 100

# Use different camera
python tools/collect_data.py --camera 1
```

The tool will:
1. Show a countdown (default 3s)
2. Record landmark frames while you hold the sign
3. Save landmarks (NOT images) to CSV with session/person IDs
4. Store metadata in JSON

### Train Model

```bash
# Train Random Forest (default)
python tools/train_model.py --data data/collected --output content_packs/asl/model

# Try SVM
python tools/train_model.py --model svm --plots

# Train with more test data
python tools/train_model.py --test-split 0.3
```

The tool will:
1. Load all CSV files from data directory
2. Extract features (translation/scale/handedness normalized)
3. Apply data augmentation (rotation, scale, noise)
4. Train classifier with cross-validation
5. Evaluate on held-out test set
6. Save model, labels, feature stats, and confusion matrix
7. Print honest accuracy assessment

### Model Requirements

For production use, aim for:
- ≥ 50 samples per class (more for similar signs like M/N, U/V)
- Multiple recording sessions/people for better generalization
- Good lighting variation in training data

## Content Pack Architecture

Each sign language is a self-contained folder in `content_packs/`:

```
content_packs/asl/
├── pack.json          # Manifest: id, name, version, categories
├── signs.json         # Sign definitions: id, label, category, difficulty, scored, description, reference_landmarks
├── modules.json       # Lesson modules: ordered sign IDs, difficulty, estimated time
├── model/
│   ├── model.joblib           # Trained classifier
│   ├── labels.json            # Class labels
│   ├── feature_stats.npz      # Normalization mean/std
│   ├── metadata.json          # Training metrics
│   ├── recognizer.joblib      # Recognizer wrapper
│   └── recognizer.json        # Recognizer config
└── templates/         # Reference landmarks for animations
```

To add a new sign language (e.g., Filipino Sign Language):
1. Create `content_packs/fsl/` with the above structure
2. No code changes needed - the app discovers packs automatically

## Usage

### Learning Flow

1. **Home** → Select a module (e.g., "Fingerspelling: A-E")
2. **Lesson** → See target letter + reference animation
3. **Practice** → Show sign to camera, hold steady for ~1s
4. **Feedback** → Green skeleton = correct, Red = adjust
5. **Progress** → Dots at bottom show module progress
6. **Next** → Click "Next" or dwell (hover 2s) on button

### Quiz Mode

- 10 random questions from module (scored signs only)
- 15 seconds per question
- Hold correct sign for 1s to answer
- Results show score, accuracy, avg time, weak signs
- "Retry Weak Signs" creates focused practice

### Dictionary

- Search signs by label (instant filter)
- Filter by category chips
- Click sign for reference animation + description
- "Practice This" jumps to lesson for that sign

### Progress

- **Accuracy Chart** - Line chart over time
- **Mastery Heatmap** - Grid of all letters colored by accuracy
- **Streak Calendar** - GitHub-style contribution graph
- **Badges** - Earned/unearned with criteria

### Instructor (role: Instructor)

- Table of all learners with completion rate, accuracy, streak
- Assign modules with due dates
- Export progress report to CSV

### Settings

- Camera selection & mirror toggle
- Theme (Dark/Light/System)
- Text size slider
- Confidence threshold & smoothing frames
- Hand dwell duration & enable/disable
- Language pack selection
- Export/Delete all data (GDPR/RA 10173 compliant)

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Esc` | Back |
| `Space` | Next / Continue |
| `←` / `→` | Previous / Next sign |
| `Tab` | Navigate UI |

## Hand Dwell Interaction

- Hover index fingertip over a button for 2 seconds (configurable)
- Circular progress ring fills around cursor
- Click triggers when ring completes
- Works on: Lesson Next, Quiz answers, large buttons
- Disable in Settings if not needed

## Accessibility

- WCAG AA contrast ratios
- Red-green colorblind safe palette (cyan accent, distinct success/error icons)
- Never color-only feedback (always icon + text)
- Visible focus rings for keyboard navigation
- Screen reader compatible labels
- Reduced motion support

## Privacy

- **No video/images stored** - only derived landmarks for recognition
- **Local SQLite only** - no cloud sync
- **Export/Delete** - full data portability and right to erasure
- **Consent screen** - first run explains what's stored
- **Philippines Data Privacy Act (RA 10172) compliant**

## Known Limitations (V1)

| Limitation | Impact | Future |
|------------|--------|--------|
| J & Z are motion signs | Not scored, reference only | Sequence model (LSTM/GRU) |
| Greetings/phrases are motion | Watch & Learn only | Dynamic sign recognition |
| Single-hand only for classification | Two hands tracked but only best used | Two-handed signs |
| No facial expression capture | Non-manual markers missing | MediaPipe Face Mesh integration |
| Static lighting assumption | May struggle in very dim light | Adaptive exposure / IR support |
| No Filipino Sign Language pack | ASL only | Community contributions welcome |

## Troubleshooting

### Camera not detected (macOS)
```bash
# Grant permission in System Settings → Privacy & Security → Camera
# Or run with:
sudo python main.py  # Not recommended for regular use
```

### Low FPS
- Reduce camera resolution in code (default 640x480)
- Close other camera apps
- Check CPU usage - MediaPipe is CPU-intensive

### Poor Recognition
- Ensure good, even lighting on hands
- Plain background works best
- Avoid dark nail polish / gloves
- Retrain with more diverse samples

### Model Not Found
```bash
# Collect data and train first
python tools/collect_data.py
python tools/train_model.py
```

### QML UI not loading
```bash
# Run with verbose output to see QML errors
python app/qml/main.py
```

## Development

### Run Tests
```bash
pytest tests/ -v
```

### Code Style
```bash
# Format
black app/ tools/

# Lint
ruff check app/ tools/

# Type check
mypy app/ tools/
```

### Packaging (PyInstaller)
```bash
pyinstaller --onefile --windowed --name "SignLanguageApp" \
  --add-data "content_packs:content_packs" \
  --add-data "app/qml:app/qml" \
  app/qml/main.py
```

## Decisions & Trade-offs

1. **MediaPipe Legacy API** - Used `mp.solutions.hands` for broader compatibility; Tasks API wrapper ready
2. **Random Forest default** - Fast training, good baseline, interpretable; SVM/MLP available
3. **Stratified split by frame** - Known limitation; should split by session/person for honest accuracy
4. **SQLite WAL mode** - Better concurrency for background DB writes
5. **QThread for camera** - Keeps UI responsive; signals for frame delivery
6. **Landmark-based features** - Not pixel-based; robust to lighting/skin tone
7. **No external video assets** - Reference animations generated from average landmarks
8. **Dark theme default** - Better for camera view contrast; light theme available

## Contributing

1. Fork the repository
2. Create feature branch
3. Run tests and linting
4. Submit PR with description

## License

MIT License - See LICENSE file for details.

## Acknowledgments

- MediaPipe team (Google) for hand tracking
- ASL community for sign reference standards
- scikit-learn for ML utilities
- Qt/PySide6 for cross-platform GUI