# ui/widgets/nav_panel.py

from PySide6.QtWidgets import QFrame, QVBoxLayout
from ui.themes.tokens import THEME_TOKENS

class NavPanel(QFrame):
    def __init__(self, parent=None, theme="dark"):
        super().__init__(parent)
        self.theme = theme
        self.setObjectName("nav_panel")
        self.setLayout(QVBoxLayout())
        self._apply_style()

    def _apply_style(self):
        tokens = THEME_TOKENS.get(self.theme, THEME_TOKENS["dark"])
        self.setStyleSheet(f"""
            QFrame#nav_panel {{
                background-color: {tokens['bg_surface']};
                border: 1px solid {tokens['border']};
                border-radius: 12px;
            }}
        """)

    def update_theme(self, theme: str):
        self.theme = theme
        self._apply_style()
