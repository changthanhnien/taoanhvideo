# ui/widgets/result_panel.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QLabel
from PySide6.QtCore import Qt
from ui.themes.tokens import THEME_TOKENS
from ui.widgets.nav_panel import NavPanel

class ResultPanel(NavPanel):
    def __init__(self, parent=None, theme="dark", task_table=None):
        super().__init__(parent, theme)
        self.task_table = task_table
        
        layout = self.layout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        self.tabs.setObjectName("result_tabs")
        layout.addWidget(self.tabs)
        
        self.history_tab = QWidget()
        
        history_layout = QVBoxLayout(self.history_tab)
        history_layout.setContentsMargins(0, 0, 0, 0)
        if self.task_table:
            history_layout.addWidget(self.task_table)
            
        self.tabs.addTab(self.history_tab, "Kết quả")
        self.tabs.setCurrentIndex(0)
        
        self._apply_tab_style()

    def _create_empty_state(self, title, message, icon):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon_lbl = QLabel(icon)
        icon_lbl.setFont(self.font())
        icon_lbl.setProperty("class", "empty-icon")
        icon_lbl.setStyleSheet("font-size: 48px; background: transparent;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        text_lbl = QLabel(message)
        text_lbl.setProperty("class", "empty-text")
        text_lbl.setStyleSheet("font-size: 14px; background: transparent;")
        text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(icon_lbl)
        layout.addWidget(text_lbl)
        return widget
        
    def _apply_tab_style(self):
        tokens = THEME_TOKENS.get(self.theme, THEME_TOKENS["dark"])
        self.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                border-top: 1px solid {tokens['border']};
                background: {tokens['bg_surface']};
            }}
            QTabBar::tab {{
                background: {tokens['bg_input']};
                color: {tokens['text_muted']};
                padding: 10px 20px;
                border: none;
                font-weight: 600;
            }}
            QTabBar::tab:selected {{
                background: {tokens['bg_surface']};
                color: {tokens['accent']};
                border-bottom: 2px solid {tokens['accent']};
            }}
            QTabBar::tab:hover:!selected {{
                background: {tokens['bg_card']};
                color: {tokens['text_primary']};
            }}
            QLabel.empty-icon {{
                color: {tokens['text_muted']};
            }}
            QLabel.empty-text {{
                color: {tokens['text_muted']};
            }}
        """)

    def update_theme(self, theme: str):
        super().update_theme(theme)
        self._apply_tab_style()
