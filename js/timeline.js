/**
 * Reframe Studio 9:16 - Timeline & Keyframe Controller
 * Manages timeline scrubbing, playhead synchronization, keyframe CRUD operations,
 * and keyframe interpolation mode changes.
 */

class TimelineController {
  constructor(engine, timelineContainerEl, keyframeContainerEl, playheadEl) {
    this.engine = engine;
    this.container = timelineContainerEl;
    this.keyframeContainer = keyframeContainerEl;
    this.playhead = playheadEl;

    this.activeKeyframeIndex = null;
    this.initTimelineEvents();
  }

  initTimelineEvents() {
    let isScrubbing = false;

    const handleSeek = (e) => {
      const rect = this.container.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const percent = Math.max(0, Math.min(1, clickX / rect.width));
      const duration = this.engine.getDuration();
      if (duration > 0) {
        const targetTime = percent * duration;
        if (!this.engine.isDemoMode) {
          this.engine.video.currentTime = targetTime;
        }
      }
    };

    this.container.addEventListener('mousedown', (e) => {
      isScrubbing = true;
      handleSeek(e);
    });

    window.addEventListener('mousemove', (e) => {
      if (isScrubbing) {
        handleSeek(e);
      }
    });

    window.addEventListener('mouseup', () => {
      isScrubbing = false;
    });
  }

  updatePlayhead(currentTime, duration) {
    if (!duration || duration <= 0) return;
    const percent = (currentTime / duration) * 100;
    this.playhead.style.left = `${percent}%`;

    this.renderKeyframeMarkers(duration);
  }

  renderKeyframeMarkers(duration) {
    if (!duration || duration <= 0) return;

    this.keyframeContainer.innerHTML = '';
    const sorted = this.engine.keyframes;

    sorted.forEach((kf, idx) => {
      const marker = document.createElement('div');
      marker.className = 'keyframe-marker';
      const percent = (kf.time / duration) * 100;
      marker.style.left = `${percent}%`;

      // Active state check (if playhead is near keyframe)
      const curTime = this.engine.getCurrentTime();
      if (Math.abs(curTime - kf.time) < 0.2) {
        marker.classList.add('active');
        this.activeKeyframeIndex = idx;
      }

      marker.title = `Keyframe @ ${kf.time.toFixed(2)}s (X: ${kf.x.toFixed(2)}, ${kf.easing || 'easeInOut'})`;

      marker.addEventListener('click', (e) => {
        e.stopPropagation();
        if (!this.engine.isDemoMode) {
          this.engine.video.currentTime = kf.time;
        }
        this.engine.setCropNormalizedX(kf.x);
        this.activeKeyframeIndex = idx;
      });

      this.keyframeContainer.appendChild(marker);
    });
  }

  addOrUpdateKeyframeAtCurrentTime() {
    const curTime = this.engine.getCurrentTime();
    const curX = this.engine.cropNormalizedX;
    const easingSelect = document.getElementById('keyframeEasing');
    const easing = easingSelect ? easingSelect.value : 'easeInOut';

    // Check if keyframe already exists near current time (< 0.15s)
    const existingIndex = this.engine.keyframes.findIndex(k => Math.abs(k.time - curTime) < 0.15);

    if (existingIndex !== -1) {
      // Update existing keyframe
      this.engine.keyframes[existingIndex].x = curX;
      this.engine.keyframes[existingIndex].easing = easing;
    } else {
      // Add new keyframe
      this.engine.keyframes.push({
        time: parseFloat(curTime.toFixed(2)),
        x: parseFloat(curX.toFixed(3)),
        easing: easing
      });
      // Keep sorted by timestamp
      this.engine.keyframes.sort((a, b) => a.time - b.time);
    }

    this.renderKeyframeMarkers(this.engine.getDuration());
  }

  removeKeyframeAtCurrentTime() {
    const curTime = this.engine.getCurrentTime();
    const existingIndex = this.engine.keyframes.findIndex(k => Math.abs(k.time - curTime) < 0.25);

    if (existingIndex !== -1) {
      this.engine.keyframes.splice(existingIndex, 1);
      this.renderKeyframeMarkers(this.engine.getDuration());
    }
  }

  jumpToPrevKeyframe() {
    const curTime = this.engine.getCurrentTime();
    const prevList = this.engine.keyframes.filter(k => k.time < curTime - 0.1);
    if (prevList.length > 0) {
      const prevKf = prevList[prevList.length - 1];
      if (!this.engine.isDemoMode) {
        this.engine.video.currentTime = prevKf.time;
      }
      this.engine.setCropNormalizedX(prevKf.x);
    }
  }

  jumpToNextKeyframe() {
    const curTime = this.engine.getCurrentTime();
    const nextList = this.engine.keyframes.filter(k => k.time > curTime + 0.1);
    if (nextList.length > 0) {
      const nextKf = nextList[0];
      if (!this.engine.isDemoMode) {
        this.engine.video.currentTime = nextKf.time;
      }
      this.engine.setCropNormalizedX(nextKf.x);
    }
  }
}
