# ui/widgets/command_palette.py
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem
from PySide6.QtCore import Qt, Signal
from ui.themes.tokens import THEME_TOKENS

class CommandPalette(QDialog):
    command_selected = Signal(str)

    def __init__(self, parent=None, theme="dark"):
        super().__init__(parent)
        self.theme = theme
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.setFixedSize(600, 400)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search commands... (e.g., 'Settings')")
        self.search_input.setFixedHeight(50)
        self.search_input.textChanged.connect(self._filter_commands)
        layout.addWidget(self.search_input)
        
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)
        
        self.commands = [
            ("image", "Tạo ảnh Flow", "🖼️"),
            ("video", "Tạo video Flow", "📹"),
            ("char_video", "Video to Video", "🎬"),
            ("long_video", "Nối khung hình", "🔗"),
            ("grok_image", "Tạo ảnh Grok", "🤖"),
            ("grok_video", "Tạo video Grok", "🛸"),
            ("watermark", "Xóa logo", "💧"),
            ("workflow_studio", "Workflow Studio", "🔀"),
            ("history", "Lịch sử tạo", "🕒"),
            ("settings", "Cài đặt hệ thống", "⚙️"),
        ]
        
        self._populate()
        self._apply_style()

    def _populate(self, filter_text=""):
        self.list_widget.clear()
        for key, label, icon in self.commands:
            if filter_text.lower() in label.lower() or filter_text == "":
                item = QListWidgetItem(f"{icon}  {label}")
                item.setData(Qt.ItemDataRole.UserRole, key)
                self.list_widget.addItem(item)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _filter_commands(self, text):
        self._populate(text)

    def _on_item_clicked(self, item):
        key = item.data(Qt.ItemDataRole.UserRole)
        self.command_selected.emit(key)
        self.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return:
            item = self.list_widget.currentItem()
            if item:
                self._on_item_clicked(item)
        elif event.key() == Qt.Key.Key_Down:
            self.list_widget.setFocus()
            super().keyPressEvent(event)
        elif event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)

    def _apply_style(self):
        tokens = THEME_TOKENS.get(self.theme, THEME_TOKENS["dark"])
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {tokens['bg_surface']};
                border: 1px solid {tokens['border_focus']};
                border-radius: 8px;
            }}
            QLineEdit {{
                background-color: {tokens['bg_input']};
                color: {tokens['text_primary']};
                border: none;
                border-bottom: 1px solid {tokens['border']};
                padding: 12px 20px;
                font-size: 14px;
            }}
            QListWidget {{
                background-color: {tokens['bg_surface']};
                color: {tokens['text_primary']};
                border: none;
                font-size: 14px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 12px 20px;
                border-bottom: 1px solid {tokens['border']};
            }}
            QListWidget::item:hover {{
                background-color: {tokens['bg_card']};
            }}
            QListWidget::item:selected {{
                background-color: {tokens['accent']};
                color: #ffffff;
            }}
        """)
