#!/usr/bin/env python3
"""
Reframe Studio 9:16 — FFmpeg Export Script
Produces perfectly smooth 9:16 vertical video from 16:9 source using FFmpeg.

Usage:
    python export.py <input_video> <keyframes.json> [output.mp4]
    python export.py input.mp4 keyframes.json                       # → output_9x16.mp4
    python export.py input.mp4 keyframes.json my_tiktok.mp4         # → my_tiktok.mp4
    python export.py input.mp4 keyframes.json -r 720x1280 -f 60    # HD @ 60fps

Options:
    -r, --resolution   Output resolution WxH (default: 1080x1920)
    -f, --fps          Output framerate (default: source fps)
    -a, --aspect       Crop aspect ratio w:h (default: 9:16)
"""

import json
import subprocess
import sys
import os
import math


def get_video_info(input_path):
    """Get video dimensions and duration using ffprobe."""
    cmd = [
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,duration,r_frame_rate',
        '-of', 'json',
        input_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ ffprobe failed: {result.stderr}")
        sys.exit(1)

    info = json.loads(result.stdout)
    stream = info['streams'][0]

    width = int(stream['width'])
    height = int(stream['height'])

    # Duration may be missing from stream, try container
    duration = float(stream.get('duration', 0))
    if duration == 0:
        cmd2 = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'json',
            input_path
        ]
        r2 = subprocess.run(cmd2, capture_output=True, text=True)
        if r2.returncode == 0:
            fmt = json.loads(r2.stdout)
            duration = float(fmt.get('format', {}).get('duration', 0))

    # Parse framerate fraction (e.g. "30000/1001")
    fps_str = stream.get('r_frame_rate', '30/1')
    if '/' in fps_str:
        num, den = fps_str.split('/')
        source_fps = float(num) / float(den)
    else:
        source_fps = float(fps_str)

    return width, height, duration, source_fps


def build_crop_x_expr(keyframes, src_w, crop_w):
    """
    Build an FFmpeg expression for the crop x-position that replicates
    the JavaScript engine's getCurrentInterpolatedX() with easing support.

    FFmpeg expression variables: t = timestamp in seconds
    """
    max_offset = max(0, src_w - crop_w)

    if not keyframes or len(keyframes) == 0:
        # Default center
        return str(int(max_offset / 2))

    # Sort by time
    kfs = sorted(keyframes, key=lambda k: k['time'])

    if len(kfs) == 1:
        return str(int(kfs[0]['x'] * max_offset))

    # Build piecewise expression using nested if()
    # We construct from the last segment backwards using nested if/else

    first_x = kfs[0]['x'] * max_offset
    last_x = kfs[-1]['x'] * max_offset

    # Start with the "after last keyframe" value
    expr = f"{last_x:.4f}"

    # Build segments from last to first
    for i in range(len(kfs) - 2, -1, -1):
        k1 = kfs[i]
        k2 = kfs[i + 1]
        x1 = k1['x'] * max_offset
        x2 = k2['x'] * max_offset
        t1 = k1['time']
        t2 = k2['time']
        dt = t2 - t1

        if dt <= 0:
            continue

        easing = k1.get('easing', 'linear')

        # Normalized progress within segment: p = (t - t1) / dt
        p_expr = f"((t-{t1:.6f})/{dt:.6f})"

        if easing == 'hold':
            # Jump cut: stay at k1.x until k2.time
            seg_expr = f"{x1:.4f}"
        elif easing == 'easeInOut':
            # Smooth cubic: p < 0.5 ? 2*p*p : 1 - pow(-2*p+2, 2)/2
            # In FFmpeg expr: if(lt(P,0.5), 2*P*P, 1-pow(-2*P+2,2)/2)
            seg_expr = (
                f"({x1:.4f}+({x2:.4f}-{x1:.4f})*"
                f"if(lt({p_expr}\\,0.5)\\,"
                f"2*{p_expr}*{p_expr}\\,"
                f"1-pow(-2*{p_expr}+2\\,2)/2))"
            )
        else:
            # Linear interpolation: x1 + (x2 - x1) * p
            seg_expr = f"({x1:.4f}+({x2:.4f}-{x1:.4f})*{p_expr})"

        # Wrap: if t >= t1 AND t < t2 → this segment, else → previous expr
        expr = f"if(between(t\\,{t1:.6f}\\,{t2:.6f})\\,{seg_expr}\\,{expr})"

    # Wrap: if t < first keyframe time → first_x, else → built expr
    expr = f"if(lt(t\\,{kfs[0]['time']:.6f})\\,{first_x:.4f}\\,{expr})"

    return expr


