# ui/workflow/node_graphics.py
from __future__ import annotations

import math
import uuid
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QPointF,
    QRectF,
    Qt,
    QTimer,
    Signal,
    QObject,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsPathItem,
    QGraphicsSceneHoverEvent,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QGraphicsScene

# ---------------------------------------------------------------------------
# Theme colours (hard-coded tokens to stay self-contained)
# ---------------------------------------------------------------------------
_C_BG_CARD = QColor("#1b2028")
_C_BORDER = QColor("#2a3140")
_C_TEXT = QColor("#e2e8f0")
_C_TEXT_MUTED = QColor("#8b949e")
_C_ACCENT = QColor("#3b82f6")
_C_ACCENT_HOVER = QColor("#60a5fa")
_C_SUCCESS = QColor("#10b981")
_C_DANGER = QColor("#ef4444")
_C_WARNING = QColor("#f59e0b")
_C_BG_APP = QColor("#0f1115")
_C_BG_SURFACE = QColor("#16191f")

_STATE_COLORS: dict[str, QColor] = {
    "idle": _C_BORDER,
    "running": _C_ACCENT,
    "success": _C_SUCCESS,
    "error": _C_DANGER,
    "waiting": _C_WARNING,
}

_NODE_TYPE_HEADER_COLORS: dict[str, QColor] = {
    "default": _C_ACCENT,
    "input": QColor("#8b5cf6"),
    "output": QColor("#06b6d4"),
    "process": QColor("#f97316"),
    "condition": QColor("#eab308"),
    "merge": QColor("#ec4899"),
}

GRID_SIZE = 20

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _snap(value: float, grid: int = GRID_SIZE) -> float:
    return round(value / grid) * grid


def _make_font(size: int = 11, bold: bool = False) -> QFont:
    f = QFont("Segoe UI", size)
    if bold:
        f.setBold(True)
    return f


# ===================================================================
# PortGraphicsItem
# ===================================================================

class PortSignals(QObject):
    """Signals emitted by a port (QGraphicsEllipseItem can't emit directly)."""
    connection_started = Signal(object)   # PortGraphicsItem
    connection_finished = Signal(object)  # PortGraphicsItem


class PortGraphicsItem(QGraphicsEllipseItem):
    """Small circle representing an input or output port on a node."""

    RADIUS = 4.0  # 8 px diameter

    def __init__(
        self,
        port_id: str,
        port_kind: str,  # "input" | "output"
        parent_node: NodeGraphicsItem,
        index: int = 0,
    ) -> None:
        diameter = self.RADIUS * 2
        super().__init__(-self.RADIUS, -self.RADIUS, diameter, diameter, parent_node)
        self.port_id = port_id
        self.port_kind = port_kind
        self.parent_node = parent_node
        self.index = index
        self._connected = False
        self._hovered = False

        self.signals = PortSignals()

        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._apply_style()

    # -- visual --------------------------------------------------------
    def _apply_style(self) -> None:
        if self._hovered:
            color = _C_ACCENT
        elif self._connected:
            color = _C_SUCCESS
        else:
            color = _C_TEXT_MUTED
        self.setBrush(QBrush(color))
        pen = QPen(color.darker(130), 1.5)
        self.setPen(pen)

    def set_connected(self, connected: bool) -> None:
        self._connected = connected
        self._apply_style()

    # -- events --------------------------------------------------------
    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None:  # noqa: N802
        self._hovered = True
        self._apply_style()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:  # noqa: N802
        self._hovered = False
        self._apply_style()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.signals.connection_started.emit(self)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.signals.connection_finished.emit(self)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    # -- helpers -------------------------------------------------------
    def center_scene_pos(self) -> QPointF:
        """Return the centre of this port in scene coordinates."""
        return self.mapToScene(self.boundingRect().center())


# ===================================================================
# _ActionButton  (tiny hit-area inside the node body)
# ===================================================================

