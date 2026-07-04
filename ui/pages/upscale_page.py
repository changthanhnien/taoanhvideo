"""NAV TOOLS - Image Upscale page.

Upload image -> Pipeline (Analyzer -> Selector -> Planner -> Executor -> Checker) -> save.
"""

from __future__ import annotations

import os
import time
import threading
import tempfile
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QObject, QThread, Qt, Signal, Property, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QLinearGradient
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QMessageBox, QRubberBand
)

from ui.widgets.split_panel import SplitPanel

from config.constants import DATA_DIR
from ui.widgets.page_styles import LEFT_PANEL_WIDTH, PROGRESS_HEIGHT, PROGRESS_STYLE
from utils.logger import log

from core.upscale.image_analyzer import ImageAnalyzer
from core.upscale.model_selector import ModelSelector
from core.upscale.scale_planner import ScalePlanner
from core.upscale.upscale_executor import UpscaleExecutor
from core.upscale.quality_checker import QualityChecker
from core.upscale.preview_manager import PreviewManager


class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setBackgroundBrush(Qt.GlobalColor.transparent)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self._pixmap_item = QGraphicsPixmapItem()
        self.scene().addItem(self._pixmap_item)
        self.rubberBand = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self.origin = None

    def setPixmap(self, pixmap):
        self._pixmap_item.setPixmap(pixmap)
        self.setSceneRect(self._pixmap_item.boundingRect())
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def get_roi_rect(self):
        if not self.rubberBand.isVisible():
            return None
        rect = self.rubberBand.geometry()
        scene_rect = self.mapToScene(rect).boundingRect()
        
        # Intersect with image bounds
        img_rect = self._pixmap_item.boundingRect()
        intersect = scene_rect.intersected(img_rect)
        if intersect.isEmpty():
            return None
            
        return (int(intersect.x()), int(intersect.y()), int(intersect.width()), int(intersect.height()))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.origin = event.position().toPoint()
            self.rubberBand.setGeometry(self.origin.x(), self.origin.y(), 0, 0)
            self.rubberBand.show()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.origin is not None:
            self.rubberBand.setGeometry(self.origin.x(), self.origin.y(), 
                                        event.position().toPoint().x() - self.origin.x(),
                                        event.position().toPoint().y() - self.origin.y()).normalized()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.origin = None
        else:
            super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor
        
        old_pos = self.mapToScene(event.position().toPoint())
        
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor
        self.scale(zoom_factor, zoom_factor)
        
        new_pos = self.mapToScene(event.position().toPoint())
        
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())


class AnimatedButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self._shine_x = -100.0
        self.anim = QPropertyAnimation(self, b"shine_x")
        self.anim.setDuration(600)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
    def get_shine_x(self): return self._shine_x
    def set_shine_x(self, x):
        self._shine_x = x
        self.update()
        
    shine_x = Property(float, get_shine_x, set_shine_x)
        
    def enterEvent(self, event):
        self.anim.setStartValue(-float(self.width()))
        self.anim.setEndValue(float(self.width()) * 1.5)
        self.anim.start()
        super().enterEvent(event)
        
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.anim.state() == QPropertyAnimation.State.Running:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            grad = QLinearGradient(self._shine_x, 0, self._shine_x + 60, 0)
            grad.setColorAt(0.0, QColor(255, 255, 255, 0))
            grad.setColorAt(0.5, QColor(255, 255, 255, 100))
            grad.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setBrush(grad)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(self.rect())


class _PipelineWorkerSignals(QObject):
    finished = Signal(object, str, object)
    progress = Signal(str, int)
    error = Signal(str)

