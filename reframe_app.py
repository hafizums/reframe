from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QRect, QThread, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygon, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoFrame, QVideoSink
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QSplitter,
    QStyle,
    QStyleOptionSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from reframe_core import (
    KEYFRAME_REMOVE_TOLERANCE,
    KEYFRAME_TIME_TOLERANCE,
    Keyframe,
    ReframeProject,
    VideoInfo,
    add_or_update_keyframe_at,
    build_ffmpeg_command,
    crop_geometry,
    default_resolution,
    find_keyframe_index_at_time,
    format_position_label,
    interpolate_position,
    marker_time_fraction,
    probe_video,
)


APP_STYLE = """
QWidget {
    background: #111318;
    color: #e8ebf2;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}
QMainWindow { background: #0c0e12; }
QGroupBox {
    border: 1px solid #292e38;
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: 600;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
QPushButton {
    background: #242a35;
    border: 1px solid #343b49;
    border-radius: 6px;
    padding: 8px 12px;
}
QPushButton:hover { background: #303746; }
QPushButton:pressed { background: #1d222b; }
QPushButton#primaryButton {
    background: #10b8c7;
    border-color: #10b8c7;
    color: #071013;
    font-weight: 700;
}
QPushButton#primaryButton:hover { background: #20cedd; }
QComboBox, QTableWidget {
    background: #171a21;
    border: 1px solid #303642;
    border-radius: 5px;
    padding: 5px;
}
QHeaderView::section {
    background: #1c2028;
    color: #bfc5d2;
    border: 0;
    padding: 6px;
}
QSlider::groove:horizontal { height: 5px; background: #2b313c; border-radius: 2px; }
QSlider::handle:horizontal {
    width: 14px;
    margin: -5px 0;
    background: #11c2d2;
    border-radius: 7px;
}
QProgressBar {
    border: 1px solid #303642;
    border-radius: 5px;
    text-align: center;
    background: #171a21;
}
QProgressBar::chunk { background: #10b8c7; }
"""


class TimelineMarkerLayer(QWidget):
    marker_clicked = Signal(int)

    MARKER_HIT_RADIUS = 10

    def __init__(self, slider: QSlider):
        super().__init__(slider)
        self._slider = slider
        self._keyframes: list[Keyframe] = []
        self._duration_ms = 1
        self._active_index: int | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self._slider.installEventFilter(self)
        slider.valueChanged.connect(self.update)
        slider.rangeChanged.connect(self._sync_geometry)

    def set_keyframes(self, keyframes: list[Keyframe], duration_ms: int, active_index: int | None) -> None:
        self._keyframes = sorted(keyframes, key=lambda item: item.time)
        self._duration_ms = max(1, duration_ms)
        self._active_index = active_index
        self._sync_geometry()
        self.update()

    @property
    def keyframes(self) -> list[Keyframe]:
        return list(self._keyframes)

    @property
    def marker_count(self) -> int:
        return len(self._keyframes)

    @property
    def active_marker_index(self) -> int | None:
        return self._active_index

    @property
    def duration_ms(self) -> int:
        return self._duration_ms

    def marker_fractions(self) -> list[float]:
        return [marker_time_fraction(keyframe.time, self._duration_ms) for keyframe in self._keyframes]

    def _groove_rect(self) -> QRect:
        option = QStyleOptionSlider()
        self._slider.initStyleOption(option)
        return self._slider.style().subControlRect(
            QStyle.ComplexControl.CC_Slider,
            option,
            QStyle.SubControl.SC_SliderGroove,
            self._slider,
        )

    def _marker_x(self, time_seconds: float) -> float:
        groove = self._groove_rect()
        if self._duration_ms <= 0:
            return groove.center().x()
        fraction = marker_time_fraction(time_seconds, self._duration_ms)
        return groove.left() + fraction * groove.width()

    def _sync_geometry(self) -> None:
        self.setGeometry(self._slider.rect())
        self.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_geometry()

    def paintEvent(self, _event) -> None:
        if not self._keyframes or self._duration_ms <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        groove = self._groove_rect()
        marker_y = groove.center().y()
        for index, keyframe in enumerate(self._keyframes):
            center_x = self._marker_x(keyframe.time)
            half = 7 if index == self._active_index else 5
            color = QColor("#7af0ff") if index == self._active_index else QColor("#11c2d2")
            diamond = QPolygon(
                [
                    QPoint(int(center_x), int(marker_y - half)),
                    QPoint(int(center_x + half), int(marker_y)),
                    QPoint(int(center_x), int(marker_y + half)),
                    QPoint(int(center_x - half), int(marker_y)),
                ]
            )
            painter.setPen(QPen(color.darker(115), 1))
            painter.setBrush(color)
            painter.drawPolygon(diamond)
        painter.end()

    def _marker_index_at(self, pos: QPoint) -> int | None:
        for index, keyframe in enumerate(self._keyframes):
            center = QPoint(int(self._marker_x(keyframe.time)), self._groove_rect().center().y())
            if (pos - center).manhattanLength() <= self.MARKER_HIT_RADIUS + 4:
                return index
        return None

    def eventFilter(self, watched, event) -> bool:
        if watched is self._slider and event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                index = self._marker_index_at(event.position().toPoint())
                if index is not None:
                    self.marker_clicked.emit(index)
                    return True
        return super().eventFilter(watched, event)


class KeyframeTimelineWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.marker_layer = TimelineMarkerLayer(self.slider)
        layout.addWidget(self.slider)

    @property
    def marker_count(self) -> int:
        return self.marker_layer.marker_count

    @property
    def active_marker_index(self) -> int | None:
        return self.marker_layer.active_marker_index

    def marker_fractions(self) -> list[float]:
        return self.marker_layer.marker_fractions()


class PreviewLabel(QLabel):
    crop_requested = Signal(float)
    resized = Signal()

    def __init__(self, interactive: bool = False):
        super().__init__()
        self.interactive = interactive
        self._pixmap_size = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(320, 220)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("background:#050608; border:1px solid #272c35; border-radius:8px;")
        self.setText("Open a video to begin")

    def set_preview_pixmap(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            return
        scaled = pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._pixmap_size = scaled.size()
        self.setPixmap(scaled)

    def _normalized_pointer_x(self, x: float) -> float | None:
        if not self._pixmap_size or self._pixmap_size.width() <= 0:
            return None
        offset_x = (self.width() - self._pixmap_size.width()) / 2
        local_x = x - offset_x
        return max(0.0, min(1.0, local_x / self._pixmap_size.width()))

    def mousePressEvent(self, event) -> None:
        if self.interactive and event.button() == Qt.MouseButton.LeftButton:
            value = self._normalized_pointer_x(event.position().x())
            if value is not None:
                self.crop_requested.emit(value)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self.interactive and (event.buttons() & Qt.MouseButton.LeftButton):
            value = self._normalized_pointer_x(event.position().x())
            if value is not None:
                self.crop_requested.emit(value)
        super().mouseMoveEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.resized.emit()


class ExportThread(QThread):
    progress = Signal(int)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        input_path: str,
        output_path: str,
        info: VideoInfo,
        keyframes: list[Keyframe],
        aspect: str,
    ):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.info = info
        self.keyframes = keyframes
        self.aspect = aspect

    def run(self) -> None:
        try:
            cmd = build_ffmpeg_command(
                self.input_path,
                self.output_path,
                self.info,
                self.keyframes,
                self.aspect,
            )
            cmd[-1:-1] = ["-progress", "pipe:1", "-nostats"]
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if process.stdout:
                for raw_line in process.stdout:
                    line = raw_line.strip()
                    if line.startswith("out_time_us="):
                        try:
                            elapsed = int(line.split("=", 1)[1]) / 1_000_000
                            if self.info.duration > 0:
                                pct = int(max(0, min(100, elapsed / self.info.duration * 100)))
                                self.progress.emit(pct)
                        except ValueError:
                            pass
            return_code = process.wait()
            if return_code != 0:
                self.failed.emit(f"FFmpeg exited with code {return_code}.")
                return
            self.progress.emit(100)
            self.completed.emit(self.output_path)
        except Exception as exc:  # UI boundary: show a useful error instead of crashing
            self.failed.emit(str(exc))


class ReframeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Reframe Studio — Python")
        self.resize(1500, 900)
        self.setMinimumSize(1050, 700)

        self.project = ReframeProject()
        self.video_info: VideoInfo | None = None
        self.current_image = QImage()
        self.current_x = 0.5
        self.scrubbing = False
        self.export_thread: ExportThread | None = None

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(0.8)
        self.video_sink = QVideoSink(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoSink(self.video_sink)

        self._build_ui()
        self._connect_signals()
        self._update_controls_enabled(False)

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Reframe Studio")
        title.setStyleSheet("font-size:24px;font-weight:800;")
        subtitle = QLabel("Native Python editor • FFmpeg export • keyframed crop motion")
        subtitle.setStyleSheet("color:#8e97a8;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()
        self.open_btn = QPushButton("Open Video")
        self.save_project_btn = QPushButton("Save Project")
        self.load_project_btn = QPushButton("Load Project")
        self.export_btn = QPushButton("Export MP4")
        self.export_btn.setObjectName("primaryButton")
        for button in (self.open_btn, self.save_project_btn, self.load_project_btn, self.export_btn):
            header.addWidget(button)
        layout.addLayout(header)

        main_split = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(main_split, 1)

        preview_panel = QWidget()
        preview_layout = QGridLayout(preview_panel)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        source_title = QLabel("SOURCE — drag/click to reposition crop")
        source_title.setStyleSheet("font-weight:700;color:#aab2c0;")
        output_title = QLabel("OUTPUT PREVIEW")
        output_title.setStyleSheet("font-weight:700;color:#aab2c0;")
        self.source_preview = PreviewLabel(interactive=True)
        self.output_preview = PreviewLabel(interactive=False)
        preview_layout.addWidget(source_title, 0, 0)
        preview_layout.addWidget(output_title, 0, 1)
        preview_layout.addWidget(self.source_preview, 1, 0)
        preview_layout.addWidget(self.output_preview, 1, 1)
        preview_layout.setColumnStretch(0, 3)
        preview_layout.setColumnStretch(1, 2)
        main_split.addWidget(preview_panel)

        control_panel = QWidget()
        control_panel.setMaximumWidth(420)
        controls = QVBoxLayout(control_panel)
        controls.setContentsMargins(8, 0, 0, 0)

        framing_group = QGroupBox("Framing")
        framing_form = QFormLayout(framing_group)
        self.aspect_combo = QComboBox()
        self.aspect_combo.addItems(["9:16", "1:1", "4:5", "4:3"])
        self.crop_slider = QSlider(Qt.Orientation.Horizontal)
        self.crop_slider.setRange(0, 1000)
        self.crop_slider.setValue(500)
        self.crop_value = QLabel("50%")
        crop_row = QHBoxLayout()
        crop_row.addWidget(self.crop_slider, 1)
        crop_row.addWidget(self.crop_value)
        crop_widget = QWidget()
        crop_widget.setLayout(crop_row)
        framing_form.addRow("Aspect", self.aspect_combo)
        framing_form.addRow("Crop X", crop_widget)
        preset_row = QHBoxLayout()
        self.left_btn = QPushButton("Left")
        self.center_btn = QPushButton("Center")
        self.right_btn = QPushButton("Right")
        preset_row.addWidget(self.left_btn)
        preset_row.addWidget(self.center_btn)
        preset_row.addWidget(self.right_btn)
        preset_widget = QWidget()
        preset_widget.setLayout(preset_row)
        framing_form.addRow("Preset", preset_widget)
        self.output_size_label = QLabel("1080 × 1920")
        framing_form.addRow("Export", self.output_size_label)
        controls.addWidget(framing_group)

        key_group = QGroupBox("Keyframes")
        key_layout = QVBoxLayout(key_group)
        ease_row = QHBoxLayout()
        ease_row.addWidget(QLabel("Transition"))
        self.easing_combo = QComboBox()
        self.easing_combo.addItem("Smooth Ease", "easeInOut")
        self.easing_combo.addItem("Linear", "linear")
        self.easing_combo.addItem("Hold / Jump", "hold")
        ease_row.addWidget(self.easing_combo, 1)
        key_layout.addLayout(ease_row)
        key_buttons = QHBoxLayout()
        self.add_key_btn = QPushButton("◆ Add Position Keyframe")
        self.remove_key_btn = QPushButton("Remove")
        key_buttons.addWidget(self.add_key_btn)
        key_buttons.addWidget(self.remove_key_btn)
        key_layout.addLayout(key_buttons)
        nav_buttons = QHBoxLayout()
        self.prev_key_btn = QPushButton("◀ Prev")
        self.next_key_btn = QPushButton("Next ▶")
        nav_buttons.addWidget(self.prev_key_btn)
        nav_buttons.addWidget(self.next_key_btn)
        key_layout.addLayout(nav_buttons)
        self.key_table = QTableWidget(0, 3)
        self.key_table.setHorizontalHeaderLabels(["Time", "Position", "Transition"])
        self.key_table.horizontalHeader().setStretchLastSection(True)
        self.key_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.key_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.key_table.setMinimumHeight(180)
        key_layout.addWidget(self.key_table)
        controls.addWidget(key_group, 1)

        self.status_label = QLabel("FFmpeg: checking…")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color:#8e97a8;")
        controls.addWidget(self.status_label)
        main_split.addWidget(control_panel)
        main_split.setStretchFactor(0, 1)
        main_split.setStretchFactor(1, 0)

        transport = QFrame()
        transport.setFrameShape(QFrame.Shape.StyledPanel)
        transport_layout = QVBoxLayout(transport)
        transport_layout.setContentsMargins(10, 8, 10, 8)
        row = QHBoxLayout()
        self.play_btn = QPushButton("▶ Play")
        self.back_btn = QPushButton("−1s")
        self.forward_btn = QPushButton("+1s")
        self.time_label = QLabel("00:00.00 / 00:00.00")
        row.addWidget(self.play_btn)
        row.addWidget(self.back_btn)
        row.addWidget(self.forward_btn)
        row.addWidget(self.time_label)
        row.addStretch()
        transport_layout.addLayout(row)
        self.timeline_widget = KeyframeTimelineWidget()
        self.timeline = self.timeline_widget.slider
        self.timeline.setRange(0, 1)
        transport_layout.addWidget(self.timeline_widget)
        self.export_progress = QProgressBar()
        self.export_progress.setRange(0, 100)
        self.export_progress.hide()
        transport_layout.addWidget(self.export_progress)
        layout.addWidget(transport)

        self._refresh_keyframe_table()
        self._refresh_output_resolution()
        self._check_dependencies()

    def _connect_signals(self) -> None:
        self.open_btn.clicked.connect(self.open_video)
        self.save_project_btn.clicked.connect(self.save_project)
        self.load_project_btn.clicked.connect(self.load_project)
        self.export_btn.clicked.connect(self.export_video)

        self.video_sink.videoFrameChanged.connect(self._on_video_frame)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._update_play_button)
        self.player.errorOccurred.connect(self._on_player_error)

        self.source_preview.crop_requested.connect(self._on_source_pointer)
        self.source_preview.resized.connect(self.render_previews)
        self.output_preview.resized.connect(self.render_previews)

        self.aspect_combo.currentTextChanged.connect(self._on_aspect_changed)
        self.crop_slider.valueChanged.connect(self._on_crop_slider)
        self.left_btn.clicked.connect(lambda: self._set_crop_x(0.0))
        self.center_btn.clicked.connect(lambda: self._set_crop_x(0.5))
        self.right_btn.clicked.connect(lambda: self._set_crop_x(1.0))

        self.play_btn.clicked.connect(self.toggle_playback)
        self.back_btn.clicked.connect(lambda: self.player.setPosition(max(0, self.player.position() - 1000)))
        self.forward_btn.clicked.connect(
            lambda: self.player.setPosition(min(self.player.duration(), self.player.position() + 1000))
        )
        self.timeline.sliderPressed.connect(self._start_scrub)
        self.timeline.sliderReleased.connect(self._finish_scrub)
        self.timeline.sliderMoved.connect(self._scrub_to)
        self.timeline_widget.marker_layer.marker_clicked.connect(self._on_timeline_marker_clicked)

        self.add_key_btn.clicked.connect(self.add_or_update_keyframe)
        self.remove_key_btn.clicked.connect(self.remove_keyframe)
        self.prev_key_btn.clicked.connect(lambda: self.jump_keyframe(-1))
        self.next_key_btn.clicked.connect(lambda: self.jump_keyframe(1))
        self.key_table.cellDoubleClicked.connect(self._jump_to_table_keyframe)

    def _check_dependencies(self) -> None:
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        if ffmpeg and ffprobe:
            self.status_label.setText("FFmpeg ready • project is processed locally")
            self.status_label.setStyleSheet("color:#7edc9b;")
        else:
            missing = []
            if not ffmpeg:
                missing.append("ffmpeg")
            if not ffprobe:
                missing.append("ffprobe")
            self.status_label.setText("Missing: " + ", ".join(missing) + ". Add FFmpeg to PATH before exporting.")
            self.status_label.setStyleSheet("color:#ff9f8f;")

    def _update_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self.play_btn,
            self.back_btn,
            self.forward_btn,
            self.timeline_widget,
            self.crop_slider,
            self.aspect_combo,
            self.add_key_btn,
            self.remove_key_btn,
            self.prev_key_btn,
            self.next_key_btn,
            self.export_btn,
            self.save_project_btn,
        ):
            widget.setEnabled(enabled)

    def open_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open video",
            "",
            "Video Files (*.mp4 *.mov *.mkv *.avi *.webm);;All Files (*)",
        )
        if path:
            self.load_video_path(path, reset_keyframes=True)

    def load_video_path(self, path: str, reset_keyframes: bool = False) -> bool:
        try:
            if not Path(path).exists():
                raise FileNotFoundError(path)
            info = probe_video(path)
        except Exception as exc:
            QMessageBox.critical(self, "Cannot open video", str(exc))
            return False

        self.video_info = info
        self.project.video_path = path
        if reset_keyframes:
            self.project.keyframes = [Keyframe(0.0, 0.5, "easeInOut")]
            self._set_crop_x(0.5)
        self.player.setSource(QUrl.fromLocalFile(path))
        self.timeline.setRange(0, max(1, int(info.duration * 1000)))
        self._update_controls_enabled(True)
        self._refresh_keyframe_table()
        self._update_time_label(0)
        self._update_keyframe_ui_state(0.0)
        return True

    def save_project(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save Reframe project", "reframe_project.json", "JSON (*.json)")
        if not path:
            return
        try:
            self.project.aspect = self.aspect_combo.currentText()
            self.project.save(path)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))

    def load_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load Reframe project", "", "JSON (*.json)")
        if not path:
            return
        try:
            project = ReframeProject.load(path)
        except Exception as exc:
            QMessageBox.critical(self, "Load failed", str(exc))
            return

        if not project.video_path or not Path(project.video_path).exists():
            replacement, _ = QFileDialog.getOpenFileName(
                self,
                "Locate project video",
                "",
                "Video Files (*.mp4 *.mov *.mkv *.avi *.webm);;All Files (*)",
            )
            if not replacement:
                return
            project.video_path = replacement

        self.project = project
        self.aspect_combo.setCurrentText(project.aspect if project.aspect in {"9:16", "1:1", "4:5", "4:3"} else "9:16")
        if self.load_video_path(project.video_path, reset_keyframes=False):
            self._refresh_keyframe_table()
            self.player.setPosition(0)

    def _on_video_frame(self, frame: QVideoFrame) -> None:
        if not frame.isValid():
            return
        image = frame.toImage()
        if image.isNull():
            return
        self.current_image = image
        self.render_previews()

    def render_previews(self) -> None:
        if self.current_image.isNull() or not self.video_info:
            return
        source = self.current_image.copy()
        src_w, src_h = source.width(), source.height()
        x, y, crop_w, crop_h = crop_geometry(src_w, src_h, self.aspect_combo.currentText(), self.current_x)

        painter = QPainter(source)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 145))
        if x > 0:
            painter.drawRect(0, 0, x, src_h)
        if x + crop_w < src_w:
            painter.drawRect(x + crop_w, 0, src_w - x - crop_w, src_h)
        if y > 0:
            painter.drawRect(x, 0, crop_w, y)
        if y + crop_h < src_h:
            painter.drawRect(x, y + crop_h, crop_w, src_h - y - crop_h)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#11c2d2"), max(2, src_w // 500)))
        painter.drawRect(x, y, max(1, crop_w - 1), max(1, crop_h - 1))
        painter.end()
        self.source_preview.set_preview_pixmap(QPixmap.fromImage(source))

        cropped = self.current_image.copy(x, y, crop_w, crop_h)
        self.output_preview.set_preview_pixmap(QPixmap.fromImage(cropped))

    def _on_source_pointer(self, source_fraction_x: float) -> None:
        if not self.video_info:
            return
        _, _, crop_w, _ = crop_geometry(
            self.video_info.width,
            self.video_info.height,
            self.aspect_combo.currentText(),
            0.0,
        )
        max_offset = max(0, self.video_info.width - crop_w)
        if max_offset <= 0:
            self._set_crop_x(0.5)
            return
        source_center = source_fraction_x * self.video_info.width
        crop_left = source_center - crop_w / 2
        self._set_crop_x(crop_left / max_offset)

    def _set_crop_x(self, value: float) -> None:
        self.current_x = max(0.0, min(1.0, float(value)))
        self.crop_slider.blockSignals(True)
        self.crop_slider.setValue(round(self.current_x * 1000))
        self.crop_slider.blockSignals(False)
        self.crop_value.setText(f"{round(self.current_x * 100)}%")
        self.render_previews()

    def _on_crop_slider(self, value: int) -> None:
        self.current_x = value / 1000
        self.crop_value.setText(f"{round(self.current_x * 100)}%")
        self.render_previews()

    def _on_aspect_changed(self, aspect: str) -> None:
        self.project.aspect = aspect
        self._refresh_output_resolution()
        self.render_previews()

    def _refresh_output_resolution(self) -> None:
        w, h = default_resolution(self.aspect_combo.currentText())
        self.output_size_label.setText(f"{w} × {h}")

    def toggle_playback(self) -> None:
        if not self.video_info:
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _update_play_button(self, state) -> None:
        self.play_btn.setText("❚❚ Pause" if state == QMediaPlayer.PlaybackState.PlayingState else "▶ Play")

    def _on_position_changed(self, position_ms: int) -> None:
        if not self.scrubbing:
            self.timeline.blockSignals(True)
            self.timeline.setValue(position_ms)
            self.timeline.blockSignals(False)
        seconds = position_ms / 1000
        if self.project.keyframes:
            self._set_crop_x(interpolate_position(self.project.keyframes, seconds))
        self._update_time_label(position_ms)
        self._update_keyframe_ui_state(seconds)

    def _on_duration_changed(self, duration_ms: int) -> None:
        if duration_ms > 0:
            self.timeline.setRange(0, duration_ms)
            self._update_time_label(self.player.position())
            self._refresh_timeline_markers()

    def _update_time_label(self, position_ms: int) -> None:
        duration_ms = self.player.duration() if self.player.duration() > 0 else int((self.video_info.duration if self.video_info else 0) * 1000)
        self.time_label.setText(f"{format_time(position_ms)} / {format_time(duration_ms)}")

    def _start_scrub(self) -> None:
        self.scrubbing = True

    def _scrub_to(self, value: int) -> None:
        self.player.setPosition(value)

    def _finish_scrub(self) -> None:
        self.player.setPosition(self.timeline.value())
        self.scrubbing = False

    def add_or_update_keyframe(self) -> None:
        time_seconds = self.player.position() / 1000
        easing = self.easing_combo.currentData()
        add_or_update_keyframe_at(
            self.project.keyframes,
            time_seconds,
            self.current_x,
            easing,
            KEYFRAME_TIME_TOLERANCE,
        )
        self._refresh_keyframe_table()
        self._update_keyframe_ui_state(time_seconds)

    def remove_keyframe(self) -> None:
        time_seconds = self.player.position() / 1000
        index = find_keyframe_index_at_time(
            self.project.keyframes,
            time_seconds,
            KEYFRAME_REMOVE_TOLERANCE,
        )
        if index is None:
            nearby = [(abs(kf.time - time_seconds), idx) for idx, kf in enumerate(self.project.keyframes)]
            if not nearby:
                return
            distance, index = min(nearby)
            if distance > KEYFRAME_REMOVE_TOLERANCE:
                return
        self.project.keyframes.pop(index)
        if not self.project.keyframes:
            self.project.keyframes = [Keyframe(0.0, self.current_x, "easeInOut")]
        self._refresh_keyframe_table()
        if self.project.keyframes:
            self._set_crop_x(interpolate_position(self.project.keyframes, time_seconds))
        self._update_keyframe_ui_state(time_seconds)

    def jump_keyframe(self, direction: int) -> None:
        frames = sorted(self.project.keyframes, key=lambda item: item.time)
        now = self.player.position() / 1000
        target = None
        if direction < 0:
            candidates = [kf for kf in frames if kf.time < now - 0.05]
            target = candidates[-1] if candidates else (frames[0] if frames else None)
        else:
            candidates = [kf for kf in frames if kf.time > now + 0.05]
            target = candidates[0] if candidates else (frames[-1] if frames else None)
        if target:
            self._jump_to_keyframe(target)

    def _jump_to_table_keyframe(self, row: int, _column: int) -> None:
        frames = sorted(self.project.keyframes, key=lambda item: item.time)
        if 0 <= row < len(frames):
            self._jump_to_keyframe(frames[row])

    def _on_timeline_marker_clicked(self, index: int) -> None:
        frames = sorted(self.project.keyframes, key=lambda item: item.time)
        if 0 <= index < len(frames):
            self._jump_to_keyframe(frames[index])

    def _jump_to_keyframe(self, keyframe: Keyframe) -> None:
        self.player.setPosition(round(keyframe.time * 1000))
        self._set_crop_x(keyframe.x)
        self._set_easing_for_keyframe(keyframe)
        self._update_keyframe_ui_state(keyframe.time)

    def _set_easing_for_keyframe(self, keyframe: Keyframe) -> None:
        index = self.easing_combo.findData(keyframe.easing)
        if index >= 0:
            self.easing_combo.blockSignals(True)
            self.easing_combo.setCurrentIndex(index)
            self.easing_combo.blockSignals(False)

    def _refresh_timeline_markers(self, active_index: int | None = None) -> None:
        duration_ms = self.player.duration() if self.player.duration() > 0 else int(
            (self.video_info.duration if self.video_info else 0) * 1000
        )
        self.timeline_widget.marker_layer.set_keyframes(
            self.project.keyframes,
            duration_ms,
            active_index,
        )

    def _update_keyframe_ui_state(self, time_seconds: float) -> None:
        frames = sorted(self.project.keyframes, key=lambda item: item.time)
        active_index = None
        active_keyframe = None
        for index, keyframe in enumerate(frames):
            if abs(keyframe.time - time_seconds) < KEYFRAME_TIME_TOLERANCE:
                active_index = index
                active_keyframe = keyframe
                break
        if active_keyframe is not None:
            self.add_key_btn.setText("◆ Update Position Keyframe")
            self._set_easing_for_keyframe(active_keyframe)
            self.key_table.blockSignals(True)
            self.key_table.selectRow(active_index)
            self.key_table.blockSignals(False)
        else:
            self.add_key_btn.setText("◆ Add Position Keyframe")
            self.key_table.blockSignals(True)
            self.key_table.clearSelection()
            self.key_table.blockSignals(False)
        self._refresh_timeline_markers(active_index)

    def _refresh_keyframe_table(self) -> None:
        frames = sorted(self.project.keyframes, key=lambda item: item.time)
        self.key_table.setRowCount(len(frames))
        transition_names = {"easeInOut": "Smooth", "linear": "Linear", "hold": "Hold"}
        for row, frame in enumerate(frames):
            self.key_table.setItem(row, 0, QTableWidgetItem(f"{frame.time:.3f}s"))
            self.key_table.setItem(row, 1, QTableWidgetItem(format_position_label(frame.x)))
            self.key_table.setItem(
                row,
                2,
                QTableWidgetItem(transition_names.get(frame.easing, frame.easing)),
            )
        self.key_table.resizeColumnsToContents()
        self._update_keyframe_ui_state(self.player.position() / 1000)

    def export_video(self) -> None:
        if not self.video_info or not self.project.video_path:
            return
        if not shutil.which("ffmpeg"):
            QMessageBox.warning(self, "FFmpeg not found", "Install FFmpeg and make sure ffmpeg is available in PATH.")
            return

        default_name = str(Path(self.project.video_path).with_name(Path(self.project.video_path).stem + "_reframed.mp4"))
        output_path, _ = QFileDialog.getSaveFileName(self, "Export reframed video", default_name, "MP4 Video (*.mp4)")
        if not output_path:
            return
        if not output_path.lower().endswith(".mp4"):
            output_path += ".mp4"

        self.export_progress.setValue(0)
        self.export_progress.show()
        self.export_btn.setEnabled(False)
        self.export_btn.setText("Exporting…")
        self.export_thread = ExportThread(
            self.project.video_path,
            output_path,
            self.video_info,
            list(self.project.keyframes),
            self.aspect_combo.currentText(),
        )
        self.export_thread.progress.connect(self.export_progress.setValue)
        self.export_thread.completed.connect(self._export_completed)
        self.export_thread.failed.connect(self._export_failed)
        self.export_thread.start()

    def _export_completed(self, output_path: str) -> None:
        self.export_btn.setEnabled(True)
        self.export_btn.setText("Export MP4")
        self.export_progress.setValue(100)
        QMessageBox.information(self, "Export complete", f"Saved to:\n{output_path}")

    def _export_failed(self, error: str) -> None:
        self.export_btn.setEnabled(True)
        self.export_btn.setText("Export MP4")
        self.export_progress.hide()
        QMessageBox.critical(self, "Export failed", error)

    def _on_player_error(self, _error, error_string: str) -> None:
        if error_string:
            self.statusBar().showMessage(error_string, 8000)


def format_time(milliseconds: int) -> str:
    milliseconds = max(0, int(milliseconds))
    total_seconds = milliseconds / 1000
    minutes = int(total_seconds // 60)
    seconds = int(total_seconds % 60)
    hundredths = int((total_seconds - int(total_seconds)) * 100)
    return f"{minutes:02d}:{seconds:02d}.{hundredths:02d}"


def run() -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Reframe Studio")
    app.setStyleSheet(APP_STYLE)
    window = ReframeWindow()
    window.show()
    return app.exec()
