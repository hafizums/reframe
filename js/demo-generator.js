/**
 * Reframe Studio 9:16 - Demo Video Generator
 * Generates an interactive animated 16:9 canvas video with dynamic audio track
 * so users can immediately test crop selection and keyframing without uploading a file.
 */

window.DemoGenerator = {
  createDemoStream(width = 1280, height = 720) {
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');

    let startTime = Date.now();

    // Subject position parameters for dynamic movement
    function renderFrame() {
      const elapsed = (Date.now() - startTime) / 1000;

      // Dark background gradient
      const bgGrad = ctx.createLinearGradient(0, 0, width, height);
      bgGrad.addColorStop(0, '#0f172a');
      bgGrad.addColorStop(0.5, '#1e1b4b');
      bgGrad.addColorStop(1, '#090d16');
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, width, height);

      // Grid background pattern
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
      ctx.lineWidth = 1;
      const gridSize = 40;
      for (let x = 0; x < width; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
      for (let y = 0; y < height; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      // Title header in video
      ctx.font = '700 24px "Plus Jakarta Sans", sans-serif';
      ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
      ctx.fillText('DEMO LANDSCAPE VIDEO (16:9)', 40, 50);

      // Speaker 1 (Left side, time 0s - 4s active)
      const speaker1X = width * 0.25;
      const speaker1Y = height * 0.55;
      const talk1 = Math.sin(elapsed * 8) > 0;
      
      // Draw Speaker 1 (Cyan avatar)
      ctx.save();
      ctx.shadowColor = '#06b6d4';
      ctx.shadowBlur = talk1 ? 25 : 5;
      ctx.fillStyle = talk1 ? '#06b6d4' : '#1e293b';
      ctx.beginPath();
      ctx.arc(speaker1X, speaker1Y - 60, 45, 0, Math.PI * 2); // head
      ctx.fill();
      ctx.fillStyle = '#0e7490';
      ctx.beginPath();
      ctx.ellipse(speaker1X, speaker1Y + 70, 70, 90, 0, Math.PI, Math.PI * 2); // body
      ctx.fill();
      ctx.restore();

      ctx.font = '600 18px "Plus Jakarta Sans", sans-serif';
      ctx.fillStyle = '#38bdf8';
      ctx.fillText('Speaker A (Left)', speaker1X - 60, speaker1Y + 180);

      // Speaker 2 (Right side, time 4s - 8s active)
      const speaker2X = width * 0.75;
      const speaker2Y = height * 0.55;
      const talk2 = Math.sin(elapsed * 6) < 0;

      // Draw Speaker 2 (Purple avatar)
      ctx.save();
      ctx.shadowColor = '#a855f7';
      ctx.shadowBlur = talk2 ? 25 : 5;
      ctx.fillStyle = talk2 ? '#a855f7' : '#1e293b';
      ctx.beginPath();
      ctx.arc(speaker2X, speaker2Y - 60, 45, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#7e22ce';
      ctx.beginPath();
      ctx.ellipse(speaker2X, speaker2Y + 70, 70, 90, 0, Math.PI, Math.PI * 2);
      ctx.fill();
      ctx.restore();

      ctx.font = '600 18px "Plus Jakarta Sans", sans-serif';
      ctx.fillStyle = '#c084fc';
      ctx.fillText('Speaker B (Right)', speaker2X - 65, speaker2Y + 180);

      // Moving Subject (Ball panning left and right across the frame)
      const moveProgress = (Math.sin(elapsed * 1.2) + 1) / 2; // 0 to 1 back and forth
      const ballX = width * 0.15 + moveProgress * (width * 0.7);
      const ballY = height * 0.3 + Math.abs(Math.sin(elapsed * 3)) * -60;

      // Draw Ball / Focus Target
      ctx.save();
      ctx.shadowColor = '#f43f5e';
      ctx.shadowBlur = 30;
      ctx.fillStyle = '#f43f5e';
      ctx.beginPath();
      ctx.arc(ballX, ballY, 28, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = '#ffffff';
      ctx.font = '800 14px "JetBrains Mono", monospace';
      ctx.fillText('TARGET', ballX - 25, ballY - 35);
      ctx.restore();

      // Draw Animated Audio Waveforms at bottom
      ctx.fillStyle = 'rgba(99, 102, 241, 0.5)';
      const bars = 30;
      const barW = width / bars;
      for (let i = 0; i < bars; i++) {
        const barH = 10 + Math.sin(elapsed * 10 + i) * 35 + Math.cos(elapsed * 5 + i * 2) * 20;
        ctx.fillRect(i * barW + 2, height - barH, barW - 4, barH);
      }

      // Timecode watermark in demo
      const secs = (elapsed % 60).toFixed(2);
      ctx.font = '500 16px "JetBrains Mono", monospace';
      ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
      ctx.fillText(`TIME: ${secs}s | Move keyframe pan slider to test reframing!`, 40, height - 45);

      requestAnimationFrame(renderFrame);
    }

    renderFrame();

    return canvas;
  }
};
