/**
 * Reframe Studio 9:16 - Main Application Controller
 * Orchestrates UI interactions, video uploads, engine setup, timeline sync, and modal exports.
 */

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const sourceVideo = document.getElementById('sourceVideo');
  const sourceCanvas = document.getElementById('sourceCanvas');
  const previewCanvas = document.getElementById('previewCanvas');
  const cropOverlay = document.getElementById('cropOverlay');
  const dropZone = document.getElementById('dropZone');
  const dropMsg = document.getElementById('dropMsg');
  const videoFileInput = document.getElementById('videoFileInput');

  // Controls & Inputs
  const aspectRatioSelect = document.getElementById('aspectRatioSelect');
  const toggleGridBtn = document.getElementById('toggleGridBtn');
  const centerCropBtn = document.getElementById('centerCropBtn');
  const loadDemoBtn = document.getElementById('loadDemoBtn');
  const exportModalBtn = document.getElementById('exportModalBtn');

  // Quick Position Slider
  const cropPosSlider = document.getElementById('cropPosSlider');
  const sliderValDisplay = document.getElementById('sliderValDisplay');
  const posPresets = document.querySelectorAll('.btn-pos-preset');
  const cropPosInfo = document.getElementById('cropPosInfo');

  // Playback Controls
  const playPauseBtn = document.getElementById('playPauseBtn');
  const playIcon = document.getElementById('playIcon');
  const pauseIcon = document.getElementById('pauseIcon');
  const stepBackBtn = document.getElementById('stepBackBtn');
  const stepForwardBtn = document.getElementById('stepForwardBtn');
  const currentTimeDisplay = document.getElementById('currentTimeDisplay');
  const durationDisplay = document.getElementById('durationDisplay');
  const volumeSlider = document.getElementById('volumeSlider');
  const muteBtn = document.getElementById('muteBtn');

  // Keyframe Controls
  const addKeyframeBtn = document.getElementById('addKeyframeBtn');
  const removeKeyframeBtn = document.getElementById('removeKeyframeBtn');
  const prevKeyframeBtn = document.getElementById('prevKeyframeBtn');
  const nextKeyframeBtn = document.getElementById('nextKeyframeBtn');
  const timelineContainer = document.getElementById('timelineContainer');
  const keyframeContainer = document.getElementById('keyframeContainer');
  const playhead = document.getElementById('playhead');

  // Modal Elements
  const exportModal = document.getElementById('exportModal');
  const closeModalBtn = document.getElementById('closeModalBtn');
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');
  const ffmpegCommandCode = document.getElementById('ffmpegCommandCode');
  const jsonKeyframesCode = document.getElementById('jsonKeyframesCode');
  const copyFfmpegBtn = document.getElementById('copyFfmpegBtn');
  const copyJsonBtn = document.getElementById('copyJsonBtn');
  const downloadJsonBtn = document.getElementById('downloadJsonBtn');
  const startRenderBtn = document.getElementById('startRenderBtn');
  const downloadLink = document.getElementById('downloadLink');
  const progressArea = document.getElementById('progressArea');
  const progressFill = document.getElementById('progressFill');
  const progressPercent = document.getElementById('progressPercent');

  // 1. Initialize Engine, Timeline, Exporter
  const engine = new ReframeEngine(sourceVideo, sourceCanvas, previewCanvas, cropOverlay);
  const timeline = new TimelineController(engine, timelineContainer, keyframeContainer, playhead);
  const exporter = new Exporter(engine);

  // Load initial demo video
  engine.setVideoSource('demo');

  // 2. Position Updates & Displays
  engine.onPositionChange = (normX) => {
    cropPosSlider.value = normX;
    const pct = Math.round(normX * 100);
    sliderValDisplay.textContent = `${pct}%`;

    const rect = engine.getCropRect();
    cropPosInfo.textContent = `X: ${normX.toFixed(2)} | ${Math.round(rect.width)} × ${Math.round(rect.height)}`;
  };

  engine.onTimeUpdate = (curTime, dur) => {
    currentTimeDisplay.textContent = formatTimecode(curTime);
    durationDisplay.textContent = formatTimecode(dur);
    timeline.updatePlayhead(curTime, dur);
    updatePlayPauseUI();
  };

  function formatTimecode(secs) {
    if (isNaN(secs) || secs < 0) return '00:00.00';
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    const ms = Math.floor((secs % 1) * 100);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
  }

  // 3. Aspect Ratio Selection
  aspectRatioSelect.addEventListener('change', (e) => {
    engine.setAspectRatio(e.target.value);
    const badge = document.getElementById('outputResBadge');
    if (badge) {
      badge.textContent = `${engine.previewCanvas.width} × ${engine.previewCanvas.height} (${e.target.value})`;
    }
  });

  // 4. Quick Position Slider & Presets
  cropPosSlider.addEventListener('input', (e) => {
    engine.setCropNormalizedX(parseFloat(e.target.value));
  });

  posPresets.forEach(btn => {
    btn.addEventListener('click', () => {
      const pos = parseFloat(btn.dataset.pos);
      engine.setCropNormalizedX(pos);
    });
  });

  centerCropBtn.addEventListener('click', () => {
    engine.setCropNormalizedX(0.5);
  });

  // 5. Grid & TikTok UI Toggle
  toggleGridBtn.addEventListener('click', () => {
    const gridLines = cropOverlay.querySelector('.crop-grid-lines');
    if (gridLines) {
      const isVisible = gridLines.style.display !== 'none';
      gridLines.style.display = isVisible ? 'none' : 'block';
      toggleGridBtn.classList.toggle('active-toggle', !isVisible);
    }
  });

  const toggleTiktokUiBtn = document.getElementById('toggleTiktokUiBtn');
  const tiktokUiOverlay = document.getElementById('tiktokUiOverlay');
  if (toggleTiktokUiBtn && tiktokUiOverlay) {
    toggleTiktokUiBtn.addEventListener('click', () => {
      const isHidden = tiktokUiOverlay.classList.toggle('hidden-overlay');
      toggleTiktokUiBtn.classList.toggle('active-toggle', !isHidden);
    });
  }

  // 6. Playback Controls
  function updatePlayPauseUI() {
    const isPlaying = !sourceVideo.paused && !sourceVideo.ended;
    playIcon.hidden = isPlaying;
    pauseIcon.hidden = !isPlaying;
  }

  playPauseBtn.addEventListener('click', () => {
    if (engine.isDemoMode) {
      // Demo is continuous canvas loop
      return;
    }
    if (sourceVideo.paused) {
      sourceVideo.play();
    } else {
      sourceVideo.pause();
    }
    updatePlayPauseUI();
  });

  stepBackBtn.addEventListener('click', () => {
    if (!engine.isDemoMode) {
      sourceVideo.currentTime = Math.max(0, sourceVideo.currentTime - 1);
    }
  });

  stepForwardBtn.addEventListener('click', () => {
    if (!engine.isDemoMode) {
      sourceVideo.currentTime = Math.min(sourceVideo.duration, sourceVideo.currentTime + 1);
    }
  });

  volumeSlider.addEventListener('input', (e) => {
    sourceVideo.volume = parseFloat(e.target.value);
  });

  muteBtn.addEventListener('click', () => {
    sourceVideo.muted = !sourceVideo.muted;
    muteBtn.style.color = sourceVideo.muted ? '#ef4444' : '';
  });

  // Keyboard Spacebar Play/Pause
  window.addEventListener('keydown', (e) => {
    if (e.code === 'Space' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'SELECT') {
      e.preventDefault();
      playPauseBtn.click();
    }
  });

  // 7. Keyframe Tools
  addKeyframeBtn.addEventListener('click', () => {
    timeline.addOrUpdateKeyframeAtCurrentTime();
  });

  removeKeyframeBtn.addEventListener('click', () => {
    timeline.removeKeyframeAtCurrentTime();
  });

  prevKeyframeBtn.addEventListener('click', () => {
    timeline.jumpToPrevKeyframe();
  });

  nextKeyframeBtn.addEventListener('click', () => {
    timeline.jumpToNextKeyframe();
  });

  // 8. File Drag & Drop & Upload
  loadDemoBtn.addEventListener('click', () => {
    dropMsg.hidden = true;
    engine.setVideoSource('demo');
  });

  videoFileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
      dropMsg.hidden = true;
      engine.setVideoSource(file);
    }
  });

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropMsg.hidden = false;
  });

  dropZone.addEventListener('dragleave', (e) => {
    if (e.target === dropZone) {
      dropMsg.hidden = true;
    }
  });

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropMsg.hidden = true;
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      engine.setVideoSource(e.dataTransfer.files[0]);
    }
  });

  // 9. Export Modal & Code Generators
  exportModal.style.display = 'none';
  exportModal.hidden = true;

  exportModalBtn.addEventListener('click', () => {
    exportModal.style.display = 'flex';
    exportModal.hidden = false;
    updateModalCodes();
  });

  closeModalBtn.addEventListener('click', () => {
    exportModal.style.display = 'none';
    exportModal.hidden = true;
  });

  exportModal.addEventListener('click', (e) => {
    if (e.target === exportModal) {
      exportModal.style.display = 'none';
      exportModal.hidden = true;
    }
  });

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      tabContents.forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      const targetId = `tab-${btn.dataset.tab}`;
      document.getElementById(targetId).classList.add('active');
    });
  });

  function updateModalCodes() {
    ffmpegCommandCode.textContent = exporter.generateFfmpegCommand();
    jsonKeyframesCode.textContent = exporter.getKeyframesJson();
  }

  copyFfmpegBtn.addEventListener('click', () => {
    navigator.clipboard.writeText(ffmpegCommandCode.textContent);
    copyFfmpegBtn.textContent = 'Copied!';
    setTimeout(() => copyFfmpegBtn.textContent = 'Copy Command', 2000);
  });

  copyJsonBtn.addEventListener('click', () => {
    navigator.clipboard.writeText(jsonKeyframesCode.textContent);
    copyJsonBtn.textContent = 'Copied!';
    setTimeout(() => copyJsonBtn.textContent = 'Copy JSON', 2000);
  });

  downloadJsonBtn.addEventListener('click', () => {
    const jsonStr = exporter.getKeyframesJson();
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'reframed_keyframes.json';
    a.click();
  });

  // Python FFmpeg Export Tab Handlers
  const downloadKeyframesForPython = document.getElementById('downloadKeyframesForPython');
  const copyPythonCmdBtn = document.getElementById('copyPythonCmdBtn');

  if (downloadKeyframesForPython) {
    downloadKeyframesForPython.addEventListener('click', () => {
      const jsonStr = exporter.getKeyframesJson();
      const blob = new Blob([jsonStr], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'keyframes.json';
      a.click();
      downloadKeyframesForPython.textContent = '✅ Downloaded!';
      setTimeout(() => downloadKeyframesForPython.textContent = '⬇ Download keyframes.json', 2500);
    });
  }

  if (copyPythonCmdBtn) {
    copyPythonCmdBtn.addEventListener('click', () => {
      const cmdEl = document.getElementById('pythonExportCommand');
      if (cmdEl) {
        navigator.clipboard.writeText(cmdEl.textContent);
        copyPythonCmdBtn.textContent = 'Copied!';
        setTimeout(() => copyPythonCmdBtn.textContent = 'Copy', 2000);
      }
    });
  }

  // Direct Browser Render Export
  startRenderBtn.addEventListener('click', () => {
    startRenderBtn.disabled = true;
    progressArea.hidden = false;
    downloadLink.hidden = true;

    const fpsSelect = document.getElementById('exportFpsSelect');
    const resSelect = document.getElementById('exportResSelect');
    const burnInCheckbox = document.getElementById('burnInOverlayCheckbox');

    const fps = parseInt(fpsSelect ? fpsSelect.value : '30');
    const targetRes = resSelect ? resSelect.value : '1080x1920';
    const burnInOverlay = burnInCheckbox ? burnInCheckbox.checked : false;

    exporter.startBrowserRendering(
      fps,
      targetRes,
      burnInOverlay,
      (pct) => {
        progressFill.style.width = `${pct}%`;
        progressPercent.textContent = `${pct}%`;
      },
      (downloadUrl, ext = 'mp4') => {
        progressFill.style.width = '100%';
        progressPercent.textContent = '100%';
        startRenderBtn.disabled = false;
        downloadLink.href = downloadUrl;
        downloadLink.download = `reframed_video_9x16.${ext}`;
        downloadLink.hidden = false;
      }
    );
  });
});
