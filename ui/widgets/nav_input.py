# ui/widgets/nav_input.py

from PySide6.QtWidgets import QLineEdit
from ui.themes.tokens import THEME_TOKENS

class NavInput(QLineEdit):
    def __init__(self, placeholder="", parent=None, theme="dark"):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.theme = theme
        self._apply_style()

    def _apply_style(self):
        tokens = THEME_TOKENS.get(self.theme, THEME_TOKENS["dark"])
        self.setStyleSheet(f"""
            QLineEdit {{
                background-color: {tokens['bg_input']};
                color: {tokens['text_primary']};
                border: 1px solid {tokens['border']};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                selection-background-color: {tokens['accent']};
            }}
            QLineEdit:hover {{
                background-color: {tokens['bg_card']};
            }}
            QLineEdit:focus {{
                border: 1px solid {tokens['border_focus']};
                background-color: {tokens['bg_surface']};
            }}
            QLineEdit:disabled {{
                background-color: {tokens['bg_surface']};
                color: {tokens['text_muted']};
            }}
        """)

    def update_theme(self, theme: str):
        self.theme = theme
        self._apply_style()
