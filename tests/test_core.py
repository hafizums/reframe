import json
from pathlib import Path

import pytest

from reframe_core import (
    KEYFRAME_TIME_TOLERANCE,
    Keyframe,
    ReframeProject,
    add_or_update_keyframe_at,
    build_crop_x_expression,
    crop_geometry,
    default_resolution,
    find_keyframe_index_at_time,
    format_position_label,
    interpolate_position,
    marker_time_fraction,
)


def test_default_resolutions():
    assert default_resolution("9:16") == (1080, 1920)
    assert default_resolution("1:1") == (1080, 1080)
    assert default_resolution("4:5") == (1080, 1350)
    assert default_resolution("4:3") == (1440, 1080)


def test_horizontal_crop_geometry():
    left = crop_geometry(1920, 1080, "9:16", 0.0)
    center = crop_geometry(1920, 1080, "9:16", 0.5)
    right = crop_geometry(1920, 1080, "9:16", 1.0)

    assert left == (0, 0, 606, 1080)
    assert center[0] == (1920 - 606) // 2
    assert right[0] == 1920 - 606


def test_linear_interpolation_endpoints():
    frames = [Keyframe(0, 0, "linear"), Keyframe(10, 1, "linear")]
    assert interpolate_position(frames, 0) == 0
    assert interpolate_position(frames, 5) == 0.5
    assert interpolate_position(frames, 10) == 1


def test_multiple_keyframe_segments_use_correct_interval():
    frames = [
        Keyframe(0, 0.1, "linear"),
        Keyframe(3, 0.8, "linear"),
        Keyframe(6, 0.3, "linear"),
    ]
    assert interpolate_position(frames, 0) == 0.1
    assert interpolate_position(frames, 1.5) == pytest.approx(0.45)
    assert interpolate_position(frames, 3) == 0.8
    assert interpolate_position(frames, 4.5) == pytest.approx(0.55)
    assert interpolate_position(frames, 6) == 0.3


def test_hold_interpolation_jumps_exactly_on_next_keyframe():
    frames = [
        Keyframe(0, 0.2, "hold"),
        Keyframe(5, 0.8, "linear"),
        Keyframe(10, 1.0, "linear"),
    ]
    assert interpolate_position(frames, 4.9) == 0.2
    assert interpolate_position(frames, 5.0) == 0.8


def test_smooth_interpolation_is_bounded():
    frames = [Keyframe(0, 0, "easeInOut"), Keyframe(10, 1, "linear")]
    samples = [interpolate_position(frames, value) for value in range(11)]
    assert samples[0] == 0
    assert samples[-1] == 1
    assert all(0 <= value <= 1 for value in samples)
    assert samples == sorted(samples)


def test_ffmpeg_expression_contains_easing_and_hold_logic():
    smooth = build_crop_x_expression(
        [Keyframe(0, 0, "easeInOut"), Keyframe(5, 1, "linear")],
        1000,
    )
    hold = build_crop_x_expression(
        [Keyframe(0, 0.25, "hold"), Keyframe(5, 0.75, "linear")],
        1000,
    )
    assert "pow(" in smooth
    assert "250.0000" in hold
    assert "lt(t\\,5.000000)" in hold


def test_format_position_label_semantics():
    assert format_position_label(0.0) == "0%   Left"
    assert format_position_label(0.25) == "25%  Left 25%"
    assert format_position_label(0.5) == "50%  Center"
    assert format_position_label(0.75) == "75%  Right 75%"
    assert format_position_label(1.0) == "100% Right"


def test_add_or_update_keyframe_does_not_create_duplicate():
    keyframes = [Keyframe(3.0, 0.2, "linear")]
    add_or_update_keyframe_at(keyframes, 3.05, 0.8, "easeInOut", KEYFRAME_TIME_TOLERANCE)
    assert len(keyframes) == 1
    assert keyframes[0].x == 0.8
    assert keyframes[0].easing == "easeInOut"
    assert keyframes[0].time == 3.0


def test_keyframes_remain_sorted_after_add():
    keyframes = [Keyframe(0.0, 0.0, "linear"), Keyframe(6.0, 1.0, "linear")]
    add_or_update_keyframe_at(keyframes, 3.0, 0.5, "linear")
    times = [keyframe.time for keyframe in keyframes]
    assert times == sorted(times)


def test_find_keyframe_index_at_time():
    keyframes = [Keyframe(0.0, 0.0, "linear"), Keyframe(3.0, 0.5, "linear")]
    assert find_keyframe_index_at_time(keyframes, 3.04, KEYFRAME_TIME_TOLERANCE) == 1
    assert find_keyframe_index_at_time(keyframes, 1.0, KEYFRAME_TIME_TOLERANCE) is None


def test_marker_time_fraction_clamps_to_unit_interval():
    assert marker_time_fraction(-1.0, 6000) == 0.0
    assert marker_time_fraction(0.0, 6000) == 0.0
    assert marker_time_fraction(3.0, 6000) == 0.5
    assert marker_time_fraction(9.0, 6000) == 1.0
    assert marker_time_fraction(1.0, 0) == 0.0


def test_project_save_load_preserves_positions(tmp_path: Path):
    project = ReframeProject(
        video_path="sample.mp4",
        aspect="9:16",
        keyframes=[
            Keyframe(0.0, 0.1, "linear"),
            Keyframe(3.0, 0.8, "easeInOut"),
            Keyframe(6.0, 0.35, "hold"),
        ],
    )
    path = tmp_path / "project.json"
    project.save(path)

    loaded = ReframeProject.load(path)
    assert loaded.video_path == "sample.mp4"
    assert loaded.aspect == "9:16"
    assert [keyframe.x for keyframe in loaded.sorted_keyframes()] == [0.1, 0.8, 0.35]
    assert [keyframe.time for keyframe in loaded.sorted_keyframes()] == [0.0, 3.0, 6.0]

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["keyframes"][1]["x"] == 0.8
