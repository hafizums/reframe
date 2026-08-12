from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from reframe_app import ReframeWindow
from reframe_core import (
    KEYFRAME_TIME_TOLERANCE,
    Keyframe,
    ReframeProject,
    VideoInfo,
    build_crop_x_expression,
    build_ffmpeg_command,
    crop_geometry,
    default_resolution,
    find_keyframe_index_at_time,
    format_position_label,
    marker_time_fraction,
    probe_video,
)

from conftest import (
    add_position_keyframe,
    create_acceptance_keyframes,
    set_linear_easing,
    set_playhead,
    sorted_keyframe_triples,
)


def test_add_three_position_keyframes_from_ui(window, playhead):
    set_linear_easing(window)
    create_acceptance_keyframes(window, playhead)

    triples = sorted_keyframe_triples(window.project)
    assert len(triples) == 3
    assert triples[0][0] == pytest.approx(0.0)
    assert triples[0][1] == pytest.approx(0.10)
    assert triples[1][0] == pytest.approx(3.0)
    assert triples[1][1] == pytest.approx(0.80)
    assert triples[2][0] == pytest.approx(6.0)
    assert triples[2][1] == pytest.approx(0.35)


def test_keyframe_timeline_has_three_markers(window, playhead):
    create_acceptance_keyframes(window, playhead)
    assert window.timeline_widget.marker_count == 3
    assert len(window.timeline_widget.marker_layer.keyframes) == 3


def test_marker_fractions_for_six_second_timeline():
    duration_ms = 6000
    assert marker_time_fraction(0.0, duration_ms) == pytest.approx(0.0)
    assert marker_time_fraction(3.0, duration_ms) == pytest.approx(0.5)
    assert marker_time_fraction(6.0, duration_ms) == pytest.approx(1.0)


def test_timeline_widget_exposes_marker_fractions(window, playhead):
    create_acceptance_keyframes(window, playhead)
    window._refresh_timeline_markers()
    assert window.timeline_widget.marker_fractions() == pytest.approx([0.0, 0.5, 1.0])


def test_clicking_marker_selects_keyframe(window, playhead):
    set_linear_easing(window)
    create_acceptance_keyframes(window, playhead)

    window._on_timeline_marker_clicked(1)

    assert window.player.position() == pytest.approx(3000, abs=1)
    assert window.current_x == pytest.approx(0.80)
    assert window.easing_combo.currentData() == "linear"
    assert window.key_table.currentRow() == 1
    assert window.timeline_widget.active_marker_index == 1


def test_add_button_changes_to_update_near_keyframe(window, playhead):
    add_position_keyframe(window, playhead, 3000, 0.80)

    set_playhead(window, playhead, 3000)
    window._update_keyframe_ui_state(3.0)
    assert window.add_key_btn.text() == "◆ Update Position Keyframe"

    set_playhead(window, playhead, 4000)
    window._update_keyframe_ui_state(4.0)
    assert window.add_key_btn.text() == "◆ Add Position Keyframe"


def test_add_button_respects_keyframe_tolerance(window, playhead):
    add_position_keyframe(window, playhead, 3000, 0.80)

    inside = 3.0 + KEYFRAME_TIME_TOLERANCE * 0.5
    outside = 3.0 + KEYFRAME_TIME_TOLERANCE + 0.05

    window._update_keyframe_ui_state(inside)
    assert window.add_key_btn.text() == "◆ Update Position Keyframe"

    window._update_keyframe_ui_state(outside)
    assert window.add_key_btn.text() == "◆ Add Position Keyframe"


def test_crop_move_does_not_mutate_keyframe_without_update(window, playhead):
    add_position_keyframe(window, playhead, 3000, 0.80)

    set_playhead(window, playhead, 3000)
    window._set_crop_x(0.20)

    assert window.project.keyframes[0].x == pytest.approx(0.80)

    window._on_position_changed(1000)
    window._on_position_changed(3000)

    assert window.project.keyframes[0].x == pytest.approx(0.80)
    assert window.current_x == pytest.approx(0.80)


