# ui/workflow/workflow_page.py
"""Workflow Studio – visual node editor page for NAVTools."""

from __future__ import annotations

import json
import uuid
import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QPointF, QRectF, QTimer, Qt, Signal, QLineF, QMimeData, QRect, QPoint
)
from PySide6.QtGui import (
    QBrush, QColor, QCursor, QFont, QLinearGradient,
    QPainter, QPainterPath, QPen, QPolygonF, QTransform,
    QIcon, QPixmap
)
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QGraphicsDropShadowEffect,
    QGraphicsEllipseItem, QGraphicsItem, QGraphicsObject,
    QGraphicsPathItem, QGraphicsProxyWidget, QGraphicsScene,
    QGraphicsView, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QScrollBar, QSpinBox, QTextEdit, QVBoxLayout,
    QWidget, QCheckBox, QGraphicsSceneMouseEvent, QSizePolicy, QGridLayout,
)

from services.flow_model_provider import model_provider
from ui.workflow.models import (
    ConnectionData, NodeData, WorkflowData,
    deserialize_workflow, save_workflow, serialize_workflow,
)
from ui.workflow.node_palette import NodePalette
from ui.workflow.node_registry import NODE_TYPES, get_node_type, can_connect
from ui.workflow.toolbar import WorkflowToolbar

try:
    from utils.logger import log
except ImportError:
    import logging
    log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# Theme
# ═══════════════════════════════════════════════════════════════════════
_BG_APP = "#0f1115"
_BG_SURFACE = "#16191f"
_BG_CARD = "#1b2028"
_BORDER = "#2a3140"
_TEXT = "#e2e8f0"
_TEXT_MUTED = "#8b949e"
_ACCENT = "#3b82f6"
_ACCENT_HOVER = "#60a5fa"
_SUCCESS = "#10b981"
_DANGER = "#ef4444"
_WARNING = "#f59e0b"
_GRID_SIZE = 20
_NODE_W = 280
_PORT_R = 5


# ═══════════════════════════════════════════════════════════════════════
# Port Item
# ═══════════════════════════════════════════════════════════════════════
class _PortItem(QGraphicsEllipseItem):
    """A small circle representing an input or output port on a node."""

    def __init__(self, port_def: dict, is_input: bool, parent: QGraphicsItem | None = None):
        d = _PORT_R * 2
        super().__init__(-_PORT_R, -_PORT_R, d, d, parent)
        self.port_def = port_def
        self.is_input = is_input
        self.port_name = port_def.get("name", "")
        self.port_type = port_def.get("type", "any")
        self.connections: list[_ConnectionWire] = []
        self._idle_color = QColor(_TEXT_MUTED)
        self.setBrush(QBrush(self._idle_color))
        self.setPen(QPen(QColor(_BORDER), 1))
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges)
        self.setZValue(10)

    def hoverEnterEvent(self, ev):
        self.setBrush(QBrush(QColor(_ACCENT)))
        self.setScale(1.3)
        super().hoverEnterEvent(ev)

    def hoverLeaveEvent(self, ev):
        c = QColor(_SUCCESS) if self.connections else self._idle_color
        self.setBrush(QBrush(c))
        self.setScale(1.0)
        super().hoverLeaveEvent(ev)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
            for wire in self.connections:
                wire.update_path()
        return super().itemChange(change, value)




# ═══════════════════════════════════════════════════════════════════════
# Connection Wire
# ═══════════════════════════════════════════════════════════════════════
class _ConnectionWire(QGraphicsPathItem):
    """Bezier curve connecting two ports."""

    def __init__(self, src_port: _PortItem, dst_port: _PortItem | None = None):
        super().__init__()
        self.src_port = src_port
        self.dst_port = dst_port
        self._color = QColor(_ACCENT)
        self.setPen(QPen(self._color, 2, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap))
        self.setZValue(1)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self._running = False
        if dst_port:
            self.update_path()

    def update_path(self, end_pos: QPointF | None = None):
        p1 = self.src_port.scenePos()
        p2 = end_pos if end_pos else (self.dst_port.scenePos() if self.dst_port else p1)
        path = QPainterPath(p1)
        dx = abs(p2.x() - p1.x()) * 0.5
        dx = max(dx, 50)
        path.cubicTo(p1.x() + dx, p1.y(), p2.x() - dx, p2.y(), p2.x(), p2.y())
        self.setPath(path)

    def set_running(self, running: bool):
        self._running = running
        pen = self.pen()
        if running:
            pen.setColor(QColor(_SUCCESS))
        else:
            pen.setColor(self._color)
        self.setPen(pen)

    def hoverEnterEvent(self, ev):
        p = self.pen()
        p.setWidth(4)
        p.setColor(QColor("#60a5fa"))
        self.setPen(p)
        super().hoverEnterEvent(ev)

    def hoverLeaveEvent(self, ev):
        p = self.pen()
        p.setWidth(2)
        p.setColor(QColor(_SUCCESS) if self._running else self._color)
        self.setPen(p)
        super().hoverLeaveEvent(ev)

    def paint(self, painter, option, widget=None):
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawPath(self.path())
        
        # draw arrowhead at end
        if self.dst_port:
            p = self.path()
            end = p.pointAtPercent(1.0)
            t = max(0.0, p.percentAtLength(p.length() - 8))
            pre = p.pointAtPercent(t)
            angle_line = QLineF(pre, end)
            arrow_size = 6
            import math
            a = math.radians(angle_line.angle())
            p1 = end + QPointF(math.cos(a + 2.6) * arrow_size, -math.sin(a + 2.6) * arrow_size)
            p2 = end + QPointF(math.cos(a - 2.6) * arrow_size, -math.sin(a - 2.6) * arrow_size)
            painter.setPen(self.pen())
            painter.setBrush(QBrush(self.pen().color()))
            painter.drawPolygon(QPolygonF([end, p1, p2]))
        super().paint(painter, option, widget)

class _ClickableLabel(QLabel):
    clicked_event = Signal(object)
    
    def mousePressEvent(self, ev):
        if ev.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            ev.accept()
        else:
            super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            self.clicked_event.emit(ev)
            ev.accept()
        else:
            super().mouseReleaseEvent(ev)

class _PreviewButton(QPushButton):
    clicked_event = Signal(object)

    def mousePressEvent(self, ev):
        if ev.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            ev.accept()
        else:
            super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            if self.rect().contains(ev.pos()):
                self.clicked_event.emit(ev)
            ev.accept()
        else:
            super().mouseReleaseEvent(ev)



def _get_rounded_pixmap(pixmap: QPixmap, radius: int = 6) -> QPixmap:
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


