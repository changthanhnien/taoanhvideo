"""VidGen AI - Reusable config form widget."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QFileDialog, QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget, QListWidget, QListWidgetItem

from config.constants import (
    IMAGE_ASPECT_RATIO_OPTIONS,
    VIDEO_ASPECT_RATIO_OPTIONS,
    DEFAULT_IMAGE_OUTPUT,
    DEFAULT_VIDEO_OUTPUT,
    IMAGE_MODEL_OPTIONS,
    SAVE_MODE_OPTIONS,
    SERVICE_OPTIONS,
    CREDITS_PER_MODEL,
)
from ui.widgets.frame_upload import FrameUpload
from utils.file_utils import generate_task_name
from services.flow_model_provider import model_provider

_SYNC_BTN_QSS = """
    QPushButton {
        background: transparent;
        border: 1px solid #3f3f46;
        border-radius: 14px;
        font-size: 16px;
        padding: 0px;
        outline: none;
    }
    QPushButton:hover { border-color: #60a5fa; }
    QPushButton:disabled { border-color: #27272a; color: #52525b; }
"""


class ConfigForm(QWidget):
    """Reusable config form for left panel - adapts per page mode."""

    sync_requested = Signal()
    test_requested = Signal(str) # Passes the current model name
    test_video_requested = Signal(str) # Passes the current quality name

    _COMPACT_QSS = (
        "ConfigForm QLabel[class='field-label'] { font-weight: 600; padding: 0; margin: 0;}"
        "ConfigForm QLineEdit, ConfigForm QComboBox, ConfigForm QSpinBox { padding: 6px 10px; min-height: 18px;}\n"
        "QToolTip { color: #ffffff; background-color: #27272a; border: 1px solid #3f3f46; border-radius: 4px; padding: 4px; }"
    )

    def __init__(self, mode: str = "video_plain", db=None, parent=None):
        super().__init__(parent)
        self._mode = mode
        self._db = db
        self._uploaded_images = []  # List of image paths for @tag
        self._init_ui()

    def _enabled_accounts_count(self) -> int:
        if self._db is None:
            return 5
        try:
            return len(self._db.get_accounts(enabled_only=True))
        except Exception:
            return 5

    def refresh_account_limit(self):
        return None

    def _pair_row(self, label1: str, widget1, label2: str, widget2):
        row = QHBoxLayout()
        row.setSpacing(10)

        col1 = QVBoxLayout()
        col1.setSpacing(3)
        col1.addWidget(self._label(label1))
        col1.addWidget(widget1)
        row.addLayout(col1, 1)

        col2 = QVBoxLayout()
        col2.setSpacing(3)
        col2.addWidget(self._label(label2))
        col2.addWidget(widget2)
        row.addLayout(col2, 1)
        return row

    def _make_sync_btn(self) -> QPushButton:
        btn = QPushButton("🔄")
        btn.setFixedSize(28, 28)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setToolTip("Đồng bộ Model từ nền tảng")
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setStyleSheet(_SYNC_BTN_QSS)
        btn.clicked.connect(self.sync_requested.emit)
        return btn

    def _init_ui(self):
        self.setStyleSheet(self._COMPACT_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        self.task_name_input = QLineEdit(generate_task_name())
        self.task_name_input.setVisible(False)

        if self._mode == "grok_image":
            self._build_grok_image_fields(layout)
        elif self._mode == "grok_video":
            self._build_grok_video_fields(layout)
        elif self._mode == "image":
            self._build_image_fields(layout)
        elif self._mode in ("char_video",):
            self._build_char_video_fields(layout)
        else:
            self._build_video_fields(layout)

        layout.addWidget(self._label("Thư mục lưu:"))
        out_row = QHBoxLayout()
        out_row.setSpacing(6)

        self.output_input = QLineEdit()
        self.output_input.setReadOnly(True)
        self.output_input.setCursor(Qt.CursorShape.PointingHandCursor)
        self.output_input.mousePressEvent = lambda ev: self._browse_output()
        if self._mode in ("image", "char_image", "grok_image"):
            self.output_input.setText(str(DEFAULT_IMAGE_OUTPUT))
        else:
            self.output_input.setText(str(DEFAULT_VIDEO_OUTPUT))
        self.output_input.setPlaceholderText("Chọn thư mục lưu...")

        browse_btn = QPushButton("📁")
        browse_btn.setFixedSize(34, 34)
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.clicked.connect(self._browse_output)

        out_row.addWidget(self.output_input, 1)
        out_row.addWidget(browse_btn)
        layout.addLayout(out_row)
        layout.addStretch()

    # ─── VIDEO ───────────────────────────────────────────────
    def _build_video_fields(self, layout):
        self.quality_combo = QComboBox()
        self._populate_video_models()

        self.sync_video_btn = self._make_sync_btn()
        
        qual_widget = QWidget()
        qual_layout = QHBoxLayout(qual_widget)
        qual_layout.setContentsMargins(0, 0, 0, 0)
        qual_layout.setSpacing(4)
        qual_layout.addWidget(self.quality_combo, 1)
        qual_layout.addWidget(self.sync_video_btn)

        self.creation_mode_combo = QComboBox()
        self.creation_mode_combo.addItem("Text -> Video")
        self.creation_mode_combo.addItem("Ảnh -> Video")
        self.creation_mode_combo.addItem("Frame đầu -> Frame cuối")

        layout.addLayout(self._pair_row("Chế độ tạo:", self.creation_mode_combo, "Mô hình:", qual_widget))

        self._credit_per_video_label = QLabel("")
        self._credit_per_video_label.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        self.quality_combo.currentTextChanged.connect(self._refresh_credit_label)
        layout.addWidget(self._credit_per_video_label)

        self.duration_combo = QComboBox()
        self.duration_combo.addItems(["4s", "6s", "8s", "10s"])
        self.duration_combo.currentTextChanged.connect(self._refresh_credit_label)
        self.quality_combo.currentTextChanged.connect(self._update_duration_options)

        self.aspect_combo = QComboBox()
        for display, value in VIDEO_ASPECT_RATIO_OPTIONS:
            self.aspect_combo.addItem(display, value)
            
        self.parallel_per_account_spin = QSpinBox()
        self.parallel_per_account_spin.setRange(1, 1000)
        self.parallel_per_account_spin.setValue(1)
        self.parallel_per_account_spin.setToolTip("Số video chạy song song (tối đa 4).")
        
        self.save_mode_combo = QComboBox()
        for mode in SAVE_MODE_OPTIONS:
            self.save_mode_combo.addItem(mode)
            
        layout.addLayout(self._pair_row("Tỷ lệ:", self.aspect_combo, "Số giây:", self.duration_combo))
        layout.addLayout(self._pair_row("Đồng thời:", self.parallel_per_account_spin, "Chế độ lưu:", self.save_mode_combo))

        self._parallel_hint = QLabel("1 tài khoản chạy 1 tiến trình")
        self._parallel_hint.setWordWrap(True)
        self._parallel_hint.setProperty("class", "info-label")
        self.parallel_per_account_spin.valueChanged.connect(
            lambda value: [
                self._parallel_hint.setText(f"1 tài khoản chạy {value} tiến trình đồng thời"),
                self._refresh_credit_label()
            ]
        )
        layout.addWidget(self._parallel_hint)

        # --- Image upload widget (for Ảnh -> Video) ---
        self._build_image_upload_section(layout)

        # --- Frame upload widget (for Frame đầu -> Frame cuối) ---
        self.frames_widget = QWidget()
        frames_vbox = QVBoxLayout(self.frames_widget)
        frames_vbox.setContentsMargins(0, 0, 0, 0)

        self.start_frame_upload = FrameUpload(label="🖼️  Ảnh khung đầu:")
        self.end_frame_upload = FrameUpload(label="🖼️  Ảnh khung cuối:")
        
        self.swap_btn = QPushButton("⇌  Hoán đổi")
        self.swap_btn.setStyleSheet("font-size: 13px; font-weight: bold; padding: 4px; border: 1px solid #3b82f6; border-radius: 4px; color: #3b82f6; background: transparent;")
        self.swap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        def _swap_frames():
            start_path = getattr(self.start_frame_upload, "_image_path", "")
            end_path = getattr(self.end_frame_upload, "_image_path", "")
            self.start_frame_upload.clear()
            self.end_frame_upload.clear()
            if end_path:
                self.start_frame_upload.set_image(end_path)
            if start_path:
                self.end_frame_upload.set_image(start_path)
                
        self.swap_btn.clicked.connect(_swap_frames)
        
        swap_layout = QHBoxLayout()
        swap_layout.addStretch()
        swap_layout.addWidget(self.swap_btn)
        swap_layout.addStretch()

        frames_vbox.addWidget(self.start_frame_upload)
        frames_vbox.addLayout(swap_layout)
        frames_vbox.addWidget(self.end_frame_upload)
        layout.addWidget(self.frames_widget)

        warning = QLabel(
            "⚠️ Tối đa 4 tiến trình song song. Đẩy quá cao dễ bị Google khóa tài khoản."
        )
        warning.setWordWrap(True)
        warning.setProperty("class", "warning-label")
        layout.addWidget(warning)

        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, 300)
        self.delay_spin.setValue(3)
        self.delay_spin.setSuffix(" giây")
        layout.addLayout(self._pair_row("Delay:", self.delay_spin, "", QLabel("")))

        self._refresh_credit_label()
        
        def _on_mode_changed(mode_str):
            if "Frame" in mode_str:
                self.frames_widget.show()
                self.image_upload_widget.hide()
            elif "Ảnh" in mode_str:
                self.frames_widget.hide()
                self.image_upload_widget.show()
            else:
                self.frames_widget.hide()
                self.image_upload_widget.hide()
                
        self.creation_mode_combo.currentTextChanged.connect(_on_mode_changed)
        _on_mode_changed(self.creation_mode_combo.currentText())

    def _update_duration_options(self, model_name):
        current = self.duration_combo.currentText()
        self.duration_combo.clear()
        if "Omni Flash" in model_name:
            opts = ["4s", "6s", "8s", "10s"]
        else:
            opts = ["4s", "6s", "8s"]
        self.duration_combo.addItems(opts)
        if current in opts:
            self.duration_combo.setCurrentText(current)

    # ─── IMAGE ───────────────────────────────────────────────
    def _build_image_fields(self, layout):
        self.model_combo = QComboBox()
        image_models = model_provider.models.get("image_models", [])
        if image_models:
            for m in image_models:
                name = m.get("name", "")
                key = m.get("key", "")
                if name:
                    display = f"🍌 {name}" if "banana" in name.lower() else name
                    self.model_combo.addItem(display, key)
        else:
            for m in IMAGE_MODEL_OPTIONS:
                self.model_combo.addItem(m)
            
        self.sync_model_btn = self._make_sync_btn()
        
        model_widget = QWidget()
        model_layout = QHBoxLayout(model_widget)
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.setSpacing(4)
        model_layout.addWidget(self.model_combo, 1)
        model_layout.addWidget(self.sync_model_btn)

        self.creation_mode_combo = QComboBox()
        self.creation_mode_combo.addItem("Text -> Ảnh")
        self.creation_mode_combo.addItem("Ảnh -> Ảnh")

        layout.addLayout(self._pair_row("Chế độ tạo:", self.creation_mode_combo, "Mô hình:", model_widget))

        self.aspect_combo = QComboBox()
        for display, value in IMAGE_ASPECT_RATIO_OPTIONS:
            self.aspect_combo.addItem(display, value)

        self.parallel_per_account_spin = QSpinBox()
        self.parallel_per_account_spin.setRange(1, 1000)
        self.parallel_per_account_spin.setValue(1)
        self.parallel_per_account_spin.setToolTip("Số ảnh chạy song song (tối đa 4).")
        
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, 300)
        self.delay_spin.setValue(3)
        self.delay_spin.setSuffix(" giây")
        
        layout.addLayout(self._pair_row("Tỷ lệ:", self.aspect_combo, "Đồng thời:", self.parallel_per_account_spin))
        layout.addLayout(self._pair_row("Delay:", self.delay_spin, "", QLabel("")))

        self._parallel_hint = QLabel(f"1 tài khoản chạy {self.parallel_per_account_spin.value()} tiến trình đồng thời")
        self._parallel_hint.setWordWrap(True)
        self._parallel_hint.setProperty("class", "info-label")
        self.parallel_per_account_spin.valueChanged.connect(
            lambda value: self._parallel_hint.setText(f"1 tài khoản chạy {value} tiến trình đồng thời")
        )
        layout.addWidget(self._parallel_hint)

        # --- Image upload for Ảnh -> Ảnh ---
        self._build_image_upload_section(layout)
        
        def _on_img_mode_changed(mode_str):
            if "Ảnh ->" in mode_str:
                self.image_upload_widget.show()
            else:
                self.image_upload_widget.hide()
                
        self.creation_mode_combo.currentTextChanged.connect(_on_img_mode_changed)
        _on_img_mode_changed(self.creation_mode_combo.currentText())

        self.save_mode_combo = QComboBox()
        for mode in SAVE_MODE_OPTIONS:
            self.save_mode_combo.addItem(mode)
        layout.addLayout(self._pair_row("Chế độ lưu:", self.save_mode_combo, "", QLabel("")))

    def _build_grok_image_fields(self, layout):
        self.creation_mode_combo = QComboBox()
        self.creation_mode_combo.addItem("Text -> Ảnh")
        self.creation_mode_combo.addItem("Ảnh -> Ảnh")

        self.grok_mode_combo = QComboBox()
        self.grok_mode_combo.addItems(["Tốc độ", "Chất lượng"])

        layout.addLayout(self._pair_row("Chế độ tạo:", self.creation_mode_combo, "Chế độ chạy:", self.grok_mode_combo))

        GROK_ASPECT_RATIO_OPTIONS = [
            ("2:3 Cao", "2:3"),
            ("3:2 Rộng", "3:2"),
            ("1:1 Vuông", "1:1"),
            ("9:16 Dọc", "9:16"),
            ("16:9 Màn hình rộng", "16:9")
        ]
        self.aspect_combo = QComboBox()
        for display, value in GROK_ASPECT_RATIO_OPTIONS:
            self.aspect_combo.addItem(display, value)

        self.parallel_per_account_spin = QSpinBox()
        self.parallel_per_account_spin.setRange(1, 1000)
        self.parallel_per_account_spin.setValue(1)
        self.parallel_per_account_spin.setToolTip("Số ảnh chạy song song (tối đa 4).")
        
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, 300)
        self.delay_spin.setValue(3)
        self.delay_spin.setSuffix(" giây")
        
        layout.addLayout(self._pair_row("Tỷ lệ:", self.aspect_combo, "Đồng thời:", self.parallel_per_account_spin))
        layout.addLayout(self._pair_row("Delay:", self.delay_spin, "", QLabel("")))

        self._parallel_hint = QLabel(f"1 tài khoản chạy {self.parallel_per_account_spin.value()} tiến trình đồng thời")
        self._parallel_hint.setWordWrap(True)
        self._parallel_hint.setProperty("class", "info-label")
        self.parallel_per_account_spin.valueChanged.connect(
            lambda value: self._parallel_hint.setText(f"1 tài khoản chạy {value} tiến trình đồng thời")
        )
        layout.addWidget(self._parallel_hint)

        self._build_image_upload_section(layout)
        
        def _on_img_mode_changed(mode_str):
            if "Ảnh ->" in mode_str:
                self.image_upload_widget.show()
            else:
                self.image_upload_widget.hide()
                
        self.creation_mode_combo.currentTextChanged.connect(_on_img_mode_changed)
        _on_img_mode_changed(self.creation_mode_combo.currentText())

        self.save_mode_combo = QComboBox()
        for mode in SAVE_MODE_OPTIONS:
            self.save_mode_combo.addItem(mode)
        layout.addLayout(self._pair_row("Chế độ lưu:", self.save_mode_combo, "", QLabel("")))

    def _build_grok_video_fields(self, layout):
        self.creation_mode_combo = QComboBox()
        self.creation_mode_combo.addItem("Text -> Video")
        self.creation_mode_combo.addItem("Ảnh -> Video")

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["480p", "720p"])

        layout.addLayout(self._pair_row("Chế độ tạo:", self.creation_mode_combo, "Chất lượng:", self.quality_combo))

        self.duration_combo = QComboBox()
        self.duration_combo.addItems(["6s", "10s"])

        GROK_VIDEO_ASPECT_RATIO_OPTIONS = [
            ("2:3 Cao", "2:3"),
            ("3:2 Rộng", "3:2"),
            ("1:1 Vuông", "1:1"),
            ("9:16 Dọc", "9:16"),
            ("16:9 Màn hình rộng", "16:9")
        ]
        self.aspect_combo = QComboBox()
        for display, value in GROK_VIDEO_ASPECT_RATIO_OPTIONS:
            self.aspect_combo.addItem(display, value)

        layout.addLayout(self._pair_row("Tỷ lệ:", self.aspect_combo, "Số giây:", self.duration_combo))

        self.parallel_per_account_spin = QSpinBox()
        self.parallel_per_account_spin.setRange(1, 1000)
        self.parallel_per_account_spin.setValue(1)
        self.parallel_per_account_spin.setToolTip("Số video chạy song song.")
        
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, 300)
        self.delay_spin.setValue(3)
        self.delay_spin.setSuffix(" giây")

        self.save_mode_combo = QComboBox()
        for mode in SAVE_MODE_OPTIONS:
            self.save_mode_combo.addItem(mode)

        layout.addLayout(self._pair_row("Đồng thời:", self.parallel_per_account_spin, "Chế độ lưu:", self.save_mode_combo))
        layout.addLayout(self._pair_row("Delay:", self.delay_spin, "", QLabel("")))

        self._parallel_hint = QLabel(f"1 tài khoản chạy {self.parallel_per_account_spin.value()} tiến trình đồng thời")
        self._parallel_hint.setWordWrap(True)
        self._parallel_hint.setProperty("class", "info-label")
        self.parallel_per_account_spin.valueChanged.connect(
            lambda value: self._parallel_hint.setText(f"1 tài khoản chạy {value} tiến trình đồng thời")
        )
        layout.addWidget(self._parallel_hint)

        self._build_image_upload_section(layout)
        
        def _on_vid_mode_changed(mode_str):
            if "Ảnh ->" in mode_str:
                self.image_upload_widget.show()
            else:
                self.image_upload_widget.hide()
                
        self.creation_mode_combo.currentTextChanged.connect(_on_vid_mode_changed)
        _on_vid_mode_changed(self.creation_mode_combo.currentText())

    # ─── CHAR VIDEO (Video to Video) ────────────────────────
    def _build_char_video_fields(self, layout):
        """Video to Video: just upload video + choose model, no creation mode."""
        self.quality_combo = QComboBox()
        self._populate_video_models()

        self.sync_video_btn = self._make_sync_btn()
        
        qual_widget = QWidget()
        qual_layout = QHBoxLayout(qual_widget)
        qual_layout.setContentsMargins(0, 0, 0, 0)
        qual_layout.setSpacing(4)
        qual_layout.addWidget(self.quality_combo, 1)
        qual_layout.addWidget(self.sync_video_btn)

        layout.addLayout(self._pair_row("Mô hình:", qual_widget, "", QLabel("")))

        self._credit_per_video_label = QLabel("")
        self._credit_per_video_label.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        self.quality_combo.currentTextChanged.connect(self._refresh_credit_label)
        layout.addWidget(self._credit_per_video_label)

        self.aspect_combo = QComboBox()
        for display, value in VIDEO_ASPECT_RATIO_OPTIONS:
            self.aspect_combo.addItem(display, value)

        self.parallel_per_account_spin = QSpinBox()
        self.parallel_per_account_spin.setRange(1, 1000)
        self.parallel_per_account_spin.setValue(1)
        self.parallel_per_account_spin.valueChanged.connect(self._refresh_credit_label)
        
        layout.addLayout(self._pair_row("Tỷ lệ:", self.aspect_combo, "Đồng thời:", self.parallel_per_account_spin))

        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, 300)
        self.delay_spin.setValue(3)
        self.delay_spin.setSuffix(" giây")
        
        self.save_mode_combo = QComboBox()
        for mode in SAVE_MODE_OPTIONS:
            self.save_mode_combo.addItem(mode)
            
        layout.addLayout(self._pair_row("Delay:", self.delay_spin, "Chế độ lưu:", self.save_mode_combo))

        self._build_image_upload_section(layout)
        
        self._refresh_credit_label()

    # ─── IMAGE UPLOAD SECTION (shared) ──────────────────────
    def _build_image_upload_section(self, layout):
        """Multi-image upload with @tag support + thumbnail preview."""
        from PySide6.QtWidgets import QScrollArea, QGridLayout, QSizePolicy
        from PySide6.QtGui import QPixmap

        self.image_upload_widget = QWidget()
        upload_vbox = QVBoxLayout(self.image_upload_widget)
        upload_vbox.setContentsMargins(0, 4, 0, 0)
        upload_vbox.setSpacing(4)
        
        header_row = QHBoxLayout()
        lbl_text = "Video đầu vào (@1, @2... tag trong prompt):" if self._mode == "char_video" else "Ảnh đầu vào (@1, @2... tag trong prompt):"
        header_row.addWidget(self._label(lbl_text))
        header_row.addStretch()
        
        add_btn = QPushButton("+ Thêm video" if self._mode == "char_video" else "+ Thêm ảnh")
        add_btn.setFixedHeight(26)
        add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        add_btn.setStyleSheet("QPushButton { background: #1e293b; border: 1px solid #3b82f6; color: #93c5fd; border-radius: 4px; padding: 2px 10px; } QPushButton:hover { background: #1e3a5f; }")
        add_btn.clicked.connect(self._add_images)
        header_row.addWidget(add_btn)
        
        clear_btn = QPushButton("Xóa hết")
        clear_btn.setFixedHeight(26)
        clear_btn.setStyleSheet("QPushButton { color: #f87171; background: transparent; border: 1px solid #7f1d1d; border-radius: 4px; padding: 2px 8px; } QPushButton:hover { background: #450a0a; }")
        clear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        clear_btn.clicked.connect(self._clear_images)
        header_row.addWidget(clear_btn)
        
        upload_vbox.addLayout(header_row)
        
        # Scroll area for thumbnails
        self._thumb_scroll = QScrollArea()
        self._thumb_scroll.setWidgetResizable(True)
        self._thumb_scroll.setFixedHeight(110)
        self._thumb_scroll.setStyleSheet(
            "QScrollArea { background: #18181b; border: 1px solid #3f3f46; border-radius: 6px; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        self._thumb_container = QWidget()
        self._thumb_layout = QHBoxLayout(self._thumb_container)
        self._thumb_layout.setContentsMargins(6, 6, 6, 6)
        self._thumb_layout.setSpacing(8)
        self._thumb_layout.addStretch()
        self._thumb_scroll.setWidget(self._thumb_container)
        upload_vbox.addWidget(self._thumb_scroll)
        
        # Also keep input_folder_input for backward compat
        self.input_folder_input = QLineEdit()
        self.input_folder_input.hide()
        
        layout.addWidget(self.image_upload_widget)

    def _add_images(self):
        title = "Chọn video" if self._mode == "char_video" else "Chọn ảnh"
        filter_str = "Videos (*.mp4 *.mov *.avi *.mkv);;All Files (*)" if self._mode == "char_video" else "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*)"
        files, _ = QFileDialog.getOpenFileNames(
            self, title, "", filter_str
        )
        if files:
            for f in files:
                if f not in self._uploaded_images:
                    self._uploaded_images.append(f)
            self._refresh_image_list()

    def _clear_images(self):
        self._uploaded_images.clear()
        self._refresh_image_list()

    def _refresh_image_list(self):
        from PySide6.QtGui import QPixmap
        # Clear old thumbnails
        while self._thumb_layout.count() > 0:
            child = self._thumb_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        for i, path in enumerate(self._uploaded_images, 1):
            thumb_widget = QWidget()
            thumb_widget.setFixedSize(80, 95)
            thumb_vbox = QVBoxLayout(thumb_widget)
            thumb_vbox.setContentsMargins(0, 0, 0, 0)
            thumb_vbox.setSpacing(2)
            
            # Thumbnail image (if video, just show a generic icon to prevent main thread freeze)
            if str(path).lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
                pixmap = QPixmap()
            else:
                pixmap = QPixmap(path)

            if not pixmap.isNull():
                pixmap = pixmap.scaled(76, 70, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            thumb_label = QLabel()
            if pixmap.isNull():
                thumb_label.setText("🎞️\nVideo")
            else:
                thumb_label.setPixmap(pixmap)
            thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb_label.setFixedSize(76, 70)
            thumb_label.setStyleSheet("QLabel { background: #27272a; border: 1px solid #3f3f46; border-radius: 4px; }")
            thumb_vbox.addWidget(thumb_label)
            
            # Tag label
            tag_label = QLabel(f"@{i}")
            tag_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tag_label.setStyleSheet("color: #93c5fd; font-size: 11px; font-weight: bold; background: transparent;")
            thumb_vbox.addWidget(tag_label)
            
            # Make image clickable for preview
            thumb_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            thumb_label.mousePressEvent = lambda event, p=path: self._preview_image(p)
            
            # Remove button overlay
            remove_btn = QPushButton("✕")
            remove_btn.setFixedSize(16, 16)
            remove_btn.setStyleSheet("QPushButton { background: #ef4444; color: white; border-radius: 8px; font-size: 10px; padding: 0; border: none; } QPushButton:hover { background: #dc2626; }")
            remove_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            remove_btn.setParent(thumb_widget)
            remove_btn.move(62, 0)
            remove_btn.show()
            idx = i - 1
            remove_btn.clicked.connect(lambda _, idx=idx: self._remove_image(idx))
            
            self._thumb_layout.addWidget(thumb_widget)
        
        self._thumb_layout.addStretch()

    def _remove_image(self, idx):
        if 0 <= idx < len(self._uploaded_images):
            self._uploaded_images.pop(idx)
            self._refresh_image_list()

    def _preview_image(self, path):
        if str(path).lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
            from ui.widgets.video_preview_dialog import VideoPreviewDialog
            dialog = VideoPreviewDialog(path, self)
        else:
            from ui.widgets.task_table import PreviewDialog
            dialog = PreviewDialog(path, self)
        dialog.exec()

    # ─── HELPERS ─────────────────────────────────────────────
    def _populate_video_models(self):
        video_models = model_provider.models.get("video_models", [])
        if video_models:
            desired_order = ["Omni Flash", "Veo 3.1 - Lite", "Veo 3.1 - Fast", "Veo 3.1 - Quality"]
            filtered_models = []
            for m in video_models:
                name = m.get("name", "")
                if not name or "Lower Priority" in name:
                    continue
                filtered_models.append(m)
                
            filtered_models.sort(key=lambda m: desired_order.index(m["name"]) if m["name"] in desired_order else 999)
            
            for m in filtered_models:
                self.quality_combo.addItem(m["name"], m.get("key", ""))
        else:
            self.quality_combo.addItems(["Omni Flash", "Veo 3.1 - Lite", "Veo 3.1 - Fast", "Veo 3.1 - Quality"])

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("class", "field-label")
        return label

    def _refresh_credit_label(self) -> None:
        if not hasattr(self, "_credit_per_video_label"):
            return

        quality = self.quality_combo.currentText()
        duration_str = self.duration_combo.currentText() if hasattr(self, "duration_combo") else "8s"
        try:
            duration_secs = int(duration_str.replace("s", ""))
        except:
            duration_secs = 8
        
        # Try to get credit from model_provider usages first (real data from platform)
        video_models = model_provider.models.get("video_models", [])
        cost = None
        for m in video_models:
            if m.get("name") == quality:
                usages = m.get("usages", [])
                for u in usages:
                    if u.get("duration") == duration_secs:
                        cost = u.get("cost")
                        break
                if cost is not None:
                    break
        
        # Fallback to static mapping
        if cost is None:
            if quality == "Omni Flash":
                cost = {4: 7, 6: 10, 8: 12, 10: 15}.get(duration_secs, 10)
            elif quality == "Veo 3.1 - Lite":
                cost = 10
            elif quality == "Veo 3.1 - Fast":
                cost = 20
            elif quality == "Veo 3.1 - Quality":
                cost = 100
            elif quality == "Veo 3.1 - Lite [Lower Priority]":
                cost = 0
            else:
                cost = CREDITS_PER_MODEL.get(quality, 10)
        
        parallel = self.parallel_per_account_spin.value() if hasattr(self, "parallel_per_account_spin") else 1
        if parallel > 1:
            self._credit_per_video_label.setText(f"💰 Credit mỗi video: {cost} (Đồng thời {parallel} luồng: {cost * parallel})")
        else:
            self._credit_per_video_label.setText(f"💰 Credit mỗi video: {cost}")

    def update_image_models(self, models: list[str] | None = None):
        if hasattr(self, "model_combo"):
            self.model_combo.clear()
            if not models:
                image_models = model_provider.models.get("image_models", [])
                if image_models:
                    for m in image_models:
                        name = m.get("name", "")
                        key = m.get("key", "")
                        if name:
                            display = f"🍌 {name}" if "banana" in name.lower() else name
                            self.model_combo.addItem(display, key)
                    return
            if models:
                for model in models:
                    self.model_combo.addItem(model)

    def update_video_models(self, qualities: list[str] | None = None):
        if hasattr(self, "quality_combo"):
            self.quality_combo.clear()
            if not qualities:
                video_models = model_provider.models.get("video_models", [])
                if video_models:
                    for m in video_models:
                        name = m.get("name", "")
                        key = m.get("key", "")
                        if name:
                            self.quality_combo.addItem(name, key)
                    return
            if qualities:
                for q in qualities:
                    self.quality_combo.addItem(q)

    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu")
        if folder:
            self.output_input.setText(folder)

    def _browse_input_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục input")
        if folder and hasattr(self, "input_folder_input"):
            self.input_folder_input.setText(folder)

    def get_config(self) -> dict:
        enabled_count = max(1, self._enabled_accounts_count())
        per_account = self.parallel_per_account_spin.value() if hasattr(self, "parallel_per_account_spin") else 1
        delay = self.delay_spin.value() if hasattr(self, "delay_spin") else 0
        config = {
            "task_name": self.task_name_input.text(),
            "project": self.task_name_input.text(),
            "output_folder": self.output_input.text(),
            "concurrent": enabled_count * per_account,
            "parallel_per_account": per_account,
            "aspect_ratio": self.aspect_combo.currentData() or "16:9",
            "delay": delay,
        }
        if hasattr(self, "creation_mode_combo"):
            config["creation_mode"] = self.creation_mode_combo.currentText()
        if hasattr(self, "grok_mode_combo"):
            config["grok_mode"] = self.grok_mode_combo.currentText()
        if hasattr(self, "duration_combo"):
            config["duration"] = self.duration_combo.currentText()
        if hasattr(self, "quality_combo"):
            config["quality"] = self.quality_combo.currentText()
            config["quality_key"] = self.quality_combo.currentData() or ""
        if hasattr(self, "service_combo"):
            config["service"] = self.service_combo.currentText()
        else:
            config["service"] = "Flow"
        if hasattr(self, "model_combo"):
            model = self.model_combo.currentText()
            config["model"] = model
            config["image_model"] = model
            config["model_key"] = self.model_combo.currentData() or ""
        if hasattr(self, "save_mode_combo"):
            config["save_mode"] = self.save_mode_combo.currentText()
        if hasattr(self, "input_folder_input"):
            config["input_folder"] = self.input_folder_input.text()
        if hasattr(self, "start_frame_upload"):
            config["start_frame"] = self.start_frame_upload.get_image_path()
        if hasattr(self, "end_frame_upload"):
            config["end_frame"] = self.end_frame_upload.get_image_path()
        # Uploaded images for @tag
        if self._uploaded_images:
            config["uploaded_images"] = list(self._uploaded_images)
        return config