class _PipelineWorker(QThread):
    def __init__(self, image_path, target_height, model_override, strategy, tile_size, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.target_height = target_height
        self.model_override = model_override
        self.strategy = strategy
        self.tile_size = tile_size
        self.signals = _PipelineWorkerSignals()
        
        self.analyzer = ImageAnalyzer()
        self.selector = ModelSelector()
        self.planner = ScalePlanner()
        self.executor = UpscaleExecutor()
        self.checker = QualityChecker()
        
        self.cancel_event = threading.Event()
        
    def cancel(self):
        self.cancel_event.set()

    def _emit(self, msg, pct=0):
        log.info(f"[Upscale] {msg}")
        self.signals.progress.emit(msg, pct)
        
    def _progress_cb(self, pct):
        # Scale 0..100% to 10..90%
        scaled_pct = 10 + int(pct * 0.8)
        self.signals.progress.emit(f"Đang xử lý ({pct:.1f}%)...", scaled_pct)

    def run(self):
        try:
            fd_out, temp_out = tempfile.mkstemp(suffix=".png")
            os.close(fd_out)
            
            runtimes = {}
            t_total_start = time.perf_counter()
            
            # Step 1: Analyze
            t0 = time.perf_counter()
            self._emit("Phân tích ảnh...", 2)
            if self.cancel_event.is_set(): raise RuntimeError("Cancelled by user")
            analysis = self.analyzer.analyze(self.image_path)
            runtimes["Analysis"] = int((time.perf_counter() - t0) * 1000)
            
            # Step 2: Select Model
            self._emit("Chọn Model...", 5)
            if self.model_override != "Auto":
                selected_model = self.model_override
            else:
                selection = self.selector.select(analysis)
                selected_model = selection["selected_model"]
                # Apply Speed strategy override
                if self.strategy == "Speed":
                    img = Image.open(self.image_path)
                    w, h = img.size
                    target_scale = float(self.target_height) / float(h)
                    
                    # Force a lightweight/fast model
                    # If target scale is small (<= 2.5), use native 2x model (lightning fast, sharp)
                    if target_scale <= 2.5:
                        selected_model = "realesr-animevideov3"
                    else:
                        selected_model = "upscayl-lite"
            
            # Step 3: Plan
            t0 = time.perf_counter()
            self._emit(f"Lập kế hoạch ({selected_model})...", 8)
            if self.cancel_event.is_set(): raise RuntimeError("Cancelled by user")
            
            img = Image.open(self.image_path)
            w, h = img.size
            
            # No pre-downscale, always feed original high-res image to AI for perfect quality
            target_scale = float(self.target_height) / float(h)
            scale = max(2.0, target_scale)
            new_w, new_h = int(w * scale), int(h * scale)
            processing_path = self.image_path
            
            plan_req = {
                "selected_model": selected_model,
                "input_width": w,
                "input_height": h,
                "target_width": new_w,
                "target_height": new_h,
                "strategy": "Balanced" if self.strategy == "Auto" else self.strategy
            }
            if self.tile_size != "Auto":
                plan_req["tile_size"] = int(self.tile_size)
                
            plan = self.planner.plan(plan_req)
            
            # Step 4: Execute
            self._emit(f"Đang upscale ({selected_model})...", 10)
            if self.cancel_event.is_set(): raise RuntimeError("Cancelled by user")
            
            exec_res = self.executor.execute(
                processing_path, temp_out, plan, selected_model, 
                new_w, new_h, 
                progress_callback=self._progress_cb, 
                cancel_event=self.cancel_event
            )
            runtimes["Engine"] = exec_res.get("execution_time_ms", 0)
            
            # Step 5: Check Quality
            t0 = time.perf_counter()
            self._emit("Kiểm tra chất lượng...", 92)
            if self.cancel_event.is_set(): raise RuntimeError("Cancelled by user")
            quality = self.checker.check(temp_out)
            runtimes["Quality Check"] = int((time.perf_counter() - t0) * 1000)
            
            runtimes["Total"] = int((time.perf_counter() - t_total_start) * 1000)
            runtimes["Manager Overhead"] = runtimes["Total"] - sum(runtimes.values()) + runtimes["Total"] # math trick, actual overhead is total - sum
            
            res_img = Image.open(temp_out).convert("RGBA")
            res_img.load()
            try: os.remove(temp_out)
            except: pass
            if processing_path != self.image_path:
                try: os.remove(processing_path)
                except: pass
            
            # Downscale back to target dimensions if it exceeds target height
            if res_img.height > self.target_height:
                aspect_ratio = float(w) / float(h)
                final_height = int(self.target_height)
                final_width = int(final_height * aspect_ratio)
                res_img = res_img.resize((final_width, final_height), Image.Resampling.LANCZOS)

            exec_res["runtimes"] = runtimes
            
            self.signals.finished.emit(res_img, selected_model, exec_res)
            
        except Exception as e:
            import traceback
            try:
                with open(DATA_DIR / "crash.log", "w", encoding="utf-8") as f:
                    f.write(traceback.format_exc())
            except Exception:
                pass
            self.signals.error.emit(str(e))


class _PreviewWorker(QThread):
    def __init__(self, image_path, target_height, roi, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.target_height = target_height
        self.roi = roi
        self.signals = _PipelineWorkerSignals()
        self.pm = PreviewManager()
        
    def run(self):
        try:
            self.signals.progress.emit("Đang tạo Preview...", 10)
            
            fd_out, temp_out = tempfile.mkstemp(suffix=".png")
            os.close(fd_out)
            
            img = Image.open(self.image_path)
            w, h = img.size
            scale = max(2.0, float(self.target_height) / float(h))
            new_w, new_h = int(w * scale), int(h * scale)
            
            res = self.pm.run_preview(self.image_path, temp_out, self.roi, new_w, new_h)
            
            res_img = Image.open(temp_out).convert("RGBA")
            res_img.load()
            try: os.remove(temp_out)
            except: pass
            
            self.signals.finished.emit(res_img, "Preview", res)
            
        except Exception as e:
            self.signals.error.emit(str(e))


class _AnalyzeWorker(QThread):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.signals = _PipelineWorkerSignals()
        
    def run(self):
        try:
            analyzer = ImageAnalyzer()
            selector = ModelSelector()
            analysis = analyzer.analyze(self.image_path)
            selection = selector.select(analysis)
            self.signals.finished.emit(None, selection["selected_model"], analysis)
        except Exception as e:
            self.signals.error.emit(str(e))


def _pil_to_qpixmap(pil_img):
    if pil_img.mode != "RGBA":
        pil_img = pil_img.convert("RGBA")
    data = pil_img.tobytes("raw", "RGBA")
    qimg = QImage(data, pil_img.width, pil_img.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg)


BTN_STYLE = """
    QPushButton {
        background: #3a3f55; color: #e0e0e0;
        border: 1px solid #555; border-radius: 6px;
        padding: 8px 16px; font-size: 13px;
    }
    QPushButton:hover { background: #4a5070; }
    QPushButton:pressed { background: #2a2f45; }
    QPushButton:disabled { background: #2a2d3a; color: #666; }
"""

CMB_STYLE = """
    QComboBox {
        background: #3a3f55; color: #e0e0e0;
        border: 1px solid #555; border-radius: 4px;
        padding: 6px 10px;
    }
    QComboBox QAbstractItemView {
        background: #2a2d3a; color: #e0e0e0;
        selection-background-color: #1976d2;
    }
"""


class UpscalePage(QWidget):
    """Page: upload image -> Pipeline -> save."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source_path = None
        self._result_pil = None
        self._worker = None
        self._init_ui()
        self.setAcceptDrops(True)

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        splitter = SplitPanel()
        root.addWidget(splitter)

        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(16, 16, 16, 16)
        left_lay.setSpacing(12)

        title = QLabel("Image Upscale")
        title.setProperty("class", "section-title")
        desc = QLabel("Tăng độ phân giải ảnh sử dụng AI Pipeline")
        desc.setStyleSheet("color: #8c909f; font-size: 12px;")
        desc.setWordWrap(True)
        left_lay.addWidget(title)
        left_lay.addWidget(desc)

        self._btn_choose = QPushButton("Chọn ảnh / Kéo thả")
        self._btn_choose.setStyleSheet(BTN_STYLE)
        self._btn_choose.clicked.connect(self._on_choose)
        left_lay.addWidget(self._btn_choose)
        
        self._btn_analyze = QPushButton("Tự động phân tích")
        self._btn_analyze.setStyleSheet(BTN_STYLE)
        self._btn_analyze.clicked.connect(self._on_analyze)
        self._btn_analyze.setVisible(False)
        left_lay.addWidget(self._btn_analyze)

        # Scale
        scale_row = QHBoxLayout()
        scale_row.addWidget(QLabel("Độ phân giải:"))
        self._cmb_scale = QComboBox()
        self._cmb_scale.addItem("720p", 720)
        self._cmb_scale.addItem("1080p", 1080)
        self._cmb_scale.addItem("1440p", 1440)
        self._cmb_scale.addItem("4K (2160p)", 2160)
        self._cmb_scale.setCurrentIndex(1)
        self._cmb_scale.setStyleSheet(CMB_STYLE)
        scale_row.addWidget(self._cmb_scale, 1)
        left_lay.addLayout(scale_row)
        
        # Model (Hidden)
        model_row = QHBoxLayout()
        lbl_model = QLabel("Model:")
        lbl_model.setVisible(False)
        model_row.addWidget(lbl_model)
        self._cmb_model = QComboBox()
        self._scan_models()
        self._cmb_model.setStyleSheet(CMB_STYLE)
        self._cmb_model.setVisible(False)
        model_row.addWidget(self._cmb_model, 1)
        left_lay.addLayout(model_row)

        # Strategy
        strat_row = QHBoxLayout()
        strat_row.addWidget(QLabel("Chất lượng:"))
        self._cmb_strategy = QComboBox()
        self._cmb_strategy.addItems(["Auto", "Speed", "Balanced", "Quality"])
        self._cmb_strategy.setStyleSheet(CMB_STYLE)
        strat_row.addWidget(self._cmb_strategy, 1)
        left_lay.addLayout(strat_row)

        # Tile Size (Hidden)
        tile_row = QHBoxLayout()
        lbl_tile = QLabel("Tile Size:")
        lbl_tile.setVisible(False)
        tile_row.addWidget(lbl_tile)
        self._cmb_tile = QComboBox()
        self._cmb_tile.addItems(["Auto", "200", "256", "400", "512", "800"])
        self._cmb_tile.setStyleSheet(CMB_STYLE)
        self._cmb_tile.setVisible(False)
        tile_row.addWidget(self._cmb_tile, 1)
        left_lay.addLayout(tile_row)
        
        # Previews (Hidden)
        preview_lay = QHBoxLayout()
        self._btn_preview = QPushButton("Preview Nhanh")
        self._btn_preview.setStyleSheet(BTN_STYLE)
        self._btn_preview.clicked.connect(self._on_preview)
        self._btn_preview.setVisible(False)
        
        self._btn_roi_preview = QPushButton("ROI Preview")
        self._btn_roi_preview.setStyleSheet(BTN_STYLE)
        self._btn_roi_preview.setToolTip("Chuột phải để vẽ vùng ROI trên ảnh gốc")
        self._btn_roi_preview.clicked.connect(self._on_roi_preview)
        self._btn_roi_preview.setVisible(False)
        
        preview_lay.addWidget(self._btn_preview)
        preview_lay.addWidget(self._btn_roi_preview)
        left_lay.addLayout(preview_lay)

        self._btn_upscale = AnimatedButton("Bắt đầu upscale")
        self._btn_upscale.setStyleSheet(BTN_STYLE.replace("#3a3f55", "#1565c0").replace("#4a5070", "#1976d2").replace("#2a2f45", "#0d47a1"))
        self._btn_upscale.clicked.connect(self._on_upscale)
        left_lay.addWidget(self._btn_upscale)
        
        self._btn_cancel = QPushButton("Hủy")
        self._btn_cancel.setStyleSheet(BTN_STYLE.replace("#3a3f55", "#4527a0").replace("#4a5070", "#512da8").replace("#2a2f45", "#311b92"))
        self._btn_cancel.setEnabled(False)
        self._btn_cancel.clicked.connect(self._on_cancel)
        left_lay.addWidget(self._btn_cancel)

        self._progress = QProgressBar()
        self._progress.setFixedHeight(24)
        self._progress.setVisible(False)
        self._progress.setTextVisible(True)
        self._progress.setStyleSheet("QProgressBar { border: 1px solid #333; border-radius: 4px; text-align: center; color: white; background: #1e2030; } QProgressBar::chunk { background-color: #2563eb; border-radius: 3px; }")
        left_lay.addWidget(self._progress)
        
        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet("color: #aaa; font-size: 11px;")
        self._lbl_status.setWordWrap(True)
        left_lay.addWidget(self._lbl_status)

        self._btn_save = AnimatedButton("Lưu ảnh")
        self._btn_save.setStyleSheet(BTN_STYLE.replace("#3a3f55", "#d32f2f").replace("#4a5070", "#e53935").replace("#2a2f45", "#b71c1c"))
        self._btn_save.setEnabled(False)
        self._btn_save.clicked.connect(self._on_save)
        left_lay.addWidget(self._btn_save)
        left_lay.addStretch(1)

        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(16, 16, 16, 16)
        
        header_row = QHBoxLayout()
        preview_label = QLabel("Kết quả so sánh (Chuột phải để vẽ vùng ROI)")
        preview_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #e0e0e0;")
        header_row.addWidget(preview_label)
        right_lay.addLayout(header_row)
        
        compare_lay = QHBoxLayout()
        
        before_vbox = QVBoxLayout()
        before_header_lay = QHBoxLayout()
        self._lbl_before_info = QLabel("Trước (Gốc)")
        before_header_lay.addWidget(self._lbl_before_info)
        before_header_lay.addStretch(1)
        self._btn_fit_before = QPushButton("⛶")
        self._btn_fit_before.setToolTip("Vừa khung")
        self._btn_fit_before.setFixedSize(24, 24)
        self._btn_fit_before.setStyleSheet("QPushButton { background: transparent; color: #aaa; border: none; font-size: 16px; padding: 0px; margin: 0px; } QPushButton:hover { color: #fff; background: #3a3f55; border-radius: 4px; }")
        self._btn_fit_before.clicked.connect(lambda: self._view_before.fitInView(self._view_before.scene().items()[0], Qt.AspectRatioMode.KeepAspectRatio) if self._view_before.scene().items() else None)
        before_header_lay.addWidget(self._btn_fit_before)
        before_vbox.addLayout(before_header_lay)
        
        self._view_before = ZoomableGraphicsView()
        self._view_before.setStyleSheet("background: #1e2030; border: 1px solid #333; border-radius: 8px;")
        before_vbox.addWidget(self._view_before, 1)
        compare_lay.addLayout(before_vbox, 1)
        
        after_vbox = QVBoxLayout()
        after_header_lay = QHBoxLayout()
        self._lbl_after_info = QLabel("Sau (Upscaled)")
        after_header_lay.addWidget(self._lbl_after_info)
        after_header_lay.addStretch(1)
        self._btn_fit_after = QPushButton("⛶")
        self._btn_fit_after.setToolTip("Vừa khung")
        self._btn_fit_after.setFixedSize(24, 24)
        self._btn_fit_after.setStyleSheet("QPushButton { background: transparent; color: #aaa; border: none; font-size: 16px; padding: 0px; margin: 0px; } QPushButton:hover { color: #fff; background: #3a3f55; border-radius: 4px; }")
        self._btn_fit_after.clicked.connect(lambda: self._view_after.fitInView(self._view_after.scene().items()[0], Qt.AspectRatioMode.KeepAspectRatio) if self._view_after.scene().items() else None)
        after_header_lay.addWidget(self._btn_fit_after)
        after_vbox.addLayout(after_header_lay)
        
        self._view_after = ZoomableGraphicsView()
        self._view_after.setStyleSheet("background: #1e2030; border: 1px solid #333; border-radius: 8px;")
        after_vbox.addWidget(self._view_after, 1)
        compare_lay.addLayout(after_vbox, 1)
        
        right_lay.addLayout(compare_lay, 1)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()
            
    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if files:
            path = files[0]
            if path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                self._load_image(path)

    def _scan_models(self):
        self._cmb_model.clear()
        self._cmb_model.addItem("Auto")
        bin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bin", "realesrgan-ncnn", "models")
        
        target_models = {
            "ultrasharp": "ultrasharp-4x.bin",
            "remacri": "remacri-4x.bin",
            "upscayl-lite": "upscayl-lite-4x.bin",
            "realesr-animevideov3": "realesr-animevideov3-x4.bin",
            "realesrgan-x4plus": "realesrgan-x4plus.bin"
        }
        
        if os.path.exists(bin_dir):
            for display_name, filename in target_models.items():
                if os.path.exists(os.path.join(bin_dir, filename)):
                    self._cmb_model.addItem(display_name)

    def _on_choose(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn ảnh", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if path:
            self._load_image(path)
            
    def _load_image(self, path):
        self._source_path = path
        self._result_pil = None
        pm = QPixmap(path)
        if not pm.isNull():
            size_bytes = os.path.getsize(path)
            size_str = f"{size_bytes / 1024:.1f}KB" if size_bytes < 1024 * 1024 else f"{size_bytes / (1024 * 1024):.1f}MB"
            res = f"{pm.width()}x{pm.height()}"
            self._lbl_before_info.setText(f"Trước - {res} - {size_str}")
            self._lbl_after_info.setText("Sau")
            
            self._view_before.setPixmap(pm)
            self._view_after.setPixmap(QPixmap())
            self._progress.setVisible(False)
            self._btn_save.setEnabled(False)
            self._lbl_status.setText("")

    def _on_analyze(self):
        if not self._source_path: return
        self._lbl_status.setText("Đang phân tích ảnh...")
        self._worker = _AnalyzeWorker(self._source_path)
        self._worker.signals.finished.connect(self._on_analyze_done)
        self._worker.signals.error.connect(self._on_error)
        self._worker.start()
        
    def _on_analyze_done(self, res, selected_model, analysis):
        self._lbl_status.setText(f"Đề xuất model: {selected_model}")
        idx = self._cmb_model.findText(selected_model)
        if idx >= 0: self._cmb_model.setCurrentIndex(idx)

    def _on_preview(self):
        if not self._source_path: return
        self._run_preview(None)
        
    def _on_roi_preview(self):
        if not self._source_path: return
        roi = self._view_before.get_roi_rect()
        if not roi:
            QMessageBox.warning(self, "Lỗi", "Vui lòng click chuột phải và kéo để vẽ vùng ROI trên ảnh gốc!")
            return
        self._run_preview(roi)
        
    def _run_preview(self, roi):
        target = self._cmb_scale.currentData()
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._lbl_status.setText("Đang tạo preview...")
        self._worker = _PreviewWorker(self._source_path, target, roi)
        self._worker.signals.progress.connect(self._on_progress)
        self._worker.signals.finished.connect(self._on_finished)
        self._worker.signals.error.connect(self._on_error)
        self._worker.start()

    def _on_upscale(self):
        if not self._source_path:
            return
        target = self._cmb_scale.currentData()
        model_override = self._cmb_model.currentText()
        
        # Extract base strategy string (e.g. "Nhanh (Speed)" -> "Speed")
        raw_strat = self._cmb_strategy.currentText()
        if "Speed" in raw_strat: strategy = "Speed"
        elif "Balanced" in raw_strat: strategy = "Balanced"
        elif "Quality" in raw_strat: strategy = "Quality"
        else: strategy = "Auto"
        
        tile_size = self._cmb_tile.currentText()
        
        self._btn_upscale.setEnabled(False)
        self._btn_cancel.setEnabled(True)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._progress.setFormat("Đang chạy... %p%")
        self._btn_save.setEnabled(False)
        self._view_after.setPixmap(QPixmap())
        self._lbl_status.setText("Khởi tạo Pipeline...")

        self._worker = _PipelineWorker(self._source_path, target, model_override, strategy, tile_size)
        self._worker.signals.progress.connect(self._on_progress)
        self._worker.signals.finished.connect(self._on_finished)
        self._worker.signals.error.connect(self._on_error)
        self._worker.start()
        
    def _on_cancel(self):
        if self._worker:
            try: self._worker.cancel()
            except: pass
        self._lbl_status.setText("Đang hủy...")
        self._btn_cancel.setEnabled(False)

    def _on_progress(self, msg, pct):
        self._progress.setFormat(msg)
        self._progress.setValue(pct)
        self._lbl_status.setText(msg)

    def _on_finished(self, res, engine_used, extra_info):
        self._result_pil = res
        self._btn_upscale.setEnabled(True)
        self._btn_cancel.setEnabled(False)
        
        import io
        io_buf = io.BytesIO()
        res.save(io_buf, format="PNG")
        size_bytes = io_buf.tell()
        size_str = f"{size_bytes / 1024:.1f}KB" if size_bytes < 1024 * 1024 else f"{size_bytes / (1024 * 1024):.1f}MB"
        
        self._lbl_after_info.setText(f"Sau ({engine_used}) - {res.width}x{res.height} - {size_str}")
        
        self._progress.setValue(100)
        self._progress.setFormat(f"Hoàn thành")
        self._btn_save.setEnabled(True)
        self._lbl_status.setText("Xử lý thành công!")

        qpm = _pil_to_qpixmap(res)
        self._view_after.setPixmap(qpm)
        
        # Display runtimes in info label if available
        if "runtimes" in extra_info:
            rt = extra_info["runtimes"]
            rt_str = (f"Runtimes: Analysis={rt.get('Analysis',0)}ms | "
                      f"Planning={rt.get('Planning',0)}ms | "
                      f"Engine={rt.get('Engine',0)}ms | "
                      f"Check={rt.get('Quality Check',0)}ms | "
                      f"Total={rt.get('Total',0)}ms")
            self._lbl_status.setText(rt_str)
            
        # Memory cleanup
        if self._worker:
            self._worker.deleteLater()
            self._worker = None

    def hideEvent(self, event):
        super().hideEvent(event)

    def _on_error(self, message):
        log.error(f"UI Upscale Error: {message}")
        self._btn_upscale.setEnabled(True)
        self._btn_cancel.setEnabled(False)
        self._progress.setFormat("Lỗi!")
        self._lbl_status.setText(f"Lỗi: Xem chi tiết trong hộp thoại.")
        
        # Memory cleanup
        if self._worker:
            self._worker.deleteLater()
            self._worker = None
            
        QMessageBox.critical(self, "Lỗi Upscale", message)

    def _on_save(self):
        if self._result_pil is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Lưu ảnh", "upscaled.png", "PNG (*.png)")
        if path:
            self._result_pil.save(path, format="PNG")
            self._lbl_status.setText(f"Đã lưu: {path}")
            QMessageBox.information(self, "Thành công", "Đã lưu ảnh thành công!")

    def start_upscale(self, image_path: str):
        if not image_path: return
        self._load_image(image_path)
        self._on_upscale()