class _ActionButton:
    """Lightweight data struct – painting is handled by NodeGraphicsItem."""

    def __init__(self, symbol: str, color: QColor, tooltip: str) -> None:
        self.symbol = symbol
        self.color = color
        self.tooltip = tooltip
        self.rect = QRectF()       # set during layout
        self.hovered = False


# ===================================================================
# NodeGraphicsItem
# ===================================================================

class NodeSignals(QObject):
    """Qt signals for node events."""
    position_changed = Signal(str, float, float)   # node_id, x, y
    size_changed = Signal(str, float, float)        # node_id, w, h
    delete_requested = Signal(str)                  # node_id
    clone_requested = Signal(str)                   # node_id
    run_requested = Signal(str)                     # node_id


class NodeGraphicsItem(QGraphicsItem):
    """Visual representation of a single workflow node."""

    HEADER_H = 24.0
    CORNER_R = 8.0
    MIN_W = 200.0
    MIN_H = 120.0
    RESIZE_HANDLE = 12.0

    def __init__(
        self,
        node_id: str,
        node_type: str = "default",
        title: str = "Node",
        x: float = 0.0,
        y: float = 0.0,
        width: float = 280.0,
        height: float = 160.0,
        state: str = "idle",
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self.node_id = node_id
        self.node_type = node_type
        self.title = title
        self._width = max(width, self.MIN_W)
        self._height = max(height, self.MIN_H)
        self.state = state

        self.signals = NodeSignals()

        # Interaction flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setPos(x, y)
        self.setZValue(1)

        # Shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 90))
        self.setGraphicsEffect(shadow)

        # Ports
        self.input_ports: list[PortGraphicsItem] = []
        self.output_ports: list[PortGraphicsItem] = []

        # Action buttons (logical only, painted manually)
        self._btn_run = _ActionButton("▶", _C_SUCCESS, "Chạy node")
        self._btn_clone = _ActionButton("⧉", _C_ACCENT, "Nhân bản")
        self._btn_delete = _ActionButton("✕", _C_DANGER, "Xoá")
        self._action_buttons = [self._btn_run, self._btn_clone, self._btn_delete]

        # Resize state
        self._resizing = False
        self._resize_origin = QPointF()

        # Running animation
        self._pulse_opacity = 1.0
        self._pulse_dir = -1
        self._pulse_timer: QTimer | None = None

    # -- ports ---------------------------------------------------------
    def add_input_port(self, port_id: str) -> PortGraphicsItem:
        port = PortGraphicsItem(port_id, "input", self, index=len(self.input_ports))
        self.input_ports.append(port)
        self._layout_ports()
        return port

    def add_output_port(self, port_id: str) -> PortGraphicsItem:
        port = PortGraphicsItem(port_id, "output", self, index=len(self.output_ports))
        self.output_ports.append(port)
        self._layout_ports()
        return port

    def _layout_ports(self) -> None:
        body_top = self.HEADER_H + 4
        body_h = self._height - self.HEADER_H - 30  # leave room for action row
        for i, p in enumerate(self.input_ports):
            count = len(self.input_ports)
            spacing = body_h / (count + 1)
            p.setPos(0, body_top + spacing * (i + 1))
        for i, p in enumerate(self.output_ports):
            count = len(self.output_ports)
            spacing = body_h / (count + 1)
            p.setPos(self._width, body_top + spacing * (i + 1))

    # -- state animation -----------------------------------------------
    def set_state(self, state: str) -> None:
        self.state = state
        if state == "running":
            self._start_pulse()
        else:
            self._stop_pulse()
        self.update()

    def _start_pulse(self) -> None:
        if self._pulse_timer is not None:
            return
        self._pulse_timer = QTimer()
        self._pulse_timer.setInterval(50)
        self._pulse_timer.timeout.connect(self._tick_pulse)
        self._pulse_timer.start()

    def _stop_pulse(self) -> None:
        if self._pulse_timer is not None:
            self._pulse_timer.stop()
            self._pulse_timer = None
            self._pulse_opacity = 1.0

    def _tick_pulse(self) -> None:
        self._pulse_opacity += self._pulse_dir * 0.04
        if self._pulse_opacity <= 0.3:
            self._pulse_dir = 1
        elif self._pulse_opacity >= 1.0:
            self._pulse_dir = -1
        self.update()

    # -- QGraphicsItem interface ----------------------------------------
    def boundingRect(self) -> QRectF:  # noqa: N802
        m = 4  # margin for shadow / glow
        return QRectF(-m, -m, self._width + 2 * m, self._height + 2 * m)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRoundedRect(0, 0, self._width, self._height, self.CORNER_R, self.CORNER_R)
        return path

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w, h = self._width, self._height
        r = self.CORNER_R

        # --- state colour stripe (left 4 px) ---
        state_color = QColor(_STATE_COLORS.get(self.state, _C_BORDER))
        if self.state == "running":
            state_color.setAlphaF(self._pulse_opacity)
        stripe_path = QPainterPath()
        stripe_path.addRoundedRect(0, 0, 6, h, r, r)
        clip = QPainterPath()
        clip.addRect(0, 0, 6, h)
        stripe_path = stripe_path.intersected(clip)
        painter.fillPath(stripe_path, QBrush(state_color))

        # --- body ---
        body = QPainterPath()
        body.addRoundedRect(0, 0, w, h, r, r)
        painter.fillPath(body, QBrush(_C_BG_CARD))

        # border
        if self.isSelected():
            pen = QPen(_C_ACCENT, 2)
        else:
            pen = QPen(_C_BORDER, 1)
        painter.setPen(pen)
        painter.drawPath(body)

        # --- header bar ---
        header_color = _NODE_TYPE_HEADER_COLORS.get(self.node_type, _C_ACCENT)
        header_path = QPainterPath()
        header_path.addRoundedRect(0, 0, w, self.HEADER_H + r, r, r)
        clip_rect = QPainterPath()
        clip_rect.addRect(0, 0, w, self.HEADER_H)
        header_path = header_path.intersected(clip_rect)
        painter.fillPath(header_path, QBrush(header_color))

        # header title
        painter.setPen(QPen(QColor("#ffffff")))
        painter.setFont(_make_font(10, bold=True))
        title_rect = QRectF(10, 0, w - 20, self.HEADER_H)
        elided = painter.fontMetrics().elidedText(self.title, Qt.TextElideMode.ElideRight, int(w - 20))
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)

        # --- action buttons row ---
        self._paint_action_row(painter, w, h)

        # --- selection glow ---
        if self.isSelected():
            glow_pen = QPen(_C_ACCENT, 2, Qt.PenStyle.SolidLine)
            glow_pen.setCosmetic(True)
            painter.setPen(glow_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(-1, -1, w + 2, h + 2), r + 1, r + 1)

        # --- resize handle ---
        self._paint_resize_handle(painter, w, h)

    def _paint_action_row(self, painter: QPainter, w: float, h: float) -> None:
        btn_size = 20.0
        spacing = 6.0
        total_w = len(self._action_buttons) * btn_size + (len(self._action_buttons) - 1) * spacing
        start_x = (w - total_w) / 2.0
        y = h - btn_size - 6

        for i, btn in enumerate(self._action_buttons):
            bx = start_x + i * (btn_size + spacing)
            btn.rect = QRectF(bx, y, btn_size, btn_size)

            bg = QColor(btn.color)
            if btn.hovered:
                bg = bg.lighter(130)
            bg.setAlpha(40)
            path = QPainterPath()
            path.addRoundedRect(btn.rect, 4, 4)
            painter.fillPath(path, QBrush(bg))

            painter.setPen(QPen(btn.color if not btn.hovered else btn.color.lighter(140)))
            painter.setFont(_make_font(9))
            painter.drawText(btn.rect, Qt.AlignmentFlag.AlignCenter, btn.symbol)

    def _paint_resize_handle(self, painter: QPainter, w: float, h: float) -> None:
        s = self.RESIZE_HANDLE
        painter.setPen(QPen(_C_TEXT_MUTED, 1))
        for i in range(3):
            offset = s - i * 4
            painter.drawLine(QPointF(w - offset, h - 2), QPointF(w - 2, h - offset))

    # -- events --------------------------------------------------------
    def itemChange(self, change, value):  # noqa: N802
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.signals.position_changed.emit(self.node_id, self.pos().x(), self.pos().y())
        return super().itemChange(change, value)

    def hoverMoveEvent(self, event: QGraphicsSceneHoverEvent) -> None:  # noqa: N802
        pos = event.pos()
        # resize handle cursor
        rh = QRectF(self._width - self.RESIZE_HANDLE, self._height - self.RESIZE_HANDLE,
                     self.RESIZE_HANDLE, self.RESIZE_HANDLE)
        if rh.contains(pos):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        # action button hover
        needs_update = False
        for btn in self._action_buttons:
            old = btn.hovered
            btn.hovered = btn.rect.contains(pos)
            if old != btn.hovered:
                needs_update = True
        if needs_update:
            self.update()
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:  # noqa: N802
        for btn in self._action_buttons:
            btn.hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        pos = event.pos()
        # Check action buttons first
        if event.button() == Qt.MouseButton.LeftButton:
            for btn in self._action_buttons:
                if btn.rect.contains(pos):
                    if btn is self._btn_run:
                        self.signals.run_requested.emit(self.node_id)
                    elif btn is self._btn_clone:
                        self.signals.clone_requested.emit(self.node_id)
                    elif btn is self._btn_delete:
                        self.signals.delete_requested.emit(self.node_id)
                    event.accept()
                    return

        # Resize?
        rh = QRectF(self._width - self.RESIZE_HANDLE, self._height - self.RESIZE_HANDLE,
                     self.RESIZE_HANDLE, self.RESIZE_HANDLE)
        if event.button() == Qt.MouseButton.LeftButton and rh.contains(pos):
            self._resizing = True
            self._resize_origin = pos
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if self._resizing:
            delta = event.pos() - self._resize_origin
            new_w = max(self.MIN_W, self._width + delta.x())
            new_h = max(self.MIN_H, self._height + delta.y())
            new_w = _snap(new_w)
            new_h = _snap(new_h)
            self.prepareGeometryChange()
            self._width = new_w
            self._height = new_h
            self._resize_origin = event.pos()
            self._layout_ports()
            self.signals.size_changed.emit(self.node_id, new_w, new_h)
            self.update()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if self._resizing:
            self._resizing = False
            # Snap position
            snapped = QPointF(_snap(self.pos().x()), _snap(self.pos().y()))
            self.setPos(snapped)
            event.accept()
            return
        # Snap after drag
        snapped = QPointF(_snap(self.pos().x()), _snap(self.pos().y()))
        self.setPos(snapped)
        super().mouseReleaseEvent(event)


