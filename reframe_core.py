from __future__ import annotations

import json
import math
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

KEYFRAME_TIME_TOLERANCE = 0.15
KEYFRAME_REMOVE_TOLERANCE = 0.35


@dataclass(order=True)
class Keyframe:
    time: float
    x: float
    easing: str = "easeInOut"

    def normalized(self) -> "Keyframe":
        return Keyframe(
            time=max(0.0, float(self.time)),
            x=max(0.0, min(1.0, float(self.x))),
            easing=self.easing if self.easing in {"easeInOut", "linear", "hold"} else "easeInOut",
        )


@dataclass
class VideoInfo:
    width: int
    height: int
    duration: float
    fps: float


@dataclass
class ReframeProject:
    video_path: str = ""
    aspect: str = "9:16"
    keyframes: list[Keyframe] = field(default_factory=lambda: [Keyframe(0.0, 0.5, "easeInOut")])

    def sorted_keyframes(self) -> list[Keyframe]:
        return sorted((kf.normalized() for kf in self.keyframes), key=lambda item: item.time)

    def save(self, path: str | Path) -> None:
        payload = {
            "video_path": self.video_path,
            "aspect": self.aspect,
            "keyframes": [asdict(kf) for kf in self.sorted_keyframes()],
        }
        Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "ReframeProject":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        keyframes = [Keyframe(**item).normalized() for item in payload.get("keyframes", [])]
        if not keyframes:
            keyframes = [Keyframe(0.0, 0.5, "easeInOut")]
        return cls(
            video_path=str(payload.get("video_path", "")),
            aspect=str(payload.get("aspect", "9:16")),
            keyframes=keyframes,
        )


def parse_aspect(aspect: str) -> tuple[int, int]:
    try:
        w, h = aspect.split(":", 1)
        aw, ah = int(w), int(h)
        if aw <= 0 or ah <= 0:
            raise ValueError
        return aw, ah
    except (ValueError, AttributeError):
        return 9, 16


def default_resolution(aspect: str) -> tuple[int, int]:
    presets = {
        "9:16": (1080, 1920),
        "1:1": (1080, 1080),
        "4:5": (1080, 1350),
        "4:3": (1440, 1080),
    }
    if aspect in presets:
        return presets[aspect]
    aw, ah = parse_aspect(aspect)
    if aw <= ah:
        out_w = 1080
        out_h = round(out_w * ah / aw)
    else:
        out_h = 1080
        out_w = round(out_h * aw / ah)
    return make_even(out_w), make_even(out_h)


def make_even(value: int) -> int:
    value = max(2, int(value))
    return value if value % 2 == 0 else value - 1


def probe_video(path: str | Path) -> VideoInfo:
    input_path = str(path)
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate:format=duration",
        "-of",
        "json",
        input_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")

    payload = json.loads(result.stdout)
    streams = payload.get("streams") or []
    if not streams:
        raise RuntimeError("No video stream found")
    stream = streams[0]

    fps_text = stream.get("r_frame_rate", "30/1")
    if "/" in fps_text:
        num, den = fps_text.split("/", 1)
        fps = float(num) / max(float(den), 1e-9)
    else:
        fps = float(fps_text)

    return VideoInfo(
        width=int(stream["width"]),
        height=int(stream["height"]),
        duration=float((payload.get("format") or {}).get("duration") or 0.0),
        fps=fps,
    )


def find_keyframe_index_at_time(
    keyframes: list[Keyframe],
    time_seconds: float,
    tolerance: float = KEYFRAME_TIME_TOLERANCE,
) -> int | None:
    for index, keyframe in enumerate(keyframes):
        if abs(keyframe.time - time_seconds) < tolerance:
            return index
    return None


def format_position_label(normalized_x: float) -> str:
    pct = int(round(max(0.0, min(1.0, normalized_x)) * 100))
    if pct == 0:
        return "0%   Left"
    if pct == 50:
        return "50%  Center"
    if pct == 100:
        return "100% Right"
    if pct < 50:
        return f"{pct}%  Left {pct}%"
    return f"{pct}%  Right {pct}%"


def add_or_update_keyframe_at(
    keyframes: list[Keyframe],
    time_seconds: float,
    x: float,
    easing: str,
    tolerance: float = KEYFRAME_TIME_TOLERANCE,
) -> Keyframe:
    normalized = Keyframe(time_seconds, x, easing).normalized()
    existing_index = find_keyframe_index_at_time(keyframes, normalized.time, tolerance)
    if existing_index is not None:
        keyframes[existing_index].x = normalized.x
        keyframes[existing_index].easing = normalized.easing
        keyframe = keyframes[existing_index]
    else:
        keyframe = Keyframe(round(normalized.time, 3), round(normalized.x, 4), normalized.easing)
        keyframes.append(keyframe)
    keyframes.sort(key=lambda item: item.time)
    return keyframe


