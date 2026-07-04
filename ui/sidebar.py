# ui/sidebar.py
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QCursor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QScrollArea, QHBoxLayout

from ui.themes.tokens import THEME_TOKENS
from ui.widgets.nav_button import NavButton

class SidebarItem(QPushButton):
    def __init__(self, key: str, label: str, icon: str = "◆", badge: str = "", parent=None):
        super().__init__(parent)
        self.key = key
        self.setText(f" {icon}  {label}")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(36)
        self.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding-left: 12px;
                border: none;
                border-radius: 6px;
                background: transparent;
                font-size: 13px;
                font-weight: 500;
            }
        """)
        self.setCheckable(True)

class SidebarGroup(QWidget):
    def __init__(self, title: str, items: list[tuple[str, str, str]], sidebar: 'Sidebar', parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(2)
        
        lbl = QLabel(title)
        lbl.setProperty("class", "sidebar-group-title")
        lbl.setStyleSheet("font-size: 11px; font-weight: bold; padding-left: 12px;")
        layout.addWidget(lbl)
        
        for key, label, icon in items:
            btn = SidebarItem(key, label, icon)
            btn.clicked.connect(lambda checked, k=key: sidebar._on_item_clicked(k))
            sidebar.btn_group.append(btn)
            layout.addWidget(btn)

class Sidebar(QWidget):
    page_changed = Signal(str)
    open_palette = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(240)
        self.setObjectName("sidebar")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 20, 12, 20)
        main_layout.setSpacing(8)

        # Brand
        brand_label = QLabel("AURA STUDIO")
        brand_label.setProperty("class", "sidebar-brand")
        brand_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        brand_label.setStyleSheet("letter-spacing: 2px;")
        main_layout.addWidget(brand_label)
        
        main_layout.addSpacing(16)



        self.btn_group = []

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)

        # CREATE
        scroll_layout.addWidget(SidebarGroup("🎨 CREATE", [
            ("image", "Tạo ảnh Flow", "🖼️"),
            ("video", "Tạo video Flow", "📹"),
            ("char_video", "Video to Video", "🎬"),
            ("long_video", "Nối khung hình", "🔗"),
            ("grok_image", "Tạo ảnh Grok", "🤖"),
            ("grok_video", "Tạo video Grok", "🛸"),
        ], self))

        # EDIT
        scroll_layout.addWidget(SidebarGroup("🪄 EDIT", [
            ("watermark", "Xóa logo", "💧"),
        ], self))

        # WORKFLOW
        scroll_layout.addWidget(SidebarGroup("🔀 WORKFLOW", [
            ("workflow_studio", "Workflow Studio", "🔀"),
            ("history", "Lịch sử tạo", "🕒"),
        ], self))

        # SYSTEM
        scroll_layout.addWidget(SidebarGroup("⚙ SYSTEM", [
            ("settings", "Cài đặt hệ thống", "⚙️"),
        ], self))

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    def _on_item_clicked(self, key):
        for btn in self.btn_group:
            btn.setChecked(btn.key == key)
        self.page_changed.emit(key)
        
    def update_theme(self, theme: str):
        tokens = THEME_TOKENS.get(theme, THEME_TOKENS["dark"])
        self.setStyleSheet(f"""
            QWidget#sidebar {{
                background-color: {tokens['bg_surface']};
                border-right: 1px solid {tokens['border']};
            }}
            QLabel {{
                color: {tokens['text_primary']};
            }}
            QLabel.sidebar-group-title {{
                color: {tokens['text_muted']};
            }}
            QLabel.sidebar-brand {{
                color: {tokens['text_primary']};
            }}
            QPushButton {{
                color: {tokens['text_primary']};
            }}
            QPushButton:hover {{
                background-color: {tokens['bg_input']};
            }}
            QPushButton:checked {{
                background-color: {tokens['bg_app']};
                color: {tokens['accent']};
            }}
        """)
