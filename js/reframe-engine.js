/**
 * Reframe Studio 9:16 - Core Engine
 * Manages video loading, crop boundary calculations, dual canvas rendering,
 * aspect ratio presets, and keyframe position interpolation.
 */

class ReframeEngine {
  constructor(sourceVideoEl, sourceCanvasEl, previewCanvasEl, overlayEl) {
    this.video = sourceVideoEl;
    this.sourceCanvas = sourceCanvasEl;
    this.sourceCtx = sourceCanvasEl.getContext('2d');
    this.previewCanvas = previewCanvasEl;
    this.previewCtx = previewCanvasEl.getContext('2d');
    this.overlay = overlayEl;

    // Aspect ratio setting (default 9:16)
    this.aspectRatioPreset = '9:16';
    this.aspectRatioValue = 9 / 16; // width / height

    // Crop position normalized [0.0 = Far Left, 1.0 = Far Right]
    this.cropNormalizedX = 0.5; // Center default
    this.showGrid = true;

    // Dynamic video dimensions
    this.videoWidth = 1280;
    this.videoHeight = 720;

    // Timeline keyframes list: Array of { time: float, x: float, easing: string }
    this.keyframes = [
      { time: 0, x: 0.5, easing: 'easeInOut' }
    ];

    // Rendering loop state
    this.isRendering = false;
    this.isDemoMode = false;
    this.demoCanvas = null;
    this.isUserDragging = false;

    // Event Listeners
    this.onPositionChange = null;
    this.onTimeUpdate = null;

    this.initOverlayEvents();
    window.addEventListener('resize', () => this.updateOverlayPosition());
  }

  setVideoSource(source) {
    if (typeof source === 'string' || source instanceof File || source instanceof Blob) {
      this.isDemoMode = false;
      const url = typeof source === 'string' ? source : URL.createObjectURL(source);
      this.video.src = url;
      this.video.load();
      
      this.video.onloadedmetadata = () => {
        this.videoWidth = this.video.videoWidth || 1280;
        this.videoHeight = this.video.videoHeight || 720;
        this.resizeCanvases();
        this.startLoop();
      };
    } else if (source === 'demo') {
      this.isDemoMode = true;
      this.demoCanvas = DemoGenerator.createDemoStream(1280, 720);
      this.videoWidth = 1280;
      this.videoHeight = 720;
      this.resizeCanvases();
      this.startLoop();
    }
  }

  setAspectRatio(preset) {
    this.aspectRatioPreset = preset;
    switch (preset) {
      case '9:16':
        this.aspectRatioValue = 9 / 16;
        break;
      case '1:1':
        this.aspectRatioValue = 1 / 1;
        break;
      case '4:5':
        this.aspectRatioValue = 4 / 5;
        break;
      case '4:3':
        this.aspectRatioValue = 4 / 3;
        break;
      default:
        this.aspectRatioValue = 9 / 16;
    }
    this.resizeCanvases();
    this.updateOverlayPosition();
  }

  resizeCanvases() {
    // Set 16:9 source canvas resolution
    this.sourceCanvas.width = this.videoWidth;
    this.sourceCanvas.height = this.videoHeight;

    // Set 9:16 preview canvas resolution (Standard 1080x1920 or matching aspect)
    const previewH = 1920;
    const previewW = Math.round(previewH * this.aspectRatioValue);
    this.previewCanvas.width = previewW;
    this.previewCanvas.height = previewH;
  }

  getCropRect() {
    // Height fills the source video height
    const cropHeight = this.videoHeight;
    // Width is determined by target aspect ratio
    const cropWidth = cropHeight * this.aspectRatioValue;

    // Max horizontal pan offset
    const maxOffset = Math.max(0, this.videoWidth - cropWidth);
    const cropX = this.cropNormalizedX * maxOffset;

    return {
      x: cropX,
      y: 0,
      width: cropWidth,
      height: cropHeight,
      maxOffset: maxOffset
    };
  }

  setCropNormalizedX(xVal) {
    this.cropNormalizedX = Math.max(0, Math.min(1, xVal));
    this.updateOverlayPosition();
    if (this.onPositionChange) {
      this.onPositionChange(this.cropNormalizedX);
    }
  }

