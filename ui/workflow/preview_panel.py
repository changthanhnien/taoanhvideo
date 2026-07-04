"""Preview panel for viewing workflow node results.

Provides image thumbnails, video thumbnails with play overlays, text preview,
plus full-screen zoomable image and video player dialogs.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal, QSize, QPoint, QPointF, QUrl, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QImage,
    QPainter,
    QPen,
    QPixmap,
    QWheelEvent,
    QMouseEvent,
    QKeyEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from utils.logger import log

# ---------------------------------------------------------------------------
# Theme tokens
# ---------------------------------------------------------------------------
_BG_APP = "#0f1115"
_BG_SURFACE = "#16191f"
_BG_CARD = "#1b2028"
_BG_INPUT = "#1b2028"
_BORDER = "#2a3140"
_TEXT = "#e2e8f0"
_TEXT_MUTED = "#8b949e"
_ACCENT = "#3b82f6"
_ACCENT_HOVER = "#60a5fa"
_DANGER = "#ef4444"
_SUCCESS = "#10b981"
_WARNING = "#f59e0b"

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff", ".tif"}
_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv", ".flv"}

# Try importing multimedia widgets – they may not be available in all
# PySide6 installations.
_multimedia_available = False
try:
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PySide6.QtMultimediaWidgets import QVideoWidget
    _multimedia_available = True
except Exception:
    pass


# ============================================================================
# Helper: generate a thumbnail QPixmap for images
# ============================================================================

def _make_thumbnail(path: str, size: int = 160) -> QPixmap:
    """Return a scaled QPixmap for *path*, or a placeholder on error."""
    pm = QPixmap(path)
    if pm.isNull():
        pm = QPixmap(size, size)
        pm.fill(QColor(_BG_CARD))
        painter = QPainter(pm)
        painter.setPen(QColor(_TEXT_MUTED))
        painter.drawText(pm.rect(), Qt.AlignCenter, "?")
        painter.end()
        return pm
    return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def _make_video_thumbnail(path: str, size: int = 160) -> QPixmap:
    """Return a placeholder thumbnail with a ▶ overlay for video files."""
    pm = QPixmap(size, size)
    pm.fill(QColor(_BG_CARD))
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)

    # Dark card background
    painter.fillRect(pm.rect(), QColor(_BG_CARD))

    # Film icon area
    painter.setPen(QPen(QColor(_BORDER), 1))
    inner = pm.rect().adjusted(20, 20, -20, -20)
    painter.drawRoundedRect(inner, 8, 8)

    # Play triangle
    painter.setBrush(QColor(_ACCENT))
    painter.setPen(Qt.NoPen)
    cx, cy = size // 2, size // 2
    tri_size = size // 5
    painter.drawPolygon([
        QPoint(cx - tri_size // 2, cy - tri_size),
        QPoint(cx - tri_size // 2, cy + tri_size),
        QPoint(cx + tri_size, cy),
    ])

    # File name
    painter.setPen(QColor(_TEXT_MUTED))
    font = QFont("Inter", 8)
    painter.setFont(font)
    name = Path(path).name
    if len(name) > 20:
        name = name[:17] + "…"
    painter.drawText(pm.rect().adjusted(4, 0, -4, -4), Qt.AlignBottom | Qt.AlignHCenter, name)
    painter.end()
    return pm


# ============================================================================
# Styled button helper
# ============================================================================

def _icon_button(text: str = "", tooltip: str = "", size: int = 32, parent: QWidget | None = None) -> QToolButton:
    btn = QToolButton(parent)
    btn.setText(text)
    btn.setToolTip(tooltip)
    btn.setFixedSize(size, size)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(f"""
        QToolButton {{
            background: {_BG_CARD};
            color: {_TEXT};
            border: 1px solid {_BORDER};
            border-radius: 6px;
            font-size: 14px;
        }}
        QToolButton:hover {{
            background: {_ACCENT};
            border-color: {_ACCENT};
        }}
    """)
    return btn


# ============================================================================
# PreviewImageDialog – fullscreen zoomable image viewer
# ============================================================================

class PreviewImageDialog(QDialog):
    """Full-screen dark image viewer with zoom, pan, and prev/next navigation."""

    def __init__(
        self,
        image_paths: list[str],
        start_index: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._paths = image_paths
        self._index = max(0, min(start_index, len(image_paths) - 1))
        self._zoom = 1.0
        self._pan_offset = QPointF(0, 0)
        self._dragging = False
        self._drag_start = QPointF()
        self._pixmap = QPixmap()

        self.setWindowTitle("Xem ảnh")
        self.setMinimumSize(800, 600)
        self.setStyleSheet(f"background: {_BG_APP};")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)

        self._setup_ui()
        self._load_image()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Canvas
        self._canvas = QLabel()
        self._canvas.setAlignment(Qt.AlignCenter)
        self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._canvas.setStyleSheet(f"background: {_BG_APP};")
        self._canvas.setMouseTracking(True)
        layout.addWidget(self._canvas, 1)

        # Bottom toolbar
        bar = QWidget()
        bar.setFixedHeight(48)
        bar.setStyleSheet(f"background: {_BG_SURFACE}; border-top: 1px solid {_BORDER};")
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(12, 0, 12, 0)

        self._btn_prev = _icon_button("◀", "Ảnh trước", parent=self)
        self._btn_prev.clicked.connect(self._prev)
        bar_layout.addWidget(self._btn_prev)

        self._lbl_counter = QLabel()
        self._lbl_counter.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: 12px;")
        self._lbl_counter.setAlignment(Qt.AlignCenter)
        bar_layout.addWidget(self._lbl_counter, 1)

        self._btn_next = _icon_button("▶", "Ảnh sau", parent=self)
        self._btn_next.clicked.connect(self._next)
        bar_layout.addWidget(self._btn_next)

        bar_layout.addSpacing(24)

        self._btn_zoom_in = _icon_button("+", "Phóng to", parent=self)
        self._btn_zoom_in.clicked.connect(lambda: self._apply_zoom(1.25))
        bar_layout.addWidget(self._btn_zoom_in)

        self._btn_zoom_out = _icon_button("−", "Thu nhỏ", parent=self)
        self._btn_zoom_out.clicked.connect(lambda: self._apply_zoom(0.8))
        bar_layout.addWidget(self._btn_zoom_out)

        self._btn_fit = _icon_button("⊡", "Vừa khung", parent=self)
        self._btn_fit.clicked.connect(self._fit_to_view)
        bar_layout.addWidget(self._btn_fit)

        bar_layout.addSpacing(24)

        self._btn_copy = _icon_button("📋", "Sao chép", parent=self)
        self._btn_copy.clicked.connect(self._copy_to_clipboard)
        bar_layout.addWidget(self._btn_copy)

        self._btn_close = _icon_button("✕", "Đóng", parent=self)
        self._btn_close.clicked.connect(self.close)
        bar_layout.addWidget(self._btn_close)

        layout.addWidget(bar)

    def _copy_to_clipboard(self) -> None:
        if not self._paths or self._index >= len(self._paths):
            return
        path = self._paths[self._index]
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QImage
        from PySide6.QtCore import QMimeData, QUrl
        import os
        if not os.path.exists(path): return
        clipboard = QApplication.clipboard()
        mime = QMimeData()
        is_img = path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
        if is_img:
            mime.setImageData(QImage(path))
        mime.setUrls([QUrl.fromLocalFile(path)])
        clipboard.setMimeData(mime)

    def contextMenuEvent(self, event):
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #1b2028; border: 1px solid #2a3140; color: #e2e8f0; border-radius: 4px; }
            QMenu::item { padding: 6px 24px; }
            QMenu::item:selected { background: #3b82f6; }
        """)
        copy_action = menu.addAction("📋 Sao chép")
        action = menu.exec(event.globalPos())
        if action == copy_action:
            self._copy_to_clipboard()

    # -- Image loading / rendering ----------------------------------------

    def _load_image(self) -> None:
        if not self._paths:
            return
        path = self._paths[self._index]
        self._pixmap = QPixmap(path)
        self._zoom = 1.0
        self._pan_offset = QPointF(0, 0)
        self._fit_to_view()
        self._update_counter()

    def _update_counter(self) -> None:
        self._lbl_counter.setText(f"{self._index + 1} / {len(self._paths)}")
        has_prev = self._index > 0
        has_next = self._index < len(self._paths) - 1
        self._btn_prev.setEnabled(has_prev)
        self._btn_next.setEnabled(has_next)

    def _render(self) -> None:
        if self._pixmap.isNull():
            return
        canvas_size = self._canvas.size()
        result = QPixmap(canvas_size)
        result.fill(QColor(_BG_APP))

        painter = QPainter(result)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        scaled_w = int(self._pixmap.width() * self._zoom)
        scaled_h = int(self._pixmap.height() * self._zoom)
        scaled = self._pixmap.scaled(scaled_w, scaled_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        x = (canvas_size.width() - scaled.width()) / 2 + self._pan_offset.x()
        y = (canvas_size.height() - scaled.height()) / 2 + self._pan_offset.y()
        painter.drawPixmap(int(x), int(y), scaled)
        painter.end()

        self._canvas.setPixmap(result)

    def _fit_to_view(self) -> None:
        if self._pixmap.isNull():
            return
        cw = self._canvas.width() or 800
        ch = self._canvas.height() or 600
        zx = cw / max(self._pixmap.width(), 1)
        zy = ch / max(self._pixmap.height(), 1)
        self._zoom = min(zx, zy, 1.0)  # Don't upscale beyond 100%
        self._pan_offset = QPointF(0, 0)
        self._render()

    def _apply_zoom(self, factor: float) -> None:
        self._zoom = max(0.1, min(self._zoom * factor, 20.0))
        self._render()

    # -- Navigation -------------------------------------------------------

    def _prev(self) -> None:
        if self._index > 0:
            self._index -= 1
            self._load_image()

    def _next(self) -> None:
        if self._index < len(self._paths) - 1:
            self._index += 1
            self._load_image()

    # -- Events -----------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        factor = 1.1 if delta > 0 else 0.9
        self._apply_zoom(factor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_start = event.position()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            delta = event.position() - self._drag_start
            self._pan_offset += delta
            self._drag_start = event.position()
            self._render()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._dragging = False

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Left:
            self._prev()
        elif event.key() == Qt.Key_Right:
            self._next()
        elif event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal:
            self._apply_zoom(1.25)
        elif event.key() == Qt.Key_Minus:
            self._apply_zoom(0.8)
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(50, self._fit_to_view)


# ============================================================================
# PreviewVideoDialog – video player
# ============================================================================

class PreviewVideoDialog(QDialog):
    """Dark-themed video player dialog with play/pause, seek, and navigation."""

    def __init__(
        self,
        video_paths: list[str],
        start_index: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._paths = video_paths
        self._index = max(0, min(start_index, len(video_paths) - 1))

        self.setWindowTitle("Phát video")
        self.setMinimumSize(854, 530)
        self.setStyleSheet(f"background: {_BG_APP};")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)

        self._player: QMediaPlayer | None = None
        self._audio: QAudioOutput | None = None
        self._video_widget: QVideoWidget | None = None
        self._playing = False

        self._setup_ui()
        self._load_video()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if _multimedia_available:
            self._video_widget = QVideoWidget()
            self._video_widget.setStyleSheet(f"background: {_BG_APP};")
            layout.addWidget(self._video_widget, 1)

            self._player = QMediaPlayer(self)
            self._audio = QAudioOutput(self)
            self._player.setAudioOutput(self._audio)
            self._player.setVideoOutput(self._video_widget)
            self._player.positionChanged.connect(self._on_position_changed)
            self._player.durationChanged.connect(self._on_duration_changed)
            self._player.playbackStateChanged.connect(self._on_state_changed)
        else:
            placeholder = QLabel("⚠ PySide6.QtMultimedia không khả dụng.\nKhông thể phát video.")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet(f"color: {_WARNING}; font-size: 14px; padding: 40px;")
            layout.addWidget(placeholder, 1)

        # -- Bottom bar ---------------------------------------------------
        bar = QWidget()
        bar.setFixedHeight(84)
        bar.setStyleSheet(f"background: {_BG_SURFACE}; border-top: 1px solid {_BORDER};")
        bar_layout = QVBoxLayout(bar)
        bar_layout.setContentsMargins(12, 6, 12, 6)
        bar_layout.setSpacing(4)

        # Seek slider
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(0, 0)
        self._slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 4px;
                background: {_BORDER};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 12px; height: 12px;
                margin: -4px 0;
                background: {_ACCENT};
                border-radius: 6px;
            }}
            QSlider::sub-page:horizontal {{
                background: {_ACCENT};
                border-radius: 2px;
            }}
        """)
        self._slider.sliderMoved.connect(self._seek)
        bar_layout.addWidget(self._slider)

        # Controls row
        ctrl = QHBoxLayout()
        ctrl.setSpacing(8)

        self._btn_prev = _icon_button("◀", "Video trước", parent=self)
        self._btn_prev.clicked.connect(self._prev)
        ctrl.addWidget(self._btn_prev)

        self._btn_play = _icon_button("▶", "Phát / Tạm dừng", 40, parent=self)
        self._btn_play.setStyleSheet(self._btn_play.styleSheet().replace("font-size: 14px", "font-size: 18px"))
        self._btn_play.clicked.connect(self._toggle_play)
        ctrl.addWidget(self._btn_play)

        self._btn_next = _icon_button("▶", "Video sau", parent=self)
        self._btn_next.clicked.connect(self._next)
        ctrl.addWidget(self._btn_next)

        ctrl.addSpacing(12)

        self._lbl_time = QLabel("00:00 / 00:00")
        self._lbl_time.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: 11px; font-family: 'JetBrains Mono', monospace;")
        ctrl.addWidget(self._lbl_time)

        ctrl.addStretch()

        self._lbl_counter = QLabel()
        self._lbl_counter.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: 11px;")
        ctrl.addWidget(self._lbl_counter)

        ctrl.addSpacing(8)

        self._btn_fullscreen = _icon_button("⛶", "Toàn màn hình", parent=self)
        self._btn_fullscreen.clicked.connect(self._toggle_fullscreen)
        ctrl.addWidget(self._btn_fullscreen)

        self._btn_copy = _icon_button("📋", "Sao chép", parent=self)
        self._btn_copy.clicked.connect(self._copy_to_clipboard)
        ctrl.addWidget(self._btn_copy)

        self._btn_close = _icon_button("✕", "Đóng", parent=self)
        self._btn_close.clicked.connect(self.close)
        ctrl.addWidget(self._btn_close)

        bar_layout.addLayout(ctrl)
        layout.addWidget(bar)

    def _copy_to_clipboard(self) -> None:
        if not self._paths or self._index >= len(self._paths):
            return
        path = self._paths[self._index]
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QMimeData, QUrl
        import os
        if not os.path.exists(path): return
        clipboard = QApplication.clipboard()
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(path)])
        clipboard.setMimeData(mime)

    def contextMenuEvent(self, event):
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #1b2028; border: 1px solid #2a3140; color: #e2e8f0; border-radius: 4px; }
            QMenu::item { padding: 6px 24px; }
            QMenu::item:selected { background: #3b82f6; }
        """)
        copy_action = menu.addAction("📋 Sao chép")
        action = menu.exec(event.globalPos())
        if action == copy_action:
            self._copy_to_clipboard()

    # -- Video loading / playback ----------------------------------------------------

    def _load_video(self) -> None:
        if not self._paths or not self._player:
            self._update_counter()
            return
        path = self._paths[self._index]
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.play()
        self._playing = True
        self._btn_play.setText("⏸")
        self._update_counter()

    def _update_counter(self) -> None:
        self._lbl_counter.setText(f"{self._index + 1} / {len(self._paths)}")
        self._btn_prev.setEnabled(self._index > 0)
        self._btn_next.setEnabled(self._index < len(self._paths) - 1)

    # -- Controls ---------------------------------------------------------

    def _toggle_play(self) -> None:
        if not self._player:
            return
        if self._playing:
            self._player.pause()
        else:
            self._player.play()

    def _seek(self, position: int) -> None:
        if self._player:
            self._player.setPosition(position)

    def _prev(self) -> None:
        if self._index > 0:
            self._index -= 1
            self._load_video()

    def _next(self) -> None:
        if self._index < len(self._paths) - 1:
            self._index += 1
            self._load_video()

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # -- Slots from player ------------------------------------------------

    def _on_position_changed(self, pos: int) -> None:
        self._slider.blockSignals(True)
        self._slider.setValue(pos)
        self._slider.blockSignals(False)
        dur = self._slider.maximum()
        self._lbl_time.setText(f"{self._fmt(pos)} / {self._fmt(dur)}")

    def _on_duration_changed(self, dur: int) -> None:
        self._slider.setRange(0, dur)

    def _on_state_changed(self, state) -> None:
        if _multimedia_available:
            self._playing = state == QMediaPlayer.PlaybackState.PlayingState
        self._btn_play.setText("⏸" if self._playing else "▶")

    @staticmethod
    def _fmt(ms: int) -> str:
        s = ms // 1000
        m = s // 60
        s = s % 60
        return f"{m:02d}:{s:02d}"

    # -- Events -----------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Space:
            self._toggle_play()
        elif event.key() == Qt.Key_Left:
            self._prev()
        elif event.key() == Qt.Key_Right:
            self._next()
        elif event.key() == Qt.Key_Escape:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.close()
        elif event.key() == Qt.Key_F or event.key() == Qt.Key_F11:
            self._toggle_fullscreen()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        if self._player:
            self._player.stop()
        super().closeEvent(event)


