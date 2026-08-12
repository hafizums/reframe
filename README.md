# Reframe Studio

A native Python desktop application for turning landscape video into vertical or social-media-friendly crops with keyframed camera movement.

This branch replaces the original HTML/CSS/JavaScript editor with a Python-first architecture:

- **PySide6** for the native desktop UI and media playback
- **QVideoSink** for frame-by-frame source and crop previews
- **FFmpeg / ffprobe** for deterministic final rendering and video metadata
- **JSON projects** for reusable keyframe timelines

## Features

- Open local MP4, MOV, MKV, AVI, or WebM video
- Source preview with draggable/clickable crop targeting
- Live cropped output preview
- Aspect presets: `9:16`, `1:1`, `4:5`, `4:3`
- Horizontal crop slider plus Left / Center / Right presets
- Timeline scrubbing and playback controls
- Keyframe add/update/remove and previous/next navigation
- Three transition modes:
  - Smooth Ease
  - Linear
  - Hold / Jump
- Save and load Reframe projects as JSON
- H.264 MP4 export through FFmpeg
- Source audio retained in the exported MP4
- Background export progress so the UI remains responsive

## Requirements

- Python 3.10+
- FFmpeg and ffprobe available in `PATH`

## Install

```bash
python -m venv .venv
```

### Windows

```powershell
.venv\Scripts\activate
pip install -e .
python main.py
```

### Linux / macOS

```bash
source .venv/bin/activate
pip install -e .
python main.py
```

After installation you can also launch with:

```bash
reframe-studio
```

## Basic workflow

1. Click **Open Video**.
2. Choose the target aspect ratio.
3. Drag or click inside the source preview to position the crop.
4. Scrub to a time on the timeline.
5. Choose the transition mode and click **Add / Update**.
6. Repeat for additional crop movements.
7. Click **Export MP4**.

The preview and FFmpeg exporter use the same Python interpolation model so keyframe timing and easing are defined in one place.

## Project files

A saved project stores:

```json
{
  "video_path": "C:/videos/input.mp4",
  "aspect": "9:16",
  "keyframes": [
    {"time": 0.0, "x": 0.5, "easing": "easeInOut"},
    {"time": 4.2, "x": 0.1, "easing": "linear"}
  ]
}
```

`x` is normalized:

- `0.0` = far left
- `0.5` = center
- `1.0` = far right

## Architecture

```text
reframe/
├── main.py              # Application entry point
├── reframe_app.py       # PySide6 desktop UI, playback, previews, export worker
├── reframe_core.py      # Project model, crop math, interpolation, FFmpeg command builder
├── pyproject.toml       # Python package metadata and dependencies
├── requirements.txt     # Simple pip dependency list
└── tests/
    └── test_core.py     # Crop/interpolation tests
```

### `reframe_core.py`

Contains the application logic that should stay independent of the UI:

- `Keyframe`
- `ReframeProject`
- video probing
- aspect/crop geometry
- crop-position interpolation
- FFmpeg crop expression generation
- final FFmpeg command generation

### `reframe_app.py`

Contains the desktop application:

- file dialogs
- Qt media player
- source and output frame previews
- crop interaction
- timeline controls
- keyframe table
- project save/load
- threaded export progress

## Export quality

Default export uses:

- H.264 (`libx264`)
- CRF 18
- AAC 192 kbps audio
- Lanczos scaling
- source frame rate
- `+faststart` for MP4 playback

## Tests

Install development dependencies and run:

```bash
pip install -e .[dev]
pytest
```

## Build a Windows executable

Qt for Python includes `pyside6-deploy` for packaging PySide6 applications. From the project directory:

```bash
pyside6-deploy main.py
```

The application currently expects FFmpeg and ffprobe to be installed separately and available in `PATH`.
