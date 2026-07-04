# ui/widgets/header.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal
from ui.themes.tokens import THEME_TOKENS
from ui.widgets.nav_button import NavButton
from ui.widgets.nav_input import NavInput

class Header(QWidget):
    theme_toggled = Signal()
    open_palette = Signal()

    def __init__(self, parent=None, theme="dark"):
        super().__init__(parent)
        self.theme = theme
        self.setFixedHeight(64)
        self.setObjectName("header")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(16)

        # 1. Command Palette / Search
        self.search_btn = NavInput(placeholder="🔍 Search (Ctrl+K)", theme=self.theme)
        self.search_btn.setReadOnly(True)
        self.search_btn.mousePressEvent = lambda e: self.open_palette.emit()
        self.search_btn.setFixedWidth(200)
        self.search_btn.setFixedHeight(32)
        layout.addWidget(self.search_btn)

        layout.addStretch()

        # 5. Quick Action
        self.quick_btn = NavButton("⚡ Quick Action", type="primary", theme=theme)
        self.quick_btn.clicked.connect(self.open_palette.emit)
        layout.addWidget(self.quick_btn)
        
        self._apply_style()

    def _apply_style(self):
        tokens = THEME_TOKENS.get(self.theme, THEME_TOKENS["dark"])
        self.setStyleSheet(f"""
            QWidget#header {{
                background-color: {tokens['bg_surface']};
                border-bottom: 1px solid {tokens['border']};
            }}
            QLabel.header-text {{
                color: {tokens['text_primary']};
            }}
            QLabel.header-tasks {{
                color: {tokens['warning_primary']};
            }}
        """)

    def update_theme(self, theme: str):
        self.theme = theme
        self.search_btn.update_theme(theme)
        self.quick_btn.update_theme(theme)
        self._apply_style()