class VideoPreviewCard(QWidget):
    def __init__(self, file_path: str, width: int = 240, height: int = 135, all_files=None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.all_files = all_files or [file_path]
        self.setFixedSize(width, height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("background: black; border-radius: 4px;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.thumb_label = QLabel(self)
        self.thumb_label.setScaledContents(True)
        self.thumb_label.setFixedSize(width, height)
        layout.addWidget(self.thumb_label)
        
        from PySide6.QtMultimedia import QMediaPlayer, QVideoSink
        from PySide6.QtCore import QUrl
        
        self.player = QMediaPlayer(self)
        self.player.setLoops(QMediaPlayer.Loops.Infinite)
        self.player.setSource(QUrl.fromLocalFile(file_path))
        
        self.sink = QVideoSink(self)
        self.player.setVideoOutput(self.sink)
        self.sink.videoFrameChanged.connect(self._on_frame_changed)
        
        self._load_thumbnail(width, height)
        self._is_playing = False
        
    def _load_thumbnail(self, w, h):
        try:
            import cv2
            cap = cv2.VideoCapture(self.file_path)
            ret, frame = cap.read()
            cap.release()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                fh, fw, ch = frame.shape
                from PySide6.QtGui import QImage
                qimg = QImage(frame.data, fw, fh, ch * fw, QImage.Format.Format_RGB888).copy()
                pix = QPixmap.fromImage(qimg)
                if not pix.isNull():
                    scaled = pix.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                    cropped = scaled.copy(0, 0, w, h)
                    rounded = _get_rounded_pixmap(cropped, 4)
                    
                    # Draw play button overlay
                    painter = QPainter(rounded)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    painter.setBrush(QColor(15, 17, 21, 180))
                    painter.setPen(Qt.PenStyle.NoPen)
                    cx, cy = w // 2, h // 2
                    r = min(w, h) // 4
                    painter.drawEllipse(QPoint(cx, cy), r, r)
                    
                    painter.setBrush(QColor("#3b82f6"))
                    tri_size = r // 2
                    painter.drawPolygon([
                        QPoint(cx - tri_size // 2, cy - tri_size),
                        QPoint(cx - tri_size // 2, cy + tri_size),
                        QPoint(cx + tri_size, cy),
                    ])
                    painter.end()
                    
                    self.thumb_label.setPixmap(rounded)
                    return
        except Exception as e:
            print("Error loading video frame thumbnail:", e)
            
        from ui.workflow.preview_panel import _make_video_thumbnail
        pm = _make_video_thumbnail(self.file_path, w)
        self.thumb_label.setPixmap(pm)
        
    def _on_frame_changed(self, frame):
        if not self._is_playing:
            return
        image = frame.toImage()
        if not image.isNull():
            pixmap = QPixmap.fromImage(image)
            scaled = pixmap.scaled(self.width(), self.height(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            cropped = scaled.copy(0, 0, self.width(), self.height())
            rounded = _get_rounded_pixmap(cropped, 4)
            self.thumb_label.setPixmap(rounded)
            
    def enterEvent(self, ev):
        if Path(self.file_path).exists():
            self._is_playing = True
            self.player.play()
        super().enterEvent(ev)
        
    def leaveEvent(self, ev):
        if Path(self.file_path).exists():
            self._is_playing = False
            self.player.pause()
            self._load_thumbnail(self.width(), self.height())
        super().leaveEvent(ev)
        
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            if Path(self.file_path).exists():
                from ui.widgets.video_preview_dialog import VideoPreviewDialog
                self._is_playing = False
                self.player.pause()
                dlg = VideoPreviewDialog(self.file_path, parent=self.window())
                dlg.exec()
        super().mousePressEvent(ev)


class ImagePreviewCard(QWidget):
    def __init__(self, file_path: str, width: int = 240, height: int = 135, all_files=None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.all_files = all_files or [file_path]
        self.setFixedSize(width, height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.thumb_label = QLabel(self)
        self.thumb_label.setScaledContents(True)
        self.thumb_label.setFixedSize(width, height)
        layout.addWidget(self.thumb_label)
        
        self._load_thumbnail(width, height)
        
    def _load_thumbnail(self, w, h):
        try:
            pix = QPixmap(self.file_path)
            if not pix.isNull():
                scaled = pix.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                cropped = scaled.copy(0, 0, w, h)
                rounded = _get_rounded_pixmap(cropped, 4)
                self.thumb_label.setPixmap(rounded)
                return
        except Exception as e:
            print("Error loading image thumbnail:", e)
            
        self.thumb_label.setText("Lỗi nạp ảnh")
        
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            if Path(self.file_path).exists():
                from ui.workflow.preview_panel import PreviewImageDialog
                try:
                    idx = self.all_files.index(self.file_path)
                except ValueError:
                    idx = 0
                dlg = PreviewImageDialog(self.all_files, start_index=idx, parent=self.window())
                dlg.exec()
        super().mousePressEvent(ev)


class WorkflowMediaPreviewWidget(QWidget):
    def __init__(self, node: _VisualNode, name: str, default_val: Any = None, parent=None):
        super().__init__(parent)
        self._node = node
        self._name = name
        self._default = default_val or []
        self._current_files = []
        
        self.setStyleSheet("background: transparent;")
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(4)
        
        self.placeholder = QPushButton("Đang chờ dữ liệu...")
        self.placeholder.setStyleSheet(f"background: {_BG_APP}; border: 1px dashed {_BORDER}; border-radius: 4px; color: {_TEXT_MUTED}; text-align: center;")
        self.placeholder.setFixedSize(240, 135)
        self.main_layout.addWidget(self.placeholder)
        
        self.grid_widget = None
        
    def update_media(self, files):
        if not files:
            self._current_files = []
            self.placeholder.show()
            if self.grid_widget:
                self.grid_widget.hide()
            return
            
        self._current_files = files
        self.placeholder.hide()
        
        if self.grid_widget:
            self.main_layout.removeWidget(self.grid_widget)
            self.grid_widget.deleteLater()
            self.grid_widget = None
            
        # Detect aspect ratio
        is_portrait = False
        try:
            f = files[0]
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                pix = QPixmap(f)
                if not pix.isNull() and pix.height() > pix.width():
                    is_portrait = True
            else:
                import cv2
                cap = cv2.VideoCapture(f)
                vw = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                vh = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                cap.release()
                if vh > vw:
                    is_portrait = True
        except Exception:
            pass
            
        self.grid_widget = QWidget()
        self.grid_widget.setStyleSheet("background: transparent;")
        grid_lay = QGridLayout(self.grid_widget)
        grid_lay.setContentsMargins(0, 0, 0, 0)
        grid_lay.setSpacing(4)
        
        count = len(files)
        cols = 2 if count > 1 else 1
        
        max_w = 264
        if cols == 1:
            if is_portrait:
                w = 135
                h = 240
            else:
                w = max_w
                h = 148
        else:
            w = (max_w - 4) // 2
            if is_portrait:
                h = int(w * 16 / 9)
            else:
                h = int(w * 9 / 16)
            
        for i, f in enumerate(files):
            r = i // cols
            c = i % cols
            
            is_vid = f.lower().endswith(('.mp4', '.mov', '.avi', '.webm', '.mkv'))
            if is_vid:
                card = VideoPreviewCard(f, w, h, all_files=files, parent=self)
            else:
                card = ImagePreviewCard(f, w, h, all_files=files, parent=self)
                
            grid_lay.addWidget(card, r, c)
            
        self.main_layout.addWidget(self.grid_widget)
        self.grid_widget.show()


# ═══════════════════════════════════════════════════════════════════════
# Visual Node
# ═══════════════════════════════════════════════════════════════════════
class _VisualNode(QGraphicsObject):
    """A draggable node on the canvas with embedded config widgets."""

    run_clicked = Signal(str)     # node_id
    clone_clicked = Signal(str)   # node_id
    delete_clicked = Signal(str)  # node_id

    def __init__(self, node_data: NodeData, node_def: dict):
        super().__init__()
        self.node_data = node_data
        self.node_def = node_def
        self._color = QColor(node_def.get("color", _ACCENT))
        self._state = node_data.state
        self._w = _NODE_W
        self._header_h = 36
        self._body_h = 0
        self._footer_h = 10
        self._border_r = 12

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setZValue(5)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)

        # Shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

        # Ports
        self.input_ports: list[_PortItem] = []
        self.output_ports: list[_PortItem] = []
        self._create_ports()

        # Embedded config widget
        self._proxy: QGraphicsProxyWidget | None = None
        self._config_widget: QWidget | None = None
        self._config_fields: dict[str, Any] = {}
        self._create_config_widget()

        # Position
        self.setPos(node_data.x, node_data.y)

    def _create_ports(self):
        inputs = self.node_def.get("inputs", [])
        outputs = self.node_def.get("outputs", [])
        for i, p_def in enumerate(inputs):
            port = _PortItem(p_def, is_input=True, parent=self)
            y = self._header_h + 20 + i * 24
            port.setPos(0, y)
            self.input_ports.append(port)
        for i, p_def in enumerate(outputs):
            port = _PortItem(p_def, is_input=False, parent=self)
            y = self._header_h + 20 + i * 24
            port.setPos(self._w, y)
            self.output_ports.append(port)

    def _create_config_widget(self):
        if self._proxy:
            if self.scene():
                self.scene().removeItem(self._proxy)
            self._proxy.deleteLater()
            self._proxy = None
            self._config_widget = None
            self._config_fields.clear()
            
        tabs = self.node_def.get("config_tabs", [])
        fields = self.node_def.get("config_fields", [])
        global_fields = self.node_def.get("global_fields", [])
        
        if not fields and not tabs and not global_fields:
            self._body_h = 10
            self._reposition_ports()
            return
        widget = QWidget()
        widget.setStyleSheet(f"""
            QWidget {{ background: transparent; color: {_TEXT}; font-size: 11px; }}
            QTextEdit {{ background: {_BG_APP}; border: 1px solid {_BORDER}; border-radius: 4px;
                         color: {_TEXT}; padding: 4px; font-size: 11px; }}
            QComboBox {{ background: {_BG_APP}; border: 1px solid {_BORDER}; border-radius: 4px;
                         color: {_TEXT}; padding: 2px 6px; font-size: 11px; }}
            QSpinBox {{ background: {_BG_APP}; border: 1px solid {_BORDER}; border-radius: 4px;
                        color: {_TEXT}; padding: 2px 6px; font-size: 11px; }}
            QCheckBox {{ color: {_TEXT}; font-size: 11px; }}
            QLineEdit {{ background: {_BG_APP}; border: 1px solid {_BORDER}; border-radius: 4px;
                         color: {_TEXT}; padding: 2px 6px; font-size: 11px; }}
            QPushButton {{ background: {_BG_APP}; border: 1px solid {_BORDER}; border-radius: 4px;
                           color: {_TEXT}; padding: 4px 8px; font-size: 11px; }}
            QPushButton:hover {{ border-color: {_ACCENT}; }}
            QLabel {{ color: {_TEXT_MUTED}; font-size: 10px; background: transparent; }}
        """)
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(8, 4, 8, 4)
        main_layout.setSpacing(4)

        fields_to_process = []
        if tabs:
            from PySide6.QtWidgets import QTabWidget
            tab_widget = QTabWidget()
            tab_widget.setStyleSheet(f"""
                QTabWidget::pane {{ border: none; top: 0px; }}
                QTabBar::tab {{ background: {_BG_APP}; border: 1px solid {_BORDER}; border-radius: 12px; padding: 4px 16px; color: {_TEXT_MUTED}; font-size: 11px; margin-right: 4px; margin-bottom: 8px; }}
                QTabBar::tab:selected {{ background: {_ACCENT}; color: white; border: 1px solid {_ACCENT}; }}
                QTabBar::tab:hover:!selected {{ border-color: {_ACCENT}; }}
            """)
            main_layout.addWidget(tab_widget)
            for tab_data in tabs:
                tab_name = tab_data.get("name", "Tab")
                page = QWidget()
                page_layout = QVBoxLayout(page)
                page_layout.setContentsMargins(0, 0, 0, 0)
                page_layout.setSpacing(4)
                page_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
                for f in tab_data.get("fields", []):
                    fields_to_process.append((f, page_layout))
                tab_widget.addTab(page, tab_name)
        else:
            for f in fields:
                fields_to_process.append((f, main_layout))
                
        for f in global_fields:
            fields_to_process.append((f, main_layout))

        for field, layout in fields_to_process:
            name = field.get("name", "")
            ftype = field.get("type", "text")
            label = field.get("label", name)
            default = field.get("default", "")

            lbl = QLabel(label)
            layout.addWidget(lbl)

            if ftype == "textarea":
                w = QTextEdit()
                w.setMinimumHeight(60)
                # To make sure it doesn't just infinitely expand, set a reasonable max height or sizing policy
                w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
                w.setPlainText(str(self.node_data.config.get(name, default)))
                self._config_fields[name] = w
                layout.addWidget(w)
                
                # Update body height dynamically if user types
                def _on_text_changed(te=w):
                    doc_h = int(te.document().size().height()) + 10
                    new_h = min(500, max(60, doc_h))
                    if te.height() != new_h:
                        te.setFixedHeight(new_h)
                        self._config_widget.adjustSize()
                        self._body_h = self._config_widget.sizeHint().height() + 8
                        self._reposition_ports()
                        self.update()
                
                w.textChanged.connect(_on_text_changed)
            elif ftype == "combo":
                w = QComboBox()
                if name == "model":
                    # Dynamically get models based on node type
                    if "Tạo Ảnh" in self.node_def.get("title", ""):
                        image_models = model_provider.models.get("image_models", [])
                        options = [m.get("name", "") for m in image_models if m.get("name")]
                        if not options:
                            options = field.get("options", [])
                    elif "Tạo Video" in self.node_def.get("title", ""):
                        video_models = model_provider.models.get("video_models", [])
                        options = [m.get("name", "") for m in video_models if m.get("name")]
                        if not options:
                            options = field.get("options", [])
                    else:
                        options = field.get("options", [])
                else:
                    options = field.get("options", [])
                w.addItems(options)
                w.setCurrentText(str(self.node_data.config.get(name, default)))
                self._config_fields[name] = w
                layout.addWidget(w)

            elif ftype == "number":
                w = QSpinBox()
                w.setRange(-1, 999999)
                w.setValue(int(self.node_data.config.get(name, default)))
                self._config_fields[name] = w
                layout.addWidget(w)
            elif ftype == "checkbox":
                w = QCheckBox()
                w.setChecked(bool(self.node_data.config.get(name, default)))
                self._config_fields[name] = w
                layout.addWidget(w)
            elif ftype in ("image_upload", "video_upload"):
                btn_text = "Chọn ảnh" if ftype == "image_upload" else "Chọn video"
                w = QPushButton(btn_text)
                w._files = list(self.node_data.config.get(name, default) or [])
                count_lbl = QLabel(f"{len(w._files)} tệp đã chọn")
                count_lbl.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: 10px;")
                
                # Preview button
                preview = QPushButton()
                preview.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                preview.setStyleSheet(f"background: {_BG_APP}; border: 1px solid {_BORDER}; border-radius: 4px;")
                preview.setFixedSize(240, 135) # 16:9 ratio
                preview.hide()
                
                # Clear button
                btn_clear = QPushButton("✕", preview)
                btn_clear.setFixedSize(20, 20)
                btn_clear.setStyleSheet("background: #ef4444; color: white; border-radius: 10px; font-weight: bold; font-size: 10px; border: none;")
                btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_clear.move(240 - 24, 4)
                
                def _clear_files(_c=False, wf=w, cl=count_lbl, pr=preview):
                    wf._files = []
                    cl.setText("0 tệp đã chọn")
                    pr.hide()
                    self._config_widget.adjustSize()
                    self._body_h = self._config_widget.sizeHint().height() + 8
                    self._reposition_ports()
                    self.update()
                    
                btn_clear.clicked.connect(_clear_files)
                
                def _update_preview(files, ft):
                    if not files:
                        preview.hide()
                        return
                    f = files[0]
                    if "image" in ft:
                        from PySide6.QtGui import QPixmap, QIcon
                        pixmap = QPixmap(f)
                        if not pixmap.isNull():
                            scaled_pixmap = pixmap.scaled(preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                            preview.setIcon(QIcon(scaled_pixmap))
                            preview.setIconSize(preview.size())
                            preview.setStyleSheet(f"background: transparent; border: none; border-radius: 4px; padding: 0; margin: 0;")
                            preview.setCursor(Qt.CursorShape.PointingHandCursor)
                            preview.show()
                        else:
                            preview.hide()
                    else:
                        from ui.workflow.preview_panel import _make_video_thumbnail
                        from PySide6.QtGui import QIcon
                        pm = _make_video_thumbnail(f, 240)
                        if not pm.isNull():
                            preview.setText("")
                            preview.setIcon(QIcon(pm))
                            preview.setIconSize(preview.size())
                            preview.setStyleSheet(f"background: transparent; border: none; border-radius: 4px; padding: 0; margin: 0;")
                            preview.setCursor(Qt.CursorShape.PointingHandCursor)
                            preview.show()
                        else:
                            preview.setText("▶ Nhấn để xem Video")
                            preview.setStyleSheet(f"background: {_BG_APP}; border: 1px solid {_BORDER}; border-radius: 4px; color: {_ACCENT}; font-size: 12px;")
                            preview.setCursor(Qt.CursorShape.PointingHandCursor)
                            preview.show()

                _update_preview(w._files, ftype)

                def _pick(_checked=False, btn=w, cl=count_lbl, ft=ftype, nm=name):
                    filt = "Ảnh (*.png *.jpg *.jpeg *.webp);;Tất cả (*)" if "image" in ft else "Video (*.mp4 *.mov *.avi);;Tất cả (*)"
                    
                    # Cố gắng lấy cửa sổ chính làm parent để dialog không bị chìm xuống dưới
                    parent_win = None
                    if self.scene() and self.scene().views():
                        parent_win = self.scene().views()[0].window()
                        
                    files, _ = QFileDialog.getOpenFileNames(parent_win, btn_text, "", filt)
                    if files:
                        btn._files = files
                        cl.setText(f"{len(files)} tệp đã chọn")
                        _update_preview(files, ft)
                        # Resize parent widget to fit new image
                        self._config_widget.adjustSize()
                        self._body_h = self._config_widget.sizeHint().height() + 8
                        self._reposition_ports()
                        self.update()

                w.clicked.connect(_pick)
                
                def _open_preview_left(pr=preview, wf=w):
                    if not wf._files:
                        return
                    f = wf._files[0]
                    if not os.path.exists(f):
                        return
                        
                    from ui.workflow.preview_panel import PreviewImageDialog, PreviewVideoDialog
                    if f.endswith(('.png', '.jpg', '.jpeg', '.webp')):
                        dlg = PreviewImageDialog([f], parent=None)
                        dlg.exec()
                    else:
                        from PySide6.QtGui import QDesktopServices
                        from PySide6.QtCore import QUrl
                        QDesktopServices.openUrl(QUrl.fromLocalFile(f))
                    
                def _open_preview_right(pos, pr=preview, wf=w):
                    if not wf._files:
                        return
                    f = wf._files[0]
                    if not os.path.exists(f):
                        return
                        
                    from PySide6.QtWidgets import QMenu, QApplication
                    from PySide6.QtGui import QImage
                    menu = QMenu(preview)
                    menu.setStyleSheet("""
                        QMenu { background: #1b2028; border: 1px solid #2a3140; color: #e2e8f0; border-radius: 4px; }
                        QMenu::item { padding: 6px 24px; }
                        QMenu::item:selected { background: #3b82f6; }
                    """)
                    is_img = f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
                    copy_action = menu.addAction("📋 Sao chép ảnh" if is_img else "📋 Sao chép tệp")
                        
                    action = menu.exec(pr.mapToGlobal(pos))
                    if action == copy_action:
                        from PySide6.QtCore import QMimeData, QUrl
                        clipboard = QApplication.clipboard()
                        mime = QMimeData()
                        if is_img:
                            mime.setImageData(QImage(f))
                        mime.setUrls([QUrl.fromLocalFile(f)])
                        clipboard.setMimeData(mime)
                                
                preview.pressed.connect(_open_preview_left)
                preview.customContextMenuRequested.connect(_open_preview_right)

                self._config_fields[name] = w
                layout.addWidget(w)
                layout.addWidget(count_lbl)
                layout.addWidget(preview)
                
            elif ftype == "media_preview":
                preview = WorkflowMediaPreviewWidget(self, name, default)
                
                # Check default
                initial_files = list(self.node_data.config.get(name, default) or [])
                if initial_files:
                    preview.update_media(initial_files)
                
                self._config_fields[name] = preview
                layout.addWidget(preview)
            elif ftype == "frame_pair":
                # Horizontal layout: [Start] [⇄] [End]
                frame_container = QWidget()
                frame_lay = QHBoxLayout(frame_container)
                frame_lay.setContentsMargins(0, 2, 0, 2)
                frame_lay.setSpacing(4)

                frame_size = 90
                saved_data = self.node_data.config.get(name, default) or {}

                def _make_frame_box(label_text, initial_files):
                    """Create a clickable frame box with label and thumbnail."""
                    box = QWidget()
                    box_lay = QVBoxLayout(box)
                    box_lay.setContentsMargins(0, 0, 0, 0)
                    box_lay.setSpacing(2)

                    thumb_btn = QPushButton(label_text)
                    thumb_btn.setFixedSize(frame_size, frame_size)
                    thumb_btn.setStyleSheet(f"""
                        QPushButton {{
                            background: {_BG_APP}; border: 1px dashed {_BORDER}; border-radius: 6px;
                            color: {_TEXT_MUTED}; font-size: 10px;
                        }}
                        QPushButton:hover {{ border-color: {_ACCENT}; }}
                    """)
                    thumb_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    thumb_btn._files = list(initial_files or [])
                    
                    del_btn = QPushButton("✕", thumb_btn)
                    del_btn.setFixedSize(16, 16)
                    del_btn.setStyleSheet("background: #ef4444; color: white; border-radius: 8px; font-weight: bold; font-size: 9px; border: none;")
                    del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    del_btn.move(frame_size - 18, 2)
                    del_btn.hide()
                    
                    def _clear_frame(_c=False, tb=thumb_btn):
                        tb._files = []
                        _refresh_thumb(tb)
                        self._config_widget.adjustSize()
                        self._body_h = self._config_widget.sizeHint().height() + 8
                        self._reposition_ports()
                        self.update()
                    del_btn.clicked.connect(_clear_frame)

                    def _refresh_thumb(tb=thumb_btn):
                        from PySide6.QtGui import QPixmap, QIcon
                        if tb._files and Path(tb._files[0]).exists():
                            pm = QPixmap(tb._files[0])
                            if not pm.isNull():
                                scaled = pm.scaled(tb.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                                tb.setIcon(QIcon(scaled))
                                tb.setIconSize(tb.size())
                                tb.setText("")
                                tb.setStyleSheet(f"QPushButton {{ background: transparent; border: 1px solid {_BORDER}; border-radius: 6px; padding: 0; }} QPushButton:hover {{ border-color: {_ACCENT}; }}")
                                del_btn.show()
                                return
                        del_btn.hide()
                        tb.setIcon(QIcon())
                        tb.setText(label_text)
                        tb.setStyleSheet(f"QPushButton {{ background: {_BG_APP}; border: 1px dashed {_BORDER}; border-radius: 6px; color: {_TEXT_MUTED}; font-size: 10px; }} QPushButton:hover {{ border-color: {_ACCENT}; }}")

                    thumb_btn._refresh = _refresh_thumb

                    def _pick_frame(_c=False, tb=thumb_btn, lt=label_text):
                        if tb._files and Path(tb._files[0]).exists():
                            from ui.workflow.preview_panel import PreviewImageDialog
                            dlg = PreviewImageDialog(tb._files, parent=None)
                            dlg.exec()
                        else:
                            parent_win = None
                            if self.scene() and self.scene().views():
                                parent_win = self.scene().views()[0].window()
                            files, _ = QFileDialog.getOpenFileNames(parent_win, lt, "", "Ảnh (*.png *.jpg *.jpeg *.webp);;Tất cả (*)")
                            if files:
                                tb._files = [files[0]]  # Only 1 frame
                                _refresh_thumb(tb)
                                self._config_widget.adjustSize()
                                self._body_h = self._config_widget.sizeHint().height() + 8
                                self._reposition_ports()
                                self.update()

                    thumb_btn.clicked.connect(_pick_frame)
                    _refresh_thumb()  # Show initial if any

                    lbl = QLabel(label_text)
                    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    lbl.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: 9px; background: transparent;")
                    box_lay.addWidget(thumb_btn, 0, Qt.AlignmentFlag.AlignCenter)
                    box_lay.addWidget(lbl, 0, Qt.AlignmentFlag.AlignCenter)
                    return box, thumb_btn

                start_box, start_btn = _make_frame_box("Bắt\nđầu", saved_data.get("start", []))
                end_box, end_btn = _make_frame_box("Kết\nthúc", saved_data.get("end", []))

                # Swap button
                swap_btn = QPushButton("⇄")
                swap_btn.setFixedSize(28, 28)
                swap_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {_BG_APP}; border: 1px solid {_BORDER}; border-radius: 14px;
                        color: {_ACCENT}; font-size: 14px; font-weight: bold;
                    }}
                    QPushButton:hover {{ border-color: {_ACCENT}; background: #1e293b; }}
                """)
                swap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                swap_btn.setToolTip("Hoán đổi Bắt đầu ↔ Kết thúc")

                def _swap(_c=False, sb=start_btn, eb=end_btn):
                    sb._files, eb._files = eb._files, sb._files
                    sb._refresh()
                    eb._refresh()

                swap_btn.clicked.connect(_swap)

                frame_lay.addWidget(start_box, 1, Qt.AlignmentFlag.AlignCenter)
                frame_lay.addWidget(swap_btn, 0, Qt.AlignmentFlag.AlignCenter)
                frame_lay.addWidget(end_box, 1, Qt.AlignmentFlag.AlignCenter)

                # Store both buttons as a tuple for get_config
                frame_container._start_btn = start_btn
                frame_container._end_btn = end_btn
                self._config_fields[name] = frame_container
                layout.addWidget(frame_container)

            elif ftype == "folder":
                row = QWidget()
                rl = QHBoxLayout(row)
                rl.setContentsMargins(0, 0, 0, 0)
                rl.setSpacing(4)
                le = QLineEdit(str(self.node_data.config.get(name, default)))
                le.setReadOnly(True)
                browse = QPushButton("...")
                browse.setFixedWidth(28)
                browse.clicked.connect(lambda _, l=le: l.setText(
                    QFileDialog.getExistingDirectory(None, "Chọn thư mục") or l.text()))
                rl.addWidget(le, 1)
                rl.addWidget(browse)
                self._config_fields[name] = le
                layout.addWidget(row)
                
            elif ftype == "video_list":
                from ui.workflow.video_list_widget import VideoListWidget
                w = VideoListWidget()
                # Load saved config
                saved_videos = self.node_data.config.get(name, [])
                w.set_videos(list(saved_videos) if saved_videos else [])
                self._config_fields[name] = w
                layout.addWidget(w)
                
                # Auto size
                def _on_vl_changed(vw=w):
                    self._config_widget.adjustSize()
                    self._body_h = self._config_widget.sizeHint().height() + 8
                    self._reposition_ports()
                    self.update()
                w.changed.connect(_on_vl_changed)
                
            elif ftype == "history_picker":
                btn = QPushButton("Chọn từ lịch sử (0)")
                btn.setStyleSheet(f"background: {_BG_APP}; border: 1px dashed {_BORDER}; padding: 4px; color: {_TEXT_MUTED};")
                btn._files = self.node_data.config.get(name, [])
                if btn._files:
                    btn.setText(f"Đã chọn {len(btn._files)} mục")
                    
                def _open_history_picker(b=btn):
                    from ui.workflow.history_picker_dialog import HistoryPickerDialog
                    main_win = None
                    from PySide6.QtWidgets import QApplication
                    for w in QApplication.topLevelWidgets():
                        if hasattr(w, "db"):
                            main_win = w
                            break
                    dlg = HistoryPickerDialog(main_win, media_type="all", parent=None)
                    if dlg.exec():
                        b._files = [it["path"] for it in dlg.selected_items]
                        b.setText(f"Đã chọn {len(b._files)} mục" if b._files else "Chọn từ lịch sử (0)")
                        self._config_widget.adjustSize()
                        self._body_h = self._config_widget.sizeHint().height() + 8
                        self._reposition_ports()
                        self.update()
                btn.clicked.connect(_open_history_picker)
                self._config_fields[name] = btn
                layout.addWidget(btn)

        # Dynamic duration: Omni Flash gets 10s, others 4s/6s/8s
        model_widget = self._config_fields.get("model")
        duration_widget = self._config_fields.get("duration")
        if isinstance(model_widget, QComboBox) and isinstance(duration_widget, QComboBox):
            def _on_model_changed(model_text, dw=duration_widget):
                current_dur = dw.currentText()
                dw.blockSignals(True)
                dw.clear()
                if "Omni Flash" in model_text:
                    dw.addItems(["4s", "6s", "8s", "10s"])
                else:
                    dw.addItems(["4s", "6s", "8s"])
                # Restore selection if valid
                idx = dw.findText(current_dur)
                if idx >= 0:
                    dw.setCurrentIndex(idx)
                else:
                    dw.setCurrentIndex(dw.count() - 1)  # pick last (8s)
                dw.blockSignals(False)

            model_widget.currentTextChanged.connect(_on_model_changed)
            # Trigger once to set initial state
            _on_model_changed(model_widget.currentText())

        widget.setFixedWidth(int(self._w - 16))
        widget.adjustSize()
        self.prepareGeometryChange()
        self._body_h = widget.sizeHint().height() + 8
        self._config_widget = widget
        self._proxy = QGraphicsProxyWidget(self)
        self._proxy.setWidget(widget)
        self._proxy.setPos(8, self._header_h)
        self._reposition_ports()

    def on_connections_changed(self):
        # Refresh video list if this node has a video_list widget
        w = self._config_fields.get("videos")
        if w and hasattr(w, "sync_with_edges"):
            w.sync_with_edges(self.input_ports[0].connections)

    def _reposition_ports(self):
        total_h = self._header_h + self._body_h + self._footer_h
        inputs = self.node_def.get("inputs", [])
        outputs = self.node_def.get("outputs", [])
        for i, port in enumerate(self.input_ports):
            spacing = total_h / (len(inputs) + 1)
            port.setPos(0, spacing * (i + 1))
        for i, port in enumerate(self.output_ports):
            spacing = total_h / (len(outputs) + 1)
            port.setPos(self._w, spacing * (i + 1))

    def get_config(self) -> dict:
        cfg = {}
        for name, widget in self._config_fields.items():
            if isinstance(widget, QTextEdit):
                cfg[name] = widget.toPlainText()
            elif isinstance(widget, QComboBox):
                cfg[name] = widget.currentText()
            elif isinstance(widget, QSpinBox):
                cfg[name] = widget.value()
            elif isinstance(widget, QCheckBox):
                cfg[name] = widget.isChecked()
            elif isinstance(widget, QPushButton) and hasattr(widget, "_files"):
                cfg[name] = widget._files
            elif isinstance(widget, QLineEdit):
                cfg[name] = widget.text()
            elif hasattr(widget, "get_videos"):
                # video_list type
                cfg[name] = widget.get_videos()
            elif hasattr(widget, "_start_btn") and hasattr(widget, "_end_btn"):
                # frame_pair type
                cfg[name] = {
                    "start": widget._start_btn._files,
                    "end": widget._end_btn._files,
                }
        return cfg

    def set_state(self, state: str):
        self._state = state
        self.node_data.state = state
        self.update()

    def boundingRect(self) -> QRectF:
        h = self._header_h + self._body_h + self._footer_h
        return QRectF(-2, -2, self._w + 4, h + 4)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self._header_h + self._body_h + self._footer_h
        rect = QRectF(0, 0, self._w, h)

        # State border color
        state_colors = {
            "idle": QColor(_BORDER),
            "running": QColor(_WARNING),
            "success": QColor(_SUCCESS),
            "error": QColor(_DANGER),
            "waiting": QColor(_ACCENT),
        }
        border_c = state_colors.get(self._state, QColor(_BORDER))

        # Body fill (Glassmorphism effect)
        # Use a slightly transparent dark background
        painter.setPen(QPen(border_c, 1.5))
        painter.setBrush(QBrush(QColor(24, 26, 31, 230)))
        painter.drawRoundedRect(rect, 14, 14)

        # Icon + Title
        icon = self.node_def.get("icon", "\uE8C8") # Default to document icon
        title = self.node_def.get("title", "Node")
        
        # Icon (Segoe Fluent Icons)
        painter.setPen(QPen(QColor("#ffffff")))
        painter.setFont(QFont("Segoe Fluent Icons", 12))
        painter.drawText(QRectF(12, 0, 24, self._header_h), Qt.AlignmentFlag.AlignVCenter, icon)
        
        # Title (Segoe UI)
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        painter.drawText(QRectF(36, 0, self._w - 60, self._header_h), Qt.AlignmentFlag.AlignVCenter, title)

        # Action buttons in header
        btn_w, btn_h = 24, 24
        btn_y = (self._header_h - btn_h) / 2
        
        # Helper to draw icon buttons
        def draw_btn(x, color, icon_str, bg_alpha=40):
            painter.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), bg_alpha)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(x, btn_y, btn_w, btn_h), 6, 6)
            painter.setPen(QPen(color))
            painter.setFont(QFont("Segoe Fluent Icons", 10))
            painter.drawText(QRectF(x, btn_y, btn_w, btn_h), Qt.AlignmentFlag.AlignCenter, icon_str)

        # Run button - show state (if runnable)
        is_runnable = self.node_def.get("runnable", True)
        if is_runnable:
            rx = self._w - 88
            if self._state == "running":
                draw_btn(rx, QColor(_WARNING), "\uE916", 60) # Timer
            elif self._state == "success":
                draw_btn(rx, QColor(_SUCCESS), "\uE73E", 60) # Checkmark
            elif self._state == "error":
                draw_btn(rx, QColor(_DANGER), "\uE711", 60) # Close/Error
            else:
                draw_btn(rx, QColor(_SUCCESS), "\uE768") # Play

        # Clone button
        cx = self._w - 60
        draw_btn(cx, QColor(_ACCENT), "\uE8C8") # Copy
        
        # Delete button
        dx = self._w - 32
        draw_btn(dx, QColor(_DANGER), "\uE74D") # Delete

        # Selection glow
        if self.isSelected():
            painter.setPen(QPen(QColor(_ACCENT_HOVER), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-1, -1, 1, 1), 14, 14)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        h = self._header_h + self._body_h + self._footer_h
        footer_y = h - self._footer_h
        pos = event.pos()

        # Check button clicks in header
        if pos.y() <= self._header_h:
            btn_w, btn_h = 24, 24
            btn_y = (self._header_h - btn_h) / 2
            if btn_y <= pos.y() <= btn_y + btn_h:
                is_runnable = self.node_def.get("runnable", True)
                if is_runnable and (self._w - 88) <= pos.x() <= (self._w - 88 + btn_w):
                    self.run_clicked.emit(self.node_data.id)
                    event.accept()
                    return
                elif self._w - 60 <= pos.x() <= self._w - 60 + btn_w:
                    self.clone_clicked.emit(self.node_data.id)
                    return
                elif self._w - 32 <= pos.x() <= self._w - 32 + btn_w:
                    self.delete_clicked.emit(self.node_data.id)
                    return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        super().mouseReleaseEvent(event)
        # Snap to grid
        x = round(self.x() / _GRID_SIZE) * _GRID_SIZE
        y = round(self.y() / _GRID_SIZE) * _GRID_SIZE
        self.setPos(x, y)
        self.node_data.x = x
        self.node_data.y = y

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for p in self.input_ports + self.output_ports:
                for w in p.connections:
                    w.update_path()
        return super().itemChange(change, value)


# ═══════════════════════════════════════════════════════════════════════
# Canvas Scene with dot grid
# ═══════════════════════════════════════════════════════════════════════
class _CanvasScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(-10000, -10000, 20000, 20000)

    def drawBackground(self, painter: QPainter, rect):
        super().drawBackground(painter, rect)
        painter.fillRect(rect, QColor(_BG_APP))

        # Limit drawing area for performance
        r = rect.intersected(QRectF(-2000, -2000, 4000, 4000))
        if r.isEmpty():
            return

        left = int(r.left()) - (int(r.left()) % _GRID_SIZE)
        top = int(r.top()) - (int(r.top()) % _GRID_SIZE)

        major = _GRID_SIZE * 5
        pen_minor = QPen(QColor("#1e2230"), 1)
        pen_major = QPen(QColor("#252a38"), 2)

        for x in range(left, int(r.right()), _GRID_SIZE):
            for y in range(top, int(r.bottom()), _GRID_SIZE):
                if x % major == 0 and y % major == 0:
                    painter.setPen(pen_major)
                else:
                    painter.setPen(pen_minor)
                painter.drawPoint(x, y)


# ═══════════════════════════════════════════════════════════════════════
# Workflow Canvas (QGraphicsView)
# ═══════════════════════════════════════════════════════════════════════
class WorkflowCanvas(QGraphicsView):
    zoom_changed = Signal(int)
    node_dropped = Signal(str, float, float)

    def __init__(self, parent=None):
        self._scene = _CanvasScene()
        super().__init__(self._scene, parent)
        self._zoom = 100
        self._panning = False
        self._pan_start = None
        self._wiring = False
        self._wire_src: _PortItem | None = None
        self._temp_wire: _ConnectionWire | None = None
        self._locked = False

        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(f"border: none; background: {_BG_APP};")
        self.setAcceptDrops(True)

        # Hint label
        self._hint = QLabel("Kéo thả node từ bảng bên trái vào đây", self)
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setStyleSheet(
            f"color: {_TEXT_MUTED}; font-size: 15px; font-style: italic; "
            f"background: transparent; border: none;"
        )
        self._hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    # ── Zoom ─────────────────────────────────────
    def wheelEvent(self, ev):
        delta = ev.angleDelta().y()
        factor = 1.12 if delta > 0 else 1 / 1.12
        new_zoom = max(25, min(400, int(self._zoom * factor)))
        if new_zoom != self._zoom:
            sf = new_zoom / self._zoom
            self.scale(sf, sf)
            self._zoom = new_zoom
            self.zoom_changed.emit(self._zoom)
        ev.accept()

    def zoom_in(self):
        self._apply_zoom(min(400, self._zoom + 15))

    def zoom_out(self):
        self._apply_zoom(max(25, self._zoom - 15))

    def _apply_zoom(self, z):
        if z != self._zoom:
            sf = z / self._zoom
            self.scale(sf, sf)
            self._zoom = z
            self.zoom_changed.emit(self._zoom)

    def fit_view(self):
        """Fit all nodes in view."""
        items = [i for i in self.scene().items() if isinstance(i, _VisualNode)]
        if not items:
            return
        
        # Now fit in view
        r = self.scene().itemsBoundingRect()
        r.adjust(-60, -60, 60, 60)
        self.fitInView(r, Qt.AspectRatioMode.KeepAspectRatio)
        t = self.transform()
        self._zoom = max(25, min(400, int(t.m11() * 100)))
        self.zoom_changed.emit(self._zoom)

    def center_view(self):
        self.centerOn(0, 0)

    def reset_zoom(self):
        self._apply_zoom(100)

    # ── Pan ──────────────────────────────────────
    def mousePressEvent(self, ev):
        if self._locked:
            ev.ignore()
            return
        # Start wiring from port
        item = self.itemAt(ev.position().toPoint())
        if isinstance(item, _PortItem) and not item.is_input:
            self._wiring = True
            self._wire_src = item
            self._temp_wire = _ConnectionWire(item)
            self.scene().addItem(self._temp_wire)
            ev.accept()
            return
        if (ev.button() == Qt.MouseButton.MiddleButton or
                (ev.button() == Qt.MouseButton.LeftButton and
                 ev.modifiers() & Qt.KeyboardModifier.AltModifier)):
            self._panning = True
            self._pan_start = ev.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            ev.accept()
            return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._wiring and self._temp_wire:
            self._temp_wire.update_path(self.mapToScene(ev.position().toPoint()))
            ev.accept()
            return
        if self._panning and self._pan_start is not None:
            d = ev.position().toPoint() - self._pan_start
            self._pan_start = ev.position().toPoint()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - d.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - d.y())
            ev.accept()
            return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self._wiring:
            self._wiring = False
            item = self.itemAt(ev.position().toPoint())
            if (isinstance(item, _PortItem) and item.is_input and
                    self._wire_src and item.parentItem() != self._wire_src.parentItem()):
                # Valid connection
                if can_connect(self._wire_src.port_type, item.port_type):
                    if self._temp_wire:
                        self._temp_wire.dst_port = item
                        self._temp_wire.update_path()
                        self._wire_src.connections.append(self._temp_wire)
                        item.connections.append(self._temp_wire)
                        item.setBrush(QBrush(QColor(_SUCCESS)))
                        self._wire_src.setBrush(QBrush(QColor(_SUCCESS)))
                        
                        if hasattr(item.parentItem(), "on_connections_changed"):
                            item.parentItem().on_connections_changed()
                        if hasattr(self._wire_src.parentItem(), "on_connections_changed"):
                            self._wire_src.parentItem().on_connections_changed()
                            
                        self._temp_wire = None
                        self._wire_src = None
                        ev.accept()
                        return
            # Invalid drop – remove temp wire
            if self._temp_wire:
                self.scene().removeItem(self._temp_wire)
                self._temp_wire = None
            self._wire_src = None
            ev.accept()
            return
        if self._panning:
            self._panning = False
            self._pan_start = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            ev.accept()
            return
        super().mouseReleaseEvent(ev)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Delete:
            for item in self.scene().selectedItems():
                if isinstance(item, _ConnectionWire):
                    if item.src_port and item in item.src_port.connections:
                        item.src_port.connections.remove(item)
                        if hasattr(item.src_port.parentItem(), "on_connections_changed"):
                            item.src_port.parentItem().on_connections_changed()
                    if item.dst_port and item in item.dst_port.connections:
                        item.dst_port.connections.remove(item)
                        if hasattr(item.dst_port.parentItem(), "on_connections_changed"):
                            item.dst_port.parentItem().on_connections_changed()
                    self.scene().removeItem(item)
            ev.accept()
            return
        super().keyPressEvent(ev)

    # ── Drop from palette ────────────────────────
    def dragEnterEvent(self, ev):
        if ev.mimeData().hasFormat("application/x-workflow-node-type"):
            ev.acceptProposedAction()
        else:
            super().dragEnterEvent(ev)

    def dragMoveEvent(self, ev):
        if ev.mimeData().hasFormat("application/x-workflow-node-type"):
            ev.acceptProposedAction()
        else:
            super().dragMoveEvent(ev)

    def dropEvent(self, ev):
        if ev.mimeData().hasFormat("application/x-workflow-node-type"):
            ntype = bytes(ev.mimeData().data("application/x-workflow-node-type")).decode("utf-8")
            pos = self.mapToScene(ev.position().toPoint())
            self.node_dropped.emit(ntype, pos.x(), pos.y())
            self._hint.hide()
            ev.acceptProposedAction()
        else:
            super().dropEvent(ev)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._hint.setGeometry(0, 0, self.width(), self.height())

    def set_hint_visible(self, v: bool):
        self._hint.setVisible(v)
        if v:
            self._hint.setGeometry(0, 0, self.width(), self.height())


# ═══════════════════════════════════════════════════════════════════════
# Viewport Controls overlay
# ═══════════════════════════════════════════════════════════════════════
class _ViewportControls(QWidget):
    def __init__(self, canvas: WorkflowCanvas, parent=None):
        super().__init__(parent)
        self._canvas = canvas
        self.setFixedWidth(40)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setStyleSheet(f"""
            _ViewportControls {{
                background: {_BG_SURFACE};
                border: 1px solid {_BORDER};
                border-radius: 8px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(2)

        btns = [
            ("＋", "Phóng to", canvas.zoom_in),
            ("－", "Thu nhỏ", canvas.zoom_out),
            ("◻", "Vừa khung", canvas.fit_view),
            ("🔒", "Khóa", self._toggle_lock),
        ]
        self._lock_btn = None
        for text, tip, fn in btns:
            b = QPushButton(text)
            b.setFixedSize(32, 32)
            b.setToolTip(tip)
            b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            b.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {_TEXT};
                    border: none; border-radius: 6px; font-size: 14px;
                }}
                QPushButton:hover {{ background: {_BG_CARD}; }}
            """)
            b.clicked.connect(fn)
            layout.addWidget(b)
            if text == "🔒":
                self._lock_btn = b
        self.adjustSize()

    def _toggle_lock(self):
        self._canvas._locked = not self._canvas._locked
        if self._lock_btn:
            self._lock_btn.setText("🔓" if not self._canvas._locked else "🔒")


# ═══════════════════════════════════════════════════════════════════════
# MiniMap
# ═══════════════════════════════════════════════════════════════════════
class _MiniMap(QWidget):
    def __init__(self, canvas: WorkflowCanvas, parent=None):
        super().__init__(parent)
        self._canvas = canvas
        self.setFixedSize(160, 100)
        self.setStyleSheet(f"background: {_BG_SURFACE}; border: 1px solid {_BORDER}; border-radius: 6px;")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self.update)
        self._timer.start()

    def paintEvent(self, ev):
        super().paintEvent(ev)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(_BG_SURFACE))

        scene = self._canvas.scene()
        if not scene:
            painter.end()
            return
        items = [i for i in scene.items() if isinstance(i, _VisualNode)]
        if not items:
            painter.setPen(QPen(QColor(_TEXT_MUTED)))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "minimap")
            painter.end()
            return

        sr = scene.itemsBoundingRect()
        if sr.isEmpty():
            painter.end()
            return
        m = 8
        vw, vh = self.width() - 2 * m, self.height() - 2 * m
        sx = vw / sr.width() if sr.width() > 0 else 1
        sy = vh / sr.height() if sr.height() > 0 else 1
        s = min(sx, sy)

        for item in items:
            r = item.boundingRect()
            x = m + (item.x() - sr.x()) * s
            y = m + (item.y() - sr.y()) * s
            w = max(3, r.width() * s)
            h = max(2, r.height() * s)
            painter.setPen(Qt.PenStyle.NoPen)
            c = QColor(item.node_def.get("color", _ACCENT))
            painter.setBrush(c)
            painter.drawRoundedRect(int(x), int(y), int(w), int(h), 1, 1)

        vp = self._canvas.mapToScene(self._canvas.viewport().rect()).boundingRect()
        vx = m + (vp.x() - sr.x()) * s
        vy = m + (vp.y() - sr.y()) * s
        painter.setPen(QPen(QColor(_ACCENT_HOVER), 1))
        painter.setBrush(QColor(59, 130, 246, 30))
        painter.drawRoundedRect(int(vx), int(vy), int(vp.width() * s), int(vp.height() * s), 2, 2)
        painter.end()


# ═══════════════════════════════════════════════════════════════════════
# WorkflowStudioPage – main assembly
# ═══════════════════════════════════════════════════════════════════════
class WorkflowStudioPage(QWidget):
    """The full Workflow Studio page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("workflow_studio_page")
        self.setStyleSheet(f"QWidget#workflow_studio_page {{ background: {_BG_APP}; }}")

        self._current_wf: WorkflowData | None = None
        self._dirty = False
        self._visual_nodes: dict[str, _VisualNode] = {}
        self._visual_wires: list[_ConnectionWire] = []

        # Layout
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._toolbar = WorkflowToolbar()
        root.addWidget(self._toolbar)

        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        self._palette = NodePalette()
        body_lay.addWidget(self._palette)

        canvas_container = QWidget()
        canvas_container.setStyleSheet("background: transparent;")
        cc_lay = QVBoxLayout(canvas_container)
        cc_lay.setContentsMargins(0, 0, 0, 0)
        cc_lay.setSpacing(0)

        self._canvas = WorkflowCanvas()
        cc_lay.addWidget(self._canvas)
        body_lay.addWidget(canvas_container, 1)
        root.addWidget(body, 1)

        # Overlays
        self._minimap = _MiniMap(self._canvas, parent=self._canvas)
        self._viewport_ctrl = _ViewportControls(self._canvas, parent=self._canvas)

        # Signals
        self._connect_signals()

        # Auto-save
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(30_000)
        self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start()

    def _connect_signals(self):
        tb = self._toolbar
        tb.run_all.connect(self._on_run_all)
        tb.stop.connect(self._on_stop)
        tb.save.connect(self.save_current)
        tb.import_wf.connect(self._on_import)
        tb.export_wf.connect(self._on_export)
        tb.auto_arrange.connect(self._on_auto_arrange)
        tb.name_changed.connect(self._on_name_changed)
        tb.favorite_toggled.connect(self._on_fav_toggled)
        self._canvas.zoom_changed.connect(tb.set_zoom_level)
        self._canvas.node_dropped.connect(self._on_node_dropped)

    # ── Lifecycle ────────────────────────────────
    def showEvent(self, ev):
        super().showEvent(ev)
        if self._current_wf is None:
            self.new_workflow()
        self._reposition_overlays()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._reposition_overlays()

    def _reposition_overlays(self):
        cw, ch = self._canvas.width(), self._canvas.height()
        # Minimap on RIGHT, Viewport controls on LEFT
        self._viewport_ctrl.move(10, ch - self._viewport_ctrl.height() - 10)
        self._minimap.move(cw - self._minimap.width() - 10, ch - self._minimap.height() - 10)

    # ── Workflow management ──────────────────────
    def new_workflow(self):
        wf = WorkflowData(name="Untitled Workflow")
        self._load_wf(wf)
        self._dirty = False

    def save_current(self):
        if not self._current_wf:
            return
        self._sync_data_from_visual()
        try:
            save_workflow(self._current_wf)
            self._dirty = False
        except Exception as e:
            QMessageBox.warning(self, "Lỗi lưu", str(e))

    def _load_wf(self, wf: WorkflowData):
        self._current_wf = wf
        self._toolbar.set_workflow_name(wf.name)
        self._toolbar.set_favorite(wf.is_favorite)
        self._toolbar.set_running(False)

        # Clear scene
        scene = self._canvas.scene()
        if scene:
            scene.clear()
        self._visual_nodes.clear()
        self._visual_wires.clear()

        # Recreate nodes
        for nd in wf.nodes:
            ndef = get_node_type(nd.node_type)
            if not ndef:
                continue
            vn = self._create_visual_node(nd, ndef)

        # Recreate connections
        for cd in wf.connections:
            src_vn = self._visual_nodes.get(cd.source_node)
            dst_vn = self._visual_nodes.get(cd.target_node)
            if not src_vn or not dst_vn:
                continue
            src_port = self._find_port(src_vn.output_ports, cd.source_port)
            dst_port = self._find_port(dst_vn.input_ports, cd.target_port)
            if src_port and dst_port:
                wire = _ConnectionWire(src_port, dst_port)
                self._canvas.scene().addItem(wire)
                src_port.connections.append(wire)
                dst_port.connections.append(wire)
                dst_port.setBrush(QBrush(QColor(_SUCCESS)))
                src_port.setBrush(QBrush(QColor(_SUCCESS)))
                self._visual_wires.append(wire)

        self._canvas.set_hint_visible(len(wf.nodes) == 0)
        self._dirty = False

    def _find_port(self, ports: list[_PortItem], name: str) -> _PortItem | None:
        for p in ports:
            if p.port_name == name:
                return p
        return ports[0] if ports else None

    def _create_visual_node(self, nd: NodeData, ndef: dict) -> _VisualNode:
        vn = _VisualNode(nd, ndef)
        vn.run_clicked.connect(self._on_node_run)
        vn.clone_clicked.connect(self._on_node_clone)
        vn.delete_clicked.connect(self._on_node_delete)
        scene = self._canvas.scene()
        if scene:
            scene.addItem(vn)
        self._visual_nodes[nd.id] = vn
        return vn

    def _sync_data_from_visual(self):
        """Sync positions and configs from visual nodes back to data model."""
        if not self._current_wf:
            return
        for nd in self._current_wf.nodes:
            vn = self._visual_nodes.get(nd.id)
            if vn:
                nd.x = vn.x()
                nd.y = vn.y()
                nd.config = vn.get_config()

        # Rebuild connections from visual wires
        self._current_wf.connections.clear()
        seen = set()
        for vn in self._visual_nodes.values():
            for port in vn.output_ports:
                for wire in port.connections:
                    if wire.dst_port and id(wire) not in seen:
                        seen.add(id(wire))
                        dst_node = wire.dst_port.parentItem()
                        if isinstance(dst_node, _VisualNode):
                            self._current_wf.connections.append(ConnectionData(
                                source_node=vn.node_data.id,
                                source_port=port.port_name,
                                target_node=dst_node.node_data.id,
                                target_port=wire.dst_port.port_name,
                            ))

    # ── Node actions ─────────────────────────────
    def _on_node_dropped(self, ntype: str, sx: float, sy: float):
        if not self._current_wf:
            return
        ndef = get_node_type(ntype)
        if not ndef:
            return
        nd = NodeData(node_type=ntype, title=ndef.get("title", ntype), x=sx, y=sy)
        for f in ndef.get("config_fields", []):
            if f.get("default") is not None:
                nd.config[f["name"]] = f["default"]
        self._current_wf.nodes.append(nd)
        self._create_visual_node(nd, ndef)
        self._canvas.set_hint_visible(False)
        self._dirty = True

    def _on_node_run(self, node_id: str):
        if hasattr(self, "_executor") and self._executor and self._executor.is_running:
            log.warning("[Workflow] Executor is already running. Please stop it first.")
            return

        vn = self._visual_nodes.get(node_id)
        if vn:
            vn.set_state("running")
            log.info(f"[Workflow] Running node: {vn.node_data.title}")
            # Use executor for single node
            try:
                from ui.workflow.executor import WorkflowExecutor
                main_win = self.window()
                self._sync_data_from_visual()
                configs = {nd.id: self._visual_nodes[nd.id].get_config()
                           for nd in self._current_wf.nodes if nd.id in self._visual_nodes}
                self._executor = WorkflowExecutor(main_win=main_win)
                self._executor.node_finished.connect(self._on_exec_node_done)
                self._executor.log_message.connect(self._on_exec_log)
                self._executor.task_requested.connect(self._on_task_requested)
                self._executor.node_output_updated.connect(self._on_exec_node_output_updated)
                self._executor.run_up_to_node(node_id, serialize_workflow(self._current_wf), configs)
            except Exception as e:
                log.error(f"[Workflow] Node run error: {e}")
                vn.set_state("error")

    def _on_node_clone(self, node_id: str):
        vn = self._visual_nodes.get(node_id)
        if not vn or not self._current_wf:
            return
        nd_old = vn.node_data
        nd = NodeData(
            node_type=nd_old.node_type,
            title=nd_old.title,
            x=nd_old.x + 40,
            y=nd_old.y + 40,
            config=dict(vn.get_config()),
        )
        self._current_wf.nodes.append(nd)
        ndef = get_node_type(nd.node_type)
        if ndef:
            self._create_visual_node(nd, ndef)
        self._dirty = True

    def _on_node_delete(self, node_id: str):
        vn = self._visual_nodes.get(node_id)
        if not vn or not self._current_wf:
            return
        # Remove wires
        for port in vn.input_ports + vn.output_ports:
            for wire in list(port.connections):
                if wire.src_port and wire in wire.src_port.connections:
                    wire.src_port.connections.remove(wire)
                if wire.dst_port and wire in wire.dst_port.connections:
                    wire.dst_port.connections.remove(wire)
                self._canvas.scene().removeItem(wire)
                if wire in self._visual_wires:
                    self._visual_wires.remove(wire)
        self._canvas.scene().removeItem(vn)
        del self._visual_nodes[node_id]
        self._current_wf.nodes = [n for n in self._current_wf.nodes if n.id != node_id]
        self._dirty = True
        self._canvas.set_hint_visible(len(self._current_wf.nodes) == 0)

    # ── Execution ────────────────────────────────
    def _on_run_all(self):
        if not self._current_wf or not self._current_wf.nodes:
            return
        self._toolbar.set_running(True)
        self._sync_data_from_visual()
        for vn in self._visual_nodes.values():
            vn.set_state("waiting")
        try:
            from ui.workflow.executor import WorkflowExecutor
            main_win = self.window()
            self._executor = WorkflowExecutor(main_win=main_win)
            self._executor.node_started.connect(self._on_exec_node_start)
            self._executor.node_finished.connect(self._on_exec_node_done)
            self._executor.execution_finished.connect(self._on_exec_done)
            self._executor.log_message.connect(self._on_exec_log)
            self._executor.task_requested.connect(self._on_task_requested)
            self._executor.node_output_updated.connect(self._on_exec_node_output_updated)
            configs = {nd.id: self._visual_nodes[nd.id].get_config()
                       for nd in self._current_wf.nodes if nd.id in self._visual_nodes}
            self._executor.run_all(serialize_workflow(self._current_wf), configs)
        except Exception as e:
            log.error(f"[Workflow] Execution error: {e}")
            self._toolbar.set_running(False)

    def _on_stop(self):
        if hasattr(self, "_executor"):
            self._executor.stop()
        self._toolbar.set_running(False)
        for vn in self._visual_nodes.values():
            if vn._state in ("running", "waiting"):
                vn.set_state("idle")

    def _on_exec_node_start(self, nid: str):
        vn = self._visual_nodes.get(nid)
        if vn:
            vn.set_state("running")

    def _on_task_requested(self, task_id: int):
        main_win = self.window()
        if main_win:
            vtask = main_win.db.get_task(task_id)
            # Must call _get_task_manager() to lazily init BrowserManager + TaskManager
            manager = main_win._get_task_manager() if hasattr(main_win, '_get_task_manager') else None
            if manager and vtask:
                # Wire toolbar delay into the task
                try:
                    toolbar_delay = self._toolbar.get_delay_seconds()
                    vtask.delay = toolbar_delay
                except Exception:
                    pass
                manager.start_task(vtask)

    def _on_exec_node_done(self, nid: str, state: str):
        vn = self._visual_nodes.get(nid)
        if vn:
            vn.set_state(state)
        # Push results to downstream preview nodes via port connections
        if hasattr(self, "_executor") and self._executor and vn:
            data = self._executor.data_store.get(nid, {})
            output = data.get("output", data.get("preview_files", []))
            if output:
                # Traverse output ports → wires → downstream nodes
                for port in vn.output_ports:
                    for wire in port.connections:
                        if wire.dst_port:
                            dst_node = wire.dst_port.parentItem()
                            if isinstance(dst_node, _VisualNode):
                                self._push_preview_data(dst_node, output)
        # Also check if this node itself is a preview node
        if vn and vn.node_data.node_type == "preview":
            if hasattr(self, "_executor") and self._executor:
                data = self._executor.data_store.get(nid, {})
                files = data.get("preview_files", data.get("output", []))
                if files:
                    self._push_preview_data(vn, files)

    def _push_preview_data(self, vn: _VisualNode, output):
        """Push output data to a node's preview widget if it has one."""
        preview_widget = vn._config_fields.get("preview_data")
        if preview_widget and hasattr(preview_widget, "update_media"):
            files = output if isinstance(output, list) else [output]
            files = [f for f in files if isinstance(f, str)]
            if files:
                preview_widget.update_media(files)
                # Save to config so _build_body can pick it up
                vn.node_data.config["preview_data"] = files
                # Trigger body resize by recreating the config widget
                vn._create_config_widget()
                vn.update()

    def _on_exec_node_output_updated(self, nid: str, result: dict):
        if hasattr(self, "_executor") and self._executor:
            self._executor.data_store[nid] = result
        vn = self._visual_nodes.get(nid)
        if vn:
            output = result.get("output", [])
            if output:
                for port in vn.output_ports:
                    for wire in port.connections:
                        if wire.dst_port:
                            dst_node = wire.dst_port.parentItem()
                            if isinstance(dst_node, _VisualNode):
                                self._push_preview_data(dst_node, output)

    def _on_exec_done(self, success: bool):
        self._toolbar.set_running(False)
        # Push final results to all preview nodes
        if hasattr(self, "_executor") and self._executor:
            for nid, vn in self._visual_nodes.items():
                if vn.node_data.node_type == "preview":
                    # Check direct data
                    data = self._executor.data_store.get(nid, {})
                    files = data.get("preview_files", data.get("output", []))
                    if files:
                        self._push_preview_data(vn, files)
                    else:
                        # Check upstream data via input port connections
                        for port in vn.input_ports:
                            for wire in port.connections:
                                if wire.src_port:
                                    src_node = wire.src_port.parentItem()
                                    if isinstance(src_node, _VisualNode) and src_node.node_data.id in self._executor.data_store:
                                        upstream_data = self._executor.data_store[src_node.node_data.id]
                                        upstream_files = upstream_data.get("output", [])
                                        if upstream_files:
                                            self._push_preview_data(vn, upstream_files)
        # Reset all node states
        for vn in self._visual_nodes.values():
            if vn._state == "running":
                vn.set_state("success" if success else "error")

    def _on_exec_log(self, nid: str, msg: str):
        log.info(f"[Workflow][{nid[:8]}] {msg}")
        vn = self._visual_nodes.get(nid)
        if vn and "lỗi" in msg.lower():
            vn.setToolTip(msg)
            
    # ── Toolbar handlers ─────────────────────────
    def _on_name_changed(self, name: str):
        if self._current_wf:
            self._current_wf.name = name
            self._dirty = True

    def _on_fav_toggled(self, fav: bool):
        if self._current_wf:
            self._current_wf.is_favorite = fav
            self._dirty = True

    def _on_auto_arrange(self):
        if not self._current_wf:
            return
            
        nodes = self._current_wf.nodes
        connections = self._current_wf.connections
        if not nodes:
            return
            
        # Build adjacency list and calculate in-degrees
        in_degree = {nd.id: 0 for nd in nodes}
        adj = {nd.id: [] for nd in nodes}
        for conn in connections:
            adj[conn.source_node].append(conn.target_node)
            if conn.target_node in in_degree:
                in_degree[conn.target_node] += 1
                
        # BFS to assign depths (layers)
        depths = {}
        queue = [(nd.id, 0) for nd in nodes if in_degree[nd.id] == 0]
        # If there are cycles or everything has in-degree > 0, just take the first node
        if not queue and nodes:
            queue = [(nodes[0].id, 0)]
            
        visited = set()
        while queue:
            nid, depth = queue.pop(0)
            if nid in visited:
                continue
            visited.add(nid)
            depths[nid] = max(depths.get(nid, 0), depth)
            for neighbor in adj.get(nid, []):
                in_degree[neighbor] -= 1
                queue.append((neighbor, depths[nid] + 1))
                
        # Assign coordinates based on depth
        layers = {}
        for nd in nodes:
            d = depths.get(nd.id, 0)
            if d not in layers:
                layers[d] = []
            layers[d].append(nd)
            
        start_x, start_y = 80.0, 80.0
        x_gap = 420
        y_gap = 280
        
        for d in sorted(layers.keys()):
            layer_nodes = layers[d]
            # Sort vertically by current Y to preserve relative order if possible, or just index
            layer_nodes.sort(key=lambda n: n.y)
            x = start_x + d * x_gap
            for i, nd in enumerate(layer_nodes):
                y = start_y + i * y_gap
                nd.x, nd.y = x, y
                vn = self._visual_nodes.get(nd.id)
                if vn:
                    vn.setPos(x, y)
                    
        # Update wires
        for vn in self._visual_nodes.values():
            for p in vn.input_ports + vn.output_ports:
                for w in p.connections:
                    w.update_path()
                    
        self._canvas.fit_view()
        self._dirty = True

    # ── Import / Export ───────────────────────────
    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Nhập Workflow", "", "JSON (*.json)")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            wf = deserialize_workflow(data)
            self._load_wf(wf)
            self._dirty = True
        except Exception as e:
            QMessageBox.warning(self, "Lỗi nhập", str(e))

    def _on_export(self):
        if not self._current_wf:
            return
        self._sync_data_from_visual()
        default = (self._current_wf.name or "workflow").replace(" ", "_") + ".json"
        path, _ = QFileDialog.getSaveFileName(self, "Xuất Workflow", default, "JSON (*.json)")
        if not path:
            return
        try:
            data = serialize_workflow(self._current_wf)
            data["viewport"] = {"zoom": self._canvas._zoom}
            Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            QMessageBox.warning(self, "Lỗi xuất", str(e))

    # ── Auto-save ────────────────────────────────
    def _autosave(self):
        if self._dirty and self._current_wf:
            self.save_current()