# ============================================================================
# WorkflowPreviewPanel – embeddable result viewer
# ============================================================================

class WorkflowPreviewPanel(QWidget):
    """Right-side panel showing the output of a selected workflow node.

    Supports image thumbnail grids, video thumbnail grids (with play overlay),
    and plain text display.
    """

    preview_requested = Signal(str)  # file_path

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_files: list[str] = []
        self._current_text: str = ""
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QWidget {{
                background: {_BG_SURFACE};
                color: {_TEXT};
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(40)
        header.setStyleSheet(f"background: {_BG_CARD}; border-bottom: 1px solid {_BORDER};")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 12, 0)

        self._lbl_title = QLabel("Xem trước")
        self._lbl_title.setStyleSheet(f"color: {_TEXT}; font-weight: 600; font-size: 13px;")
        header_layout.addWidget(self._lbl_title)
        header_layout.addStretch()

        self._lbl_count = QLabel("")
        self._lbl_count.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: 11px;")
        header_layout.addWidget(self._lbl_count)

        layout.addWidget(header)

        # Stacked content
        self._stack = QStackedWidget()
        layout.addWidget(self._stack, 1)

        # -- Page 0: Empty placeholder
        empty = QLabel("Chọn một node để xem kết quả")
        empty.setAlignment(Qt.AlignCenter)
        empty.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: 12px; padding: 40px;")
        self._stack.addWidget(empty)

        # -- Page 1: Thumbnail grid (images / videos)
        self._grid_scroll = QScrollArea()
        self._grid_scroll.setWidgetResizable(True)
        self._grid_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._grid_scroll.setStyleSheet(f"""
            QScrollArea {{
                background: {_BG_SURFACE};
                border: none;
            }}
            QScrollBar:vertical {{
                width: 6px;
                background: {_BG_SURFACE};
            }}
            QScrollBar::handle:vertical {{
                background: {_BORDER};
                border-radius: 3px;
                min-height: 20px;
            }}
        """)
        self._grid_container = QWidget()
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setContentsMargins(8, 8, 8, 8)
        self._grid_layout.setSpacing(8)
        self._grid_scroll.setWidget(self._grid_container)
        self._stack.addWidget(self._grid_scroll)

        # -- Page 2: Text preview
        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setStyleSheet(f"""
            QTextEdit {{
                background: {_BG_CARD};
                color: {_TEXT};
                border: none;
                padding: 12px;
                font-family: 'JetBrains Mono', 'Consolas', monospace;
                font-size: 12px;
                selection-background-color: {_ACCENT};
            }}
        """)
        self._stack.addWidget(self._text_edit)

    # -- Public API -------------------------------------------------------

    def show_empty(self) -> None:
        """Show the empty placeholder."""
        self._current_files = []
        self._current_text = ""
        self._lbl_title.setText("Xem trước")
        self._lbl_count.setText("")
        self._stack.setCurrentIndex(0)

    def show_text(self, text: str, title: str = "Kết quả văn bản") -> None:
        """Display plain text output."""
        self._current_text = text
        self._current_files = []
        self._lbl_title.setText(title)
        self._lbl_count.setText("")
        self._text_edit.setPlainText(text)
        self._stack.setCurrentIndex(2)

    def show_files(self, file_paths: list[str], title: str = "Kết quả") -> None:
        """Display a thumbnail grid of files (images and/or videos)."""
        self._current_files = file_paths
        self._current_text = ""
        self._lbl_title.setText(title)
        self._lbl_count.setText(f"{len(file_paths)} file")
        self._populate_grid(file_paths)
        self._stack.setCurrentIndex(1)

    def show_node_output(self, node_data: dict | None, output: dict | None) -> None:
        """Convenience: auto-detect content type from node output data."""
        if output is None:
            self.show_empty()
            return

        label = (node_data or {}).get("label", "Kết quả")
        out = output.get("output")
        preview_files = output.get("preview_files")

        # If preview_files is set, use those
        if preview_files and isinstance(preview_files, list):
            self.show_files(preview_files, label)
            return

        # Text output
        if isinstance(out, str) and not Path(out).exists():
            self.show_text(out, label)
            return

        # Single file path
        if isinstance(out, str) and Path(out).exists():
            self.show_files([out], label)
            return

        # List of file paths
        if isinstance(out, list):
            paths = [str(p) for p in out if isinstance(p, str)]
            existing = [p for p in paths if Path(p).exists()]
            if existing:
                self.show_files(existing, label)
                return
            # Maybe it's a list of non-file strings (text data)
            if paths:
                self.show_text("\n".join(paths), label)
                return

        # Fallback: display as text
        self.show_text(str(out) if out is not None else "(không có dữ liệu)", label)

    # -- Grid management --------------------------------------------------

    def _clear_grid(self) -> None:
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _populate_grid(self, file_paths: list[str]) -> None:
        self._clear_grid()

        cols = max(1, self.width() // 180) if self.width() > 0 else 2
        row, col = 0, 0

        images_list: list[str] = []
        videos_list: list[str] = []

        for fp in file_paths:
            ext = Path(fp).suffix.lower()
            if ext in _IMAGE_EXTS:
                images_list.append(fp)
            elif ext in _VIDEO_EXTS:
                videos_list.append(fp)

        for fp in file_paths:
            ext = Path(fp).suffix.lower()
            card = self._make_card(fp, ext, images_list, videos_list)
            self._grid_layout.addWidget(card, row, col)
            col += 1
            if col >= cols:
                col = 0
                row += 1

        # Spacer at bottom
        self._grid_layout.setRowStretch(row + 1, 1)

    def _make_card(
        self,
        file_path: str,
        ext: str,
        images_list: list[str],
        videos_list: list[str],
    ) -> QWidget:
        card = QFrame()
        card.setFixedSize(160, 185)
        card.setCursor(Qt.PointingHandCursor)
        card.setStyleSheet(f"""
            QFrame {{
                background: {_BG_CARD};
                border: 1px solid {_BORDER};
                border-radius: 8px;
            }}
            QFrame:hover {{
                border-color: {_ACCENT};
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(4, 4, 4, 4)
        card_layout.setSpacing(2)

        thumb_label = QLabel()
        thumb_label.setFixedSize(152, 152)
        thumb_label.setAlignment(Qt.AlignCenter)
        thumb_label.setStyleSheet("border: none; background: transparent;")

        if ext in _IMAGE_EXTS:
            pm = _make_thumbnail(file_path, 148)
            thumb_label.setPixmap(pm)
        elif ext in _VIDEO_EXTS:
            pm = _make_video_thumbnail(file_path, 148)
            thumb_label.setPixmap(pm)
        else:
            thumb_label.setText("📄")
            thumb_label.setStyleSheet(f"border: none; color: {_TEXT_MUTED}; font-size: 32px;")

        card_layout.addWidget(thumb_label)

        name_label = QLabel(Path(file_path).name)
        name_label.setFixedHeight(20)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: 10px; border: none;")
        # Elide long names
        fm = name_label.fontMetrics()
        elided = fm.elidedText(Path(file_path).name, Qt.ElideMiddle, 148)
        name_label.setText(elided)
        card_layout.addWidget(name_label)

        # Click handler
        def on_click(_fp=file_path, _ext=ext):
            self.preview_requested.emit(_fp)
            if _ext in _IMAGE_EXTS:
                dlg = PreviewImageDialog(images_list, images_list.index(_fp) if _fp in images_list else 0, self)
                dlg.exec()
            elif _ext in _VIDEO_EXTS:
                dlg = PreviewVideoDialog(videos_list, videos_list.index(_fp) if _fp in videos_list else 0, self)
                dlg.exec()

        card.mousePressEvent = lambda event, handler=on_click: handler()

        return card

    # -- Resize -----------------------------------------------------------

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Re-flow the grid on resize
        if self._current_files and self._stack.currentIndex() == 1:
            self._populate_grid(self._current_files)
