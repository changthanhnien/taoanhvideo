# ui/widgets/nav_select.py

from PySide6.QtWidgets import QComboBox, QStyledItemDelegate
from PySide6.QtCore import Qt
from ui.themes.tokens import THEME_TOKENS

class NavSelectDelegate(QStyledItemDelegate):
    def __init__(self, theme="dark", parent=None):
        super().__init__(parent)
        self.theme = theme

    def update_theme(self, theme):
        self.theme = theme

class NavSelect(QComboBox):
    def __init__(self, parent=None, theme="dark"):
        super().__init__(parent)
        self.theme = theme
        self._delegate = NavSelectDelegate(self.theme, self)
        self.setItemDelegate(self._delegate)
        self._apply_style()

    def _apply_style(self):
        tokens = THEME_TOKENS.get(self.theme, THEME_TOKENS["dark"])
        self.setStyleSheet(f"""
            QComboBox {{
                background-color: {tokens['bg_input']};
                color: {tokens['text_primary']};
                border: 1px solid {tokens['border']};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }}
            QComboBox:hover {{
                background-color: {tokens['bg_card']};
            }}
            QComboBox:focus {{
                border: 1px solid {tokens['border_focus']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 30px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {tokens['bg_surface']};
                color: {tokens['text_primary']};
                border: 1px solid {tokens['border']};
                border-radius: 6px;
                selection-background-color: {tokens['accent']};
                selection-color: {tokens['text_primary']};
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 8px 12px;
            }}
        """)

    def update_theme(self, theme: str):
        self.theme = theme
        self._delegate.update_theme(theme)
        self._apply_style()
