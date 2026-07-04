"""Video preview dialog."""

import os
import sys
from PySide6.QtCore import QUrl, Qt, QTimer, QSize
from PySide6.QtGui import QIcon, QAction, QCursor
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QPushButton, QSlider, QVBoxLayout, 
    QLabel, QMenu, QWidget, QSizePolicy, QApplication, QFrame
)
import subprocess

class VideoPreviewDialog(QDialog):
    def __init__(self, video_path, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.setWindowTitle("Video Preview")
        self.resize(800, 500)
        
        # We need a layout with 0 margins for a sleek look
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Dark background
        self.setStyleSheet("QDialog { background-color: #0f0f13; }")

        # --- Video Widget ---
        self.video = QVideoWidget()
        self.video.setStyleSheet("background-color: black;")
        
        # --- Player and Audio ---
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setVideoOutput(self.video)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.8)

        # --- Control Bar ---
        self.control_bar = QFrame()
        self.control_bar.setStyleSheet("""
            QFrame { background-color: #1a1a24; border-top: 1px solid #2a2a35; }
            QPushButton { 
                background: transparent; color: white; border: none; font-size: 18px; padding: 5px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #333344; }
            QLabel { color: #cccccc; font-size: 12px; font-family: monospace; }
        """)
        controls_layout = QHBoxLayout(self.control_bar)
        controls_layout.setContentsMargins(10, 5, 10, 5)
        controls_layout.setSpacing(10)

        # Play/Pause
        self.btn_play = QPushButton("▶")
        self.btn_play.setFixedSize(36, 36)
        self.btn_play.clicked.connect(self._toggle_play)

        # Time Label
        self.lbl_time = QLabel("00:00 / 00:00")
        
        # Slider
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal { border: 1px solid #333; height: 6px; background: #222; border-radius: 3px; }
            QSlider::sub-page:horizontal { background: #3b82f6; border-radius: 3px; }
            QSlider::handle:horizontal { background: white; width: 12px; margin-top: -3px; margin-bottom: -3px; border-radius: 6px; }
        """)
        self.slider.sliderMoved.connect(self._on_slider_moved)

        # Audio Toggle
        self.btn_audio = QPushButton("🔊")
        self.btn_audio.setFixedSize(36, 36)
        self.btn_audio.clicked.connect(self._toggle_audio)

        # Volume Slider
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setFixedWidth(80)
        self.vol_slider.setStyleSheet(self.slider.styleSheet())
        self.vol_slider.valueChanged.connect(self._on_volume_changed)

        # Fullscreen
        self.btn_fullscreen = QPushButton("⛶")
        self.btn_fullscreen.setFixedSize(36, 36)
        self.btn_fullscreen.clicked.connect(self._toggle_fullscreen)

        # More (3 dots)
        self.btn_more = QPushButton("⋮")
        self.btn_more.setFixedSize(36, 36)
        self.btn_more.clicked.connect(self._show_menu)

        # Add to controls
        controls_layout.addWidget(self.btn_play)
        controls_layout.addWidget(self.lbl_time)
        controls_layout.addWidget(self.slider)
        controls_layout.addWidget(self.btn_audio)
        controls_layout.addWidget(self.vol_slider)
        controls_layout.addWidget(self.btn_fullscreen)
        controls_layout.addWidget(self.btn_more)

        # Add to main layout
        layout.addWidget(self.video, 1)
        layout.addWidget(self.control_bar, 0)

        # Connect player signals
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)

        # Set source and play
        self.player.setSource(QUrl.fromLocalFile(video_path))
        self.player.play()
        
        self._is_muted = False
        self._is_fullscreen = False

    def _fmt_time(self, ms):
        s = int(ms / 1000)
        return f"{s // 60:02d}:{s % 60:02d}"

    def _update_time_label(self):
        cur = self._fmt_time(self.player.position())
        tot = self._fmt_time(self.player.duration())
        self.lbl_time.setText(f"{cur} / {tot}")

    def _toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlayingState:
            self.btn_play.setText("⏸")
        else:
            self.btn_play.setText("▶")

    def _on_slider_moved(self, value):
        self.player.setPosition(value)

    def _on_position_changed(self, value):
        if not self.slider.isSliderDown():
            self.slider.setValue(value)
        self._update_time_label()

    def _on_duration_changed(self, value):
        self.slider.setMaximum(value)
        self._update_time_label()

    def _toggle_audio(self):
        self._is_muted = not self._is_muted
        self.audio_output.setMuted(self._is_muted)
        if self._is_muted:
            self.btn_audio.setText("🔇")
            self.vol_slider.setEnabled(False)
        else:
            self.btn_audio.setText("🔊")
            self.vol_slider.setEnabled(True)

    def _on_volume_changed(self, value):
        self.audio_output.setVolume(value / 100.0)
        if value == 0:
            self.btn_audio.setText("🔇")
        elif not self._is_muted:
            self.btn_audio.setText("🔊")

    def _toggle_fullscreen(self):
        if not self._is_fullscreen:
            self.showFullScreen()
            self._is_fullscreen = True
            self.btn_fullscreen.setText("🗗")
        else:
            self.showNormal()
            self._is_fullscreen = False
            self.btn_fullscreen.setText("⛶")

    def _show_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #2a2a35; color: white; border: 1px solid #3a3a45; }
            QMenu::item { padding: 8px 20px; }
            QMenu::item:selected { background-color: #3b82f6; }
        """)
        
        open_folder = QAction("Mở thư mục chứa file", self)
        open_folder.triggered.connect(self._open_folder)
        menu.addAction(open_folder)
        
        copy_path = QAction("Copy đường dẫn", self)
        copy_path.triggered.connect(self._copy_path)
        menu.addAction(copy_path)
        
        menu.exec(QCursor.pos())

    def _open_folder(self):
        if os.path.exists(self.video_path):
            folder = os.path.dirname(self.video_path)
            if os.name == 'nt':
                os.startfile(folder)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', folder])
            else:
                subprocess.Popen(['xdg-open', folder])

    def _copy_path(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.video_path)

    def closeEvent(self, event):
        self.player.stop()
        super().closeEvent(event)
