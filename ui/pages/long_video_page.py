"""NAV TOOLS - Long video extend-chain page."""

from __future__ import annotations

import time
import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QThread, Qt, QUrl, Signal, QSize
from PySide6.QtGui import QCursor, QDesktopServices, QPainter, QColor, QPen, QBrush, QPalette, QIcon
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
    QMenu,
)

from config.constants import DEFAULT_VIDEO_OUTPUT
from utils.file_utils import generate_task_name
from utils.logger import log


def ensure_player_icons():
    import os
    dir_path = os.path.dirname(os.path.abspath(__file__))
    svgs = {
        "play.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#f8fafc"><polygon points="6 3 20 12 6 21 6 3"/></svg>',
        "pause.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#f8fafc"><rect x="5" y="4" width="4" height="16" rx="1"/><rect x="15" y="4" width="4" height="16" rx="1"/></svg>',
        "volume_on.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#f8fafc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" fill="#f8fafc"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>',
        "volume_off.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" fill="#ef4444"/><line x1="22" y1="9" x2="16" y2="15"/><line x1="16" y1="9" x2="22" y2="15"/></svg>',
        "more.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#f8fafc" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="5" r="1.5" fill="#f8fafc"/><circle cx="12" cy="12" r="1.5" fill="#f8fafc"/><circle cx="12" cy="19" r="1.5" fill="#f8fafc"/></svg>'
    }
    paths = {}
    for name, content in svgs.items():
        p = os.path.join(dir_path, name)
        if not os.path.exists(p):
            try:
                with open(p, "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception:
                pass
        paths[name.split(".")[0]] = p.replace("\\", "/")
    return paths


def get_video_duration(path):
    import subprocess
    import re
    import sys
    from config.constants import FFMPEG_PATH
    try:
        cmd = [str(FFMPEG_PATH), "-i", str(path)]
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = 0x08000000 # CREATE_NO_WINDOW
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", creationflags=creation_flags)
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", res.stderr)
        if m:
            hours = int(m.group(1))
            minutes = int(m.group(2))
            seconds = float(m.group(3))
            return hours * 3600 + minutes * 60 + seconds
    except Exception as e:
        log.warning(f"get_video_duration failed: {e}")
    
    # Fallback to OpenCV
    try:
        import cv2
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        if fps > 0:
            return frame_count / fps
    except:
        pass
    return 10.0


def get_video_info(path):
    import os
    import sys
    import tempfile
    import shutil
    from pathlib import Path
    
    width, height, fps = 1280, 720, 30.0
    try:
        # Create a temp ASCII path to bypass Windows Unicode limitations in cv2/ffmpeg
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "probe.mp4"
            try:
                # Try creating a hard link first (instant, 0 bytes)
                os.link(str(path), str(temp_file))
            except Exception:
                # Fallback to copy if hard link is not supported across drives
                shutil.copy2(str(path), str(temp_file))
                
            # Now use OpenCV on the clean ASCII path
            import cv2
            cap = cv2.VideoCapture(str(temp_file))
            if cap.isOpened():
                w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                f = cap.get(cv2.CAP_PROP_FPS)
                if w > 0 and h > 0:
                    width = int(w)
                    height = int(h)
                if f > 0:
                    fps = float(f)
                cap.release()
    except Exception as e:
        log.warning(f"get_video_info failed: {e}")
    return width, height, fps


def setup_rounded_mask(widget, radius=8):
    from PySide6.QtCore import QObject, QEvent
    from PySide6.QtGui import QPainterPath, QRegion
    
    class MaskEventFilter(QObject):
        def __init__(self, target, r):
            super().__init__(target)
            self.target = target
            self.r = r
            
        def eventFilter(self, obj, event):
            if event.type() == QEvent.Type.Resize:
                path = QPainterPath()
                path.addRoundedRect(0, 0, self.target.width(), self.target.height(), self.r, self.r)
                self.target.setMask(QRegion(path.toFillPolygon().toPolygon()))
            return super().eventFilter(obj, event)
            
    filter_obj = MaskEventFilter(widget, radius)
    widget.installEventFilter(filter_obj)
    widget._mask_filter = filter_obj
    
    path = QPainterPath()
    path.addRoundedRect(0, 0, widget.width(), widget.height(), radius, radius)
    widget.setMask(QRegion(path.toFillPolygon().toPolygon()))


class QRangeSlider(QWidget):
    # Emits (start_value, end_value)
    rangeChanged = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.min_val = 0.0
        self.max_val = 10.0
        self.start_val = 0.0
        self.end_val = 10.0
        
        self.setFixedHeight(24)
        self.setMinimumWidth(160)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self._active_handle = None # None, 'start', 'end'
        self._handle_width = 8

    def setRange(self, min_val, max_val):
        self.min_val = float(min_val)
        self.max_val = float(max_val) if max_val > min_val else min_val + 1.0
        self.start_val = self.min_val
        self.end_val = self.max_val
        self.update()

    def setValues(self, start, end):
        self.start_val = max(self.min_val, min(self.max_val, float(start)))
        self.end_val = max(self.start_val, min(self.max_val, float(end)))
        self.update()

    def _val_to_pos(self, val):
        if self.max_val == self.min_val:
            return 0
        w = self.width() - 2 * self._handle_width
        ratio = (val - self.min_val) / (self.max_val - self.min_val)
        return int(self._handle_width + ratio * w)

    def _pos_to_val(self, pos):
        w = self.width() - 2 * self._handle_width
        if w <= 0:
            return self.min_val
        ratio = (pos - self._handle_width) / w
        ratio = max(0.0, min(1.0, ratio))
        return self.min_val + ratio * (self.max_val - self.min_val)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Draw background track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#1e293b"))) 
        painter.drawRoundedRect(0, 4, self.width(), self.height() - 8, 4, 4)

        # Draw selected active range
        pos_start = self._val_to_pos(self.start_val)
        pos_end = self._val_to_pos(self.end_val)
        
        # Premium neon blue accent fill
        painter.setBrush(QBrush(QColor("#2563eb"))) 
        painter.drawRect(pos_start, 4, pos_end - pos_start, self.height() - 8)

        # Draw left and right handles
        painter.setBrush(QBrush(QColor("#ffffff")))
        # Left handle
        painter.drawRoundedRect(pos_start - self._handle_width // 2, 0, self._handle_width, self.height(), 2, 2)
        # Right handle
        painter.drawRoundedRect(pos_end - self._handle_width // 2, 0, self._handle_width, self.height(), 2, 2)
        
        # Add little grab lines
        painter.setPen(QPen(QColor("#94a3b8"), 1))
        painter.drawLine(pos_start, 4, pos_start, self.height() - 4)
        painter.drawLine(pos_end, 4, pos_end, self.height() - 4)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().x()
            pos_start = self._val_to_pos(self.start_val)
            pos_end = self._val_to_pos(self.end_val)

            dist_start = abs(pos - pos_start)
            dist_end = abs(pos - pos_end)
            
            if dist_start < dist_end and dist_start < 15:
                self._active_handle = 'start'
            elif dist_end < 15:
                self._active_handle = 'end'
            else:
                if dist_start < dist_end:
                    self._active_handle = 'start'
                    self._update_value_from_pos(pos)
                else:
                    self._active_handle = 'end'
                    self._update_value_from_pos(pos)
            self.update()

    def mouseMoveEvent(self, event):
        if self._active_handle:
            pos = event.position().x()
            self._update_value_from_pos(pos)

    def mouseReleaseEvent(self, event):
        self._active_handle = None

    def _update_value_from_pos(self, pos):
        val = self._pos_to_val(pos)
        if self._active_handle == 'start':
            self.start_val = min(val, self.end_val - 0.1)
        elif self._active_handle == 'end':
            self.end_val = max(val, self.start_val + 0.1)
        self.update()
        self.rangeChanged.emit(self.start_val, self.end_val)


class LongVideoWorker(QThread):
    chain_started = Signal(str)
    scene_started = Signal(int, int)
    scene_done = Signal(int, str)
    scene_failed = Signal(int, str)
    progress = Signal(str)
    all_done = Signal(str)
    error = Signal(str)

    def __init__(self, scenes, output_dir, parent=None):
        super().__init__(parent)
        self.scenes = list(scenes)
        self.output_dir = Path(output_dir)
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        import subprocess
        import tempfile
        from config.constants import FFMPEG_PATH
        
        # Enforce no window creation on Windows
        creation_flags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            creation_flags = subprocess.CREATE_NO_WINDOW

        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.chain_started.emit(str(self.output_dir))
            
            # Query target resolution and fps from the first video to align all segments
            target_w, target_h, target_fps = 1280, 720, 30.0
            if self.scenes:
                target_w, target_h, target_fps = get_video_info(self.scenes[0]["video_path"])
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)
                trimmed_paths = []
                
                for idx, scene in enumerate(self.scenes, 1):
                    if self._cancelled:
                        self.progress.emit("Đã dừng")
                        return
                        
                    self.scene_started.emit(idx, len(self.scenes))
                    
                    video_path = scene["video_path"]
                    start_t = scene["start_trim"]
                    end_t = scene["end_trim"]
                    mute_audio = scene["mute_audio"]
                    
                    temp_segment = temp_dir_path / f"scene_{idx:03d}.mp4"
                    
                    dur = max(0.1, end_t - start_t)
                    if mute_audio:
                        cmd = [
                            str(FFMPEG_PATH), "-y",
                            "-ss", f"{start_t:.3f}",
                            "-i", str(video_path),
                            "-f", "lavfi",
                            "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                            "-t", f"{dur:.3f}",
                            "-vf", f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
                            "-r", f"{target_fps:.2f}",
                            "-c:v", "libx264",
                            "-preset", "superfast",
                            "-crf", "23",
                            "-c:a", "aac",
                            "-shortest",
                            str(temp_segment)
                        ]
                        log.info(f"LongVideoWorker: Trimming scene {idx} (MUTED, silent audio added): {' '.join(cmd)}")
                        res = subprocess.run(cmd, capture_output=True, text=True, creationflags=creation_flags)
                        if res.returncode != 0:
                            raise RuntimeError(f"FFmpeg trim error: {res.stderr}")
                    else:
                        cmd = [
                            str(FFMPEG_PATH), "-y",
                            "-ss", f"{start_t:.3f}",
                            "-i", str(video_path),
                            "-t", f"{dur:.3f}",
                            "-vf", f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
                            "-r", f"{target_fps:.2f}",
                            "-c:v", "libx264",
                            "-preset", "superfast",
                            "-crf", "23",
                            "-c:a", "aac",
                            "-ar", "44100",
                            "-ac", "2",
                            str(temp_segment)
                        ]
                        log.info(f"LongVideoWorker: Trimming scene {idx}: {' '.join(cmd)}")
                        res = subprocess.run(cmd, capture_output=True, text=True, creationflags=creation_flags)
                        if res.returncode != 0:
                            log.warning(f"Trim with audio failed (might have no audio track), adding silent audio track: {res.stderr}")
                            cmd_no_audio = [
                                str(FFMPEG_PATH), "-y",
                                "-ss", f"{start_t:.3f}",
                                "-i", str(video_path),
                                "-f", "lavfi",
                                "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                                "-t", f"{dur:.3f}",
                                "-vf", f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
                                "-r", f"{target_fps:.2f}",
                                "-c:v", "libx264",
                                "-preset", "superfast",
                                "-crf", "23",
                                "-c:a", "aac",
                                "-shortest",
                                str(temp_segment)
                            ]
                            res2 = subprocess.run(cmd_no_audio, capture_output=True, text=True, creationflags=creation_flags)
                            if res2.returncode != 0:
                                raise RuntimeError(f"FFmpeg trim error: {res2.stderr}")
                            
                    trimmed_paths.append(temp_segment)
                    self.scene_done.emit(idx, str(temp_segment))

                if self._cancelled:
                    self.progress.emit("Đã dừng")
                    return
                    
                list_file = temp_dir_path / "list.txt"
                with open(list_file, "w", encoding="utf-8") as f:
                    for p in trimmed_paths:
                        escaped_path = str(p).replace("\\", "/")
                        f.write(f"file '{escaped_path}'\n")
                        
                final_output = self.output_dir / f"merged_{int(time.time())}.mp4"
                
                cmd_concat = [
                    str(FFMPEG_PATH), "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", str(list_file),
                    "-c", "copy",
                    str(final_output)
                ]
                
                log.info(f"LongVideoWorker: Concatenating scenes: {' '.join(cmd_concat)}")
                res_concat = subprocess.run(cmd_concat, capture_output=True, text=True, creationflags=creation_flags)
                if res_concat.returncode != 0:
                    raise RuntimeError(f"FFmpeg concat error: {res_concat.stderr}")
                    
                self.all_done.emit(str(final_output).replace("\\", "/"))
                
        except Exception as e:
            self.error.emit(str(e))


class _PromptRow(QFrame):
    delete_requested = Signal(object)
    move_up_requested = Signal(object)
    move_down_requested = Signal(object)
    value_changed = Signal()

    def __init__(self, index, parent=None):
        super().__init__(parent)
        self.index = index
        self.video_path = ""
        self.duration = 0.0
        self.start_trim = 0.0
        self.end_trim = 0.0
        self.audio_muted = False
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("QFrame { background: #131a2c; border: 1px solid #2d3449; border-radius: 8px; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        self.index_label = QLabel(f"Cảnh {self.index}")
        self.index_label.setStyleSheet("color: #fbbf24; font-weight: 600; min-width: 46px;")
        top_row.addWidget(self.index_label)

        self.video_label = QLabel("Chưa chọn video (Nhấp để chọn từ lịch sử...)")
        self.video_label.setStyleSheet("color: #94a3b8; font-style: italic;")
        self.video_label.setWordWrap(True)
        self.video_label.setMinimumWidth(80)
        self.video_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.video_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.video_label.mousePressEvent = lambda ev: self._on_select_clicked()
        top_row.addWidget(self.video_label, 1)

        self.btn_select = QPushButton("Chọn")
        self.btn_select.setFixedWidth(64)
        self.btn_select.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_select.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #3b82f6;
            }
        """)
        self.btn_select.clicked.connect(self._on_select_clicked)
        top_row.addWidget(self.btn_select)

        # Play/Pause Preview Button
        self.btn_play_preview = QPushButton("▶")
        self.btn_play_preview.setFixedWidth(36)
        self.btn_play_preview.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_play_preview.setEnabled(False) # Disabled until a video is selected
        self.btn_play_preview.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #3b82f6;
                border: 1px solid #334155;
                border-radius: 6px;
                font-size: 14px;
                padding: 4px;
            }
            QPushButton:hover:enabled {
                background-color: #334155;
            }
            QPushButton:disabled {
                color: #4b5563;
            }
        """)
        self.btn_play_preview.clicked.connect(self._on_play_preview_clicked)
        top_row.addWidget(self.btn_play_preview)

        self.btn_mute = QPushButton("🔊")
        self.btn_mute.setFixedWidth(36)
        self.btn_mute.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_mute.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #10b981;
                border: 1px solid #334155;
                border-radius: 6px;
                font-size: 14px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #334155;
            }
        """)
        self.btn_mute.clicked.connect(self._on_toggle_mute)
        top_row.addWidget(self.btn_mute)

        self.btn_up = QPushButton("▲")
        self.btn_up.setFixedWidth(36)
        self.btn_up.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_up.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
            }
        """)
        self.btn_up.clicked.connect(lambda: self.move_up_requested.emit(self))
        top_row.addWidget(self.btn_up)

        self.btn_down = QPushButton("▼")
        self.btn_down.setFixedWidth(36)
        self.btn_down.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_down.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
            }
        """)
        self.btn_down.clicked.connect(lambda: self.move_down_requested.emit(self))
        top_row.addWidget(self.btn_down)

        self.btn_delete = QPushButton("🗑️")
        self.btn_delete.setFixedWidth(36)
        self.btn_delete.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_delete.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #ef4444;
                border: 1px solid #ef4444;
                border-radius: 6px;
                font-size: 13px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: #ffffff;
            }
        """)
        self.btn_delete.clicked.connect(lambda: self.delete_requested.emit(self))
        top_row.addWidget(self.btn_delete)

        layout.addLayout(top_row)

        self.trim_widget = QWidget()
        trim_layout = QHBoxLayout(self.trim_widget)
        trim_layout.setContentsMargins(58, 0, 0, 0)
        trim_layout.setSpacing(10)

        trim_layout.addWidget(QLabel("Cắt:"))
        
        self.range_slider = QRangeSlider()
        self.range_slider.rangeChanged.connect(self._on_slider_changed)
        trim_layout.addWidget(self.range_slider, 1)

        self.trim_info = QLabel("0.0s - 0.0s")
        self.trim_info.setStyleSheet("color: #fbbf24; font-weight: bold; min-width: 90px;")
        trim_layout.addWidget(self.trim_info)

        layout.addWidget(self.trim_widget)
        self.trim_widget.hide()

    def _update_play_icon(self, playing):
        self.btn_play_preview.setIcon(QIcon())
        self.btn_play_preview.setText("⏸" if playing else "▶")

    def _on_play_preview_clicked(self):
        p = self.parent()
        while p and not hasattr(p, "play_scene_preview"):
            p = p.parent()
        if p:
            p.play_scene_preview(self)

    def _on_toggle_mute(self):
        self.audio_muted = not self.audio_muted
        if self.audio_muted:
            self.btn_mute.setText("🔇")
            self.btn_mute.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b;
                    color: #ef4444;
                    border: 1px solid #ef4444;
                    border-radius: 6px;
                    font-size: 14px;
                    padding: 4px;
                }
                QPushButton:hover {
                    background-color: rgba(239, 68, 68, 0.1);
                }
            """)
        else:
            self.btn_mute.setText("🔊")
            self.btn_mute.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b;
                    color: #10b981;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    font-size: 14px;
                    padding: 4px;
                }
                QPushButton:hover {
                    background-color: #334155;
                }
            """)
        self.value_changed.emit()

    def set_index(self, index):
        self.index = index
        self.index_label.setText(f"Cảnh {index}")

    def set_video(self, path):
        self.video_path = path
        if not path:
            self.video_label.setText("Chưa chọn video (Nhấp để chọn từ lịch sử...)")
            self.video_label.setStyleSheet("color: #94a3b8; font-style: italic;")
            self.btn_play_preview.setEnabled(False)
            self._update_play_icon(False)
            self.trim_widget.hide()
            self.duration = 0.0
            self.start_trim = 0.0
            self.end_trim = 0.0
            self.value_changed.emit()
            return

        self.video_label.setText(Path(path).name)
        self.video_label.setStyleSheet("color: #e5e7eb; font-weight: 500; font-style: normal;")
        self.btn_play_preview.setEnabled(True)
        self._update_play_icon(False)
        
        self.duration = get_video_duration(path)
        if self.duration <= 0.1:
            self.duration = 10.0

        self.range_slider.setRange(0.0, self.duration)
        self.range_slider.setValues(0.0, self.duration)
        self.start_trim = 0.0
        self.end_trim = self.duration
        self.trim_info.setText(f"0.0s - {self.duration:.1f}s")
        self.trim_widget.show()
        self.value_changed.emit()

    def _on_slider_changed(self, start, end):
        self.start_trim = start
        self.end_trim = end
        self.trim_info.setText(f"{start:.1f}s - {end:.1f}s")
        
        p = self.parent()
        while p and not hasattr(p, "play_scene_preview"):
            p = p.parent()
        if p and p._preview_row == self:
            p.update_preview_bounds()
            
        self.value_changed.emit()

    def _on_select_clicked(self):
        from ui.workflow.history_picker_dialog import HistoryPickerDialog
        main_win = None
        for w in QApplication.topLevelWidgets():
            if hasattr(w, "db"):
                main_win = w
                break
        
        dialog = HistoryPickerDialog(main_win, media_type="video", multi_select=True, parent=main_win)
        if dialog.exec():
            items = dialog.selected_items
            if items:
                # Find the parent LongVideoPage and distribute selected videos sequentially
                p = self.parent()
                while p and not isinstance(p, LongVideoPage):
                    p = p.parent()
                if p:
                    p.populate_batch_videos(self, items)

    def set_read_only(self, value):
        self.btn_select.setEnabled(not value)
        self.btn_play_preview.setEnabled(not value and bool(self.video_path))
        self.btn_mute.setEnabled(not value)
        self.btn_up.setEnabled(not value)
        self.btn_down.setEnabled(not value)
        self.btn_delete.setEnabled(not value)
        self.range_slider.setEnabled(not value)