def test_update_keyframe_changes_position_without_duplicate(window, playhead):
    add_position_keyframe(window, playhead, 3000, 0.80)

    set_playhead(window, playhead, 3000)
    window._set_crop_x(0.20)
    window.add_or_update_keyframe()

    assert len(window.project.keyframes) == 1
    assert window.project.keyframes[0].time == pytest.approx(3.0)
    assert window.project.keyframes[0].x == pytest.approx(0.20)


def test_keyframe_table_displays_position_labels(window, playhead):
    set_linear_easing(window)
    add_position_keyframe(window, playhead, 0, 0.0)
    add_position_keyframe(window, playhead, 3000, 0.5)
    add_position_keyframe(window, playhead, 6000, 1.0)

    assert window.key_table.item(0, 1).text() == format_position_label(0.0)
    assert window.key_table.item(1, 1).text() == format_position_label(0.5)
    assert window.key_table.item(2, 1).text() == format_position_label(1.0)
    assert "Left" in window.key_table.item(0, 1).text()
    assert "Center" in window.key_table.item(1, 1).text()
    assert "Right" in window.key_table.item(2, 1).text()


def test_active_table_row_follows_playhead(window, playhead):
    add_position_keyframe(window, playhead, 3000, 0.80)

    window._update_keyframe_ui_state(3.0)
    assert window.key_table.currentRow() == 0
    assert window.timeline_widget.active_marker_index == 0

    window._update_keyframe_ui_state(4.0)
    assert not window.key_table.selectionModel().hasSelection()
    assert window.timeline_widget.active_marker_index is None


def test_scrubbing_updates_interpolated_crop_position(window, playhead):
    set_linear_easing(window)
    add_position_keyframe(window, playhead, 0, 0.0)
    add_position_keyframe(window, playhead, 10000, 1.0)

    window._on_position_changed(5000)
    assert window.current_x == pytest.approx(0.5)

    window._on_position_changed(2500)
    assert window.current_x == pytest.approx(0.25)

    window._on_position_changed(7500)
    assert window.current_x == pytest.approx(0.75)


def test_multi_segment_ui_interpolation(window, playhead):
    set_linear_easing(window)
    create_acceptance_keyframes(window, playhead)

    expectations = [
        (0, 0.10),
        (1500, 0.45),
        (3000, 0.80),
        (4500, 0.575),
        (6000, 0.35),
    ]
    for position_ms, expected_x in expectations:
        window._on_position_changed(position_ms)
        assert window.current_x == pytest.approx(expected_x)


def test_delete_keyframe_refreshes_timeline_and_table(window, playhead):
    set_linear_easing(window)
    create_acceptance_keyframes(window, playhead)

    set_playhead(window, playhead, 3000)
    window.remove_keyframe()

    assert len(window.project.keyframes) == 2
    assert window.timeline_widget.marker_count == 2
    assert window.key_table.rowCount() == 2
    assert find_keyframe_index_at_time(window.project.keyframes, 3.0) is None

    window._on_position_changed(4500)
    assert window.current_x == pytest.approx(0.2875)


def test_delete_last_keyframe_leaves_valid_fallback(window, playhead):
    add_position_keyframe(window, playhead, 3000, 0.80)

    set_playhead(window, playhead, 3000)
    window._set_crop_x(0.25)
    window.remove_keyframe()

    assert len(window.project.keyframes) == 1
    assert window.project.keyframes[0].time == pytest.approx(0.0)
    assert window.project.keyframes[0].x == pytest.approx(0.25)
    assert window.timeline_widget.marker_count == 1
    assert window.key_table.rowCount() == 1