  updateOverlayPosition() {
    if (!this.sourceCanvas || !this.overlay) return;
    const rect = this.getCropRect();

    // Calculate overlay CSS position relative to displayed canvas size
    const canvasBox = this.sourceCanvas.getBoundingClientRect();
    if (canvasBox.width <= 0) return;

    const scaleX = canvasBox.width / this.videoWidth;

    const overlayWidthPx = rect.width * scaleX;
    const overlayXPx = rect.x * scaleX;

    this.overlay.style.width = `${overlayWidthPx}px`;
    this.overlay.style.left = `${overlayXPx}px`;
  }

  initOverlayEvents() {
    let startMouseX = 0;
    let startNormalizedX = 0;

    const handleStart = (e) => {
      this.isUserDragging = true;
      startMouseX = e.clientX || (e.touches && e.touches[0].clientX) || 0;
      startNormalizedX = this.cropNormalizedX;
      document.body.style.userSelect = 'none';
    };

    const handleMove = (e) => {
      if (!this.isUserDragging) return;
      const currentMouseX = e.clientX || (e.touches && e.touches[0].clientX) || 0;
      const deltaX = currentMouseX - startMouseX;

      const canvasBox = this.sourceCanvas.getBoundingClientRect();
      const rect = this.getCropRect();
      if (rect.maxOffset <= 0 || canvasBox.width <= 0) return;

      const scaleX = canvasBox.width / this.videoWidth;
      const deltaVideoPx = deltaX / scaleX;
      const deltaNormalized = deltaVideoPx / rect.maxOffset;

      this.setCropNormalizedX(startNormalizedX + deltaNormalized);
    };

    const handleEnd = () => {
      if (this.isUserDragging) {
        this.isUserDragging = false;
        document.body.style.userSelect = '';

        // Sync drag position to active keyframe if single keyframe or near current time
        const curTime = this.getCurrentTime();
        if (this.keyframes.length === 1 && this.keyframes[0].time === 0) {
          this.keyframes[0].x = this.cropNormalizedX;
        } else {
          const kf = this.keyframes.find(k => Math.abs(k.time - curTime) < 0.25);
          if (kf) {
            kf.x = this.cropNormalizedX;
          }
        }
      }
    };

    // Overlay drag events
    this.overlay.addEventListener('mousedown', handleStart);
    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleEnd);

    this.overlay.addEventListener('touchstart', handleStart, { passive: true });
    window.addEventListener('touchmove', handleMove, { passive: true });
    window.addEventListener('touchend', handleEnd);

    // Canvas click to center crop window
    const handleCanvasClick = (e) => {
      if (e.target === this.overlay || this.overlay.contains(e.target)) return;
      const canvasBox = this.sourceCanvas.getBoundingClientRect();
      if (canvasBox.width <= 0) return;
      
      const clickX = e.clientX - canvasBox.left;
      const scaleX = canvasBox.width / this.videoWidth;
      const clickVideoX = clickX / scaleX;
      
      const rect = this.getCropRect();
      if (rect.maxOffset <= 0) return;

      const targetCropX = clickVideoX - (rect.width / 2);
      const normalizedX = targetCropX / rect.maxOffset;
      this.setCropNormalizedX(normalizedX);

      const curTime = this.getCurrentTime();
      if (this.keyframes.length === 1 && this.keyframes[0].time === 0) {
        this.keyframes[0].x = this.cropNormalizedX;
      }
    };

