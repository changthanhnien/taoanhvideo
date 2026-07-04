from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsPolygonItem, QGraphicsRectItem, QGraphicsEllipseItem
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QBrush, QPolygonF, QPainterPath
from PySide6.QtCore import Qt, QRectF, QPointF, Signal

class AdvancedPreviewCanvas(QGraphicsView):
    roi_changed = Signal(int, int, int, int)
    polygon_changed = Signal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setStyleSheet("background-color: #09090e; border: none;")
        
        self.pixmap_item = None
        self.shape = "rect" # rect, ellipse, diamond, polygon
        self.is_drawing = False
        self.is_panning = False
        self.pan_start = None
        
        self.start_pt = None
        self.current_shape_item = None
        
        self.polygon_points = []
        self.polygon_item = None
        self.poly_points_items = []
        self.dragged_point_idx = -1
        
        self.roi = None # (x, y, w, h)
        
    def set_image(self, bgr_image):
        h, w, c = bgr_image.shape
        qimg = QImage(bgr_image.data, w, h, w * c, QImage.Format.Format_BGR888)
        pix = QPixmap.fromImage(qimg)
        
        if self.pixmap_item:
            self.scene.removeItem(self.pixmap_item)
            
        self.pixmap_item = self.scene.addPixmap(pix)
        self.pixmap_item.setZValue(0)
        self.scene.setSceneRect(QRectF(pix.rect()))
        self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
        self._redraw_shapes()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.pixmap_item:
            self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def _redraw_shapes(self):
        if self.current_shape_item:
            self.scene.removeItem(self.current_shape_item)
            self.current_shape_item = None
            
        if self.polygon_item:
            self.scene.removeItem(self.polygon_item)
            self.polygon_item = None
            
        for it in self.poly_points_items:
            self.scene.removeItem(it)
        self.poly_points_items.clear()
        
        pen = QPen(QColor("#8b5cf6"), 2)  # Solid purple stroke
        pen.setStyle(Qt.SolidLine)
        brush = QBrush(QColor(139, 92, 246, int(255 * 0.3)))  # rgba(139, 92, 246, 0.3)
        
        if self.shape == "polygon" and self.polygon_points:
            poly = QPolygonF()
            for p in self.polygon_points:
                poly.append(p)
            self.polygon_item = self.scene.addPolygon(poly, pen, brush)
            self.polygon_item.setZValue(1)
            
            for p in self.polygon_points:
                it = self.scene.addEllipse(p.x()-4, p.y()-4, 8, 8, QPen(Qt.yellow), QBrush(Qt.yellow))
                it.setZValue(2)
                self.poly_points_items.append(it)
                
        elif self.roi:
            x, y, w, h = self.roi
            rect = QRectF(x, y, w, h)
            if self.shape == "rect":
                self.current_shape_item = self.scene.addRect(rect, pen, brush)
                
                # Add original web app style handles (4 cyan corner dots, 6x6 pixels)
                for pt in [rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight()]:
                    handle = self.scene.addRect(pt.x()-3, pt.y()-3, 6, 6, QPen(Qt.NoPen), QBrush(QColor("#06b6d4")))
                    handle.setZValue(2)
                    self.poly_points_items.append(handle)
                    
            elif self.shape == "ellipse":
                self.current_shape_item = self.scene.addEllipse(rect, pen, brush)
            elif self.shape == "diamond":
                cx, cy = rect.center().x(), rect.center().y()
                poly = QPolygonF([QPointF(cx, rect.top()), QPointF(rect.right(), cy), QPointF(cx, rect.bottom()), QPointF(rect.left(), cy)])
                self.current_shape_item = self.scene.addPolygon(poly, pen, brush)
            if self.current_shape_item:
                self.current_shape_item.setZValue(1)

    def set_shape(self, shape):
        self.shape = shape
        self._redraw_shapes()
        
    def reset_polygon(self):
        self.polygon_points.clear()
        self.roi = None
        self._redraw_shapes()
        self.polygon_changed.emit([])
        
    def wheelEvent(self, event):
        if event.modifiers() == Qt.ControlModifier:
            zoom_in_factor = 1.15
            zoom_out_factor = 1.0 / zoom_in_factor
            if event.angleDelta().y() > 0:
                self.scale(zoom_in_factor, zoom_in_factor)
            else:
                self.scale(zoom_out_factor, zoom_out_factor)
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and event.modifiers() == Qt.ShiftModifier):
            self.is_panning = True
            self.pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            return
            
        if not self.pixmap_item: 
            super().mousePressEvent(event)
            return
            
        pt = self.mapToScene(event.pos())
        
        if event.button() == Qt.RightButton:
            self.reset_polygon()
            return
            
        if event.button() == Qt.LeftButton:
            if self.shape == "polygon":
                hit = -1
                for i, p in enumerate(self.polygon_points):
                    if (p.x() - pt.x())**2 + (p.y() - pt.y())**2 < 100: # radius 10
                        hit = i
                        break
                if hit != -1:
                    self.dragged_point_idx = hit
                else:
                    self.polygon_points.append(pt)
                    self._emit_polygon()
                    self._redraw_shapes()
            else:
                self.is_drawing = True
                self.start_pt = pt
                
    def mouseMoveEvent(self, event):
        if self.is_panning:
            delta = event.pos() - self.pan_start
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self.pan_start = event.pos()
            return
            
        if not self.pixmap_item: 
            super().mouseMoveEvent(event)
            return
            
        pt = self.mapToScene(event.pos())
        
        if self.shape == "polygon":
            if self.dragged_point_idx != -1:
                self.polygon_points[self.dragged_point_idx] = pt
                self._emit_polygon()
                self._redraw_shapes()
        else:
            if self.is_drawing:
                rect = self.scene.sceneRect()
                pt_x = max(rect.left(), min(pt.x(), rect.right()))
                pt_y = max(rect.top(), min(pt.y(), rect.bottom()))
                
                start_x = max(rect.left(), min(self.start_pt.x(), rect.right()))
                start_y = max(rect.top(), min(self.start_pt.y(), rect.bottom()))
                
                x = min(start_x, pt_x)
                y = min(start_y, pt_y)
                w = abs(start_x - pt_x)
                h = abs(start_y - pt_y)
                
                self.roi = (int(x), int(y), int(w), int(h))
                self._redraw_shapes()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and self.is_panning):
            self.is_panning = False
            self.setCursor(Qt.ArrowCursor)
            return
            
        if not self.pixmap_item: 
            super().mouseReleaseEvent(event)
            return
            
        if event.button() == Qt.LeftButton:
            if self.shape == "polygon":
                if self.dragged_point_idx != -1:
                    self.dragged_point_idx = -1
            else:
                if self.is_drawing:
                    self.is_drawing = False
                    if self.roi and self.roi[2] > 5 and self.roi[3] > 5:
                        self.roi_changed.emit(*self.roi)
                    else:
                        self.roi = None
                        self._redraw_shapes()

    def _emit_polygon(self):
        pts = [{"x": int(p.x()), "y": int(p.y())} for p in self.polygon_points]
        self.polygon_changed.emit(pts)

