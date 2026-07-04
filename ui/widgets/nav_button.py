# ui/widgets/nav_button.py

from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Property
from ui.themes.tokens import THEME_TOKENS

class NavButton(QPushButton):
    def __init__(self, text="", parent=None, type="primary", theme="dark"):
        super().__init__(text, parent)
        self.type = type
        self.theme = theme
        self._current_bg_color = ""
        self._hover_bg_color = ""
        self._apply_style()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
    def _apply_style(self):
        tokens = THEME_TOKENS.get(self.theme, THEME_TOKENS["dark"])
        if self.type == "primary":
            bg = tokens["accent_primary"]
            hover = tokens["accent_hover"]
            color = "#ffffff" # Force white text for primary buttons
            border = "none"
        elif self.type == "ghost":
            bg = "transparent"
            hover = tokens["bg_card"]
            color = tokens["text_primary"]
            border = "none"
        else: # secondary
            bg = tokens["bg_input"]
            hover = tokens["bg_card"]
            color = tokens["text_primary"]
            border = f"1px solid {tokens['border']}"
            
        self._current_bg_color = bg
        self._hover_bg_color = hover
        
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {color};
                border: {border};
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
            QPushButton:pressed {{
                background-color: {tokens.get('accent_active', bg)};
                margin-top: 1px;
            }}
            QPushButton:disabled {{
                background-color: {tokens['bg_surface']};
                color: {tokens['text_muted']};
                border: 1px solid {tokens['border_subtle']};
            }}
        """)

    def update_theme(self, theme: str):
        self.theme = theme
        self._apply_style()