    this.sourceCanvas.addEventListener('click', handleCanvasClick);
  }

  // Interpolates crop position for current time based on keyframes
  getCurrentInterpolatedX(currentTime) {
    if (!this.keyframes || this.keyframes.length === 0) {
      return this.cropNormalizedX;
    }
    if (this.keyframes.length === 1) {
      return this.keyframes[0].x;
    }

    // Sort keyframes by timestamp
    const sorted = [...this.keyframes].sort((a, b) => a.time - b.time);

    // Before first keyframe
    if (currentTime <= sorted[0].time) {
      return sorted[0].x;
    }
    // After last keyframe
    if (currentTime >= sorted[sorted.length - 1].time) {
      return sorted[sorted.length - 1].x;
    }

    // Find bounding keyframe segment
    let prevIndex = 0;
    for (let i = 0; i < sorted.length - 1; i++) {
      if (currentTime >= sorted[i].time && currentTime <= sorted[i + 1].time) {
        prevIndex = i;
        break;
      }
    }

    const k1 = sorted[prevIndex];
    const k2 = sorted[prevIndex + 1];

    const segmentDuration = k2.time - k1.time;
    if (segmentDuration <= 0) return k1.x;

    let t = (currentTime - k1.time) / segmentDuration;

    // Apply Easing
    const mode = k1.easing || 'easeInOut';
    if (mode === 'easeInOut') {
      // Smooth cubic bezier easing
      t = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
    } else if (mode === 'hold') {
      // Step jump
      t = 0;
    }

    return k1.x + (k2.x - k1.x) * t;
  }

  getCurrentTime() {
    if (this.isDemoMode) {
      return (Date.now() / 1000) % 30; // 30s loop
    }
    return this.video.currentTime || 0;
  }

  getDuration() {
    if (this.isDemoMode) {
      return 30; // 30s demo duration
    }
    return this.video.duration || 0;
  }

  startLoop() {
    if (this.isRendering) return;
    this.isRendering = true;

    const render = () => {
      if (!this.isRendering) return;

      const curTime = this.getCurrentTime();

      // Update position from keyframe interpolation ONLY when user is NOT actively dragging
      if (this.keyframes.length > 0 && !this.isUserDragging) {
        const autoX = this.getCurrentInterpolatedX(curTime);
        this.cropNormalizedX = autoX;
        this.updateOverlayPosition();
      } else {
        this.updateOverlayPosition();
      }

      // Draw Source Canvas (16:9)
      const sourceDrawable = this.isDemoMode ? this.demoCanvas : this.video;
      if (sourceDrawable) {
        this.sourceCtx.drawImage(sourceDrawable, 0, 0, this.videoWidth, this.videoHeight);

        // Draw Crop Highlight Bounding Box on source canvas if needed
        const rect = this.getCropRect();
        
        // Translucent dark mask outside crop
        this.sourceCtx.fillStyle = 'rgba(0, 0, 0, 0.45)';
        // Left dark mask
        this.sourceCtx.fillRect(0, 0, rect.x, this.videoHeight);
        // Right dark mask
        this.sourceCtx.fillRect(rect.x + rect.width, 0, this.videoWidth - (rect.x + rect.width), this.videoHeight);

        // Draw Reframed Live Preview Canvas (9:16 Output)
        this.previewCtx.drawImage(
          sourceDrawable,
          rect.x, rect.y, rect.width, rect.height, // Source crop rectangle
          0, 0, this.previewCanvas.width, this.previewCanvas.height // Preview destination canvas
        );

        // Burn-in TikTok UI Overlay graphics if requested
        if (this.burnInOverlay) {
          this.drawTiktokOverlayOnCanvas(this.previewCtx, this.previewCanvas.width, this.previewCanvas.height, curTime);
        }
      }

      if (this.onTimeUpdate) {
        this.onTimeUpdate(curTime, this.getDuration());
      }

      requestAnimationFrame(render);
    };

    render();
  }

  drawTiktokOverlayOnCanvas(ctx, w, h, curTime) {
    ctx.save();

    // Bottom gradient vignette
    const btmGrad = ctx.createLinearGradient(0, h * 0.65, 0, h);
    btmGrad.addColorStop(0, 'transparent');
    btmGrad.addColorStop(1, 'rgba(0, 0, 0, 0.7)');
    ctx.fillStyle = btmGrad;
    ctx.fillRect(0, h * 0.65, w, h * 0.35);

    // Right Action Sidebar Icons
    const sidebarX = w * 0.88;
    const sidebarStartY = h * 0.48;
    const iconGap = h * 0.085;

    // 1. Avatar Circle
    ctx.save();
    ctx.shadowColor = 'rgba(0, 0, 0, 0.5)';
    ctx.shadowBlur = 10;
    ctx.beginPath();
    ctx.arc(sidebarX, sidebarStartY, w * 0.045, 0, Math.PI * 2);
    ctx.fillStyle = '#6366f1';
    ctx.fill();
    ctx.lineWidth = 3;
    ctx.strokeStyle = '#ffffff';
    ctx.stroke();

    ctx.font = `bold ${Math.round(w * 0.035)}px "Plus Jakarta Sans"`;
    ctx.fillStyle = '#ffffff';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('🎬', sidebarX, sidebarStartY);
    ctx.restore();

    // 2. Like Heart Icon + Counter
    const y2 = sidebarStartY + iconGap;
    ctx.save();
    ctx.font = `bold ${Math.round(w * 0.05)}px sans-serif`;
    ctx.fillStyle = '#ff2c55';
    ctx.textAlign = 'center';
    ctx.fillText('❤️', sidebarX, y2);
    ctx.font = `bold ${Math.round(w * 0.026)}px "Plus Jakarta Sans"`;
    ctx.fillStyle = '#ffffff';
    ctx.fillText('142.8K', sidebarX, y2 + (w * 0.045));
    ctx.restore();

    // 3. Comment Bubble Icon + Counter
    const y3 = sidebarStartY + iconGap * 2;
    ctx.save();
    ctx.font = `bold ${Math.round(w * 0.045)}px sans-serif`;
    ctx.fillStyle = '#ffffff';
    ctx.textAlign = 'center';
    ctx.fillText('💬', sidebarX, y3);
    ctx.font = `bold ${Math.round(w * 0.026)}px "Plus Jakarta Sans"`;
    ctx.fillText('2.4K', sidebarX, y3 + (w * 0.045));
    ctx.restore();

    // 4. Bookmark Ribbon Icon + Counter
    const y4 = sidebarStartY + iconGap * 3;
    ctx.save();
    ctx.font = `bold ${Math.round(w * 0.045)}px sans-serif`;
    ctx.fillStyle = '#ffee55';
    ctx.textAlign = 'center';
    ctx.fillText('🔖', sidebarX, y4);
    ctx.font = `bold ${Math.round(w * 0.026)}px "Plus Jakarta Sans"`;
    ctx.fillStyle = '#ffffff';
    ctx.fillText('18.9K', sidebarX, y4 + (w * 0.045));
    ctx.restore();

    // 5. Spinning Vinyl Disc Icon
    const y5 = sidebarStartY + iconGap * 4.1;
    ctx.save();
    ctx.translate(sidebarX, y5);
    ctx.rotate(curTime * 2);
    ctx.beginPath();
    ctx.arc(0, 0, w * 0.04, 0, Math.PI * 2);
    ctx.fillStyle = '#181818';
    ctx.fill();
    ctx.lineWidth = 4;
    ctx.strokeStyle = '#333333';
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(0, 0, w * 0.012, 0, Math.PI * 2);
    ctx.fillStyle = '#ff2c55';
    ctx.fill();
    ctx.restore();

    // Bottom Left Info: Author & Caption
    const infoLeftX = w * 0.05;
    const infoBottomY = h * 0.92;

    ctx.save();
    ctx.textAlign = 'left';

    ctx.font = `bold ${Math.round(w * 0.035)}px "Plus Jakarta Sans"`;
    ctx.fillStyle = '#ffffff';
    ctx.fillText('@reframestudio ✓', infoLeftX, infoBottomY - (h * 0.05));

    ctx.font = `400 ${Math.round(w * 0.028)}px "Plus Jakarta Sans"`;
    ctx.fillStyle = 'rgba(255, 255, 255, 0.95)';
    ctx.fillText('Reframed 16:9 landscape to true 9:16 vertical video #reframe #tiktok', infoLeftX, infoBottomY - (h * 0.025));

    ctx.font = `500 ${Math.round(w * 0.025)}px "JetBrains Mono"`;
    ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
    ctx.fillText('🎵 Original Sound - Reframe Studio 9:16', infoLeftX, infoBottomY);
    ctx.restore();

    ctx.restore();
  }

  stopLoop() {
    this.isRendering = false;
  }
}
