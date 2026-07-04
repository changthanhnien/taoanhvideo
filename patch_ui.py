import re

with open("ui/widgets/task_table.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Update PromptCellWidget copy button
copy_old = """    def _on_copy(self):
        QApplication.clipboard().setText(self._prompt)"""
copy_new = """    def _on_copy(self):
        QApplication.clipboard().setText(self._prompt)
        sender = self.sender()
        if sender:
            sender.setText("✓")
            QTimer.singleShot(1500, lambda: self._reset_btn(sender))

    def _reset_btn(self, btn):
        try:
            btn.setText("📋")
        except:
            pass"""
code = code.replace(copy_old, copy_new)

# 2. Update columns in TaskTable._setup_columns
cols_old = """    def _setup_columns(self):
        if self._mode in ("image", "char_image"):
            cols = ["#", "Prompt", "Ảnh kết quả", "Trạng thái"]
        elif self._mode in ("video_ref",):
            cols = ["#", "Preview", "Filename", "Prompt", "Trạng thái"]
        elif self._mode in ("frame_video",):
            cols = ["#", "Start", "→", "End", "Prompt", "Trạng thái"]
        else:
            cols = ["#", "Prompt", "Video", "Trạng thái"]"""
cols_new = """    def _setup_columns(self):
        if self._mode in ("image", "char_image", "video_plain"):
            cols = ["#", "Prompt", "Kết quả", "Trạng thái", "Tải xuống"]
        elif self._mode in ("video_ref",):
            cols = ["#", "Preview", "Filename", "Prompt", "Trạng thái"]
        elif self._mode in ("frame_video",):
            cols = ["#", "Start", "→", "End", "Prompt", "Trạng thái"]
        else:
            cols = ["#", "Prompt", "Kết quả", "Trạng thái", "Tải xuống"]"""
code = code.replace(cols_old, cols_new)

# Update column sizing
resize_old = """        if self._mode in ("image", "char_image"):
            header.resizeSection(2, 120)
        elif self._mode == "video_ref":
            header.resizeSection(1, 110)
            header.resizeSection(2, 180)
        elif self._mode == "frame_video":
            header.resizeSection(1, 140)
            header.resizeSection(2, 28)
            header.resizeSection(3, 140)
        else:
            header.resizeSection(2, 120)"""
resize_new = """        if self._mode in ("image", "char_image", "video_plain"):
            header.resizeSection(2, 120)
            header.resizeSection(3, 100)
            header.resizeSection(4, 90)
        elif self._mode == "video_ref":
            header.resizeSection(1, 110)
            header.resizeSection(2, 180)
        elif self._mode == "frame_video":
            header.resizeSection(1, 140)
            header.resizeSection(2, 28)
            header.resizeSection(3, 140)
        else:
            header.resizeSection(2, 120)
            header.resizeSection(3, 100)
            header.resizeSection(4, 90)"""
code = code.replace(resize_old, resize_new)

# 3. Update set_items to handle the new action column (Tải xuống + Trash)
set_items_old = """            if self._mode in ("image", "char_image"):
                thumb = ThumbnailCellWidget(item.output_path, item.thumbnail_path, item.id)
                thumb.retry_clicked.connect(lambda _=False, value=item.id: self.item_retry.emit(value))
                self.table.setCellWidget(row, 2, thumb)
                self._set_status(row, status_col, item.status, item.output_path)
                continue

            self.table.setCellWidget(row, 1, PromptCellWidget(item.prompt))
            thumb = ThumbnailCellWidget(item.output_path, item.thumbnail_path, item.id)
            thumb.retry_clicked.connect(lambda _=False, value=item.id: self.item_retry.emit(value))
            self.table.setCellWidget(row, 2, thumb)
            self._set_status(row, status_col, item.status, item.output_path)"""
set_items_new = """            if self._mode in ("image", "char_image", "video_plain"):
                self.table.setCellWidget(row, 1, PromptCellWidget(item.prompt))
                thumb = ThumbnailCellWidget(item.output_path, item.thumbnail_path, item.id)
                thumb.retry_clicked.connect(lambda _=False, value=item.id: self.item_retry.emit(value))
                self.table.setCellWidget(row, 2, thumb)
                self._set_status(row, 3, item.status, item.output_path)
                self._set_actions(row, 4, item.status, item.output_path)
                continue

            self.table.setCellWidget(row, 1, PromptCellWidget(item.prompt))
            thumb = ThumbnailCellWidget(item.output_path, item.thumbnail_path, item.id)
            thumb.retry_clicked.connect(lambda _=False, value=item.id: self.item_retry.emit(value))
            self.table.setCellWidget(row, 2, thumb)
            self._set_status(row, 3, item.status, item.output_path)
            self._set_actions(row, 4, item.status, item.output_path)"""
code = code.replace(set_items_old, set_items_new)

# 4. Remove download button from _set_status and create _set_actions
status_old = """        # Use a widget with download button for completed status
        if status == ItemStatus.COMPLETED and output_path:
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(4, 2, 4, 2)
            layout.setSpacing(2)
            layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            status_label = QLabel(text)
            status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            status_label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold; background: transparent;")
            layout.addWidget(status_label)
            
            dl_btn = QPushButton("📥 Tải xuống")
            dl_btn.setFixedHeight(22)
            dl_btn.setStyleSheet(
                "QPushButton { font-size: 11px; padding: 1px 6px; background: #1e293b; border: 1px solid #22c55e; border-radius: 4px; color: #22c55e; }"
                "QPushButton:hover { background: #14532d; }"
            )
            dl_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            dl_btn.clicked.connect(lambda _=False, path=output_path: self._open_file_location(path))
            layout.addWidget(dl_btn)
            
            self.table.setCellWidget(row, col, widget)
        else:
            # Clear any existing widget
            self.table.removeCellWidget(row, col)
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setForeground(QColor(color))
            self.table.setItem(row, col, item)"""

status_new = """        # Render only status text in status column
        self.table.removeCellWidget(row, col)
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setForeground(QColor(color))
        self.table.setItem(row, col, item)

    def _set_actions(self, row: int, col: int, status: str, output_path: str = ""):
        if self._mode not in ("image", "char_image", "video_plain"):
            return
            
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Download button
        if status == ItemStatus.COMPLETED and output_path:
            dl_btn = QPushButton("📥")
            dl_btn.setToolTip("Tải xuống")
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
        del_btn.clicked.connect(lambda: self._delete_row(row))
        layout.addWidget(del_btn)
        
        self.table.setCellWidget(row, col, widget)
        
    def _delete_row(self, row: int):
        self.table.removeRow(row)
        count = self.table.rowCount()
        self.count_badge.setText(f"{count} prompts")"""

code = code.replace(status_old, status_new)

# Update update_item_status to also call _set_actions
update_old = """        self._set_status(row, col, status, output_path)"""
update_new = """        self._set_status(row, col, status, output_path)
        if hasattr(self, '_set_actions'):
            self._set_actions(row, col + 1, status, output_path)"""
code = code.replace(update_old, update_new)

# update col index for update_item_status
update_col_old = """    def update_item_status(self, row: int, status: str):
        col = self.table.columnCount() - 1"""
update_col_new = """    def update_item_status(self, row: int, status: str):
        col = self.table.columnCount() - 2 if self._mode in ("image", "char_image", "video_plain") else self.table.columnCount() - 1"""
code = code.replace(update_col_old, update_col_new)

with open("ui/widgets/task_table.py", "w", encoding="utf-8") as f:
    f.write(code)
print("Updated task_table.py")
