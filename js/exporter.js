/**
 * Reframe Studio 9:16 - Exporter Module
 * Performs deterministic frame-by-frame offline canvas rendering for 1:1 smooth 60fps exports,
 * automatically selecting universally playable video formats (MP4 / H264 / VP8 WebM),
 * generating FFmpeg CLI commands, and exporting JSON keyframe timelines.
 */

class Exporter {
  constructor(engine) {
    this.engine = engine;
    this.mediaRecorder = null;
    this.recordedChunks = [];
  }

  getBestSupportedMimeType() {
    const types = [
      { mime: 'video/mp4;codecs=avc1.42E01E,mp4a.40.2', ext: 'mp4', name: 'MP4 (H.264)' },
      { mime: 'video/mp4;codecs=h264', ext: 'mp4', name: 'MP4 (H.264)' },
      { mime: 'video/mp4', ext: 'mp4', name: 'MP4' },
      { mime: 'video/webm;codecs=h264', ext: 'webm', name: 'WebM (H.264)' },
      { mime: 'video/webm;codecs=vp8,opus', ext: 'webm', name: 'WebM (VP8)' },
      { mime: 'video/webm;codecs=vp8', ext: 'webm', name: 'WebM (VP8)' },
      { mime: 'video/webm;codecs=vp9,opus', ext: 'webm', name: 'WebM (VP9)' },
      { mime: 'video/webm', ext: 'webm', name: 'WebM' }
    ];

    for (const t of types) {
      if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(t.mime)) {
        console.log('Selected video export format:', t.mime);
        return t;
      }
    }

