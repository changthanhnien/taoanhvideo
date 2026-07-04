import os
import shutil
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QPushButton,
    QScrollArea, QGridLayout, QComboBox, QButtonGroup, QCheckBox, QFileDialog, QMessageBox, QMenu
)
from PySide6.QtCore import Qt, Signal, QSize, QRunnable, QThreadPool, QObject, QUrl
from PySide6.QtGui import QPixmap, QIcon, QImageReader, QImage, QPainter, QPainterPath, QRegion, QColor, QPalette
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

_BG_APP = "#0f172a"
_BG_PANEL = "#111827"
_BORDER = "#1f2937"
_BORDER_LIGHT = "#374151"
_ACCENT = "#3b82f6"
_ACCENT_HOVER = "#2563eb"
_TEXT = "#f8fafc"
_TEXT_MUTED = "#94a3b8"

def ensure_check_icon():
    dir_path = os.path.dirname(os.path.abspath(__file__))
    svg_path = os.path.join(dir_path, "check.svg")
    if not os.path.exists(svg_path):
        try:
            svg_content = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>'
            with open(svg_path, "w", encoding="utf-8") as f:
                f.write(svg_content)
        except Exception:
            pass
    return svg_path.replace("\\", "/")

def ensure_arrow_icon():
    dir_path = os.path.dirname(os.path.abspath(__file__))
    svg_path = os.path.join(dir_path, "down_arrow.svg")
    if not os.path.exists(svg_path):
        try:
            svg_content = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>'
            with open(svg_path, "w", encoding="utf-8") as f:
                f.write(svg_content)
        except Exception:
            pass
    return svg_path.replace("\\", "/")

def ensure_arrow_hover_icon():
    dir_path = os.path.dirname(os.path.abspath(__file__))
    svg_path = os.path.join(dir_path, "down_arrow_hover.svg")
    if not os.path.exists(svg_path):
        try:
            svg_content = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>'
            with open(svg_path, "w", encoding="utf-8") as f:
                f.write(svg_content)
        except Exception:
            pass
    return svg_path.replace("\\", "/")

def ensure_up_arrow_icon():
    dir_path = os.path.dirname(os.path.abspath(__file__))
    svg_path = os.path.join(dir_path, "up_arrow.svg")
    if not os.path.exists(svg_path):
        try:
            svg_content = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 15 12 9 6 15"/></svg>'
            with open(svg_path, "w", encoding="utf-8") as f:
                f.write(svg_content)
        except Exception:
            pass
    return svg_path.replace("\\", "/")

def ensure_up_arrow_hover_icon():
    dir_path = os.path.dirname(os.path.abspath(__file__))
    svg_path = os.path.join(dir_path, "up_arrow_hover.svg")
    if not os.path.exists(svg_path):
        try:
            svg_content = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 15 12 9 6 15"/></svg>'
            with open(svg_path, "w", encoding="utf-8") as f:
                f.write(svg_content)
        except Exception:
            pass
    return svg_path.replace("\\", "/")

