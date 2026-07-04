import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFileDialog, QDialog
)
from PySide6.QtCore import Qt, Signal, QRect, QPoint, QSize, QUrl
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QIcon, QPixmap
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget

_BG_APP = "#0f172a"
_BG_PANEL = "#1e293b"
_BORDER = "#334155"
_ACCENT = "#3b82f6"
_TEXT = "#f8fafc"
_TEXT_MUTED = "#94a3b8"

class RangeSlider(QWidget):
    valueChanged = Signal(float, float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)
        self.setMinimumWidth(100)
        self._start = 0.0
        self._end = 1.0
        self._handle_radius = 6
        self._dragging_start = False
        self._dragging_end = False

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        track_rect = QRect(self._handle_radius, self.height() // 2 - 2, 
                           self.width() - 2 * self._handle_radius, 4)
        p.setBrush(QColor(_BORDER))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(track_rect, 2, 2)
        
        w = self.width() - 2 * self._handle_radius
        x1 = int(self._handle_radius + self._start * w)
        x2 = int(self._handle_radius + self._end * w)
        active_rect = QRect(x1, self.height() // 2 - 2, x2 - x1, 4)
        p.setBrush(QColor(_ACCENT))
        p.drawRoundedRect(active_rect, 2, 2)
        
        p.setBrush(QColor(_TEXT))
        p.drawEllipse(QPoint(x1, self.height() // 2), self._handle_radius, self._handle_radius)
        p.drawEllipse(QPoint(x2, self.height() // 2), self._handle_radius, self._handle_radius)

    def mousePressEvent(self, ev):
        w = self.width() - 2 * self._handle_radius
        x1 = self._handle_radius + self._start * w
        x2 = self._handle_radius + self._end * w
        
        if abs(ev.position().x() - x1) < 15:
            self._dragging_start = True
        elif abs(ev.position().x() - x2) < 15:
            self._dragging_end = True

    def mouseMoveEvent(self, ev):
        w = self.width() - 2 * self._handle_radius
        x = ev.position().x() - self._handle_radius
        ratio = max(0.0, min(1.0, x / w))
        
        if self._dragging_start:
            self._start = min(ratio, self._end - 0.05)
            self.update()
            self.valueChanged.emit(self._start, self._end)
        elif self._dragging_end:
            self._end = max(ratio, self._start + 0.05)
            self.update()
            self.valueChanged.emit(self._start, self._end)

    def mouseReleaseEvent(self, ev):
        self._dragging_start = False
        self._dragging_end = False

class VideoListItemWidget(QWidget):
    remove_requested = Signal()
    swap_down_requested = Signal()
    swap_up_requested = Signal()
    
    def __init__(self, file_path: str, is_first: bool, is_last: bool, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.trim_start_ratio = 0.0
        self.trim_end_ratio = 1.0
        
        self.setStyleSheet(f"QWidget {{ background: {_BG_PANEL}; border: 1px solid {_BORDER}; border-radius: 6px; }}")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)
        
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        self.thumb_container = QWidget()
        self.thumb_container.setFixedSize(80, 60)
        self.thumb_container.setStyleSheet("background: black; border-radius: 4px;")
        thumb_layout = QVBoxLayout(self.thumb_container)
        thumb_layout.setContentsMargins(0, 0, 0, 0)
        
        self.video_widget = QVideoWidget()
        self.video_widget.hide()
        thumb_layout.addWidget(self.video_widget)
        
        self.thumb_label = QLabel()
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setStyleSheet("color: white; font-size: 10px;")
        
        is_node_input = "wf_vid" in file_path or not Path(file_path).exists()
        
        if not is_node_input:
            self.thumb_label.setText("Video")
        else:
            self.thumb_label.setText("Từ Node")
        thumb_layout.addWidget(self.thumb_label)
        
        self.player = QMediaPlayer(self)
        self.player.setVideoOutput(self.video_widget)
        self.player.setLoops(QMediaPlayer.Loops.Infinite) # Loop silently
        if not is_node_input:
            self.player.setSource(QUrl.fromLocalFile(file_path))
        
        top_layout.addWidget(self.thumb_container)
        
        ctrl_layout = QVBoxLayout()
        ctrl_layout.setContentsMargins(0, 0, 0, 0)
        
        name_lbl = QLabel(Path(file_path).name if not is_node_input else "Video từ Node trước")
        name_lbl.setStyleSheet("border: none; background: transparent;")
        ctrl_layout.addWidget(name_lbl)
        
        self.slider = RangeSlider()
        self.slider.setStyleSheet("border: none; background: transparent;")
        self.slider.valueChanged.connect(self._on_slider_changed)
        ctrl_layout.addWidget(self.slider)
        
        top_layout.addLayout(ctrl_layout, 1)
        

        
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(20, 20)
        del_btn.setStyleSheet("border: none; background: transparent; color: #ef4444; font-weight: bold;")
        del_btn.clicked.connect(self.remove_requested.emit)
        top_layout.addWidget(del_btn, 0, Qt.AlignmentFlag.AlignTop)
        
        main_layout.addLayout(top_layout)
        
    def _on_slider_changed(self, s, e):
        self.trim_start_ratio = s
        self.trim_end_ratio = e

    def enterEvent(self, ev):
        if Path(self.file_path).exists():
            self.thumb_label.hide()
            self.video_widget.show()
            self.player.play()
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        if Path(self.file_path).exists():
            self.player.pause()
            self.video_widget.hide()
            self.thumb_label.show()
        super().leaveEvent(ev)
        
    def mousePressEvent(self, ev):
        if Path(self.file_path).exists():
            from ui.workflow.preview_panel import PreviewVideoDialog
            dlg = PreviewVideoDialog(self.file_path, parent=None)
            dlg.exec()

class VideoListWidget(QWidget):
    changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.videos = [] # list of dicts: {"path": str, "start": float, "end": float}
        self.setMinimumHeight(150)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{ width: 6px; background: transparent; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {_TEXT_MUTED}; border-radius: 3px; min-height: 20px; }}
            QScrollBar::handle:vertical:hover {{ background: {_TEXT}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        """)
        
        self.content = QWidget()
        self.content.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(4)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll.setWidget(self.content)
        layout.addWidget(self.scroll, 1)
        
        add_btn = QPushButton("+ Chọn Video")
        add_btn.setStyleSheet(f"background: {_BG_APP}; border: 1px dashed {_BORDER}; border-radius: 4px; padding: 4px; color: {_TEXT_MUTED};")
        add_btn.clicked.connect(self._on_add_clicked)
        layout.addWidget(add_btn)
        
    def _on_add_clicked(self):
        # Find actual top-level main_window to pass to HistoryPickerDialog
        main_win = None
        from PySide6.QtWidgets import QApplication
        for w in QApplication.topLevelWidgets():
            if hasattr(w, "db"):
                main_win = w
                break
                
        try:
            from ui.workflow.history_picker_dialog import HistoryPickerDialog
            # MUST pass parent=None to prevent the dialog from being clipped inside the QGraphicsProxyWidget
            dlg = HistoryPickerDialog(main_win, media_type="video", parent=None)
            if dlg.exec():
                for item in dlg.selected_items:
                    self.videos.append({"path": item["path"], "start": 0.0, "end": 1.0})
                self.refresh_ui()
                self.changed.emit()
        except Exception as e:
            import traceback
            traceback.print_exc()
            # Fallback
            files, _ = QFileDialog.getOpenFileNames(self, "Chọn Video", "", "Video (*.mp4 *.avi *.mkv);;Tất cả (*)")
            if files:
                for f in files:
                    self.videos.append({"path": f, "start": 0.0, "end": 1.0})
                self.refresh_ui()
                self.changed.emit()
            
    def set_videos(self, videos: list):
        self.videos = videos
        self.refresh_ui()
        
    def get_videos(self) -> list:
        idx = 0
        for i in range(self.content_layout.count()):
            item = self.content_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), VideoListItemWidget):
                if idx < len(self.videos):
                    self.videos[idx]["start"] = item.widget().trim_start_ratio
                    self.videos[idx]["end"] = item.widget().trim_end_ratio
                idx += 1
        return self.videos
        
    def sync_with_edges(self, connections: list):
        # connections is a list of _ConnectionWire items pointing to this node's input port
        # We need to ensure self.videos contains entries for these nodes.
        # Format: wf_vid_{node_id}
        
        # Keep existing manual picks, update node-based picks
        existing_manual = [v for v in self.videos if "wf_vid_" not in v["path"] and Path(v["path"]).exists()]
        
        new_videos = existing_manual
        for wire in connections:
            if wire.src_port and wire.src_port.parentItem():
                src_node = wire.src_port.parentItem()
                node_id = src_node.node_data.id
                # Only add if it's a generator type
                if src_node.node_data.node_type == "generate_video":
                    # Check if already in list to preserve start/end
                    existing = next((v for v in self.videos if v["path"] == f"wf_vid_{node_id}"), None)
                    if existing:
                        new_videos.append(existing)
                    else:
                        new_videos.append({"path": f"wf_vid_{node_id}", "start": 0.0, "end": 1.0})
        
        self.videos = new_videos
        self.refresh_ui()
        self.changed.emit()
        
    def refresh_ui(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()
                item.layout().deleteLater()
                
        for i, vid in enumerate(self.videos):
            w = VideoListItemWidget(vid["path"], is_first=(i==0), is_last=(i==len(self.videos)-1))
            w.slider._start = vid.get("start", 0.0)
            w.slider._end = vid.get("end", 1.0)
            w.trim_start_ratio = w.slider._start
            w.trim_end_ratio = w.slider._end
            
            w.remove_requested.connect(lambda idx=i: self._remove_item(idx))
            self.content_layout.addWidget(w)
            
            if i < len(self.videos) - 1:
                swap_layout = QHBoxLayout()
                swap_layout.setContentsMargins(0, 0, 0, 0)
                swap_layout.addStretch()
                swap_btn = QPushButton("⇅")
                swap_btn.setFixedSize(24, 24)
                swap_btn.setStyleSheet("border: none; background: transparent; font-size: 16px; font-weight: bold; color: #3b82f6;")
                swap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                swap_btn.clicked.connect(lambda _, idx=i: self._swap_items(idx, idx+1))
                swap_layout.addWidget(swap_btn)
                swap_layout.addStretch()
                self.content_layout.addLayout(swap_layout)
            
    def _remove_item(self, idx):
        if 0 <= idx < len(self.videos):
            self.videos.pop(idx)
            self.refresh_ui()
            self.changed.emit()
            
    def _swap_items(self, idx1, idx2):
        if 0 <= idx1 < len(self.videos) and 0 <= idx2 < len(self.videos):
            self.videos[idx1], self.videos[idx2] = self.videos[idx2], self.videos[idx1]
            self.refresh_ui()
            self.changed.emit()
