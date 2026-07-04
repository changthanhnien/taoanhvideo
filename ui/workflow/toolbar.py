# ui/workflow/toolbar.py
"""Top toolbar for the Workflow Studio page."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

# ---------------------------------------------------------------------------
# Theme constants
# ---------------------------------------------------------------------------
_BG_SURFACE = "#16191f"
_BG_INPUT = "#1b2028"
_BORDER = "#2a3140"
_TEXT = "#e2e8f0"
_TEXT_MUTED = "#8b949e"
_ACCENT = "#3b82f6"
_ACCENT_HOVER = "#60a5fa"
_SUCCESS = "#10b981"
_DANGER = "#ef4444"
_WARNING = "#f59e0b"


def _icon_btn(text: str, tooltip: str, color: str = _TEXT, bg: str = "transparent",
              bg_hover: str = _BG_INPUT, min_w: int = 36) -> QPushButton:
    """Create a small toolbar icon button."""
    btn = QPushButton(text)
    btn.setToolTip(tooltip)
    btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    btn.setFixedHeight(32)
    btn.setMinimumWidth(min_w)
    btn.setStyleSheet(f"""
        QPushButton {{
            background: {bg};
            color: {color};
            border: 1px solid transparent;
            border-radius: 6px;
            font-family: "Segoe Fluent Icons";
            font-size: 14px;
            padding: 0 8px;
        }}
        QPushButton:hover {{
            background: {bg_hover};
            border-color: {_BORDER};
        }}
        QPushButton:pressed {{
            opacity: 0.8;
        }}
        QPushButton:disabled {{
            background: {_BG_INPUT};
            color: {_TEXT_MUTED};
        }}
    """)
    return btn


def _action_btn(text: str, tooltip: str, bg: str, bg_hover: str, min_w: int = 72) -> QPushButton:
    """Create a coloured action button."""
    btn = QPushButton(text)
    btn.setToolTip(tooltip)
    btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    btn.setFixedHeight(32)
    btn.setMinimumWidth(min_w)
    btn.setStyleSheet(f"""
        QPushButton {{
            background: {bg};
            color: #ffffff;
            border: none;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            padding: 0 12px;
        }}
        QPushButton:hover {{
            background: {bg_hover};
        }}
        QPushButton:pressed {{
            opacity: 0.85;
        }}
        QPushButton:disabled {{
            background: {_BG_INPUT};
            color: {_TEXT_MUTED};
        }}
    """)
    return btn


# ---------------------------------------------------------------------------
# WorkflowToolbar
# ---------------------------------------------------------------------------

class WorkflowToolbar(QWidget):
    """Horizontal toolbar at the top of the Workflow Studio page.

    Signals
    -------
    run_all()           – user clicked ▶ Run All
    pause()             – user clicked ⏸ Pause
    stop()              – user clicked ⏹ Stop
    save()              – user clicked Save (or Ctrl+S)
    import_wf()         – user clicked Import
    export_wf()         – user clicked Export
    auto_arrange()      – user clicked ⟳ Auto Arrange
    name_changed(str)   – workflow name was edited
    favorite_toggled(bool) – star toggled
    """

    run_all = Signal()
    pause = Signal()
    stop = Signal()
    save = Signal()
    import_wf = Signal()
    export_wf = Signal()
    auto_arrange = Signal()
    name_changed = Signal(str)
    favorite_toggled = Signal(bool)
    zoom_in = Signal()
    zoom_out = Signal()
    fit_view = Signal()
    center_view = Signal()
    lock_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet(f"""
            WorkflowToolbar {{
                background: {_BG_SURFACE};
                border: 1px solid {_BORDER};
                border-radius: 8px;
            }}
        """)

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 0, 12, 0)
        root.setSpacing(8)

        # ── LEFT: workflow name + star ──────────────────────────────
        self._name_edit = QLineEdit("Untitled Workflow")
        self._name_edit.setFixedHeight(30)
        self._name_edit.setMinimumWidth(160)
        self._name_edit.setMaximumWidth(280)
        self._name_edit.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        self._name_edit.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                color: {_TEXT};
                padding: 0 6px;
            }}
            QLineEdit:hover {{
                border-color: {_BORDER};
            }}
            QLineEdit:focus {{
                background: {_BG_INPUT};
                border-color: {_ACCENT};
            }}
        """)
        self._name_edit.editingFinished.connect(
            lambda: self.name_changed.emit(self._name_edit.text().strip() or "Untitled Workflow")
        )

        self._is_favorite = False
        self._star_btn = _icon_btn("\uE734", "Yêu thích", min_w=32)
        self._star_btn.clicked.connect(self._toggle_favorite)

        # ── Add items to layout to center them ────────────────────
        root.addStretch()  # Left stretch
        root.addWidget(self._name_edit)
        root.addWidget(self._star_btn)
        
        # separator
        sep = QWidget()
        sep.setFixedSize(1, 16)
        sep.setStyleSheet(f"background: {_BORDER};")
        root.addWidget(sep)
        
        self._run_btn = _action_btn("▶  Chạy", "Chạy toàn bộ workflow", _SUCCESS, "#0ea472")
        self._run_btn.clicked.connect(self.run_all.emit)
        root.addWidget(self._run_btn)

        self._stop_btn = _icon_btn("\uE71A", "Dừng", _DANGER)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop_clicked)
        self._is_running = False
        root.addWidget(self._stop_btn)

        # delay
        self._btn_delay = QLabel("\uE916 Delay")
        self._btn_delay.setStyleSheet(f"font-family: 'Segoe Fluent Icons', 'Segoe UI'; color: {_TEXT_MUTED}; font-size: 12px;")
        root.addWidget(self._btn_delay)

        self._delay_spin = QSpinBox()
        self._delay_spin.setRange(0, 300)
        self._delay_spin.setValue(0)
        self._delay_spin.setSuffix("s")
        self._delay_spin.setFixedHeight(28)
        self._delay_spin.setFixedWidth(70)
        self._delay_spin.setStyleSheet(f"""
            QSpinBox {{
                background: {_BG_INPUT};
                border: 1px solid {_BORDER};
                border-radius: 4px;
                color: {_TEXT};
                font-size: 11px;
                padding: 0 4px;
            }}
            QSpinBox:focus {{ border-color: {_ACCENT}; }}
        """)
        root.addWidget(self._delay_spin)

        root.addStretch()  # Right stretch

        # ── RIGHT: save / import / export / zoom ────────────────────
        self._save_btn = _icon_btn("\uE74E", "Lưu (Ctrl+S)")
        self._save_btn.clicked.connect(self.save.emit)
        root.addWidget(self._save_btn)

        self._import_btn = _icon_btn("\uE8B5", "Nhập workflow")
        self._import_btn.clicked.connect(self.import_wf.emit)
        root.addWidget(self._import_btn)

        self._export_btn = _icon_btn("\uE896", "Xuất workflow")
        self._export_btn.clicked.connect(self.export_wf.emit)
        root.addWidget(self._export_btn)

        self._zoom_label = QLabel("100%")
        self._zoom_label.setStyleSheet(
            f"color: {_TEXT_MUTED}; font-size: 11px; padding: 0 6px;"
        )
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zoom_label.setFixedWidth(48)
        root.addWidget(self._zoom_label)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def set_workflow_name(self, name: str) -> None:
        self._name_edit.setText(name)

    def set_favorite(self, is_fav: bool) -> None:
        self._is_favorite = is_fav
        self._star_btn.setText("★" if is_fav else "☆")
        self._star_btn.setStyleSheet(
            self._star_btn.styleSheet()  # keep base style
        )

    def set_zoom_level(self, percent: int) -> None:
        self._zoom_label.setText(f"{percent}%")

    def set_running(self, running: bool) -> None:
        """Toggle button states when workflow is running."""
        self._is_running = running
        self._run_btn.setEnabled(not running)
        self._stop_btn.setEnabled(running)
        if running:
            self._run_btn.setText("⏳ Đang chạy...")
            self._run_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {_SUCCESS};
                    color: #ffffff;
                    border: none;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 600;
                    padding: 0 12px;
                }}
            """)
            self._stop_btn.setText("⏹")
            self._stop_btn.setToolTip("Dừng")
            self._stop_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {_DANGER};
                    border: 1px solid transparent; border-radius: 6px;
                    font-size: 14px; min-width: 32px;
                }}
                QPushButton:hover {{ background: {_DANGER}; color: white; }}
            """)
        else:
            self._run_btn.setText("▶  Chạy")
            self._run_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {_SUCCESS};
                    color: #ffffff;
                    border: none;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 600;
                    padding: 0 12px;
                }}
                QPushButton:hover {{
                    background: #0ea472;
                }}
                QPushButton:disabled {{
                    background: {_BG_INPUT};
                    color: {_TEXT_MUTED};
                }}
            """)
            self._stop_btn.setText("⏹")
            self._stop_btn.setToolTip("Dừng")
            self._stop_btn.setEnabled(False)
        
        self.setFocus()

    def _on_stop_clicked(self):
        """Stop button clicked - emit stop signal."""
        self.stop.emit()
        self.set_running(False)


    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _toggle_favorite(self) -> None:
        self._is_favorite = not self._is_favorite
        self._star_btn.setText("★" if self._is_favorite else "☆")
        self.favorite_toggled.emit(self._is_favorite)

    def get_delay_seconds(self) -> int:
        return self._delay_spin.value()