def ensure_control_svgs():
    dir_path = os.path.dirname(os.path.abspath(__file__))
    svgs = {
        "play_control.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#94a3b8"><polygon points="6 3 20 12 6 21 6 3"/></svg>',
        "pause_control.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#94a3b8"><rect x="5" y="4" width="4" height="16" rx="1"/><rect x="15" y="4" width="4" height="16" rx="1"/></svg>',
        "volume_on_control.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" fill="#94a3b8"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>',
        "volume_off_control.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" fill="#94a3b8"/><line x1="22" y1="9" x2="16" y2="15"/><line x1="16" y1="9" x2="22" y2="15"/></svg>',
        "prev_control.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="19 20 9 12 19 4 19 20" fill="#94a3b8"/><line x1="5" y1="19" x2="5" y2="5"/></svg>',
        "next_control.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 4 15 12 5 20 5 4" fill="#94a3b8"/><line x1="19" y1="5" x2="19" y2="19"/></svg>'
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

def ensure_action_svgs():
    dir_path = os.path.dirname(os.path.abspath(__file__))
    svgs = {
        "download_action.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
        "trash_action.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>',
        "select_all.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/></svg>',
        "deselect_all.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>',
        "close_action.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
        "close_action_hover.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'
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

def get_rounded_pixmap(pixmap, radius=8):
    if pixmap.isNull():
        return pixmap
    target = QPixmap(pixmap.size())
    target.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(target)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    
    path = QPainterPath()
    path.addRoundedRect(0, 0, pixmap.width(), pixmap.height(), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return target


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


class ThumbnailWorkerSignals(QObject):
    finished = Signal(str, QPixmap)

class ThumbnailWorker(QRunnable):
    def __init__(self, path, is_vid):
        super().__init__()
        self.path = path
        self.is_vid = is_vid
        self.signals = ThumbnailWorkerSignals()
        
    def run(self):
        pix = None
        try:
            if self.is_vid:
                import cv2
                cap = cv2.VideoCapture(self.path)
                ret, frame = cap.read()
                cap.release()
                if ret:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = frame.shape
                    qimg = QImage(frame.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
                    pix = QPixmap.fromImage(qimg)
            else:
                pix = QPixmap(self.path)
        except Exception:
            pass
            
        if pix and not pix.isNull():
            scaled_pix = pix.scaled(110, 75, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            self.signals.finished.emit(self.path, scaled_pix)
        else:
            self.signals.finished.emit(self.path, QPixmap())

class HistoryItemWidget(QWidget):
    clicked = Signal(dict)
    
    def __init__(self, item_data, parent=None):
        super().__init__(parent)
        self.item_data = item_data
        self.setFixedSize(115, 115)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(f"""
            HistoryItemWidget {{
                background: {_BG_PANEL};
                border: 1px solid {_BORDER};
                border-radius: 8px;
            }}
            HistoryItemWidget:focus {{
                border: 1.5px dashed {_ACCENT};
            }}
            HistoryItemWidget:hover {{
                border: 1px solid {_ACCENT};
            }}
            HistoryItemWidget[selected="true"] {{
                border: 1.5px solid {_ACCENT};
                background: rgba(59, 130, 246, 0.06);
            }}
            HistoryItemWidget[active_preview="true"] {{
                border: 1.5px solid {_ACCENT};
                background: rgba(59, 130, 246, 0.12);
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        self.thumb = QLabel()
        self.thumb.setScaledContents(True)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setStyleSheet("border: none; background: #000000; border-radius: 4px;")
        layout.addWidget(self.thumb, 1)
        
        path = item_data.get("path", "")
        self.path = path
        self.is_vid = item_data.get("is_vid", False)
        
        # Loading badge
        self.thumb.setText("🎬 VIDEO" if self.is_vid else "🖼️ IMAGE")
        self.thumb.setStyleSheet("border: none; background: #0b0f19; color: #475569; font-size: 10px; font-weight: bold; border-radius: 4px;")
        
        # Load thumb asynchronously
        worker = ThumbnailWorker(path, self.is_vid)
        worker.signals.finished.connect(self._on_thumb_loaded)
        QThreadPool.globalInstance().start(worker)
        
        name_lbl = QLabel(Path(path).name)
        name_lbl.setStyleSheet(f"border: none; color: {_TEXT_MUTED}; font-size: 9px; font-weight: 500;")
        name_lbl.setWordWrap(True)
        layout.addWidget(name_lbl)
        
        self.checkbox = QCheckBox(self)
        self.checkbox.setFixedSize(22, 22)
        svg_rel_path = ensure_check_icon()
        self.checkbox.setStyleSheet(f"""
            QCheckBox {{ background: transparent; }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid #64748b;
                border-radius: 4px;
                background-color: rgba(15, 23, 42, 0.7);
            }}
            QCheckBox::indicator:hover {{
                border-color: {_ACCENT};
            }}
            QCheckBox::indicator:checked {{
                background-color: {_ACCENT};
                border-color: {_ACCENT};
                image: url({svg_rel_path});
            }}
        """)
        self.checkbox.move(6, 6)
        self.checkbox.raise_()
        self.checkbox.stateChanged.connect(self._on_state_changed)
        
    def _on_state_changed(self, state):
        target_val = self.checkbox.isChecked()
        if self.property("selected") != target_val:
            self.setProperty("selected", target_val)
            self.style().unpolish(self)
            self.style().polish(self)
        
    def _on_thumb_loaded(self, path, pixmap):
        if path == self.path and pixmap and not pixmap.isNull():
            self.thumb.setPixmap(pixmap)
            self.thumb.setStyleSheet("border: none; background: #000000; border-radius: 4px;")
            
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item_data)
        super().mousePressEvent(ev)

class RoundedOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        path = QPainterPath()
        path.addRect(0, 0, self.width(), self.height())
        
        path_inner = QPainterPath()
        path_inner.addRoundedRect(0, 0, self.width(), self.height(), 8, 8)
        
        path_clip = path.subtracted(path_inner)
        painter.fillPath(path_clip, QColor("#111827"))

class HistoryPickerWidget(QWidget):
    selection_changed = Signal()
    
    def __init__(self, main_win, media_type="all", multi_select=True, parent=None):
        super().__init__(parent)
        self.main_win = main_win
        if self.main_win is None:
            from PySide6.QtWidgets import QApplication
            for w in QApplication.topLevelWidgets():
                if hasattr(w, "db"):
                    self.main_win = w
                    break
                    
        self.media_type = media_type # "all", "video", "image"
        self.multi_select = multi_select
        self.selected_items = []
        self.action_paths = ensure_action_svgs()
        
        # Check if parent or any ancestor is a HistoryPickerDialog
        self.is_dialog = False
        p = parent
        while p:
            if p.__class__.__name__ == "HistoryPickerDialog":
                self.is_dialog = True
                break
            p = p.parent() if hasattr(p, "parent") else None
            
        self.outer_widget = QWidget(self)
        self.outer_widget.setStyleSheet(f"""
            QWidget#Outer {{ background: {_BG_APP}; border: none; }}
            QLabel {{ color: {_TEXT}; font-family: 'Segoe UI', Arial, sans-serif; }}
        """)
        self.outer_widget.setObjectName("Outer")
        
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self.outer_widget)
        
        main_vbox = QVBoxLayout(self.outer_widget)
        main_vbox.setContentsMargins(0, 0, 0, 0)
        main_vbox.setSpacing(0)
        
        # --- Main Layout ---
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        main_vbox.addLayout(content_layout, 1)
        
        # --- Left Sidebar ---
        sidebar = QWidget()
        sidebar.setFixedWidth(180)
        sidebar.setStyleSheet(f"background: {_BG_PANEL}; border-right: 1px solid {_BORDER};")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 16, 12, 16)
        
        lbl_title = QLabel("Lịch sử")
        lbl_title.setStyleSheet(f"color: {_TEXT}; font-size: 18px; font-weight: bold; margin-left: 8px; margin-bottom: 12px;")
        sidebar_layout.addWidget(lbl_title)
        
        self.btn_all = QPushButton("🗂️ Tất cả")
        self.btn_vid = QPushButton("🎬 Video")
        self.btn_img = QPushButton("🖼️ Ảnh")
        
        for btn in (self.btn_all, self.btn_vid, self.btn_img):
            btn.setStyleSheet(f"""
                QPushButton {{ text-align: left; padding: 10px 14px; background: transparent; border: none; border-radius: 6px; color: {_TEXT_MUTED}; font-size: 13px; font-weight: 500; margin-bottom: 4px; }}
                QPushButton:hover {{ background: {_BORDER}; color: {_TEXT}; }}
                QPushButton:checked {{ background: rgba(59, 130, 246, 0.15); color: {_ACCENT}; font-weight: bold; }}
            """)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            sidebar_layout.addWidget(btn)
            
        self.filter_group = QButtonGroup(self)
        self.filter_group.addButton(self.btn_all, 0)
        self.filter_group.addButton(self.btn_vid, 1)
        self.filter_group.addButton(self.btn_img, 2)
        self.filter_group.idClicked.connect(self._on_filter_changed)
        
        if self.media_type == "video": self.btn_vid.setChecked(True)
        elif self.media_type == "image": self.btn_img.setChecked(True)
        else: self.btn_all.setChecked(True)
        
        # Add Stretch to push filters to top
        sidebar_layout.addStretch()
        
        # Add "Tải file lên" button at the bottom of the Left Sidebar
        self.btn_upload = QPushButton("📤  Tải file lên")
        self.btn_upload.setStyleSheet(f"""
            QPushButton {{ 
                text-align: left; 
                padding: 10px 14px; 
                background: transparent; 
                border: 1px solid {_BORDER_LIGHT}; 
                border-radius: 6px; 
                color: {_TEXT}; 
                font-size: 13px; 
                font-weight: 500; 
                margin-top: 8px;
            }}
            QPushButton:hover {{ 
                background: {_BORDER}; 
                border-color: {_ACCENT}; 
            }}
        """)
        self.btn_upload.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_upload.clicked.connect(self._on_upload_file)
        sidebar_layout.addWidget(self.btn_upload)
        
        content_layout.addWidget(sidebar)
        
        # --- Center Panel ---
        center_w = QWidget()
        center_layout = QVBoxLayout(center_w)
        center_layout.setContentsMargins(16, 16, 16, 16)
        
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)
        
        # Sort Dropdown Menu (QPushButton + QMenu)
        self.btn_sort = QPushButton("Mới nhất ")
        self.btn_sort.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.btn_sort.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sort.setFixedSize(110, 32)
        
        # Load down arrow icon initially
        down_arrow_path = self.action_paths["select_all"].replace("select_all.svg", "down_arrow.svg")
        self.btn_sort.setIcon(QIcon(down_arrow_path))
        self.btn_sort.setIconSize(QSize(10, 10))
        
        self.sort_menu = QMenu(self)
        self.sort_menu.setStyleSheet(f"""
            QMenu {{
                background-color: #111827;
                color: {_TEXT};
                border: 1px solid {_BORDER_LIGHT};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 20px;
                border-radius: 4px;
                color: {_TEXT};
            }}
            QMenu::item:selected {{
                background-color: {_ACCENT};
                color: #ffffff;
            }}
        """)
        
        action_newest = self.sort_menu.addAction("Mới nhất")
        action_oldest = self.sort_menu.addAction("Cũ nhất")
        action_newest.triggered.connect(lambda: self._on_sort_changed("Mới nhất"))
        action_oldest.triggered.connect(lambda: self._on_sort_changed("Cũ nhất"))
        self.btn_sort.setMenu(self.sort_menu)
        
        # Style Sort Button with identical toolbar button styles
        self.btn_sort.setStyleSheet(f"""
            QPushButton {{
                background: #111827;
                color: {_TEXT};
                border: 1px solid {_BORDER_LIGHT};
                padding: 6px 14px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover, QPushButton:focus {{
                border-color: {_ACCENT};
            }}
            QPushButton::menu-indicator {{
                width: 0px;
                height: 0px;
                image: none;
            }}
        """)
        
        self.sort_menu.aboutToShow.connect(self._on_menu_show)
        self.sort_menu.aboutToHide.connect(self._on_menu_hide)
        top_bar.addWidget(self.btn_sort)
        
        self.btn_select_all = QPushButton(" Chọn tất cả")
        self.btn_select_all.setIcon(QIcon(self.action_paths["select_all"]))
        self.btn_select_all.setIconSize(QSize(15, 15))
        self.btn_select_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_select_all.setStyleSheet(f"""
            QPushButton {{
                background: #111827;
                color: {_TEXT};
                border: 1px solid {_BORDER_LIGHT};
                padding: 6px 14px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {_BORDER};
                border-color: {_BORDER_LIGHT};
            }}
        """)
        self.btn_select_all.clicked.connect(self._select_all)
        top_bar.addWidget(self.btn_select_all)
        
        self.btn_download = QPushButton(" Tải xuống")
        self.btn_download.setIcon(QIcon(self.action_paths["download_action"]))
        self.btn_download.setIconSize(QSize(15, 15))
        self.btn_download.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_download.setStyleSheet(f"""
            QPushButton {{
                background: #111827;
                color: #10b981;
                border: 1px solid #10b981;
                padding: 6px 14px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: rgba(16, 185, 129, 0.1);
            }}
        """)
        self.btn_download.clicked.connect(self._on_download)
        self.btn_download.hide()
        top_bar.addWidget(self.btn_download)
        
        self.btn_trash = QPushButton(" Xóa")
        self.btn_trash.setIcon(QIcon(self.action_paths["trash_action"]))
        self.btn_trash.setIconSize(QSize(15, 15))
        self.btn_trash.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_trash.setStyleSheet(f"""
            QPushButton {{
                background: #111827;
                color: #ef4444;
                border: 1px solid #ef4444;
                padding: 6px 14px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: rgba(239, 68, 68, 0.1);
            }}
        """)
        self.btn_trash.clicked.connect(self._on_delete)
        self.btn_trash.hide()
        top_bar.addWidget(self.btn_trash)
        
        top_bar.addStretch()
        center_layout.addLayout(top_bar)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{
                border: none;
                background: {_BG_APP};
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {_BORDER_LIGHT};
                min-height: 20px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {_ACCENT};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                border: none;
                background: none;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
                border: none;
            }}
            QScrollBar:horizontal {{
                border: none;
                background: {_BG_APP};
                height: 8px;
                margin: 0px;
                border-radius: 4px;
            }}
            QScrollBar::handle:horizontal {{
                background: {_BORDER_LIGHT};
                min-width: 20px;
                border-radius: 4px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {_ACCENT};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                border: none;
                background: none;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: transparent;
                border: none;
            }}
        """)
        
        self.grid_w = QWidget()
        self.grid_w.setStyleSheet("background: transparent; border: none;")
        self.grid_layout = QGridLayout(self.grid_w)
        self.grid_layout.setSpacing(12)
        self.grid_layout.setContentsMargins(4, 4, 4, 4)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        
        self.scroll.setWidget(self.grid_w)
        self.scroll.viewport().setStyleSheet("background: transparent;")
        center_layout.addWidget(self.scroll)
        
        self.empty_lbl = QLabel("📭 Chưa có hình ảnh hoặc video nào được tạo.")
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_lbl.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: 14px; font-weight: 500; padding: 40px;")
        self.empty_lbl.hide()
        center_layout.addWidget(self.empty_lbl, 1)
        
        content_layout.addWidget(center_w, 1)
        
        # --- Right Preview Panel ---
        preview_w = QWidget()
        p_width = 260 if self.is_dialog else 340
        lbl_w = p_width - 32
        lbl_h = 200 if self.is_dialog else 220
        
        preview_w.setFixedWidth(p_width)
        preview_w.setStyleSheet(f"background: {_BG_PANEL}; border-left: 1px solid {_BORDER};")
        preview_layout = QVBoxLayout(preview_w)
        preview_layout.setContentsMargins(16, 16, 16, 16)
        
        # Preview container with stacked layout to prevent QVideoWidget flash
        self.preview_container = QWidget(preview_w)
        self.preview_container.setFixedSize(lbl_w, lbl_h)
        self.preview_container.setStyleSheet(f"background-color: #070b12; border: 1px solid {_BORDER}; border-radius: 8px;")
        
        from PySide6.QtWidgets import QStackedLayout
        self.preview_stack = QStackedLayout(self.preview_container)
        self.preview_stack.setStackingMode(QStackedLayout.StackingMode.StackAll)
        
        self.video_widget = QVideoWidget(self.preview_container)
        palette = self.video_widget.palette()
        for role in [QPalette.ColorRole.Window, QPalette.ColorRole.Base, QPalette.ColorRole.Button]:
            palette.setColor(role, QColor(7, 11, 18))
        self.video_widget.setPalette(palette)
        self.video_widget.setAutoFillBackground(True)
        self.video_widget.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.video_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.video_widget.setStyleSheet("background-color: #070b12; border: none; border-radius: 8px;")
        self.video_widget.hide()
        
        self.preview_lbl = QLabel("ℹ️ Chưa chọn mục nào", self.preview_container)
        self.preview_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_lbl.setStyleSheet(f"color: {_TEXT_MUTED}; background-color: #070b12; border: none; border-radius: 8px; padding: 12px;")
        
        self.preview_stack.addWidget(self.video_widget)
        self.preview_stack.addWidget(self.preview_lbl)
        setup_rounded_mask(self.video_widget, 8)
        setup_rounded_mask(self.preview_lbl, 8)
        
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        self.player.setLoops(QMediaPlayer.Loops.Infinite) # Infinite loop
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
        
        self.video_overlay = RoundedOverlay(self.video_widget)
        self.video_overlay.hide()
        
        preview_layout.addWidget(self.preview_container, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Audio & Playback Controls (Premium Pill controls with Skip buttons)
        self.control_paths = ensure_control_svgs()
        self._is_muted = False
        self.controls_widget = QWidget()
        self.controls_widget.setFixedHeight(36)
        self.controls_widget.setFixedWidth(160)
        self.controls_widget.setStyleSheet(f"""
            QWidget {{
                background: #0f172a;
                border: 1px solid {_BORDER};
                border-radius: 18px;
            }}
            QPushButton {{
                background: transparent;
                border: none;
                padding: 4px;
            }}
        """)
        controls_layout = QHBoxLayout(self.controls_widget)
        controls_layout.setContentsMargins(12, 0, 12, 0)
        controls_layout.setSpacing(12)
        
        self.btn_prev = QPushButton()
        self.btn_prev.setIcon(QIcon(self.control_paths["prev_control"]))
        self.btn_prev.setIconSize(QSize(16, 16))
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.setToolTip("Tập tin trước")
        
        self.btn_play_pause = QPushButton()
        self.btn_play_pause.setIcon(QIcon(self.control_paths["pause_control"]))
        self.btn_play_pause.setIconSize(QSize(16, 16))
        self.btn_play_pause.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play_pause.setToolTip("Tạm dừng / Phát tiếp")
        
        self.btn_next = QPushButton()
        self.btn_next.setIcon(QIcon(self.control_paths["next_control"]))
        self.btn_next.setIconSize(QSize(16, 16))
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.setToolTip("Tập tin tiếp theo")
        
        self.btn_mute = QPushButton()
        self.btn_mute.setIcon(QIcon(self.control_paths["volume_on_control"]))
        self.btn_mute.setIconSize(QSize(16, 16))
        self.btn_mute.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mute.setToolTip("Tắt / Bật âm thanh")
        
        controls_layout.addWidget(self.btn_prev)
        controls_layout.addWidget(self.btn_play_pause)
        controls_layout.addWidget(self.btn_next)
        controls_layout.addWidget(self.btn_mute)
        
        preview_layout.addWidget(self.controls_widget, alignment=Qt.AlignmentFlag.AlignCenter)
        self.controls_widget.hide()
        
        # Connect controls
        def toggle_play():
            if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.player.pause()
            else:
                self.player.play()
                
        def toggle_mute():
            self._is_muted = not self._is_muted
            self.audio_output.setMuted(self._is_muted)
            self.btn_mute.setIcon(QIcon(self.control_paths["volume_off_control"] if self._is_muted else self.control_paths["volume_on_control"]))
            
        def play_next():
            if not self._items or not hasattr(self, "_current_item_path"):
                return
            idx = -1
            for i, it in enumerate(self._items):
                if it["path"] == self._current_item_path:
                    idx = i
                    break
            if idx != -1:
                next_idx = (idx + 1) % len(self._items)
                self._select_item_by_path(self._items[next_idx]["path"])
                
        def play_prev():
            if not self._items or not hasattr(self, "_current_item_path"):
                return
            idx = -1
            for i, it in enumerate(self._items):
                if it["path"] == self._current_item_path:
                    idx = i
                    break
            if idx != -1:
                prev_idx = (idx - 1 + len(self._items)) % len(self._items)
                self._select_item_by_path(self._items[prev_idx]["path"])
                
        self.btn_play_pause.clicked.connect(toggle_play)
        self.btn_mute.clicked.connect(toggle_mute)
        self.btn_next.clicked.connect(play_next)
        self.btn_prev.clicked.connect(play_prev)
        
        def _on_state_changed(state):
            if state == QMediaPlayer.PlaybackState.PlayingState:
                self.btn_play_pause.setIcon(QIcon(self.control_paths["pause_control"]))
            else:
                self.btn_play_pause.setIcon(QIcon(self.control_paths["play_control"]))
        self.player.playbackStateChanged.connect(_on_state_changed)
        
        # Info Box Card
        info_card = QWidget()
        info_card.setStyleSheet(f"background: #0b0f19; border: 1px solid {_BORDER}; border-radius: 6px;")
        info_card_layout = QVBoxLayout(info_card)
        info_card_layout.setContentsMargins(10, 10, 10, 10)
        
        self.info_lbl = QLabel("ℹ️ Chọn một tệp tin để xem thông tin chi tiết.")
        self.info_lbl.setWordWrap(True)
        self.info_lbl.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: 12px; font-weight: 500;")
        info_card_layout.addWidget(self.info_lbl)
        
        preview_layout.addWidget(info_card)
        preview_layout.addStretch()
        
        content_layout.addWidget(preview_w)
        
        self._items = []
        self._load_data()



    def _on_sort_changed(self, text):
        self.btn_sort.setText(text + " ")
        self._load_data()

    def _on_menu_show(self):
        up_arrow = self.action_paths["select_all"].replace("select_all.svg", "up_arrow.svg")
        self.btn_sort.setIcon(QIcon(up_arrow))
        self.btn_sort.setStyleSheet(f"""
            QPushButton {{
                background: #111827;
                color: {self._TEXT};
                border: 1px solid {self._ACCENT};
                padding: 6px 14px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton::menu-indicator {{
                width: 0px;
                height: 0px;
                image: none;
            }}
        """)

    def _on_menu_hide(self):
        down_arrow = self.action_paths["select_all"].replace("select_all.svg", "down_arrow.svg")
        self.btn_sort.setIcon(QIcon(down_arrow))
        self.btn_sort.setStyleSheet(f"""
            QPushButton {{
                background: #111827;
                color: {self._TEXT};
                border: 1px solid {self._BORDER_LIGHT};
                padding: 6px 14px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover, QPushButton:focus {{
                border-color: {self._ACCENT};
            }}
            QPushButton::menu-indicator {{
                width: 0px;
                height: 0px;
                image: none;
            }}
        """)

    def _on_filter_changed(self, _id):
        self._load_data()

    def _load_data(self):
        filter_id = self.filter_group.checkedId()
        order = "DESC" if "Mới nhất" in self.btn_sort.text() else "ASC"
        
        # Fetch matching records from DB without strict limit first so we can filter on exists()
        try:
            cursor = self.main_win.db.execute(
                f"SELECT id, output_path FROM task_items WHERE output_path IS NOT NULL AND output_path != '' ORDER BY id {order}"
            )
            rows = cursor.fetchall()
        except:
            rows = []
            
        self._items = []
        for r in rows:
            if len(self._items) >= 60:
                break
            paths = str(r[1]).split("|")
            for p in paths:
                p = p.strip()
                if not p or not Path(p).exists(): continue
                ext = Path(p).suffix.lower()
                is_vid = ext in ('.mp4', '.mov', '.avi', '.webm')
                if filter_id == 1 and not is_vid: continue
                if filter_id == 2 and is_vid: continue
                self._items.append({"id": r[0], "path": p, "is_vid": is_vid})
                if len(self._items) >= 60:
                    break
                
        self._render_grid()
        self._update_ok_btn()

    def _render_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        if not self._items:
            filter_id = self.filter_group.checkedId()
            if filter_id == 1:
                self.empty_lbl.setText("📭 Chưa có video nào được tạo.")
            elif filter_id == 2:
                self.empty_lbl.setText("📭 Chưa có hình ảnh nào được tạo.")
            else:
                self.empty_lbl.setText("📭 Chưa có hình ảnh hoặc video nào được tạo.")
            self.scroll.hide()
            self.empty_lbl.show()
            self._reset_preview()
            return
            
        self.scroll.show()
        self.empty_lbl.hide()
        
        # Reset preview if current item was filtered out or deleted
        if hasattr(self, "_current_item_path") and self._current_item_path:
            exists = any(it["path"] == self._current_item_path for it in self._items)
            if not exists:
                self._reset_preview()
        
        for i, it in enumerate(self._items):
            w = HistoryItemWidget(it)
            w.clicked.connect(self._on_item_clicked)
            w.checkbox.stateChanged.connect(self._update_ok_btn)
            is_checked = any(x["path"] == it["path"] for x in self.selected_items)
            w.checkbox.setChecked(is_checked)
            self.grid_layout.addWidget(w, 0, i)
            
        self._rearrange_grid()

    def _rearrange_grid(self):
        if not self._items or self.grid_layout.count() == 0:
            return
        
        # Calculate available width mathematically to avoid Qt layout timing updates
        sidebar_w = 180
        preview_w = 260 if self.is_dialog else 340
        margins_w = 32
        scroll_width = self.width() - sidebar_w - preview_w - margins_w
        available_width = max(200, scroll_width - 24)
        spacing = 12
        
        if self.is_dialog:
            cols = 3
        else:
            # Enlarge items and make columns dynamic to eliminate left/right borders completely!
            desired_width = 180
            cols = max(2, available_width // (desired_width + spacing))
        
        item_width = (available_width - (spacing * (cols - 1))) // cols
        item_height = item_width # Keep it square
        
        widgets = []
        for i in range(self.grid_layout.count()):
            w = self.grid_layout.itemAt(i).widget()
            if w:
                widgets.append(w)
                if isinstance(w, HistoryItemWidget):
                    w.setFixedSize(item_width, item_height)
                
        for w in widgets:
            self.grid_layout.removeWidget(w)
            
        for i, w in enumerate(widgets):
            self.grid_layout.addWidget(w, i // cols, i % cols)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rearrange_grid()

    def _on_item_clicked(self, data):
        path = data["path"]
        self._current_item_path = path
        
        # Toggle or check checkbox when the card is clicked
        for i in range(self.grid_layout.count()):
            w = self.grid_layout.itemAt(i).widget()
            if isinstance(w, HistoryItemWidget) and w.item_data["path"] == path:
                if not self.multi_select:
                    # Uncheck others first
                    for j in range(self.grid_layout.count()):
                        w2 = self.grid_layout.itemAt(j).widget()
                        if isinstance(w2, HistoryItemWidget) and w2.item_data["path"] != path:
                            w2.checkbox.blockSignals(True)
                            w2.checkbox.setChecked(False)
                            w2.checkbox.blockSignals(False)
                    w.checkbox.setChecked(True)
                else:
                    # Toggle check state in multi select
                    w.checkbox.setChecked(not w.checkbox.isChecked())

        # Update active preview property only on changed widgets
        for i in range(self.grid_layout.count()):
            w = self.grid_layout.itemAt(i).widget()
            if isinstance(w, HistoryItemWidget):
                is_active = (w.item_data["path"] == path)
                target_val = "true" if is_active else "false"
                if w.property("active_preview") != target_val:
                    w.setProperty("active_preview", target_val)
                    w.style().unpolish(w)
                    w.style().polish(w)
                
        self.info_lbl.setText(f"📁 <b>Tên file:</b> {Path(path).name}<br><br>📊 <b>Kích thước:</b> {round(os.path.getsize(path)/(1024*1024), 2)} MB")
        
        self._current_data = data
        if data["is_vid"]:
            self.video_widget.show()
            # Show a loading placeholder to mask the video loading process and prevent any flash
            self.preview_lbl.setText("⌛ Đang tải...")
            self.preview_lbl.setStyleSheet("color: #94a3b8; background-color: #070b12; border: none; border-radius: 8px; padding: 12px;")
            self.preview_lbl.show()
            self.controls_widget.show()
            self.btn_play_pause.setEnabled(True)
            self.btn_mute.setEnabled(True)
            self.btn_play_pause.setIcon(QIcon(self.control_paths["pause_control"]))
            self.btn_mute.setIcon(QIcon(self.control_paths["volume_off_control"] if self._is_muted else self.control_paths["volume_on_control"]))
            self.audio_output.setMuted(self._is_muted)
            
            # Detect aspect ratio using OpenCV to avoid black bars
            vw, vh = 16, 9
            try:
                import cv2
                cap = cv2.VideoCapture(path)
                if cap.isOpened():
                    w_val = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                    h_val = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                    if w_val > 0 and h_val > 0:
                        vw, vh = w_val, h_val
                cap.release()
            except:
                pass
                
            ratio = vw / vh
            max_w = 228 if self.is_dialog else 308
            max_h = 400 if self.is_dialog else 500
            
            # Calculate target dimensions fitting in max box keeping aspect ratio
            w1 = max_w
            h1 = int(max_w / ratio)
            if h1 <= max_h:
                target_w, target_height = w1, h1
            else:
                target_w, target_height = int(max_h * ratio), max_h
                
            self.video_widget.setFixedSize(target_w, target_height)
            self.preview_container.setFixedSize(target_w, target_height)
            
            self.player.setSource(QUrl.fromLocalFile(path))
            self.player.play()
        else:
            self._current_data = None
            self.player.stop()
            self.player.setSource(QUrl())
            self.video_overlay.hide()
            self.video_widget.hide()
            self.preview_lbl.show()
            self.controls_widget.hide()
            self.btn_play_pause.setEnabled(False)
            self.btn_mute.setEnabled(False)
            pix = QPixmap(path)
            if not pix.isNull():
                pw = pix.width()
                ph = pix.height()
                if pw > 0 and ph > 0:
                    ratio = pw / ph
                    max_w = 228 if self.is_dialog else 308
                    max_h = 400 if self.is_dialog else 500
                    
                    w1 = max_w
                    h1 = int(max_w / ratio)
                    if h1 <= max_h:
                        target_w, target_height = w1, h1
                    else:
                        target_w, target_height = int(max_h * ratio), max_h
                        
                    self.preview_lbl.setFixedSize(target_w, target_height)
                    self.preview_container.setFixedSize(target_w, target_height)
                    self.preview_lbl.setStyleSheet("background: transparent; border: none; padding: 0px;")
                    
                    # Round corners of the image
                    scaled_pix = pix.scaled(target_w, target_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    rounded_pix = get_rounded_pixmap(scaled_pix, 8)
                    self.preview_lbl.setPixmap(rounded_pix)

    def _select_item_by_path(self, path):
        target_widget = None
        for i in range(self.grid_layout.count()):
            w = self.grid_layout.itemAt(i).widget()
            if isinstance(w, HistoryItemWidget) and w.item_data["path"] == path:
                target_widget = w
                break
        if target_widget:
            self._on_item_clicked(target_widget.item_data)

    def _select_all(self):
        all_selected = True
        for i in range(self.grid_layout.count()):
            w = self.grid_layout.itemAt(i).widget()
            if isinstance(w, HistoryItemWidget) and not w.checkbox.isChecked():
                all_selected = False
                break
                
        new_state = not all_selected
        for i in range(self.grid_layout.count()):
            w = self.grid_layout.itemAt(i).widget()
            if isinstance(w, HistoryItemWidget):
                w.checkbox.setChecked(new_state)
                
        if new_state:
            self.btn_select_all.setText(" Bỏ chọn tất cả")
            self.btn_select_all.setIcon(QIcon(self.action_paths["deselect_all"]))
        else:
            self.btn_select_all.setText(" Chọn tất cả")
            self.btn_select_all.setIcon(QIcon(self.action_paths["select_all"]))
            
        self._update_ok_btn()

    def _update_ok_btn(self):
        count = 0
        self.selected_items = []
        total_count = 0
        for i in range(self.grid_layout.count()):
            w = self.grid_layout.itemAt(i).widget()
            if isinstance(w, HistoryItemWidget):
                total_count += 1
                if w.checkbox.isChecked():
                    count += 1
                    self.selected_items.append({"path": w.item_data["path"]})
                
        self.selection_changed.emit()
        
        if count > 0:
            self.btn_download.show()
            self.btn_trash.show()
            if count == total_count:
                self.btn_select_all.setText(" Bỏ chọn tất cả")
                self.btn_select_all.setIcon(QIcon(self.action_paths["deselect_all"]))
            else:
                self.btn_select_all.setText(f" Đã chọn {count}")
                self.btn_select_all.setIcon(QIcon(self.action_paths["deselect_all"]))
        else:
            self.btn_download.hide()
            self.btn_trash.hide()
            self.btn_select_all.setText(" Chọn tất cả")
            self.btn_select_all.setIcon(QIcon(self.action_paths["select_all"]))
            
    def _on_download(self):
        if not self.selected_items:
            return
        out_dir = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu file")
        if not out_dir:
            return
        
        import shutil
        success = 0
        for it in self.selected_items:
            src = it["path"]
            if Path(src).exists():
                try:
                    shutil.copy2(src, Path(out_dir) / Path(src).name)
                    success += 1
                except:
                    pass
        QMessageBox.information(self, "Thành công", f"Đã lưu {success} file vào {out_dir}")
        
    def _on_delete(self):
        if not self.selected_items:
            return
        rep = QMessageBox.question(self, "Xác nhận", f"Xóa vĩnh viễn {len(self.selected_items)} file đã chọn khỏi máy tính?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if rep == QMessageBox.StandardButton.Yes:
            self._reset_preview()
                
            import os
            for it in self.selected_items:
                try:
                    p = Path(it["path"])
                    if p.exists():
                        p.unlink()
                except Exception as e:
                    print(f"Error deleting file: {e}")
            
            # Clear selection list and reload grid
            self.selected_items = []
            self._load_data()

    def _reset_preview(self):
        self._current_data = None
        try:
            self.player.stop()
            self.player.setSource(QUrl())
        except Exception:
            pass
        self.video_overlay.hide()
        self.video_widget.hide()
        self.preview_lbl.show()
        self.preview_lbl.setPixmap(QPixmap())
        lbl_w = 228 if self.is_dialog else 308
        lbl_h = 200 if self.is_dialog else 220
        self.preview_lbl.setFixedSize(lbl_w, lbl_h)
        self.preview_container.setFixedSize(lbl_w, lbl_h)
        self.preview_lbl.setStyleSheet("color: #64748b; background: #070b12; border: 1px solid #1e293b; border-radius: 8px; padding: 12px;")
        self.preview_lbl.setText("ℹ️ Chưa chọn mục nào")
        self.info_lbl.setText("ℹ️ Chọn một tệp tin để xem thông tin chi tiết.")
        self.controls_widget.hide()
        self.btn_play_pause.setEnabled(False)
        self.btn_mute.setEnabled(False)

    def _on_media_status_changed(self, status):
        from PySide6.QtMultimedia import QMediaPlayer
        if status in (QMediaPlayer.MediaStatus.BufferedMedia, QMediaPlayer.MediaStatus.LoadedMedia):
            if hasattr(self, "_current_data") and self._current_data and self._current_data.get("is_vid"):
                self.preview_lbl.hide()

    def _on_upload_file(self):
        file_filter = "Media Files (*.mp4 *.mov *.avi *.webm *.jpg *.jpeg *.png *.webp)"
        paths, _ = QFileDialog.getOpenFileNames(self, "Tải file lên", "", file_filter)
        if not paths:
            return
            
        import shutil
        from config.constants import DEFAULT_VIDEO_OUTPUT, DEFAULT_IMAGE_OUTPUT
        from utils.logger import log
        
        db = self.main_win.db if self.main_win else None
        if not db:
            QMessageBox.warning(self, "Lỗi", "Không tìm thấy kết nối cơ sở dữ liệu.")
            return
            
        # 1. Ensure dummy task exists
        try:
            row = db.execute("SELECT id FROM tasks WHERE name = 'Tệp tải lên' LIMIT 1").fetchone()
            if row:
                task_id = row[0]
            else:
                db.execute("INSERT INTO tasks (name, mode, status) VALUES ('Tệp tải lên', 'upload', 'COMPLETED')")
                db.commit()
                row = db.execute("SELECT id FROM tasks WHERE name = 'Tệp tải lên' LIMIT 1").fetchone()
                task_id = row[0] if row else 1
        except Exception as ex:
            log.error(f"Failed to ensure upload task row: {ex}")
            task_id = 1
            
        uploaded_count = 0
        for src_path in paths:
            src_path_obj = Path(src_path)
            if not src_path_obj.exists():
                continue
                
            ext = src_path_obj.suffix.lower()
            is_vid = ext in ('.mp4', '.mov', '.avi', '.webm')
            
            # 2. Determine target folder and copy the file
            target_dir = DEFAULT_VIDEO_OUTPUT if is_vid else DEFAULT_IMAGE_OUTPUT
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Avoid name collision
            import time
            new_filename = f"upload_{int(time.time())}_{src_path_obj.name}"
            dest_path = target_dir / new_filename
            
            try:
                shutil.copy2(src_path, dest_path)
                # 3. Insert record into task_items table
                db.execute(
                    "INSERT INTO task_items (task_id, prompt, status, output_path, completed_at) VALUES (?, ?, 'COMPLETED', ?, datetime('now', 'localtime'))",
                    (task_id, src_path_obj.name, str(dest_path).replace("\\", "/"))
                )
                db.commit()
                uploaded_count += 1
            except Exception as e:
                log.error(f"Error copying/inserting uploaded file: {e}")
                
        if uploaded_count > 0:
            self._load_data()
            QMessageBox.information(self, "Tải file lên", f"Đã tải lên thành công {uploaded_count} tệp.")

    def hideEvent(self, event):
        if hasattr(self, "player") and self.player:
            try:
                self.player.stop()
            except:
                pass
        super().hideEvent(event)


# HistoryPickerDialog wrapper for popup selection
class HistoryPickerDialog(QDialog):
    def accept(self):
        if hasattr(self, "widget") and hasattr(self.widget, "player") and self.widget.player:
            try:
                self.widget.player.stop()
            except:
                pass
        super().accept()

    def reject(self):
        if hasattr(self, "widget") and hasattr(self.widget, "player") and self.widget.player:
            try:
                self.widget.player.stop()
            except:
                pass
        super().reject()

    def __init__(self, main_win, media_type="all", multi_select=True, parent=None):
        if parent is None:
            parent = main_win
        super().__init__(parent)
        self.main_win = main_win
        self.selected_items = []
        self.action_paths = ensure_action_svgs()
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(1000, 640)
        
        if parent:
            top_window = parent.window()
            if top_window:
                p_geo = top_window.geometry()
                x = p_geo.x() + (p_geo.width() - 1000) // 2
                y = p_geo.y() + (p_geo.height() - 640) // 2
                self.move(max(0, x), max(0, y))
            
        self.outer_widget = QWidget(self)
        self.outer_widget.setStyleSheet(f"""
            QWidget#Outer {{ background: {_BG_APP}; border: 1px solid {_BORDER}; border-radius: 8px; }}
            QLabel {{ color: {_TEXT}; font-family: 'Segoe UI', Arial, sans-serif; }}
        """)
        self.outer_widget.setObjectName("Outer")
        
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self.outer_widget)
        
        main_vbox = QVBoxLayout(self.outer_widget)
        main_vbox.setContentsMargins(0, 0, 0, 0)
        main_vbox.setSpacing(0)
        
        # --- Title Bar ---
        title_bar = QWidget()
        title_bar.setObjectName("TitleBar")
        title_bar.setFixedHeight(45)
        title_bar.setStyleSheet(f"QWidget#TitleBar {{ background: {_BG_PANEL}; border-bottom: 1px solid {_BORDER}; border-top-left-radius: 8px; border-top-right-radius: 8px; }}")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 16, 0)
        
        title_lbl = QLabel("Lịch sử tạo")
        title_lbl.setStyleSheet(f"color: {_TEXT}; font-weight: bold; font-size: 15px;")
        title_layout.addWidget(title_lbl)
        title_layout.addStretch()
        
        btn_close = QPushButton()
        btn_close.setFixedSize(28, 28)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        close_svg_path = self.action_paths["close_action"]
        close_svg_hover_path = self.action_paths["close_action_hover"]
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                qproperty-icon: url({close_svg_path});
                qproperty-iconSize: 12px 12px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background: #ef4444;
                qproperty-icon: url({close_svg_hover_path});
            }}
        """)
        btn_close.clicked.connect(self.reject)
        title_layout.addWidget(btn_close)
        
        main_vbox.addWidget(title_bar)
        
        # Dragging support
        self._dragging = False
        self._drag_pos = None
        
        def _tb_mousePressEvent(ev):
            if ev.button() == Qt.MouseButton.LeftButton:
                self._dragging = True
                self._drag_pos = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
                ev.accept()
        def _tb_mouseMoveEvent(ev):
            if self._dragging:
                self.move(ev.globalPosition().toPoint() - self._drag_pos)
                ev.accept()
        def _tb_mouseReleaseEvent(ev):
            self._dragging = False
            ev.accept()
            
        title_bar.mousePressEvent = _tb_mousePressEvent
        title_bar.mouseMoveEvent = _tb_mouseMoveEvent
        title_bar.mouseReleaseEvent = _tb_mouseReleaseEvent
        
        # --- Embedded Picker Widget ---
        self.widget = HistoryPickerWidget(main_win, media_type, multi_select, parent=self)
        main_vbox.addWidget(self.widget, 1)
        
        # --- Footer ---
        footer_widget = QWidget()
        footer_widget.setFixedHeight(56)
        footer_widget.setStyleSheet(f"background: {_BG_PANEL}; border-top: 1px solid {_BORDER}; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;")
        footer_layout = QHBoxLayout(footer_widget)
        footer_layout.setContentsMargins(24, 0, 24, 0)
        footer_layout.setSpacing(12)
        footer_layout.addStretch()
        
        btn_cancel = QPushButton("Hủy")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {_BORDER_LIGHT};
                padding: 8px 24px;
                border-radius: 6px;
                color: {_TEXT};
                font-weight: 500;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {_BORDER};
                border-color: {_BORDER_LIGHT};
            }}
        """)
        btn_cancel.clicked.connect(self.reject)
        
        self.btn_ok = QPushButton("Chọn (0)")
        self.btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ok.setStyleSheet(f"""
            QPushButton {{
                background: {_ACCENT};
                border: none;
                padding: 8px 24px;
                border-radius: 6px;
                color: white;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {_ACCENT_HOVER};
            }}
            QPushButton:disabled {{
                background: {_BORDER};
                color: {_TEXT_MUTED};
            }}
        """)
        self.btn_ok.clicked.connect(self._on_ok)
        
        footer_layout.addWidget(btn_cancel)
        footer_layout.addWidget(self.btn_ok)
        main_vbox.addWidget(footer_widget)
        
        # Connect selection updates
        self.widget.selection_changed.connect(self._on_selection_changed)
        self._on_selection_changed()
        
        # Initially transparent, fade in after first paint to prevent initial white flash on Windows DWM
        self.setWindowOpacity(0.0)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(80, lambda: self.setWindowOpacity(1.0))
        
    def _on_selection_changed(self):
        count = len(self.widget.selected_items)
        self.btn_ok.setText(f"Chọn ({count})")
        self.btn_ok.setEnabled(count > 0)
        
    def _on_ok(self):
        self.selected_items = self.widget.selected_items
        self.accept()

    def keyPressEvent(self, event):
        key = event.key()
        
        # Space or Enter to toggle play/pause of the preview video player
        if key in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            focus_w = QApplication.focusWidget()
            if isinstance(focus_w, QLineEdit) or isinstance(focus_w, QTextEdit):
                super().keyPressEvent(event)
                return
            
            # Toggle playback of the widget's player
            if hasattr(self, "widget") and hasattr(self.widget, "player"):
                if self.widget.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                    self.widget.player.pause()
                else:
                    self.widget.player.play()
            event.accept()
            return

        # Arrow keys to navigate items in the grid
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            if hasattr(self, "widget") and hasattr(self.widget, "grid_layout"):
                # Find all HistoryItemWidgets in the grid layout order
                widgets = []
                for i in range(self.widget.grid_layout.count()):
                    w = self.widget.grid_layout.itemAt(i).widget()
                    if isinstance(w, HistoryItemWidget):
                        widgets.append(w)
                
                if not widgets:
                    super().keyPressEvent(event)
                    return
                    
                # Find the active item index
                active_idx = -1
                for idx, w in enumerate(widgets):
                    if w.item_data["path"] == getattr(self.widget, "_current_item_path", None):
                        active_idx = idx
                        break
                
                # If no active item, start with the first one
                if active_idx == -1:
                    self.widget._on_item_clicked(widgets[0].item_data)
                    widgets[0].setFocus()
                    event.accept()
                    return

                # Determine column count by inspecting grid layout positions
                max_col = 0
                for i in range(self.widget.grid_layout.count()):
                    pos = self.widget.grid_layout.getItemPosition(i)
                    if pos[1] > max_col:
                        max_col = pos[1]
                cols = max_col + 1
                
                new_idx = active_idx
                if key == Qt.Key.Key_Left:
                    new_idx = active_idx - 1
                elif key == Qt.Key.Key_Right:
                    new_idx = active_idx + 1
                elif key == Qt.Key.Key_Up:
                    new_idx = active_idx - cols
                elif key == Qt.Key.Key_Down:
                    new_idx = active_idx + cols
                    
                if 0 <= new_idx < len(widgets):
                    self.widget._on_item_clicked(widgets[new_idx].item_data)
                    widgets[new_idx].setFocus()
                    event.accept()
                    return

        super().keyPressEvent(event)

    def done(self, r):
        if hasattr(self, "widget") and hasattr(self.widget, "player"):
            try:
                self.widget.player.stop()
                self.widget.player.setSource(QUrl())
            except Exception:
                pass
        super().done(r)

    def closeEvent(self, event):
        if hasattr(self, "widget") and hasattr(self.widget, "player"):
            try:
                self.widget.player.stop()
                self.widget.player.setSource(QUrl())
            except Exception:
                pass
        super().closeEvent(event)
