# ui/workflow/node_config_widget.py
"""Compact config form rendered inside each workflow node."""

from __future__ import annotations

import os
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Theme constants (dark mode)
# ---------------------------------------------------------------------------
_BG_INPUT = "#1b2028"
_BORDER = "#2a3140"
_TEXT = "#e2e8f0"
_TEXT_MUTED = "#8b949e"
_ACCENT = "#3b82f6"

_BASE_INPUT_STYLE = f"""
    background-color: {_BG_INPUT};
    border: 1px solid {_BORDER};
    border-radius: 4px;
    color: {_TEXT};
    padding: 3px 6px;
    font-size: 11px;
"""

_TEXTAREA_STYLE = f"""
    QTextEdit {{
        {_BASE_INPUT_STYLE}
    }}
    QTextEdit:focus {{
        border-color: {_ACCENT};
    }}
"""

_LINEEDIT_STYLE = f"""
    QLineEdit {{
        {_BASE_INPUT_STYLE}
        min-height: 22px;
    }}
    QLineEdit:focus {{
        border-color: {_ACCENT};
    }}
"""

_COMBO_STYLE = f"""
    QComboBox {{
        {_BASE_INPUT_STYLE}
        min-height: 22px;
    }}
    QComboBox:focus {{
        border-color: {_ACCENT};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {_TEXT_MUTED};
        margin-right: 6px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {_BG_INPUT};
        color: {_TEXT};
        border: 1px solid {_BORDER};
        selection-background-color: {_ACCENT};
        selection-color: white;
        font-size: 11px;
    }}
"""

_SPINBOX_STYLE = f"""
    QSpinBox {{
        {_BASE_INPUT_STYLE}
        min-height: 22px;
    }}
    QSpinBox:focus {{
        border-color: {_ACCENT};
    }}
    QSpinBox::up-button, QSpinBox::down-button {{
        background: transparent;
        border: none;
        width: 16px;
    }}
    QSpinBox::up-arrow {{
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-bottom: 4px solid {_TEXT_MUTED};
    }}
    QSpinBox::down-arrow {{
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 4px solid {_TEXT_MUTED};
    }}
"""

_CHECKBOX_STYLE = f"""
    QCheckBox {{
        color: {_TEXT};
        font-size: 11px;
        spacing: 6px;
    }}
    QCheckBox::indicator {{
        width: 14px;
        height: 14px;
        border: 1px solid {_BORDER};
        border-radius: 3px;
        background: {_BG_INPUT};
    }}
    QCheckBox::indicator:checked {{
        background: {_ACCENT};
        border-color: {_ACCENT};
    }}
"""

_UPLOAD_BTN_STYLE = f"""
    QPushButton {{
        background-color: {_BG_INPUT};
        border: 1px dashed {_BORDER};
        border-radius: 4px;
        color: {_TEXT_MUTED};
        padding: 4px 8px;
        font-size: 11px;
    }}
    QPushButton:hover {{
        border-color: {_ACCENT};
        color: {_TEXT};
    }}
"""

_BROWSE_BTN_STYLE = f"""
    QPushButton {{
        background-color: {_BG_INPUT};
        border: 1px solid {_BORDER};
        border-radius: 4px;
        color: {_TEXT};
        padding: 3px 8px;
        font-size: 11px;
        min-width: 28px;
    }}
    QPushButton:hover {{
        border-color: {_ACCENT};
    }}
"""

_LABEL_STYLE = f"color: {_TEXT_MUTED}; font-size: 10px; font-weight: 600;"

_IMAGE_FILTERS = "Ảnh (*.png *.jpg *.jpeg *.bmp *.webp);;Tất cả (*)"
_VIDEO_FILTERS = "Video (*.mp4 *.avi *.mov *.mkv *.webm);;Tất cả (*)"

_THUMB_SIZE = 36


# ---------------------------------------------------------------------------
# Helper: thumbnail strip widget
# ---------------------------------------------------------------------------