class PreviewWidget(QWidget):
    roi_changed = Signal(int, int, int, int)
    polygon_changed = Signal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        
        # div.canvas-toolbar
        div_canvas_toolbar = QWidget()
        div_canvas_toolbar.setStyleSheet("background: transparent; border: none;")
        ct_lay = QHBoxLayout(div_canvas_toolbar)
        ct_lay.setContentsMargins(0,0,0,0)
        
        # div.zoom-controls
        div_zoom_controls = QWidget()
        zc_lay = QHBoxLayout(div_zoom_controls)
        zc_lay.setContentsMargins(0,0,0,0)
        zc_lay.setSpacing(5)
        
        import qtawesome as qta
        self.btn_zoom_out = QPushButton()
        self.btn_zoom_out.setIcon(qta.icon('fa5s.search-minus', color='white'))
        self.btn_zoom_out.setStyleSheet("background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 6px; width: 32px; height: 32px;")
        
        self.span_zoom_level = QLabel("100%")
        self.span_zoom_level.setStyleSheet("color: #06b6d4; font-weight: 600; font-size: 11px; font-family: monospace; padding: 0 10px;")
        self.span_zoom_level.setAlignment(Qt.AlignCenter)
        
        self.btn_zoom_in = QPushButton()
        self.btn_zoom_in.setIcon(qta.icon('fa5s.search-plus', color='white'))
        self.btn_zoom_in.setStyleSheet("background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 6px; width: 32px; height: 32px;")
        
        self.btn_zoom_reset = QPushButton()
        self.btn_zoom_reset.setIcon(qta.icon('fa5s.undo-alt', color='white'))
        self.btn_zoom_reset.setStyleSheet("background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 6px; width: 32px; height: 32px;")
        self.btn_zoom_reset.clicked.connect(self.reset_shapes)
        
        zc_lay.addWidget(self.btn_zoom_out)
        zc_lay.addWidget(self.span_zoom_level)
        zc_lay.addWidget(self.btn_zoom_in)
        zc_lay.addWidget(self.btn_zoom_reset)
        
        # div.canvas-hints
        lbl_hint = QLabel("Khi đã zoom: giữ <b>Space</b> + kéo để di chuyển")
        lbl_hint.setStyleSheet("color: #9aa0b9; font-size: 11px;")
        
        ct_lay.addWidget(div_zoom_controls)
        ct_lay.addStretch()
        ct_lay.addWidget(lbl_hint)
        
        layout.addWidget(div_canvas_toolbar)
        
        self.canvas = AdvancedPreviewCanvas()
        self.canvas.roi_changed.connect(self.roi_changed.emit)
        self.canvas.polygon_changed.connect(self.polygon_changed.emit)
        layout.addWidget(self.canvas, 1)
        
    def reset_shapes(self):
        self.canvas.reset_polygon()
        
    def load_frame(self, file_path):
        import cv2
        import numpy as np
        
        path_str = str(file_path).lower()
        if path_str.endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
            cap = cv2.VideoCapture(str(file_path))
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    self.canvas.set_image(frame)
                cap.release()
        else:
            frame = cv2.imread(str(file_path))
            if frame is not None:
                self.canvas.set_image(frame)
                
    def set_shape(self, shape):
        self.canvas.set_shape(shape)
        
    def set_roi(self, x, y, w, h):
        self.canvas.roi = (x, y, w, h)
        self.canvas._redraw_shapes()
