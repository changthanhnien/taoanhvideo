# ui/themes/engine.py

from config.constants import FONT_BODY
from ui.themes.tokens import THEME_TOKENS

def compile_theme(theme_name: str) -> str:
    """Compiles JSON-like tokens into a QSS string."""
    tokens = THEME_TOKENS.get(theme_name, THEME_TOKENS["dark"])
    
    qss = f"""
    * {{
        font-family: "{FONT_BODY}", "Segoe UI", sans-serif;
        color: {tokens['text_primary']};
    }}
    
    QMainWindow, QDialog, QWidget#main_window {{
        background-color: {tokens['bg_app']};
    }}
    
    QWidget#sidebar, QWidget#header {{
        background-color: {tokens['bg_surface']};
        border: none;
        border-right: 1px solid {tokens['border']};
    }}
    
    QWidget#workspace {{
        background-color: {tokens['bg_app']};
    }}
    
    QLabel.warning-label {{
        color: {tokens['warning_primary']};
        border: 1px solid {tokens['warning_primary']};
        border-radius: 6px;
        padding: 4px 6px;
    }}
    QLabel.info-label {{
        color: {tokens['text_muted']};
        font-style: italic;
    }}
    
    QWidget#result_panel, QWidget#configPanel, QFrame#nav_panel, QWidget#card, QScrollArea > QWidget > QWidget {{
        background-color: {tokens['bg_surface']};
        border: 1px solid {tokens['border']};
        border-radius: 12px;
    }}
    
    /* Global Components */
    QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox {{
        background-color: {tokens['bg_input']};
        color: {tokens['text_primary']};
        border: 1px solid {tokens['border']};
        border-radius: 6px;
        padding: 8px 12px;
        font-size: 13px;
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus {{
        border: 1px solid {tokens['border_focus']};
        background-color: {tokens['bg_input']};
    }}
    QSpinBox::up-button, QSpinBox::down-button {{
        width: 16px;
        border: none;
        background: transparent;
    }}
    
    QComboBox {{
        background-color: {tokens['bg_input']};
        color: {tokens['text_primary']};
        border: 1px solid {tokens['border']};
        border-radius: 6px;
        padding: 8px 12px;
        font-size: 13px;
    }}
    QComboBox:focus {{
        border: 1px solid {tokens['border_focus']};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox::down-arrow {{
        width: 10px;
        height: 10px;
    }}
    
    QDialog {{
        background-color: {tokens['bg_app']};
        color: {tokens['text_primary']};
    }}
    
    QTabWidget::pane {{
        border: 1px solid {tokens['border']};
        border-radius: 8px;
        background: {tokens['bg_surface']};
    }}
    QTabBar::tab {{
        background: {tokens['bg_surface']};
        color: {tokens['text_muted']};
        padding: 8px 16px;
        border: none;
        border-bottom: 2px solid transparent;
    }}
    QTabBar::tab:selected {{
        color: {tokens['accent']};
        border-bottom: 2px solid {tokens['accent']};
    }}
    QTabBar::tab:hover {{
        color: {tokens['text_primary']};
    }}
    
    QPushButton {{
        background-color: {tokens['bg_input']};
        color: {tokens['text_primary']};
        border: 1px solid {tokens['border']};
        border-radius: 6px;
        padding: 6px 12px;
        font-weight: 500;
    }}
    QPushButton:hover {{
        background-color: {tokens['bg_card']};
        border: 1px solid {tokens['border_focus']};
    }}
    QPushButton:pressed {{
        background-color: {tokens['bg_surface']};
    }}
    
    QTableWidget, QTableView, QListWidget, QListView {{
        background-color: {tokens['bg_input']};
        color: {tokens['text_primary']};
        border: 1px solid {tokens['border']};
        border-radius: 8px;
        gridline-color: {tokens['border']};
    }}
    QHeaderView::section {{
        background-color: {tokens['bg_surface']};
        color: {tokens['text_muted']};
        padding: 8px;
        border: none;
        border-bottom: 1px solid {tokens['border']};
        border-right: 1px solid {tokens['border']};
    }}
    QTableWidget::item:selected {{
        background-color: {tokens['accent_primary']};
        color: #ffffff;
    }}
    
    /* Scrollbars */
    QScrollBar:vertical {{
        border: none;
        background: {tokens['scrollbar_bg']};
        width: 8px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {tokens['scrollbar_handle']};
        min-height: 20px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {tokens['scrollbar_handle_hover']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        border: none;
        background: none;
    }}

    QScrollBar:horizontal {{
        border: none;
        background: {tokens['scrollbar_bg']};
        height: 8px;
        margin: 0px;
    }}
    QScrollBar::handle:horizontal {{
        background: {tokens['scrollbar_handle']};
        min-width: 20px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {tokens['scrollbar_handle_hover']};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        border: none;
        background: none;
    }}
    
    /* Splitter */
    QSplitter::handle {{
        background-color: transparent;
    }}
    QSplitter::handle:horizontal {{
        width: 2px;
    }}
    QSplitter::handle:horizontal:hover {{
        background-color: {tokens['border_focus']};
    }}
    """
    return qss