class _ThumbnailStrip(QWidget):
    """Horizontal strip showing small thumbnails of selected files."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 2, 0, 0)
        self._layout.setSpacing(3)
        self._layout.addStretch()

    def set_files(self, paths: list[str]) -> None:
        # Clear existing thumbnails
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for p in paths[:8]:  # cap at 8 visible
            lbl = QLabel()
            lbl.setFixedSize(_THUMB_SIZE, _THUMB_SIZE)
            lbl.setStyleSheet(
                f"background: {_BG_INPUT}; border: 1px solid {_BORDER}; border-radius: 3px;"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            if p.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp")):
                pix = QPixmap(p)
                if not pix.isNull():
                    lbl.setPixmap(
                        pix.scaled(
                            _THUMB_SIZE - 4,
                            _THUMB_SIZE - 4,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                else:
                    lbl.setText("🖼")
            else:
                lbl.setText("🎞")
                lbl.setStyleSheet(
                    lbl.styleSheet() + f" color: {_TEXT_MUTED}; font-size: 16px;"
                )

            self._layout.insertWidget(self._layout.count() - 1, lbl)

        if len(paths) > 8:
            more = QLabel(f"+{len(paths) - 8}")
            more.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: 10px;")
            self._layout.insertWidget(self._layout.count() - 1, more)


# ---------------------------------------------------------------------------
# NodeConfigWidget
# ---------------------------------------------------------------------------

class NodeConfigWidget(QWidget):
    """Renders the configuration form for a single node type.

    Parameters
    ----------
    node_type_def : dict
        The node-type definition from *node_registry.NODE_TYPES*.
    parent : QWidget | None
        Optional parent widget.
    """

    config_changed = Signal()

    def __init__(self, node_type_def: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fields: dict[str, Any] = {}  # name → widget
        self._strips: dict[str, _ThumbnailStrip] = {}  # name → strip (for uploads)
        self._file_paths: dict[str, list[str]] = {}  # name → [paths]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        config_fields: list[dict] = node_type_def.get("config_fields", [])
        for fdef in config_fields:
            self._build_field(fdef, layout)

    # ------------------------------------------------------------------
    # Field builders
    # ------------------------------------------------------------------

    def _build_field(self, fdef: dict, parent_layout: QVBoxLayout) -> None:
        ftype = fdef.get("type", "")
        name = fdef["name"]
        label_text = fdef.get("label", name)
        default = fdef.get("default")

        # Label (skip for checkbox – it has inline label)
        if ftype != "checkbox":
            lbl = QLabel(label_text)
            lbl.setStyleSheet(_LABEL_STYLE)
            parent_layout.addWidget(lbl)

        if ftype == "textarea":
            w = QTextEdit()
            w.setPlaceholderText(label_text)
            w.setFixedHeight(52)
            w.setStyleSheet(_TEXTAREA_STYLE)
            w.setAcceptRichText(False)
            if default:
                w.setPlainText(str(default))
            w.textChanged.connect(self._emit_changed)
            self._fields[name] = w
            parent_layout.addWidget(w)

        elif ftype == "combo":
            w = QComboBox()
            w.setStyleSheet(_COMBO_STYLE)
            options = fdef.get("options", [])
            if options:
                w.addItems([str(o) for o in options])
            if default and str(default) in [str(o) for o in options]:
                w.setCurrentText(str(default))
            w.currentTextChanged.connect(lambda _: self._emit_changed())
            self._fields[name] = w
            parent_layout.addWidget(w)

        elif ftype == "number":
            w = QSpinBox()
            w.setStyleSheet(_SPINBOX_STYLE)
            w.setRange(-999999, 999999)
            if default is not None:
                w.setValue(int(default))
            w.valueChanged.connect(lambda _: self._emit_changed())
            self._fields[name] = w
            parent_layout.addWidget(w)

        elif ftype == "checkbox":
            w = QCheckBox(label_text)
            w.setStyleSheet(_CHECKBOX_STYLE)
            if default is not None:
                w.setChecked(bool(default))
            w.stateChanged.connect(lambda _: self._emit_changed())
            self._fields[name] = w
            parent_layout.addWidget(w)

        elif ftype in ("image_upload", "video_upload"):
            is_image = ftype == "image_upload"
            btn = QPushButton(f"＋ {'Chọn ảnh' if is_image else 'Chọn video'}…")
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet(_UPLOAD_BTN_STYLE)
            self._file_paths[name] = list(default) if isinstance(default, list) else []

            strip = _ThumbnailStrip()
            self._strips[name] = strip

            if is_image:
                btn.clicked.connect(lambda _c=False, n=name: self._pick_files(n, _IMAGE_FILTERS))
            else:
                btn.clicked.connect(lambda _c=False, n=name: self._pick_files(n, _VIDEO_FILTERS))

            self._fields[name] = btn  # store btn as placeholder
            parent_layout.addWidget(btn)
            parent_layout.addWidget(strip)

        elif ftype == "folder":
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            le = QLineEdit()
            le.setReadOnly(True)
            le.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            le.mousePressEvent = lambda ev, _le=le: self._pick_folder(_le)
            le.setStyleSheet(_LINEEDIT_STYLE)
            le.setPlaceholderText("Chọn thư mục…")
            if default:
                le.setText(str(default))
            le.textChanged.connect(lambda _: self._emit_changed())

            browse_btn = QPushButton("…")
            browse_btn.setFixedWidth(32)
            browse_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            browse_btn.setStyleSheet(_BROWSE_BTN_STYLE)
            browse_btn.clicked.connect(lambda _c=False, _le=le: self._pick_folder(_le))

            row.addWidget(le, 1)
            row.addWidget(browse_btn)
            self._fields[name] = le
            parent_layout.addLayout(row)

    # ------------------------------------------------------------------
    # File / folder pickers
    # ------------------------------------------------------------------

    def _pick_files(self, field_name: str, file_filter: str) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Chọn tệp", "", file_filter)
        if paths:
            existing = self._file_paths.get(field_name, [])
            existing.extend(paths)
            self._file_paths[field_name] = existing
            strip = self._strips.get(field_name)
            if strip:
                strip.set_files(existing)
            self._emit_changed()

    def _pick_folder(self, line_edit: QLineEdit) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục")
        if folder:
            line_edit.setText(folder)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_config(self) -> dict[str, Any]:
        """Return a dict of *field_name → value* for all config fields."""
        result: dict[str, Any] = {}
        for name, widget in self._fields.items():
            if isinstance(widget, QTextEdit):
                result[name] = widget.toPlainText()
            elif isinstance(widget, QComboBox):
                result[name] = widget.currentText()
            elif isinstance(widget, QSpinBox):
                result[name] = widget.value()
            elif isinstance(widget, QCheckBox):
                result[name] = widget.isChecked()
            elif isinstance(widget, QLineEdit):
                result[name] = widget.text()
            elif name in self._file_paths:
                result[name] = list(self._file_paths[name])
            else:
                result[name] = None
        return result

    def set_config(self, config: dict[str, Any]) -> None:
        """Populate fields from *config* dict. Unknown keys are ignored."""
        for name, value in config.items():
            widget = self._fields.get(name)
            if widget is None:
                continue

            if isinstance(widget, QTextEdit):
                widget.setPlainText(str(value) if value else "")
            elif isinstance(widget, QComboBox):
                idx = widget.findText(str(value))
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            elif isinstance(widget, QSpinBox):
                try:
                    widget.setValue(int(value))
                except (ValueError, TypeError):
                    pass
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QLineEdit):
                widget.setText(str(value) if value else "")
            elif name in self._file_paths and isinstance(value, list):
                self._file_paths[name] = list(value)
                strip = self._strips.get(name)
                if strip:
                    strip.set_files(value)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _emit_changed(self) -> None:
        self.config_changed.emit()
