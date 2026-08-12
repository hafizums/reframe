# Reframe Studio 9:16

A browser-based video reframing tool that converts **16:9 landscape videos** into **9:16 vertical videos** for TikTok, Instagram Reels, and YouTube Shorts.

![Preview](https://img.shields.io/badge/Status-Ready-brightgreen) ![License](https://img.shields.io/badge/License-MIT-blue)

---

## What It Does

Upload any 16:9 landscape video and visually select which horizontal region to keep in a 9:16 vertical crop. Drag the crop window left/right across the source video, set keyframes along the timeline so the crop pans smoothly over time, then export a perfectly smooth vertical video using Python + FFmpeg.

---

## Features

### 🎬 Visual Crop Editor
- Drag or click on the 16:9 source canvas to position the vertical crop window
- Real-time 9:16 preview showing exactly what the output will look like
- Support for multiple aspect ratios: `9:16`, `1:1`, `4:5`, `4:3`

### ⏱️ Keyframe Timeline
- Add keyframes at any point in the video to animate the crop position over time
- Three interpolation modes:
  - **Smooth Easing** — cubic ease-in-out for natural camera pans
  - **Linear Pan** — constant speed movement
  - **Hold / Jump Cut** — stays in position then jumps to the next keyframe
- Interactive timeline scrubber with diamond keyframe markers

### 📱 TikTok Preview Overlay
- Toggle a realistic TikTok UI overlay on the 9:16 preview (like button, comments, share, spinning vinyl disc, creator handle, music ticker)
- See exactly how your video will look when posted

### 🚀 Export Options

| Method | Quality | Speed |
|--------|---------|-------|
| **Python + FFmpeg** (Recommended) | Frame-perfect, lossless H.264 MP4 | Fast |
| **Browser Export** | Good, may have minor frame timing issues | Real-time |
| **FFmpeg CLI** | Copy the raw command for terminal use | — |

### 🎨 Built-in Demo Mode
- No video? The app launches with an animated demo so you can explore all features immediately

---

## Quick Start

### 1. Serve the app locally

```bash
cd Reframe
npx serve .
```

Open `http://localhost:3000` in your browser.

### 2. Use the editor

1. **Upload** a 16:9 video (drag & drop or click the upload area)
2. **Drag** the cyan crop box left/right on the source canvas
3. **Add keyframes** along the timeline to animate the crop pan
4. **Preview** the result in the 9:16 live output panel

### 3. Export with Python + FFmpeg

```bash
# Download keyframes.json from the Export modal, then:
python export.py input.mp4 keyframes.json output_9x16.mp4
```

**Advanced options:**
```bash
# Custom resolution & framerate
python export.py input.mp4 keyframes.json -r 720x1280 -f 60

# Square crop for Instagram
python export.py input.mp4 keyframes.json -a 1:1
```

---

## Requirements

| Tool | Version | Purpose |
|------|---------|---------|
| Modern browser | Chrome / Edge / Firefox | Run the web app |
| [Python 3](https://www.python.org/downloads/) | 3.8+ | Run the export script |
| [FFmpeg](https://ffmpeg.org/download.html) | 4.0+ | Encode the output video |

---

## Project Structure

```
Reframe/
├── index.html              # Main app shell & layout
├── styles.css              # Dark theme, glassmorphic UI styling
├── app.js                  # UI controller & event wiring
├── export.py               # Python FFmpeg export script
├── js/
│   ├── reframe-engine.js   # Core dual-canvas rendering & crop logic
│   ├── timeline.js         # Timeline scrubber & keyframe management
│   ├── exporter.js         # Browser-based MediaRecorder export
│   └── demo-generator.js   # Animated demo video generator
└── README.md
```

---

## How the Export Works

1. **In the browser**: You position the crop and set keyframes. The engine stores each keyframe as `{ time, x, easing }` where `x` is a normalized `0.0–1.0` horizontal position.

2. **export.py** reads this JSON and builds an FFmpeg `-vf crop=...` filter with time-based expressions that replicate the exact same easing math:
   - `easeInOut` → cubic bezier: `2t² (t<0.5)` / `1 - (-2t+2)²/2 (t≥0.5)`
   - `linear` → straight interpolation
   - `hold` → step function

3. **FFmpeg** processes every frame deterministically — no dropped frames, no lag, perfectly smooth output.

---

## License

MIT
"# reframe" 
