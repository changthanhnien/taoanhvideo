"""VidGen AI - Task table widget for displaying prompt results."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QCursor, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config.constants import ItemStatus


class AnimatedStatusWidget(QLabel):
    """Animate a loading icon using QTimer."""
    def __init__(self, text, color, parent=None):
        super().__init__(parent)
        self.base_text = text
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"color: {color}; background: transparent; font-weight: bold;")
        
        # Braille spinner animation
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.frame_idx = 0
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_frame)
        self.timer.start(100)
        self._update_frame()
        
    def set_status(self, text, color):
        self.base_text = text
        self.setStyleSheet(f"color: {color}; background: transparent; font-weight: bold;")
        self._update_frame()
        
    def _update_frame(self):
        icon = self.frames[self.frame_idx]
        self.setText(f"{icon} {self.base_text}")
        self.frame_idx = (self.frame_idx + 1) % len(self.frames)


class PromptDetailDialog(QDialog):
    """Dialog showing prompt, model, ratio, with copy button."""

    def __init__(self, prompt, model="", aspect_ratio="", parent=None):
        super().__init__(parent)
        self._prompt = prompt
        self._model = model
        self._aspect_ratio = aspect_ratio
        self.setWindowTitle("Chi tiết Prompt")
        self.setFixedSize(520, 400)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Nội dung Prompt")
        title.setProperty("class", "field-label")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #dae2fd;")
        layout.addWidget(title)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(self._prompt)
        self.text_edit.setStyleSheet("background: #18181b; border: 1px solid #3f3f46; border-radius: 6px; color: #f4f4f5; padding: 8px; font-size: 13px;")
        layout.addWidget(self.text_edit, 1)

        # Info row: model + ratio
        info_row = QHBoxLayout()
        info_row.setSpacing(16)
        if self._model:
            model_label = QLabel(f"🎨 Mô hình: {self._model}")
            model_label.setStyleSheet("color: #93c5fd; font-size: 12px; background: #1e293b; padding: 4px 10px; border-radius: 4px;")
            info_row.addWidget(model_label)
        if self._aspect_ratio:
            ratio_label = QLabel(f"📐 Tỷ lệ: {self._aspect_ratio}")
            ratio_label.setStyleSheet("color: #a78bfa; font-size: 12px; background: #1e293b; padding: 4px 10px; border-radius: 4px;")
            info_row.addWidget(ratio_label)
        info_row.addStretch()
        layout.addLayout(info_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.copy_btn = QPushButton("📋  Copy prompt")
        self.copy_btn.setObjectName("btn-primary")
        self.copy_btn.setStyleSheet("QPushButton { background: #3b82f6; color: white; border: none; border-radius: 6px; padding: 8px 20px; font-size: 13px; } QPushButton:hover { background: #2563eb; }")
        self.copy_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.copy_btn.clicked.connect(self._on_copy)
        btn_row.addWidget(self.copy_btn)

        close_btn = QPushButton("Đóng")
        close_btn.setObjectName("btn-ghost")
        close_btn.setStyleSheet("QPushButton { background: transparent; color: #94a3b8; border: 1px solid #3f3f46; border-radius: 6px; padding: 8px 20px; font-size: 13px; } QPushButton:hover { background: #1e293b; }")
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _on_copy(self):
        QApplication.clipboard().setText(self._prompt)
        self.copy_btn.setText("✓  Đã copy!")
        QTimer.singleShot(1500, lambda: self.copy_btn.setText("📋  Copy prompt"))


class PromptCellWidget(QWidget):
    def __init__(self, prompt, model="", aspect_ratio="", parent=None):
        super().__init__(parent)
        self._prompt = prompt
        self._model = model
        self._aspect_ratio = aspect_ratio
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 4, 2)
        layout.setSpacing(4)

        self.label = QLabel(self._prompt)
        self.label.setStyleSheet("color: #dae2fd; background: transparent; padding: 0; font-size: 13px;")
        self.label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.label.setToolTip("Click để xem chi tiết")
        self.label.mousePressEvent = self._on_label_click
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.label, 1)

        copy_btn = QPushButton("📋")
        copy_btn.setFixedSize(26, 26)
        copy_btn.setToolTip("Copy prompt")
        copy_btn.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid #2d3449; border-radius: 4px; font-size: 13px; padding: 0; }"
            "QPushButton:hover { background: #222a3d; border-color: #4d8eff; }"
        )
        copy_btn.clicked.connect(self._on_copy)
        layout.addWidget(copy_btn, 0, Qt.AlignmentFlag.AlignVCenter)

    def _on_label_click(self, event):
        PromptDetailDialog(self._prompt, self._model, self._aspect_ratio, self).exec()

    def _on_copy(self):
        QApplication.clipboard().setText(self._prompt)
        sender = self.sender()
        if sender:
            sender.setText("✓")
            QTimer.singleShot(1500, lambda: self._reset_btn(sender))

    def _reset_btn(self, btn):
        try:
            btn.setText("📋")
        except:
            pass

    def set_prompt(self, prompt: str):
        self._prompt = prompt
        self.label.setText(prompt)


class ThumbnailCellWidget(QWidget):
    retry_clicked = Signal()
    preview_clicked = Signal(str)

    def __init__(self, output_path="", thumbnail_path="", item_id=0, parent=None):
        super().__init__(parent)
        self.output_path = output_path
        self.thumbnail_path = thumbnail_path
        self.item_id = item_id
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.empty_label = QLabel("")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: #64748b; background: transparent; font-size: 12px;")
        layout.addWidget(self.empty_label)

        self.open_btn = QPushButton("👁 Xem")
        self.open_btn.setFixedHeight(22)
        self.open_btn.setStyleSheet(
            "QPushButton { font-size: 11px; padding: 1px 6px; background: #1e293b; border: 1px solid #3b82f6; border-radius: 4px; color: #3b82f6; }"
            "QPushButton:hover { background: #1e3a5f; }"
        )
        self.open_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.open_btn.clicked.connect(self._preview_in_app)
        
        has_file = bool(self.output_path or self.thumbnail_path)
        self.open_btn.setVisible(has_file)
        self.empty_label.setVisible(not has_file)
        
        layout.addWidget(self.open_btn)

    def _preview_in_app(self):
        target = self.output_path or self.thumbnail_path
        if target and Path(target).exists():
            self.preview_clicked.emit(str(target))
        elif target:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
        else:
            self.retry_clicked.emit()

    def update_output(self, output_path):
        self.output_path = output_path
        has_file = bool(output_path)
        self.open_btn.setVisible(has_file)
        self.empty_label.setVisible(not has_file)


class TaskTable(QWidget):
    """Right panel - task table showing prompts, thumbnails, status."""

    item_retry = Signal(int)   # Emit item_id to retry
    item_open_file = Signal(int)

    def __init__(self, mode: str = "video", parent=None):
        super().__init__(parent)
        self._mode = mode
        self._item_data = {}  # row -> {prompt, model, ratio, item_id}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        header_row.addStretch()

        self.count_badge = QLabel("0 prompts")
        self.count_badge.setStyleSheet(
            "color: #64748b; font-size: 11px; padding: 2px 8px; background: #1e293b; border-radius: 8px;"
        )
        header_row.addWidget(self.count_badge)
        layout.addLayout(header_row)

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet(
            """
            QTableWidget { background: transparent; border: none; font-size: 13px; outline: none; }
            QTableWidget::item { padding: 4px 6px; border-bottom: 1px solid #222a3d; }
            QTableWidget::item:focus { outline: none; border: none; }
            QHeaderView::section {
                background: #131b2e;
                color: #8c909f;
                font-weight: 600;
                font-size: 11px;
                padding: 4px 6px;
                border: none;
                border-bottom: 1px solid #424754;
            }
        """
        )
        layout.addWidget(self.table, 1)
        self._setup_columns()

    def _setup_columns(self):
        if self._mode in ("image", "char_image", "video", "grok_image", "grok_video"):
            cols = ["#", "Prompt", "Kết quả", "Trạng thái", "Tải xuống"]
        elif self._mode in ("video_ref",):
            cols = ["#", "Preview", "Filename", "Prompt", "Trạng thái"]
        elif self._mode in ("frame_video",):
            cols = ["#", "Start", "→", "End", "Prompt", "Trạng thái"]
        else:
            cols = ["#", "Prompt", "Kết quả", "Trạng thái", "Tải xuống"]

        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.resizeSection(0, 36)

        prompt_col = 1 if self._mode not in ("video_ref", "frame_video") else 3
        if self._mode == "frame_video":
            prompt_col = 4
        header.setSectionResizeMode(prompt_col, QHeaderView.ResizeMode.Stretch)
        header.resizeSection(len(cols) - 1, 140)

        if self._mode in ("image", "char_image", "video", "grok_image", "grok_video"):
            header.resizeSection(2, 120)
            header.resizeSection(3, 130)
            header.resizeSection(4, 140)
        elif self._mode == "video_ref":
            header.resizeSection(1, 110)
            header.resizeSection(2, 180)
            header.resizeSection(4, 130)
        elif self._mode == "frame_video":
            header.resizeSection(1, 140)
            header.resizeSection(2, 28)
            header.resizeSection(3, 140)
            header.resizeSection(5, 130)
        else:
            header.resizeSection(2, 120)
            header.resizeSection(3, 130)
            header.resizeSection(4, 90)

    def set_items(self, items: list, task_model=None, task_ratio=None):
        self.table.setRowCount(len(items))
        self.table.verticalHeader().setDefaultSectionSize(62)
        self.count_badge.setText(f"{len(items)} prompts")
        
        # Store task-level info for detail dialog
        self._task_model = task_model or ""
        self._task_ratio = task_ratio or ""

        for row, item in enumerate(items):
            num_item = QTableWidgetItem(str(row + 1))
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            num_item.setData(Qt.UserRole, getattr(item, "id", 0))
            self.table.setItem(row, 0, num_item)
            
            # Store item data for retry
            self._item_data[row] = {
                "item_id": getattr(item, "id", 0),
                "prompt": getattr(item, "prompt", ""),
                "model": self._task_model,
                "ratio": self._task_ratio,
            }

            if self._mode in ("image", "char_image", "video", "grok_image", "grok_video"):
                status_col = self.table.columnCount() - 2
                action_col = self.table.columnCount() - 1
            else:
                status_col = self.table.columnCount() - 1
                action_col = None

            if self._mode == "video_ref":
                thumb = ThumbnailCellWidget(item.output_path, item.thumbnail_path, item.id)
                thumb.retry_clicked.connect(lambda _=False, value=item.id: self.item_retry.emit(value))
                self.table.setCellWidget(row, 1, thumb)
                self.table.setItem(row, 2, QTableWidgetItem(item.reference_image or ""))
                self.table.setCellWidget(row, 3, PromptCellWidget(item.prompt, self._task_model, self._task_ratio))
                self._set_status(row, status_col, item.status, item.output_path)
                continue

            if self._mode == "frame_video":
                self.table.setItem(row, 1, QTableWidgetItem(item.start_frame or ""))
                arrow_item = QTableWidgetItem("→")
                arrow_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 2, arrow_item)
                self.table.setItem(row, 3, QTableWidgetItem(item.end_frame or ""))
                self.table.setCellWidget(row, 4, PromptCellWidget(item.prompt, self._task_model, self._task_ratio))
                self._set_status(row, status_col, item.status, item.output_path)
                continue

            # Standard modes: image, char_image, video_plain
            self.table.setCellWidget(row, 1, PromptCellWidget(item.prompt, self._task_model, self._task_ratio))
            thumb = ThumbnailCellWidget(item.output_path, item.thumbnail_path, item.id)
            thumb.retry_clicked.connect(lambda _=False, value=item.id: self.item_retry.emit(value))
            thumb.preview_clicked.connect(self._handle_preview)
            self.table.setCellWidget(row, 2, thumb)
            self._set_status(row, status_col, item.status, item.output_path)
            if action_col is not None:
                self._set_actions(row, action_col, item.status, item.output_path)

    def _handle_preview(self, target_path: str):
        paths = []
        target_idx = 0
        ext = Path(target_path).suffix.lower()
        is_video = ext in ('.mp4', '.mov', '.avi', '.mkv', '.webm')
        
        # Gather all valid paths from the table of the SAME TYPE
        for r in range(self.table.rowCount()):
            cell = self.table.cellWidget(r, 2)
            if isinstance(cell, ThumbnailCellWidget):
                p = cell.output_path or cell.thumbnail_path
                if p and Path(p).exists():
                    p_ext = Path(p).suffix.lower()
                    p_is_vid = p_ext in ('.mp4', '.mov', '.avi', '.mkv', '.webm')
                    if is_video == p_is_vid:
                        paths.append(str(p))
                        if str(p) == target_path:
                            target_idx = len(paths) - 1
        
        if not paths:
            return
            
        if is_video:
            try:
                from ui.widgets.video_preview_dialog import VideoPreviewDialog
                dialog = VideoPreviewDialog(target_path, self)
                dialog.exec()
            except Exception as e:
                # Fallback if multimedia not available
                QDesktopServices.openUrl(QUrl.fromLocalFile(target_path))
        else:
            from ui.workflow.preview_panel import PreviewImageDialog
            dialog = PreviewImageDialog(paths, target_idx, self)
            dialog.exec()

    def _set_status(self, row: int, col: int, status: str, output_path: str = ""):
        """Set status cell. CRITICAL: if output file exists → always COMPLETED."""
        # GUARANTEE: If output file exists, status is always Done
        if output_path and Path(output_path).exists() and Path(output_path).stat().st_size > 0:
            status = ItemStatus.COMPLETED
        
        status_labels = {
            ItemStatus.PENDING: ("Đang chờ", "#94a3b8", True),
            ItemStatus.UPLOADING: ("Đang tải lên", "#4d8eff", True),
            ItemStatus.GENERATING: ("Đang tạo", "#4d8eff", True),
            ItemStatus.DOWNLOADING: ("Đang tải", "#4d8eff", True),
            ItemStatus.COMPLETED: ("✅ Done", "#22c55e", False),
            ItemStatus.ERROR: ("❌ Lỗi", "#ef4444", False),
        }
        text, color, animated = status_labels.get(status, ("?", "#94a3b8", False))
        
        if animated:
            existing = self.table.cellWidget(row, col)
            if isinstance(existing, AnimatedStatusWidget):
                existing.set_status(text, color)
            else:
                widget = AnimatedStatusWidget(text, color)
                self.table.setCellWidget(row, col, widget)
                self.table.setItem(row, col, QTableWidgetItem(""))
        else:
            self.table.removeCellWidget(row, col)
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setForeground(QColor(color))
            self.table.setItem(row, col, item)

    def _set_actions(self, row: int, col: int, status: str, output_path: str = ""):
        if self._mode not in ("image", "char_image", "video", "grok_image", "grok_video"):
            return
        
        # GUARANTEE: override status if file exists
        if output_path and Path(output_path).exists() and Path(output_path).stat().st_size > 0:
            status = ItemStatus.COMPLETED
            
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Retry/reload button
        retry_btn = QPushButton("🔄")
        retry_btn.setToolTip("Chạy lại prompt này")
        retry_btn.setFixedSize(26, 26)
        retry_btn.setStyleSheet(
            "QPushButton { font-size: 12px; padding: 0; background: transparent; border: 1px solid #475569; border-radius: 4px; color: #93c5fd; }"
            "QPushButton:hover { background: #1e3a5f; border-color: #3b82f6; }"
        )
        retry_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        item_id = self._item_data.get(row, {}).get("item_id", 0)
        retry_btn.clicked.connect(lambda _=False, iid=item_id: self.item_retry.emit(iid))
        layout.addWidget(retry_btn)
        
        # Download button (only if completed)
        if status == ItemStatus.COMPLETED and output_path:
            dl_btn = QPushButton("📥")
            dl_btn.setToolTip("Mở thư mục chứa file")
            dl_btn.setFixedSize(26, 26)
            dl_btn.setStyleSheet(
                "QPushButton { font-size: 12px; padding: 0; background: #1e293b; border: 1px solid #22c55e; border-radius: 4px; color: #22c55e; }"
                "QPushButton:hover { background: #14532d; }"
            )
            dl_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            dl_btn.clicked.connect(lambda _=False, path=output_path: self._open_file_location(path))
            layout.addWidget(dl_btn)
            
        # Delete button
        del_btn = QPushButton("🗑")
        del_btn.setToolTip("Xóa")
        del_btn.setFixedSize(26, 26)
        del_btn.setStyleSheet(
            "QPushButton { font-size: 13px; padding: 0; background: transparent; border: 1px solid #475569; border-radius: 4px; color: #ef4444; }"
            "QPushButton:hover { background: #450a0a; border-color: #ef4444; }"
        )
        del_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        del_btn.clicked.connect(self._delete_row)
        layout.addWidget(del_btn)
        
        self.table.setCellWidget(row, col, widget)
        
    def _delete_row(self):
        sender = self.sender()
        if sender:
            wrapper = sender.parent()
            for r in range(self.table.rowCount()):
                for c in range(self.table.columnCount()):
                    if self.table.cellWidget(r, c) == wrapper:
                        self.table.removeRow(r)
                        count = self.table.rowCount()
                        self.count_badge.setText(f"{count} prompts")
                        return

    def _open_file_location(self, path: str):
        """Open the folder containing the file and select it."""
        import os, subprocess
        if Path(path).exists():
            flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            subprocess.Popen(f'explorer /select,"{path}"', creationflags=flags)
        elif Path(path).parent.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))

    def clear(self):
        self.table.setRowCount(0)
        self.count_badge.setText("0 prompts")

    def update_item_status(self, row: int, status: str, output_path: str = None):
        col = self.table.columnCount() - 2 if self._mode in ("image", "char_image", "video", "grok_image", "grok_video") else self.table.columnCount() - 1
        # Try to get output_path from the thumbnail widget
        if not output_path:
            output_path = ""
            if self._mode in ("image", "char_image", "grok_image"):
                thumb_col = 2
            elif self._mode == "video_ref":
                thumb_col = 1
            else:
                thumb_col = 2
            widget = self.table.cellWidget(row, thumb_col)
            if isinstance(widget, ThumbnailCellWidget):
                output_path = widget.output_path or ""
        
        # GUARANTEE: if output file exists, always show Done
        if output_path and Path(output_path).exists() and Path(output_path).stat().st_size > 0:
            status = ItemStatus.COMPLETED
        
        self._set_status(row, col, status, output_path)
        if self._mode in ("image", "char_image", "video", "grok_image", "grok_video"):
            self._set_actions(row, col + 1, status, output_path)
            
        if output_path:
            self.update_item_output(row, output_path)

    def update_item_output(self, row: int, output_path: str):
        if self._mode in ("image", "char_image", "grok_image"):
            thumb_col = 2
        elif self._mode == "video_ref":
            thumb_col = 1
        else:
            thumb_col = 2
        widget = self.table.cellWidget(row, thumb_col)
        if isinstance(widget, ThumbnailCellWidget):
            widget.update_output(output_path)

    def update_item_error(self, row: int, error_msg: str):
        col = self.table.columnCount() - 2 if self._mode in ("image", "char_image", "video") else self.table.columnCount() - 1
        
        # GUARANTEE: Check if output file exists - if yes, override to Done
        thumb_col = 2 if self._mode not in ("video_ref",) else 1
        widget = self.table.cellWidget(row, thumb_col)
        if isinstance(widget, ThumbnailCellWidget) and widget.output_path:
            if Path(widget.output_path).exists() and Path(widget.output_path).stat().st_size > 0:
                # File exists! Show Done, not Error
                self._set_status(row, col, ItemStatus.COMPLETED, widget.output_path)
                if self._mode in ("image", "char_image", "video"):
                    self._set_actions(row, col + 1, ItemStatus.COMPLETED, widget.output_path)
                return
        
        error_labels = {
            "RESOURCE_EXHAUSTED": "Hết quota",
            "USER_QUOTA_REACHED": "Hết quota",
            "PERMISSION_DENIED": "Không có quyền",
            "MODEL_ACCESS_DENIED": "Model bị chặn",
            "INVALID_ARGUMENT": "Google API lỗi - thử lại sau",
            "Media not found": "Media không tìm thấy",
            "RECAPTCHA": "Lỗi reCAPTCHA",
            "Session hết hạn": "Session hết hạn",
            "không an toàn": "Prompt vi phạm chính sách",
            "bị chặn": "Prompt bị chặn",
            "Hết quota tạo ảnh": "Hết quota ảnh",
            "Hết quota tạo video": "Hết quota video",
            "HTTP 400": "Google API lỗi (400)",
            "HTTP 403": "Bị từ chối (403)",
            "HTTP 429": "Quá tải - thử lại sau",
            "HTTP 500": "Google server lỗi (500)",
            "Download failed": "Tải thất bại",
            "Storyboard failed": "Lỗi tạo storyboard",
            "Image download failed": "Tải ảnh thất bại",
            "Opening in existing browser session": "Lỗi khởi động trình duyệt",
        }
        short_msg = "Lỗi"
        lowered = (error_msg or "").lower()
        for key, label in error_labels.items():
            if key.lower() in lowered:
                short_msg = label
                break

        # The user requested: "nếu lỗi thì nó k được báo đỏ... nên cứ để Chờ là được"
        # We will show it as 'Đang chờ' but with a tooltip explaining the error, and a gray/orange color.
        widget = AnimatedStatusWidget("Đang chờ", "#f59e0b")
        widget.setToolTip(f"Lỗi phiên trước: {short_msg} | {error_msg or ''}")
        self.table.setCellWidget(row, col, widget)
        self.table.setItem(row, col, QTableWidgetItem(""))
        
        # Update actions with retry
        if self._mode in ("image", "char_image", "video"):
            self._set_actions(row, col + 1, ItemStatus.ERROR, "")