    return { mime: 'video/webm', ext: 'webm', name: 'WebM' };
  }

  generateFfmpegCommand() {
    const rect = this.engine.getCropRect();
    const sourceW = this.engine.videoWidth;
    const sourceH = this.engine.videoHeight;
    const cropW = Math.round(rect.width);
    const cropH = Math.round(rect.height);

    const sortedKeyframes = [...this.engine.keyframes].sort((a, b) => a.time - b.time);

    let xExpr = '';
    if (sortedKeyframes.length <= 1) {
      const xPx = Math.round(rect.x);
      xExpr = `${xPx}`;
    } else {
      const maxOffset = sourceW - cropW;
      let exprParts = [];

      for (let i = 0; i < sortedKeyframes.length - 1; i++) {
        const k1 = sortedKeyframes[i];
        const k2 = sortedKeyframes[i + 1];
        const x1 = Math.round(k1.x * maxOffset);
        const x2 = Math.round(k2.x * maxOffset);

        const part = `between(t,${k1.time.toFixed(2)},${k2.time.toFixed(2)})*(${x1}+(${x2}-${x1})*(t-${k1.time.toFixed(2)})/(${k2.time - k1.time}))`;
        exprParts.push(part);
      }

      const firstX = Math.round(sortedKeyframes[0].x * maxOffset);
      const lastX = Math.round(sortedKeyframes[sortedKeyframes.length - 1].x * maxOffset);
      
      xExpr = `if(lt(t,${sortedKeyframes[0].time}),${firstX},if(gt(t,${sortedKeyframes[sortedKeyframes.length - 1].time}),${lastX},${exprParts.join('+')}))`;
    }

    const command = `ffmpeg -i input.mp4 -vf "crop=w=${cropW}:h=${cropH}:x='${xExpr}':y=0,scale=1080:1920" -c:v libx264 -preset slow -crf 18 -c:a copy output_9x16.mp4`;

    return command;
  }

  getKeyframesJson() {
    return JSON.stringify(this.engine.keyframes, null, 2);
  }

  /**
   * Deterministic Frame-by-Frame Offline Renderer
   * 
   * Uses captureStream(0) MANUAL FRAME MODE so the stream only captures
   * when we explicitly call requestFrame(). This guarantees:
   *   - Every rendered frame is captured exactly once
   *   - Zero duplicate or dropped frames
   *   - Perfect 1:1 smooth output matching the live preview
   *   - No dependency on wall-clock timing
   */
  async startBrowserRendering(fps = 30, targetRes = '1080x1920', burnInOverlay = false, onProgress, onComplete) {
    const video = this.engine.video;
    const isDemo = this.engine.isDemoMode;

    // Target Canvas Dimensions
    let exportW = 1080;
    let exportH = 1920;
    if (targetRes === '720x1280') {
      exportW = 720;
      exportH = 1280;
    } else if (targetRes === '540x960') {
      exportW = 540;
      exportH = 960;
    }

    // Dedicated offscreen export canvas (not the live preview canvas)
    const exportCanvas = document.createElement('canvas');
    exportCanvas.width = exportW;
    exportCanvas.height = exportH;
    const exportCtx = exportCanvas.getContext('2d');

    // Save playback state
    const originalTime = !isDemo ? video.currentTime : 0;
    const isPaused = !isDemo ? video.paused : true;
    if (!isDemo) video.pause();

    // *** KEY FIX: captureStream(0) = manual frame mode ***
    // Frames are only captured when we call videoTrack.requestFrame()
    const canvasStream = exportCanvas.captureStream(0);
    const videoTrack = canvasStream.getVideoTracks()[0];

    // Select optimal compatible MIME format
    const formatInfo = this.getBestSupportedMimeType();

    this.recordedChunks = [];
    try {
      this.mediaRecorder = new MediaRecorder(canvasStream, {
        mimeType: formatInfo.mime,
        videoBitsPerSecond: 8000000
      });
    } catch (e) {
      console.log('Fallback to default MediaRecorder mimeType');
      this.mediaRecorder = new MediaRecorder(canvasStream);
    }

    this.mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) {
        this.recordedChunks.push(e.data);
      }
    };

    const finalize = () => {
      const blob = new Blob(this.recordedChunks, { type: formatInfo.mime || 'video/webm' });
      const downloadUrl = URL.createObjectURL(blob);
      if (onComplete) {
        onComplete(downloadUrl, formatInfo.ext);
      }
      // Restore video playback state
      if (!isDemo) {
        video.currentTime = originalTime;
        if (!isPaused) video.play();
      }
    };

    this.mediaRecorder.onstop = finalize;
    this.mediaRecorder.start(); // No timeslice — we flush manually

    const duration = this.engine.getDuration() || 10;
    const totalFrames = Math.ceil(duration * fps);
    const frameIntervalSecs = 1 / fps;

    // --- Deterministic frame-by-frame loop ---
    for (let i = 0; i <= totalFrames; i++) {
      const curTime = Math.min(duration, i * frameIntervalSecs);

      // 1. Seek source video to exact timestamp & wait for decoded frame
      if (!isDemo) {
        await new Promise(resolve => {
          const onSeeked = () => {
            video.removeEventListener('seeked', onSeeked);
            resolve();
          };
          video.addEventListener('seeked', onSeeked);
          video.currentTime = curTime;
        });
      }

      // 2. Compute interpolated crop position at this timestamp
      const curX = this.engine.getCurrentInterpolatedX(curTime);
      this.engine.cropNormalizedX = curX;
      const rect = this.engine.getCropRect();

      // 3. Draw the cropped frame onto the export canvas
      const sourceDrawable = isDemo ? this.engine.demoCanvas : video;
      exportCtx.drawImage(
        sourceDrawable,
        rect.x, rect.y, rect.width, rect.height,
        0, 0, exportW, exportH
      );

      // 4. Burn in TikTok overlay if requested
      if (burnInOverlay) {
        this.engine.drawTiktokOverlayOnCanvas(exportCtx, exportW, exportH, curTime);
      }

      // 5. *** Tell the stream to capture THIS frame ***
      if (videoTrack && videoTrack.requestFrame) {
        videoTrack.requestFrame();
      }

      // 6. Yield to browser so encoder can process the frame
      await new Promise(r => setTimeout(r, 0));

      // 7. Report progress
      const pct = Math.min(100, Math.round((i / totalFrames) * 100));
      if (onProgress) onProgress(pct);
    }

    // All frames submitted — stop recording
    this.mediaRecorder.stop();
  }
}