def marker_time_fraction(keyframe_time: float, duration_ms: int) -> float:
    if duration_ms <= 0:
        return 0.0
    return max(0.0, min(1.0, keyframe_time / (duration_ms / 1000)))


def crop_geometry(src_w: int, src_h: int, aspect: str, normalized_x: float) -> tuple[int, int, int, int]:
    aw, ah = parse_aspect(aspect)
    ratio = aw / ah

    crop_h = src_h
    crop_w = int(math.floor(crop_h * ratio))
    if crop_w > src_w:
        crop_w = src_w
        crop_h = int(math.floor(crop_w / ratio))

    crop_w = make_even(crop_w)
    crop_h = make_even(crop_h)
    max_x = max(0, src_w - crop_w)
    x = int(round(max(0.0, min(1.0, normalized_x)) * max_x))
    y = max(0, (src_h - crop_h) // 2)
    return x, y, crop_w, crop_h


def interpolate_position(keyframes: Iterable[Keyframe], time_seconds: float) -> float:
    frames = sorted((kf.normalized() for kf in keyframes), key=lambda item: item.time)
    if not frames:
        return 0.5
    if len(frames) == 1 or time_seconds <= frames[0].time:
        return frames[0].x
    if time_seconds >= frames[-1].time:
        return frames[-1].x

    for left, right in zip(frames, frames[1:]):
        if left.time <= time_seconds < right.time:
            duration = right.time - left.time
            if duration <= 0:
                return left.x
            t = (time_seconds - left.time) / duration
            if left.easing == "hold":
                t = 0.0
            elif left.easing == "easeInOut":
                t = 2 * t * t if t < 0.5 else 1 - ((-2 * t + 2) ** 2) / 2
            return left.x + (right.x - left.x) * t
    return frames[-1].x


def build_crop_x_expression(keyframes: Iterable[Keyframe], max_offset: int) -> str:
    frames = sorted((kf.normalized() for kf in keyframes), key=lambda item: item.time)
    if not frames:
        return f"{max_offset / 2:.4f}"
    if len(frames) == 1:
        return f"{frames[0].x * max_offset:.4f}"

    first_x = frames[0].x * max_offset
    expression = f"{frames[-1].x * max_offset:.4f}"

    for left, right in reversed(list(zip(frames, frames[1:]))):
        dt = right.time - left.time
        if dt <= 0:
            continue
        x1 = left.x * max_offset
        x2 = right.x * max_offset
        p = f"((t-{left.time:.6f})/{dt:.6f})"

        if left.easing == "hold":
            segment = f"{x1:.4f}"
        elif left.easing == "easeInOut":
            eased = f"if(lt({p}\\,0.5)\\,2*{p}*{p}\\,1-pow(-2*{p}+2\\,2)/2)"
            segment = f"({x1:.4f}+({x2:.4f}-{x1:.4f})*{eased})"
        else:
            segment = f"({x1:.4f}+({x2:.4f}-{x1:.4f})*{p})"

        expression = f"if(lt(t\\,{right.time:.6f})\\,{segment}\\,{expression})"

    return f"if(lt(t\\,{frames[0].time:.6f})\\,{first_x:.4f}\\,{expression})"


def build_ffmpeg_command(
    input_path: str | Path,
    output_path: str | Path,
    video_info: VideoInfo,
    keyframes: Iterable[Keyframe],
    aspect: str = "9:16",
    resolution: tuple[int, int] | None = None,
    fps: float | None = None,
) -> list[str]:
    out_w, out_h = resolution or default_resolution(aspect)
    out_w, out_h = make_even(out_w), make_even(out_h)

    _, y, crop_w, crop_h = crop_geometry(video_info.width, video_info.height, aspect, 0.0)
    max_offset = max(0, video_info.width - crop_w)
    x_expr = build_crop_x_expression(keyframes, max_offset)
    target_fps = fps or video_info.fps

    vf = (
        f"crop={crop_w}:{crop_h}:'{x_expr}':{y},"
        f"scale={out_w}:{out_h}:flags=lanczos"
    )

    return [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-r",
        f"{target_fps:.6f}",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
