# ui/workflow/node_palette.py
"""Left-hand panel listing available node types for drag-and-drop onto the canvas."""

from __future__ import annotations

from PySide6.QtCore import QMimeData, Qt, QPoint
from PySide6.QtGui import QCursor, QDrag, QFont, QPixmap, QPainter, QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QFrame,
)

from ui.workflow.node_registry import NODE_TYPES, get_all_categories

# ---------------------------------------------------------------------------
# Theme constants
# ---------------------------------------------------------------------------
_BG_SURFACE = "#16191f"
_BG_CARD = "#1b2028"
_BG_INPUT = "#1b2028"
_BORDER = "#2a3140"
_TEXT = "#e2e8f0"
_TEXT_MUTED = "#8b949e"
_ACCENT = "#3b82f6"

_SEARCH_STYLE = f"""
    QLineEdit {{
        background-color: {_BG_INPUT};
        border: 1px solid {_BORDER};
        border-radius: 6px;
        color: {_TEXT};
        padding: 6px 10px 6px 28px;
        font-size: 12px;
    }}
    QLineEdit:focus {{
        border-color: {_ACCENT};
    }}
"""


# ---------------------------------------------------------------------------
# Draggable node card
# ---------------------------------------------------------------------------

class _NodeCard(QFrame):
    """A single draggable card representing a node type."""

    def __init__(self, node_key: str, node_def: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._node_key = node_key
        self._node_def = node_def
        self._color = node_def.get("color", _ACCENT)
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        self.setFixedHeight(36)
        self.setToolTip(f"{node_def.get('title', node_key)} – kéo thả vào canvas")

        self.setStyleSheet(f"""
            _NodeCard {{
                background: {_BG_CARD};
                border: 1px solid {_BORDER};
                border-radius: 6px;
            }}
            _NodeCard:hover {{
                background: {_BG_INPUT};
                border: 1px solid {_TEXT_MUTED};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)

        icon_label = QLabel(node_def.get("icon", "◆"))
        icon_label.setFixedWidth(20)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"font-family: 'Segoe Fluent Icons'; font-size: 14px; background: transparent; border: none; color: {_TEXT};")
        layout.addWidget(icon_label)

        title_label = QLabel(node_def.get("title", node_key))
        title_label.setStyleSheet(
            f"font-size: 12px; font-weight: 500; color: {_TEXT}; background: transparent; border: none;"
        )
        layout.addWidget(title_label, 1)

    # ------------------------------------------------------------------
    # Drag support
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
        super().mousePressEvent(event)
        
    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._node_key == "history":
            # Open history dialog directly
            main_win = None
            from PySide6.QtWidgets import QApplication
            for w in QApplication.topLevelWidgets():
                if hasattr(w, "db"):
                    main_win = w
                    break
            from ui.workflow.history_picker_dialog import HistoryPickerDialog
            dlg = HistoryPickerDialog(main_win, media_type="all", parent=None)
            dlg.exec()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._node_key == "history":
            return
            
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if not hasattr(self, "_drag_start"):
            return
        if (event.position().toPoint() - self._drag_start).manhattanLength() < 10:
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(self._node_key)
        mime.setData("application/x-workflow-node-type", self._node_key.encode("utf-8"))
        drag.setMimeData(mime)

        # Create a small drag pixmap
        pix = QPixmap(140, 32)
        pix.fill(QColor(self._color))
        painter = QPainter(pix)
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter,
                         f"{self._node_def.get('icon', '')} {self._node_def.get('title', '')}")
        painter.end()
        drag.setPixmap(pix)
        drag.setHotSpot(QPoint(70, 16))

        self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))


# ---------------------------------------------------------------------------
# Category group
# ---------------------------------------------------------------------------

class _CategoryGroup(QWidget):
    """Collapsible group header + list of node cards."""

    def __init__(self, category: str, node_keys: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._category = category
        self._cards: list[_NodeCard] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(3)

        header = QLabel(category.upper())
        header.setStyleSheet(
            f"color: {_TEXT_MUTED}; font-size: 10px; font-weight: bold; "
            f"padding: 6px 4px 2px 4px; background: transparent;"
        )
        layout.addWidget(header)

        for key in node_keys:
            node_def = NODE_TYPES.get(key)
            if node_def is None:
                continue
            card = _NodeCard(key, node_def)
            self._cards.append(card)
            layout.addWidget(card)

    def filter(self, query: str) -> int:
        """Hide cards not matching *query*. Returns the count of visible cards."""
        q = query.lower().strip()
        visible = 0
        for card in self._cards:
            title = card._node_def.get("title", "").lower()
            match = not q or q in title or q in card._node_key
            card.setVisible(match)
            if match:
                visible += 1
        self.setVisible(visible > 0)
        return visible


# ---------------------------------------------------------------------------
# NodePalette
# ---------------------------------------------------------------------------

class NodePalette(QWidget):
    """Left panel showing all available node types grouped by category.

    Width: 220 px, collapsible via ``setVisible(False)``.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(220)
        self.setStyleSheet(f"""
            NodePalette {{
                background: {_BG_SURFACE};
                border-right: 1px solid {_BORDER};
            }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        # ── Header ──
        title = QLabel("📦 Nodes")
        title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {_TEXT};")
        outer.addWidget(title)

        # ── Search bar ──
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Tìm node…")
        self._search.setStyleSheet(_SEARCH_STYLE)
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_search)
        outer.addWidget(self._search)

        # ── Scrollable node list ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: {_BORDER};
                border-radius: 3px;
                min-height: 24px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        self._scroll_layout = QVBoxLayout(scroll_content)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(2)

        self._groups: list[_CategoryGroup] = []
        categories = get_all_categories()
        for cat_name, node_keys in categories.items():
            group = _CategoryGroup(cat_name, node_keys)
            self._groups.append(group)
            self._scroll_layout.addWidget(group)

        self._scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        outer.addWidget(scroll, 1)

    # ------------------------------------------------------------------
    # Search filter
    # ------------------------------------------------------------------

    def _on_search(self, text: str) -> None:
        for group in self._groups:
            group.filter(text)
