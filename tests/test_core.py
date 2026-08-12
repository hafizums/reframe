from reframe_core import (
    Keyframe,
    build_crop_x_expression,
    crop_geometry,
    default_resolution,
    interpolate_position,
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


def test_linear_interpolation():
    frames = [Keyframe(0, 0, "linear"), Keyframe(10, 1, "linear")]
    assert interpolate_position(frames, 0) == 0
    assert interpolate_position(frames, 5) == 0.5
    assert interpolate_position(frames, 10) == 1


def test_hold_interpolation():
    frames = [Keyframe(0, 0.2, "hold"), Keyframe(5, 0.8, "linear")]
    assert interpolate_position(frames, 4.9) == 0.2
    assert interpolate_position(frames, 5) == 0.8


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
