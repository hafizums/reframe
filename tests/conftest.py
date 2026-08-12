from __future__ import annotations

import pytest

from reframe_app import ReframeWindow
from reframe_core import Keyframe, ReframeProject, VideoInfo


@pytest.fixture
def playhead():
    state = {"ms": 0}

    def get_position() -> int:
        return state["ms"]

    def set_position(ms: int) -> None:
        state["ms"] = int(ms)

    return state, get_position, set_position


@pytest.fixture
def window(qtbot, playhead):
    state, get_position, set_position = playhead
    win = ReframeWindow()
    qtbot.addWidget(win)

    win.video_info = VideoInfo(width=640, height=360, duration=6.0, fps=30.0)
    win.project = ReframeProject(video_path="synthetic.mp4", aspect="9:16", keyframes=[])
    win.timeline.setRange(0, 6000)
    win._update_controls_enabled(True)

    win.player.position = get_position
    win.player.setPosition = set_position
    win.player.duration = lambda: 6000

    win.show()
    qtbot.waitExposed(win)
    return win


def set_playhead(window: ReframeWindow, playhead, position_ms: int) -> None:
    state, _, set_position = playhead
    set_position(position_ms)
    state["ms"] = position_ms


def set_linear_easing(window: ReframeWindow) -> None:
    index = window.easing_combo.findData("linear")
    assert index >= 0
    window.easing_combo.setCurrentIndex(index)


def add_position_keyframe(window: ReframeWindow, playhead, position_ms: int, x: float, easing: str = "linear") -> None:
    set_playhead(window, playhead, position_ms)
    window._set_crop_x(x)
    index = window.easing_combo.findData(easing)
    if index >= 0:
        window.easing_combo.setCurrentIndex(index)
    window.add_or_update_keyframe()


def create_acceptance_keyframes(window: ReframeWindow, playhead) -> None:
    add_position_keyframe(window, playhead, 0, 0.10)
    add_position_keyframe(window, playhead, 3000, 0.80)
    add_position_keyframe(window, playhead, 6000, 0.35)


def sorted_keyframe_triples(project: ReframeProject) -> list[tuple[float, float, str]]:
    return [(kf.time, kf.x, kf.easing) for kf in project.sorted_keyframes()]