def export_video(input_path, keyframes_path, output_path='output_9x16.mp4',
                 out_w=1080, out_h=1920, target_fps=None, aspect_w=9, aspect_h=16):
    """Export reframed vertical video using FFmpeg."""

    # Validate inputs
    if not os.path.exists(input_path):
        print(f"❌ Input video not found: {input_path}")
        sys.exit(1)
    if not os.path.exists(keyframes_path):
        print(f"❌ Keyframes JSON not found: {keyframes_path}")
        sys.exit(1)

    # Load keyframes
    with open(keyframes_path, 'r') as f:
        keyframes = json.load(f)

    # Get source video info
    src_w, src_h, duration, source_fps = get_video_info(input_path)
    fps = target_fps or source_fps

    print(f"┌─────────────────────────────────────────────")
    print(f"│  Reframe Studio 9:16 — FFmpeg Export")
    print(f"├─────────────────────────────────────────────")
    print(f"│  Source     : {src_w}×{src_h} @ {source_fps:.2f}fps, {duration:.2f}s")
    print(f"│  Output     : {out_w}×{out_h} @ {fps:.2f}fps")
    print(f"│  Keyframes  : {len(keyframes)}")
    print(f"│  Crop Aspect: {aspect_w}:{aspect_h}")
    print(f"│  Output File: {output_path}")
    print(f"└─────────────────────────────────────────────")

    # Calculate crop dimensions
    aspect_ratio = aspect_w / aspect_h
    crop_h = src_h
    crop_w = int(math.floor(src_h * aspect_ratio))

    # Clamp if wider than source
    if crop_w > src_w:
        crop_w = src_w
        crop_h = int(math.floor(src_w / aspect_ratio))

    # Ensure even dimensions (required by most codecs)
    crop_w = crop_w - (crop_w % 2)
    crop_h = crop_h - (crop_h % 2)
    out_w = out_w - (out_w % 2)
    out_h = out_h - (out_h % 2)

    print(f"\n  Crop region: {crop_w}×{crop_h} from {src_w}×{src_h}")

    # Build x-position expression
    x_expr = build_crop_x_expr(keyframes, src_w, crop_w)

    # Build filter chain
    vf = f"crop={crop_w}:{crop_h}:'{x_expr}':0,scale={out_w}:{out_h}:flags=lanczos"

    # Build FFmpeg command
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-vf', vf,
        '-c:v', 'libx264',
        '-preset', 'slow',
        '-crf', '18',
        '-pix_fmt', 'yuv420p',
        '-r', str(fps),
        '-c:a', 'aac',
        '-b:a', '192k',
        '-movflags', '+faststart',
        output_path
    ]

    print(f"\n  Running FFmpeg...\n")

    process = subprocess.run(cmd)

    if process.returncode == 0:
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"\n  ✅ Export complete: {output_path} ({size_mb:.1f} MB)")
    else:
        print(f"\n  ❌ FFmpeg failed with return code {process.returncode}")
        print(f"  Make sure FFmpeg is installed: https://ffmpeg.org/download.html")
        sys.exit(1)


def print_usage():
    print(__doc__)
    sys.exit(0)


if __name__ == '__main__':
    if len(sys.argv) < 3 or '--help' in sys.argv or '-h' in sys.argv:
        print_usage()

    input_video = sys.argv[1]
    keyframes_json = sys.argv[2]

    # Default values
    output = 'output_9x16.mp4'
    resolution = '1080x1920'
    fps = None
    aspect = '9:16'

    # Parse positional output arg
    i = 3
    if i < len(sys.argv) and not sys.argv[i].startswith('-'):
        output = sys.argv[i]
        i += 1

    # Parse flags
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg in ('-r', '--resolution') and i + 1 < len(sys.argv):
            resolution = sys.argv[i + 1]
            i += 2
        elif arg in ('-f', '--fps') and i + 1 < len(sys.argv):
            fps = int(sys.argv[i + 1])
            i += 2
        elif arg in ('-a', '--aspect') and i + 1 < len(sys.argv):
            aspect = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    # Parse resolution
    if 'x' in resolution:
        out_w, out_h = map(int, resolution.split('x'))
    else:
        out_w, out_h = 1080, 1920

    # Parse aspect
    if ':' in aspect:
        aw, ah = map(int, aspect.split(':'))
    else:
        aw, ah = 9, 16

    export_video(input_video, keyframes_json, output, out_w, out_h, fps, aw, ah)