class LongVideoPage(QWidget):
    DEFAULT_SCENES = 3
    MAX_SCENES = 20

    def __init__(self, db=None, browser_mgr=None, settings=None, parent=None):
        super().__init__(parent)
        self._db = db
        self._browser_mgr = browser_mgr
        self._settings = settings
        self._worker = None
        self._prompt_rows = []
        self._final_path = None
        self._preview_row = None
        self.player_icon_paths = ensure_player_icons()
        self._init_ui()

    def _init_ui(self):
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)

        # Left panel container (fixed width, fixed position buttons at the bottom)
        self.left_container = QWidget()
        self.left_container.setFixedWidth(580)
        left = QVBoxLayout(self.left_container)
        left.setContentsMargins(16, 16, 16, 16)
        left.setSpacing(12)

        title = QLabel("Nối khung hình")
        title.setProperty("class", "section-title")
        desc = QLabel("Ghép nối nhiều video liên tiếp từ lịch sử và cắt ghép timeline theo ý muốn.")
        desc.setStyleSheet("color: #8c909f; font-size: 12px;")
        desc.setWordWrap(True)
        left.addWidget(title)
        left.addWidget(desc)

        top_actions = QHBoxLayout()
        self._add_btn = QPushButton("+ Thêm cảnh")
        self._add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._add_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 6px;
                font-weight: bold;
                padding: 6px 14px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2563eb;
                border-color: #2563eb;
            }
        """)
        self._add_btn.clicked.connect(self._on_add_scene)
        
        top_actions.addWidget(self._add_btn)
        left.addLayout(top_actions)

        self._scene_count_label = QLabel()
        self._scene_count_label.setStyleSheet("color: #8c909f; font-size: 12px;")
        left.addWidget(self._scene_count_label)

        # Scroll area for scene list (only the scene list itself scrolls)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("""
            QScrollArea { 
                border: 1px solid #2d3449; 
                border-radius: 8px; 
                background-color: #070b12;
            }
            QScrollBar:vertical {
                border: none;
                background: #0f172a;
                width: 10px;
                margin: 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #334155;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #2563eb;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
                height: 0px;
            }
        """)
        rows_host = QWidget()
        self._rows_layout = QVBoxLayout(rows_host)
        self._rows_layout.setContentsMargins(10, 10, 10, 10)
        self._rows_layout.setSpacing(8)
        self._scroll.setWidget(rows_host)
        left.addWidget(self._scroll, 1)

        left.addWidget(QLabel("Thư mục lưu:"))
        out_row = QHBoxLayout()
        self.output_edit = QLineEdit(str(DEFAULT_VIDEO_OUTPUT))
        self.output_edit.setReadOnly(True)
        self.output_edit.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.output_edit.mousePressEvent = lambda ev: self._on_browse_output()
        self.output_edit.setStyleSheet("""
            QLineEdit {
                background-color: #0f172a;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        browse_out = QPushButton("Thư mục")
        browse_out.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        browse_out.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #334155;
            }
        """)
        browse_out.clicked.connect(self._on_browse_output)
        out_row.addWidget(self.output_edit, 1)
        out_row.addWidget(browse_out)
        left.addLayout(out_row)

        action_row = QHBoxLayout()
        
        self.start_btn = QPushButton("Bắt đầu nối")
        self.start_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
            QPushButton:disabled {
                background-color: #1f2937;
                color: #4b5563;
            }
        """)
        self.start_btn.clicked.connect(self._on_start)
        
        self.cancel_btn = QPushButton("Dừng")
        self.cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
            QPushButton:disabled {
                background-color: #1f2937;
                color: #4b5563;
            }
        """)
        self.cancel_btn.clicked.connect(self._on_cancel)
        
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                font-weight: bold;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #334155;
            }
            QPushButton:disabled {
                background-color: #1f2937;
                color: #4b5563;
            }
        """)
        self.reset_btn.clicked.connect(self._on_reset)
        
        action_row.addWidget(self.start_btn)
        action_row.addWidget(self.cancel_btn)
        action_row.addWidget(self.reset_btn)
        left.addLayout(action_row)

        self.progress_label = QLabel("Sẵn sàng")
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        left.addWidget(self.progress_label)
        left.addWidget(self.progress_bar)

        # --- Right Panel: Premium Video Player & Final Download/Reload actions ---
        right = QVBoxLayout()
        self.right_host = QWidget()
        self.right_host.setLayout(right)
        right.setContentsMargins(16, 16, 16, 16)
        right.setSpacing(12)

        # Right preview container with stacked layout to prevent QVideoWidget flash
        self.right_preview_container = QWidget()
        self.right_preview_container.setMinimumHeight(380)
        self.right_preview_container.setStyleSheet("background-color: #070b12; border: 1px solid #2d3449; border-radius: 8px;")
        
        from PySide6.QtWidgets import QStackedLayout
        self.right_preview_stack = QStackedLayout(self.right_preview_container)
        self.right_preview_stack.setStackingMode(QStackedLayout.StackingMode.StackAll)
        
        self.right_player_widget = QVideoWidget(self.right_preview_container)
        palette = self.right_player_widget.palette()
        for role in [QPalette.ColorRole.Window, QPalette.ColorRole.Base, QPalette.ColorRole.Button]:
            palette.setColor(role, QColor(7, 11, 18))
        self.right_player_widget.setPalette(palette)
        self.right_player_widget.setAutoFillBackground(True)
        self.right_player_widget.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.right_player_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.right_player_widget.setStyleSheet("background-color: #070b12; border: none; border-radius: 8px;")
        setup_rounded_mask(self.right_player_widget, 8)
        
        self.right_placeholder = QLabel("Kết quả ghép nối sẽ hiển thị tại đây", self.right_preview_container)
        self.right_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.right_placeholder.setStyleSheet("""
            QLabel {
                color: #64748b; 
                background: #070b12; 
                border: none; 
                border-radius: 8px; 
                font-size: 14px;
                font-weight: 500;
            }
        """)
        
        self.right_preview_stack.addWidget(self.right_player_widget)
        self.right_preview_stack.addWidget(self.right_placeholder)
        right.addWidget(self.right_preview_container, 1)

        self._current_right_vid = False
        self.right_player = QMediaPlayer()
        self.right_audio_output = QAudioOutput()
        self.right_player.setAudioOutput(self.right_audio_output)
        self.right_player.setVideoOutput(self.right_player_widget)
        self.right_player.setLoops(QMediaPlayer.Loops.Infinite)
        self.right_player.positionChanged.connect(self._on_player_position_changed)
        self.right_player.mediaStatusChanged.connect(self._on_right_media_status_changed)

        # Center-aligned controls
        self.right_controls = QWidget()
        self.right_controls.setFixedHeight(44)
        controls_lay = QHBoxLayout(self.right_controls)
        controls_lay.setContentsMargins(0, 0, 0, 0)
        controls_lay.setSpacing(12)

        controls_lay.addStretch(1)

        btn_style = """
            QPushButton {
                background-color: #1e293b;
                color: #ffffff;
                border: 1px solid #334155;
                border-radius: 18px;
                font-size: 14px;
                font-weight: bold;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #2563eb;
                border-color: #2563eb;
            }
        """

        self.btn_right_play = QPushButton("▶")
        self.btn_right_play.setFixedSize(36, 36)
        self.btn_right_play.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_right_play.setStyleSheet(btn_style)
        self.btn_right_play.clicked.connect(self._toggle_right_play)
        controls_lay.addWidget(self.btn_right_play)

        self.btn_right_mute = QPushButton("🔊")
        self.btn_right_mute.setFixedSize(36, 36)
        self.btn_right_mute.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_right_mute.setStyleSheet(btn_style)
        self.btn_right_mute.clicked.connect(self._toggle_right_mute)
        controls_lay.addWidget(self.btn_right_mute)

        # Premium 3-dot Option Button
        self.btn_right_more = QPushButton("⋮")
        self.btn_right_more.setFixedSize(36, 36)
        self.btn_right_more.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_right_more.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #ffffff;
                border: 1px solid #334155;
                border-radius: 18px;
                font-size: 16px;
                font-weight: bold;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #334155;
            }
        """)
        self.btn_right_more.clicked.connect(self._show_player_menu)
        controls_lay.addWidget(self.btn_right_more)
        
        controls_lay.addStretch(1)
        right.addWidget(self.right_controls)
        self.right_controls.hide()

        # Output info label (hidden to match design)
        self.final_label = QLabel("")
        self.final_label.hide()

        # Action Buttons Layout
        self.right_actions_layout = QHBoxLayout()

        self.btn_download = QPushButton("💾 Tải xuống")
        self.btn_download.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_download.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #3b82f6;
            }
        """)
        self.btn_download.clicked.connect(self._on_download_video)
        self.right_actions_layout.addWidget(self.btn_download)

        self.btn_reload = QPushButton("🔄 Chạy lại")
        self.btn_reload.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_reload.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        self.btn_reload.clicked.connect(self._on_reload)
        self.right_actions_layout.addWidget(self.btn_reload)
        
        right.addLayout(self.right_actions_layout)

        main.addWidget(self.left_container, 0)
        main.addWidget(self.right_host, 1)

        for _ in range(self.DEFAULT_SCENES):
            self._add_row()
        self._refresh_scene_count()
        self._set_running_ui(False)

    def _toggle_right_play(self):
        if self.right_player:
            if self.right_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.right_player.pause()
                self.btn_right_play.setIcon(QIcon())
                self.btn_right_play.setText("▶")
                if self._preview_row:
                    self._preview_row._update_play_icon(False)
            else:
                if self._preview_row:
                    curr_pos = self.right_player.position()
                    start_ms = int(self._preview_row.start_trim * 1000)
                    end_ms = int(self._preview_row.end_trim * 1000)
                    if curr_pos < start_ms or curr_pos >= end_ms:
                        self.right_player.setPosition(start_ms)
                self.right_player.play()
                self.btn_right_play.setIcon(QIcon())
                self.btn_right_play.setText("⏸")
                if self._preview_row:
                    self._preview_row._update_play_icon(True)

    def _toggle_right_mute(self):
        if self.right_audio_output:
            is_muted = self.right_audio_output.isMuted()
            self.right_audio_output.setMuted(not is_muted)
            self.btn_right_mute.setIcon(QIcon())
            self.btn_right_mute.setText("🔇" if not is_muted else "🔊")

    def _reset_right_player(self):
        self._current_right_vid = False
        if self.right_player:
            self.right_player.stop()
            self.right_player.setSource(QUrl())
        if self._preview_row:
            self._preview_row._update_play_icon(False)
            self._preview_row = None
        if hasattr(self, "btn_right_play") and self.btn_right_play:
            self.btn_right_play.setIcon(QIcon())
            self.btn_right_play.setText("▶")
        if self.right_controls:
            self.right_controls.hide()
        self.right_placeholder.setText("Kết quả ghép nối sẽ hiển thị tại đây")
        self.right_placeholder.setStyleSheet("""
            QLabel {
                color: #64748b; 
                background: #070b12; 
                border: none; 
                border-radius: 8px; 
                font-size: 14px;
                font-weight: 500;
            }
        """)
        self.right_placeholder.show()
        self.final_label.setText("Chưa có kết quả ghép nối")

    def _on_right_media_status_changed(self, status):
        from PySide6.QtMultimedia import QMediaPlayer
        if status in (QMediaPlayer.MediaStatus.BufferedMedia, QMediaPlayer.MediaStatus.LoadedMedia):
            if hasattr(self, "_current_right_vid") and self._current_right_vid:
                self.right_placeholder.hide()

    def _reset_preview(self):
        self._reset_right_player()

    def _on_download_video(self):
        if not self._final_path or not Path(self._final_path).exists():
            QMessageBox.warning(self, "Tải xuống", "Không tìm thấy file kết quả để tải xuống.")
            return
            
        file_dir, file_name = QFileDialog.getSaveFileName(
            self, "Tải xuống video", str(Path.home() / Path(self._final_path).name), "Video Files (*.mp4)"
        )
        if file_dir:
            try:
                shutil.copy2(self._final_path, file_dir)
                QMessageBox.information(self, "Tải xuống", f"Đã tải xuống video thành công về:\n{file_dir}")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi tải xuống", f"Không thể tải xuống video: {e}")

    def _on_reload(self):
        self._on_start()

    def _add_row(self):
        row = _PromptRow(len(self._prompt_rows) + 1)
        row.delete_requested.connect(self._on_delete_row)
        row.move_up_requested.connect(self._move_row_up)
        row.move_down_requested.connect(self._move_row_down)
        row.value_changed.connect(self._refresh_scene_count)
        self._prompt_rows.append(row)
        self._rows_layout.addWidget(row)
        self._refresh_scene_count()
        return row

    def _relayout_prompts(self):
        for idx, row in enumerate(self._prompt_rows, 1):
            row.set_index(idx)
        self._refresh_scene_count()

    def populate_batch_videos(self, start_row, items):
        try:
            start_idx = self._prompt_rows.index(start_row)
        except ValueError:
            return
            
        for i, item in enumerate(items):
            target_idx = start_idx + i
            while target_idx >= len(self._prompt_rows):
                if len(self._prompt_rows) >= self.MAX_SCENES:
                    break
                self._add_row()
                
            if target_idx < len(self._prompt_rows):
                self._prompt_rows[target_idx].set_video(item["path"])
                
        self._refresh_scene_count()

    def _move_row_up(self, row):
        index = self._prompt_rows.index(row)
        if index > 0:
            self._prompt_rows[index - 1], self._prompt_rows[index] = self._prompt_rows[index], self._prompt_rows[index - 1]
            self._rebuild_rows()

    def _move_row_down(self, row):
        index = self._prompt_rows.index(row)
        if index < len(self._prompt_rows) - 1:
            self._prompt_rows[index + 1], self._prompt_rows[index] = self._prompt_rows[index], self._prompt_rows[index + 1]
            self._rebuild_rows()

    def _rebuild_rows(self):
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
        for row in self._prompt_rows:
            self._rows_layout.addWidget(row)
        self._relayout_prompts()

    def _on_add_scene(self):
        if len(self._prompt_rows) >= self.MAX_SCENES:
            return
        self._add_row()

    def _on_delete_row(self, row):
        if len(self._prompt_rows) <= 1:
            return
        if row in self._prompt_rows:
            self._prompt_rows.remove(row)
            row.setParent(None)
            self._rebuild_rows()

    def _refresh_scene_count(self):
        total_count = len(self._prompt_rows)
        self._scene_count_label.setText(f"Số cảnh: {total_count}")

    def _on_browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục Output")
        if path:
            self.output_edit.setText(path)

    def _set_running_ui(self, running):
        self.start_btn.setEnabled(not running)
        self.start_btn.setText("Đang ghép nối..." if running else "Bắt đầu nối")
        self.cancel_btn.setEnabled(running)
        self._add_btn.setEnabled((not running) and len(self._prompt_rows) < self.MAX_SCENES)
        for row in self._prompt_rows:
            row.set_read_only(running)
        self.output_edit.setEnabled(not running)
        self.reset_btn.setEnabled(not running)

    def _collect_scenes(self) -> list[dict]:
        scenes = []
        for row in self._prompt_rows:
            if row.video_path:
                scenes.append({
                    "video_path": row.video_path,
                    "start_trim": row.start_trim,
                    "end_trim": row.end_trim,
                    "mute_audio": row.audio_muted
                })
        return scenes

    def _on_start(self):
        scenes = self._collect_scenes()
        if not scenes:
            QMessageBox.warning(self, "Nối khung hình", "Chưa chọn video nào để ghép nối.")
            return
            
        out_dir = Path(self.output_edit.text().strip() or DEFAULT_VIDEO_OUTPUT)
        self.progress_bar.show()
        self.progress_bar.setRange(0, len(scenes))
        self.progress_bar.setValue(0)
        self.progress_label.setText("Đang chuẩn bị ghép nối...")
        
        self._reset_right_player()
        self.final_label.setText("Đang xử lý...")
        self._final_path = None
        
        self._worker = LongVideoWorker(
            scenes,
            out_dir,
            self
        )
        self._worker.chain_started.connect(self._on_chain_started)
        self._worker.scene_started.connect(self._on_scene_started)
        self._worker.scene_done.connect(self._on_scene_done)
        self._worker.scene_failed.connect(self._on_scene_failed)
        self._worker.progress.connect(self._on_progress)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.error.connect(self._on_worker_error)
        self._worker.finished.connect(self._on_worker_finished)
        self._set_running_ui(True)
        self._worker.start()

    def _on_cancel(self):
        if self._worker:
            self._worker.cancel()
        self._set_running_ui(False)
        self._reset_right_player()

    def _on_reset(self):
        while len(self._prompt_rows) > 0:
            row = self._prompt_rows.pop()
            row.setParent(None)
            row.deleteLater()
            
        for _ in range(self.DEFAULT_SCENES):
            self._add_row()
            
        self._rebuild_rows()
        self.progress_label.setText("Sẵn sàng")
        self.progress_bar.hide()
        self._reset_right_player()
        self._final_path = None

    def _on_chain_started(self, output_dir):
        self.progress_label.setText(f"Đầu ra: {output_dir}")

    def _on_scene_started(self, index, total):
        self.progress_label.setText(f"Đang xử lý cảnh {index}/{total}")
    def _on_scene_done(self, index, path):
        self.progress_bar.setValue(index)
        self.progress_label.setText(f"Đã xử lý xong cảnh {index}")

    def _on_scene_failed(self, index, error):
        self.progress_label.setText(f"Cảnh {index} gặp lỗi: {error}")

    def _on_progress(self, text):
        self.progress_label.setText(str(text))

    def _on_all_done(self, final_path):
        self._final_path = final_path
        self.progress_label.setText("Ghép nối hoàn tất!")
        self.final_label.setText(f"File ghép nối thành công:\n{final_path}")
        
        # Reset any active preview row playback button
        if self._preview_row:
            self._preview_row._update_play_icon(False)
            self._preview_row = None

        self._ensure_right_player()

        self._current_right_vid = True
        self.right_placeholder.setText("Loading...")
        self.right_placeholder.show()
        self.right_controls.show()
        
        self.right_player.setSource(QUrl.fromLocalFile(final_path))
        self.right_player.play()
        self.btn_right_play.setIcon(QIcon())
        self.btn_right_play.setText("⏸")
        self.btn_right_mute.setIcon(QIcon())
        self.btn_right_mute.setText("🔊")
        self.right_audio_output.setMuted(False)
        
        QMessageBox.information(self, "Thành công", f"Đã ghép nối xong video:\n{final_path}")
 
    def _ensure_right_player(self):
        pass
 
    def play_scene_preview(self, row):
        if not row.video_path:
            return
            
        self._ensure_right_player()
        
        # If this row is already playing, pause it
        if self._preview_row == row and self.right_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.right_player.pause()
            row._update_play_icon(False)
            self.btn_right_play.setIcon(QIcon())
            self.btn_right_play.setText("▶")
            return
            
        # Stop previous row preview button if any
        if self._preview_row and self._preview_row != row:
            self._preview_row._update_play_icon(False)
            
        self._preview_row = row
        
        self._current_right_vid = True
        self.right_placeholder.setText("Loading...")
        self.right_placeholder.show()
        self.right_controls.show()
        
        # Load video file if it changed
        file_url = QUrl.fromLocalFile(row.video_path)
        if self.right_player.source() != file_url:
            self.right_player.setSource(file_url)
            
        # Seek to start_trim
        self.right_player.setPosition(int(row.start_trim * 1000))
        self.right_player.play()
        
        row._update_play_icon(True)
        self.btn_right_play.setIcon(QIcon())
        self.btn_right_play.setText("⏸")
        
        # Unmute player if muted (to match standard video play)
        self.btn_right_mute.setIcon(QIcon())
        self.btn_right_mute.setText("🔊")
        self.right_audio_output.setMuted(False)

    def update_preview_bounds(self):
        if self._preview_row and self.right_player:
            start_ms = int(self._preview_row.start_trim * 1000)
            end_ms = int(self._preview_row.end_trim * 1000)
            curr_pos = self.right_player.position()
            if curr_pos < start_ms or curr_pos > end_ms:
                self.right_player.setPosition(start_ms)

    def _on_player_position_changed(self, pos):
        if self._preview_row:
            start_ms = int(self._preview_row.start_trim * 1000)
            end_ms = int(self._preview_row.end_trim * 1000)
            if pos < start_ms:
                self.right_player.setPosition(start_ms)
            elif pos >= end_ms:
                if self.right_player.loops() == QMediaPlayer.Loops.Infinite:
                    self.right_player.setPosition(start_ms)
                else:
                    self.right_player.pause()
                    self._preview_row._update_play_icon(False)
                    self.btn_right_play.setIcon(QIcon(self.player_icon_paths["play"]))

    def hideEvent(self, event):
        if hasattr(self, "right_player") and self.right_player:
            try:
                self.right_player.stop()
            except:
                pass
        super().hideEvent(event)

    def _on_worker_error(self, message):
        self.progress_label.setText(str(message))
        self.final_label.setText(f"Lỗi: {message}")
        log.warning(message)

    def _on_worker_finished(self):
        self._set_running_ui(False)
        self._worker = None

    def _on_final_link(self, path):
        if path:
            p = Path(path)
            if p.exists():
                folder = p.parent
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(DEFAULT_VIDEO_OUTPUT)))
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(DEFAULT_VIDEO_OUTPUT)))

    def _show_player_menu(self):
        if not self.right_player:
            return
            
        menu = QMenu(self.window())
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e293b;
                color: #ffffff;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #2563eb;
            }
        """)
        
        loop_act = menu.addAction("🔄 Phát lặp lại")
        loop_act.setCheckable(True)
        loop_act.setChecked(self.right_player.loops() == QMediaPlayer.Loops.Infinite)
        
        speed_menu = menu.addMenu("⚡ Tốc độ phát")
        speed_menu.setStyleSheet(menu.styleSheet())
        
        speeds = [0.5, 1.0, 1.5, 2.0]
        current_speed = self.right_player.playbackRate()
        for s in speeds:
            act = speed_menu.addAction(f"{s}x")
            act.setCheckable(True)
            act.setChecked(abs(current_speed - s) < 0.05)
            act.triggered.connect(lambda checked=False, val=s: self.right_player.setPlaybackRate(val))
            
        action = menu.exec(self.btn_right_more.mapToGlobal(self.btn_right_more.rect().bottomLeft()))
        if action == loop_act:
            is_looping = self.right_player.loops() == QMediaPlayer.Loops.Infinite
            self.right_player.setLoops(QMediaPlayer.Loops.Once if is_looping else QMediaPlayer.Loops.Infinite)