def test_project_reload_restores_marker_state(qtbot, tmp_path: Path, playhead):
    win1 = ReframeWindow()
    qtbot.addWidget(win1)
    win1.video_info = VideoInfo(width=640, height=360, duration=6.0, fps=30.0)
    win1.project = ReframeProject(video_path="synthetic.mp4", aspect="9:16", keyframes=[])
    win1.timeline.setRange(0, 6000)
    state, get_position, set_position = playhead
    win1.player.position = get_position
    win1.player.setPosition = set_position
    win1.player.duration = lambda: 6000
    win1.show()
    qtbot.waitExposed(win1)

    set_linear_easing(win1)
    create_acceptance_keyframes(win1, playhead)

    project_path = tmp_path / "acceptance.json"
    win1.project.aspect = "9:16"
    win1.project.save(project_path)

    win2 = ReframeWindow()
    qtbot.addWidget(win2)
    win2.video_info = VideoInfo(width=640, height=360, duration=6.0, fps=30.0)
    win2.player.duration = lambda: 6000
    win2.timeline.setRange(0, 6000)
    win2.project = ReframeProject.load(project_path)
    win2.aspect_combo.setCurrentText(win2.project.aspect)
    win2._refresh_keyframe_table()
    win2.show()
    qtbot.waitExposed(win2)

    assert len(win2.project.sorted_keyframes()) == 3
    assert [kf.x for kf in win2.project.sorted_keyframes()] == pytest.approx([0.10, 0.80, 0.35])
    assert [kf.time for kf in win2.project.sorted_keyframes()] == pytest.approx([0.0, 3.0, 6.0])
    assert [kf.easing for kf in win2.project.sorted_keyframes()] == ["linear", "linear", "linear"]
    assert win2.timeline_widget.marker_count == 3
    assert win2.key_table.rowCount() == 3
    assert win2.key_table.item(1, 1).text() == format_position_label(0.80)


def test_ffmpeg_expression_uses_acceptance_keyframe_boundaries():
    keyframes = [
        Keyframe(0.0, 0.10, "linear"),
        Keyframe(3.0, 0.80, "linear"),
        Keyframe(6.0, 0.35, "linear"),
    ]
    _, _, crop_w, _ = crop_geometry(640, 360, "9:16", 0.0)
    max_offset = max(0, 640 - crop_w)
    expression = build_crop_x_expression(keyframes, max_offset)

    assert "0.000000" in expression
    assert "3.000000" in expression
    assert "6.000000" in expression
    assert "0.1000" in expression or f"{0.10 * max_offset:.4f}" in expression
    assert f"{0.80 * max_offset:.4f}" in expression
    assert f"{0.35 * max_offset:.4f}" in expression


def test_build_ffmpeg_command_uses_project_keyframes():
    keyframes = [
        Keyframe(0.0, 0.10, "linear"),
        Keyframe(3.0, 0.80, "linear"),
        Keyframe(6.0, 0.35, "linear"),
    ]
    info = VideoInfo(width=640, height=360, duration=6.0, fps=30.0)
    command = build_ffmpeg_command("input.mp4", "output.mp4", info, keyframes, "9:16")

    vf_index = command.index("-vf") + 1
    vf = command[vf_index]
    assert "3.000000" in vf
    assert "6.000000" in vf


@pytest.mark.integration
def test_ffmpeg_acceptance_project_exports(tmp_path: Path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe not available in PATH")

    input_path = tmp_path / "source.mp4"
    output_path = tmp_path / "export.mp4"

    generate_cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=640x360:rate=30",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=44100",
        "-t",
        "6",
        "-pix_fmt",
        "yuv420p",
        "-shortest",
        str(input_path),
    ]
    result = subprocess.run(generate_cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        pytest.skip(f"could not generate synthetic test video: {result.stderr.strip()}")

    info = probe_video(input_path)
    keyframes = [
        Keyframe(0.0, 0.10, "linear"),
        Keyframe(3.0, 0.80, "linear"),
        Keyframe(6.0, 0.35, "linear"),
    ]
    export_cmd = build_ffmpeg_command(input_path, output_path, info, keyframes, "9:16")
    export_result = subprocess.run(export_cmd, capture_output=True, text=True, check=False)
    assert export_result.returncode == 0, export_result.stderr

    assert output_path.exists()
    assert output_path.stat().st_size > 0

    exported = probe_video(output_path)
    assert exported.duration == pytest.approx(info.duration, rel=0.05, abs=0.25)

    expected_w, expected_h = default_resolution("9:16")
    assert exported.width == expected_w
    assert exported.height == expected_h

    probe_streams = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_type,width,height",
        "-of",
        "json",
        str(output_path),
    ]
    probe_result = subprocess.run(probe_streams, capture_output=True, text=True, check=True)
    payload = json.loads(probe_result.stdout)
    streams = payload.get("streams") or []
    assert streams
    assert streams[0]["codec_type"] == "video"