# ===================================================================
# ConnectionGraphicsItem
# ===================================================================

class ConnectionGraphicsItem(QGraphicsPathItem):
    """Bézier curve connecting an output port to an input port."""

    ARROW_SIZE = 8.0

    def __init__(
        self,
        connection_id: str,
        source_port: PortGraphicsItem | None = None,
        target_port: PortGraphicsItem | None = None,
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self.connection_id = connection_id
        self.source_port = source_port
        self.target_port = target_port
        self._running = False
        self._dash_offset = 0.0
        self._dash_timer: QTimer | None = None

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(0)  # below nodes

        self._pen_normal = QPen(_C_ACCENT, 2, Qt.PenStyle.SolidLine)
        self._pen_normal.setCapStyle(Qt.PenCapStyle.RoundCap)
        self._pen_hover = QPen(_C_ACCENT_HOVER, 2.5, Qt.PenStyle.SolidLine)
        self._pen_hover.setCapStyle(Qt.PenCapStyle.RoundCap)
        self._pen_selected = QPen(QColor("#93c5fd"), 2.5, Qt.PenStyle.SolidLine)
        self._pen_selected.setCapStyle(Qt.PenCapStyle.RoundCap)
        self._hovered = False

        self.update_path()

    # -- path construction -------------------------------------------
    def update_path(self, temp_target: QPointF | None = None) -> None:
        """Rebuild the cubic bezier path from source port to target port."""
        if self.source_port is None:
            return

        p1 = self.source_port.center_scene_pos()
        if temp_target is not None:
            p2 = temp_target
        elif self.target_port is not None:
            p2 = self.target_port.center_scene_pos()
        else:
            return

        path = QPainterPath(p1)
        dx = abs(p2.x() - p1.x()) * 0.5
        dx = max(dx, 50)
        cp1 = QPointF(p1.x() + dx, p1.y())
        cp2 = QPointF(p2.x() - dx, p2.y())
        path.cubicTo(cp1, cp2, p2)
        self.setPath(path)

    # -- running animation -------------------------------------------
    def set_running(self, running: bool) -> None:
        self._running = running
        if running:
            if self._dash_timer is None:
                self._dash_timer = QTimer()
                self._dash_timer.setInterval(40)
                self._dash_timer.timeout.connect(self._tick_dash)
            self._dash_timer.start()
        else:
            if self._dash_timer is not None:
                self._dash_timer.stop()
            self.update()

    def _tick_dash(self) -> None:
        self._dash_offset += 1.0
        if self._dash_offset > 20.0:
            self._dash_offset = 0.0
        self.update()

    # -- paint -------------------------------------------------------
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self.isSelected():
            pen = QPen(self._pen_selected)
        elif self._hovered:
            pen = QPen(self._pen_hover)
        else:
            pen = QPen(self._pen_normal)

        if self._running:
            pen.setStyle(Qt.PenStyle.CustomDashLine)
            pen.setDashPattern([6, 4])
            pen.setDashOffset(self._dash_offset)

        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self.path())

        # --- arrowhead at target ---
        self._draw_arrow(painter, pen)

    def _draw_arrow(self, painter: QPainter, pen: QPen) -> None:
        path = self.path()
        if path.isEmpty():
            return
        length = path.length()
        if length < 1.0:
            return

        # Point & tangent near the end
        t_end = 1.0
        p_end = path.pointAtPercent(t_end)
        t_near = max(0.0, path.percentAtLength(length - 1.0))
        p_near = path.pointAtPercent(t_near)
        angle = math.atan2(p_end.y() - p_near.y(), p_end.x() - p_near.x())

        s = self.ARROW_SIZE
        p1 = QPointF(
            p_end.x() - s * math.cos(angle - math.pi / 6),
            p_end.y() - s * math.sin(angle - math.pi / 6),
        )
        p2 = QPointF(
            p_end.x() - s * math.cos(angle + math.pi / 6),
            p_end.y() - s * math.sin(angle + math.pi / 6),
        )
        arrow = QPolygonF([p_end, p1, p2])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(pen.color()))
        painter.drawPolygon(arrow)

    # -- hover -------------------------------------------------------
    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None:  # noqa: N802
        self._hovered = True
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:  # noqa: N802
        self._hovered = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
        super().hoverLeaveEvent(event)

    def shape(self) -> QPainterPath:
        """Wider hit area for easier clicking."""
        stroker = QPainterPath()
        ps = self.path()
        if ps.isEmpty():
            return stroker
        from PySide6.QtGui import QPainterPathStroker
        s = QPainterPathStroker()
        s.setWidth(10)
        return s.createStroke(ps)
