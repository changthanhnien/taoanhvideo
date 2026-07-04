# ui/workflow/canvas.py
from __future__ import annotations

import copy
import uuid
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QPointF,
    QRectF,
    Qt,
    Signal,
    QEvent,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QKeySequence,
    QPainter,
    QPen,
    QShortcut,
    QTransform,
    QWheelEvent,
    QMouseEvent,
    QKeyEvent,
    QContextMenuEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QMenu,
    QWidget,
)

from ui.workflow.models import (
    ConnectionData,
    NodeData,
    WorkflowData,
    serialize_workflow,
    deserialize_workflow,
)
from ui.workflow.node_graphics import (
    ConnectionGraphicsItem,
    NodeGraphicsItem,
    PortGraphicsItem,
    GRID_SIZE,
    _snap,
)

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
_C_BG = QColor("#0f1115")
_C_GRID_DOT = QColor("#1b2028")
_C_ACCENT = QColor("#3b82f6")

# Available node types for the context menu
_NODE_TYPES = [
    ("input", "Đầu vào"),
    ("output", "Đầu ra"),
    ("process", "Xử lý"),
    ("condition", "Điều kiện"),
    ("merge", "Gộp"),
    ("default", "Mặc định"),
]


# ===================================================================
# WorkflowCanvas
# ===================================================================

class WorkflowCanvas(QGraphicsView):
    """Infinite-scroll node canvas with pan, zoom, grid, undo/redo."""

    # Signals
    node_added = Signal(str)       # node_id
    node_removed = Signal(str)     # node_id
    connection_added = Signal(str) # connection_id
    selection_changed = Signal(list)  # list[str] node_ids

    # Zoom limits
    ZOOM_MIN = 0.1
    ZOOM_MAX = 5.0
    ZOOM_STEP = 1.15

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # Scene
        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(-50_000, -50_000, 100_000, 100_000)
        self.setScene(self._scene)

        # Rendering
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
            | QPainter.RenderHint.TextAntialiasing
        )
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)

        # Interaction
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Style
        self.setStyleSheet("QGraphicsView { border: none; }")
        self.setBackgroundBrush(QBrush(_C_BG))

        # Internal state
        self._pan_active = False
        self._pan_start = QPointF()
        self._space_held = False
        self._current_zoom = 1.0

        # Node / connection registries  (id -> graphics item)
        self._nodes: dict[str, NodeGraphicsItem] = {}
        self._connections: dict[str, ConnectionGraphicsItem] = {}

        # Connection-in-progress
        self._temp_connection: ConnectionGraphicsItem | None = None
        self._conn_source_port: PortGraphicsItem | None = None

        # Undo / redo (snapshot list)
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self._undo_limit = 50

        # Clipboard
        self._clipboard: list[dict] = []

        # Scene selection → signal bridge
        self._scene.selectionChanged.connect(self._on_scene_selection)

        # Keyboard shortcuts
        self._setup_shortcuts()

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------
    def _setup_shortcuts(self) -> None:
        def _sc(keys: str, slot) -> None:
            s = QShortcut(QKeySequence(keys), self)
            s.activated.connect(slot)

        _sc("Ctrl+Z", self.undo)
        _sc("Ctrl+Y", self.redo)
        _sc("Ctrl+C", self._copy_selected)
        _sc("Ctrl+V", self._paste)
        _sc("Delete", self._delete_selected)

    # ------------------------------------------------------------------
    # Grid drawing
    # ------------------------------------------------------------------
    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802
        super().drawBackground(painter, rect)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(_C_GRID_DOT))

        # Only draw dots visible in the exposed rect
        left = int(rect.left()) - (int(rect.left()) % GRID_SIZE)
        top = int(rect.top()) - (int(rect.top()) % GRID_SIZE)
        right = int(rect.right())
        bottom = int(rect.bottom())

        dot_radius = 1.0
        points: list[QPointF] = []
        x = left
        while x <= right:
            y = top
            while y <= bottom:
                points.append(QPointF(x, y))
                y += GRID_SIZE
            x += GRID_SIZE

        # Draw in batches for efficiency
        for pt in points:
            painter.drawEllipse(pt, dot_radius, dot_radius)

    # ------------------------------------------------------------------
    # Pan (middle mouse or Space + drag)
    # ------------------------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_held = True
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_held = False
            if not self._pan_active:
                self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
                self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton and self._space_held
        ):
            self._pan_active = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._pan_active:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y())
            )
            event.accept()
            return

        # Update temp connection while dragging from port
        if self._temp_connection is not None:
            scene_pos = self.mapToScene(event.position().toPoint())
            self._temp_connection.update_path(temp_target=scene_pos)
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._pan_active and (
            event.button() == Qt.MouseButton.MiddleButton
            or event.button() == Qt.MouseButton.LeftButton
        ):
            self._pan_active = False
            if self._space_held:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
                self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return

        # Finish connection if in-progress
        if self._temp_connection is not None and event.button() == Qt.MouseButton.LeftButton:
            self._finish_connection(event.position())
            event.accept()
            return

        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------
    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        angle = event.angleDelta().y()
        if angle == 0:
            return
        factor = self.ZOOM_STEP if angle > 0 else 1.0 / self.ZOOM_STEP
        new_zoom = self._current_zoom * factor
        if new_zoom < self.ZOOM_MIN or new_zoom > self.ZOOM_MAX:
            return
        self._current_zoom = new_zoom
        self.scale(factor, factor)

    def zoom_to_fit(self) -> None:
        """Fit all nodes into view."""
        items = [it for it in self._scene.items() if isinstance(it, NodeGraphicsItem)]
        if not items:
            return
        r = QRectF()
        for it in items:
            r = r.united(it.sceneBoundingRect())
        r.adjust(-60, -60, 60, 60)
        self.fitInView(r, Qt.AspectRatioMode.KeepAspectRatio)
        self._current_zoom = self.transform().m11()

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------
    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # noqa: N802
        # Only show if clicking on empty canvas
        item = self.itemAt(event.pos())
        if item is not None:
            super().contextMenuEvent(event)
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #16191f;
                color: #e2e8f0;
                border: 1px solid #2a3140;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #3b82f6;
            }
            QMenu::separator {
                height: 1px;
                background: #2a3140;
                margin: 4px 8px;
            }
        """)

        add_menu = menu.addMenu("➕  Thêm node")
        for ntype, label in _NODE_TYPES:
            act = add_menu.addAction(label)
            scene_pos = self.mapToScene(event.pos())
            act.triggered.connect(lambda checked=False, t=ntype, l=label, p=scene_pos: self.add_node(
                node_type=t, title=l, x=p.x(), y=p.y(),
            ))

        menu.addSeparator()
        menu.addAction("🔍  Phóng vừa khung", self.zoom_to_fit)
        menu.addSeparator()
        paste_act = menu.addAction("📋  Dán (Ctrl+V)")
        paste_act.setEnabled(bool(self._clipboard))
        paste_act.triggered.connect(self._paste)

        menu.exec(event.globalPos())

    # ------------------------------------------------------------------
    # Node management
    # ------------------------------------------------------------------
    def add_node(
        self,
        node_type: str = "default",
        title: str = "Node",
        x: float = 0.0,
        y: float = 0.0,
        width: float = 280.0,
        height: float = 160.0,
        node_id: str | None = None,
        config: dict | None = None,
        state: str = "idle",
        push_undo: bool = True,
    ) -> NodeGraphicsItem:
        if push_undo:
            self._push_undo()

        nid = node_id or uuid.uuid4().hex
        sx, sy = _snap(x), _snap(y)
        gnode = NodeGraphicsItem(
            node_id=nid,
            node_type=node_type,
            title=title,
            x=sx,
            y=sy,
            width=width,
            height=height,
            state=state,
        )

        # Default ports based on type
        if node_type != "output":
            gnode.add_output_port(f"{nid}_out_0")
        if node_type != "input":
            gnode.add_input_port(f"{nid}_in_0")

        # Wire port signals
        for p in gnode.input_ports + gnode.output_ports:
            p.signals.connection_started.connect(self._on_port_connection_start)
            p.signals.connection_finished.connect(self._on_port_connection_finish)

        # Wire node signals
        gnode.signals.delete_requested.connect(self.remove_node)
        gnode.signals.clone_requested.connect(self._clone_node)
        gnode.signals.position_changed.connect(self._on_node_moved)

        self._scene.addItem(gnode)
        self._nodes[nid] = gnode
        self.node_added.emit(nid)
        return gnode

    def remove_node(self, node_id: str, push_undo: bool = True) -> None:
        gnode = self._nodes.get(node_id)
        if gnode is None:
            return
        if push_undo:
            self._push_undo()

        # Remove connections attached to this node
        to_remove = [
            cid for cid, conn in self._connections.items()
            if (conn.source_port and conn.source_port.parent_node is gnode)
            or (conn.target_port and conn.target_port.parent_node is gnode)
        ]
        for cid in to_remove:
            self._remove_connection(cid, push_undo=False)

        self._scene.removeItem(gnode)
        del self._nodes[node_id]
        self.node_removed.emit(node_id)

    def _clone_node(self, node_id: str) -> None:
        src = self._nodes.get(node_id)
        if src is None:
            return
        self.add_node(
            node_type=src.node_type,
            title=src.title + " (bản sao)",
            x=src.pos().x() + 40,
            y=src.pos().y() + 40,
            width=src._width,
            height=src._height,
        )

    def _on_node_moved(self, node_id: str, x: float, y: float) -> None:
        # Update connection paths when a node moves
        gnode = self._nodes.get(node_id)
        if gnode is None:
            return
        for conn in self._connections.values():
            if conn.source_port and conn.source_port.parent_node is gnode:
                conn.update_path()
            elif conn.target_port and conn.target_port.parent_node is gnode:
                conn.update_path()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    def _on_port_connection_start(self, port: PortGraphicsItem) -> None:
        """Begin drawing a temporary connection from *port*."""
        self._conn_source_port = port
        cid = uuid.uuid4().hex
        self._temp_connection = ConnectionGraphicsItem(
            connection_id=cid,
            source_port=port,
        )
        self._scene.addItem(self._temp_connection)
        self._temp_connection.update_path(temp_target=port.center_scene_pos())

    def _on_port_connection_finish(self, port: PortGraphicsItem) -> None:
        """Snap temp connection to the released port if valid."""
        # This is called when mouse is released on a port
        if self._temp_connection is None or self._conn_source_port is None:
            return
        if port is self._conn_source_port:
            return  # same port
        if port.port_kind == self._conn_source_port.port_kind:
            return  # same kind (both input or both output)
        if port.parent_node is self._conn_source_port.parent_node:
            return  # same node

        # Determine direction: output → input
        if self._conn_source_port.port_kind == "output":
            src_port, tgt_port = self._conn_source_port, port
        else:
            src_port, tgt_port = port, self._conn_source_port

        self._complete_connection(src_port, tgt_port)

    def _finish_connection(self, view_pos: QPointF) -> None:
        """Called on mouse release – check if landed on a port."""
        if self._temp_connection is None:
            return

        scene_pos = self.mapToScene(view_pos.toPoint())
        items = self._scene.items(scene_pos)
        target_port: PortGraphicsItem | None = None
        for item in items:
            if isinstance(item, PortGraphicsItem) and item is not self._conn_source_port:
                target_port = item
                break

        if target_port is not None and self._conn_source_port is not None:
            if target_port.port_kind != self._conn_source_port.port_kind and \
               target_port.parent_node is not self._conn_source_port.parent_node:
                if self._conn_source_port.port_kind == "output":
                    src_port, tgt_port = self._conn_source_port, target_port
                else:
                    src_port, tgt_port = target_port, self._conn_source_port
                self._complete_connection(src_port, tgt_port)
                return

        # Cancel – no valid target
        self._cancel_temp_connection()

    def _complete_connection(self, src_port: PortGraphicsItem, tgt_port: PortGraphicsItem) -> None:
        """Finalise a connection between two ports."""
        self._push_undo()

        # Remove temp item
        if self._temp_connection is not None:
            self._scene.removeItem(self._temp_connection)
            self._temp_connection = None

        cid = uuid.uuid4().hex
        conn = ConnectionGraphicsItem(
            connection_id=cid,
            source_port=src_port,
            target_port=tgt_port,
        )
        conn.update_path()
        self._scene.addItem(conn)
        self._connections[cid] = conn

        src_port.set_connected(True)
        tgt_port.set_connected(True)

        self._conn_source_port = None
        self.connection_added.emit(cid)

    def _cancel_temp_connection(self) -> None:
        if self._temp_connection is not None:
            self._scene.removeItem(self._temp_connection)
            self._temp_connection = None
        self._conn_source_port = None

    def _remove_connection(self, cid: str, push_undo: bool = True) -> None:
        conn = self._connections.get(cid)
        if conn is None:
            return
        if push_undo:
            self._push_undo()
        self._scene.removeItem(conn)
        del self._connections[cid]

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------
    def _on_scene_selection(self) -> None:
        ids = [
            it.node_id
            for it in self._scene.selectedItems()
            if isinstance(it, NodeGraphicsItem)
        ]
        self.selection_changed.emit(ids)

    def _delete_selected(self) -> None:
        selected = list(self._scene.selectedItems())
        if not selected:
            return
        self._push_undo()
        for item in selected:
            if isinstance(item, NodeGraphicsItem):
                self.remove_node(item.node_id, push_undo=False)
            elif isinstance(item, ConnectionGraphicsItem):
                self._remove_connection(item.connection_id, push_undo=False)

    # ------------------------------------------------------------------
    # Copy / Paste
    # ------------------------------------------------------------------
    def _copy_selected(self) -> None:
        self._clipboard.clear()
        for item in self._scene.selectedItems():
            if isinstance(item, NodeGraphicsItem):
                self._clipboard.append({
                    "node_type": item.node_type,
                    "title": item.title,
                    "x": item.pos().x(),
                    "y": item.pos().y(),
                    "width": item._width,
                    "height": item._height,
                })

    def _paste(self) -> None:
        if not self._clipboard:
            return
        self._push_undo()
        offset = 60.0
        for data in self._clipboard:
            self.add_node(
                node_type=data["node_type"],
                title=data["title"],
                x=data["x"] + offset,
                y=data["y"] + offset,
                width=data["width"],
                height=data["height"],
                push_undo=False,
            )

    # ------------------------------------------------------------------
    # Undo / Redo  (snapshot-based)
    # ------------------------------------------------------------------
    def _snapshot(self) -> dict:
        """Capture the full canvas state as a serialisable dict."""
        nodes: list[dict] = []
        for nid, gn in self._nodes.items():
            nodes.append({
                "id": nid,
                "node_type": gn.node_type,
                "title": gn.title,
                "x": gn.pos().x(),
                "y": gn.pos().y(),
                "width": gn._width,
                "height": gn._height,
                "state": gn.state,
            })
        conns: list[dict] = []
        for cid, gc in self._connections.items():
            src_nid = gc.source_port.parent_node.node_id if gc.source_port else ""
            src_pid = gc.source_port.port_id if gc.source_port else ""
            tgt_nid = gc.target_port.parent_node.node_id if gc.target_port else ""
            tgt_pid = gc.target_port.port_id if gc.target_port else ""
            conns.append({
                "id": cid,
                "source_node": src_nid,
                "source_port": src_pid,
                "target_node": tgt_nid,
                "target_port": tgt_pid,
            })
        return {"nodes": nodes, "connections": conns}

    def _restore(self, snap: dict) -> None:
        """Rebuild the canvas from a snapshot dict."""
        # Clear everything first
        for cid in list(self._connections.keys()):
            conn = self._connections.pop(cid)
            self._scene.removeItem(conn)
        for nid in list(self._nodes.keys()):
            node = self._nodes.pop(nid)
            self._scene.removeItem(node)

        # Rebuild nodes
        for nd in snap.get("nodes", []):
            self.add_node(
                node_id=nd["id"],
                node_type=nd.get("node_type", "default"),
                title=nd.get("title", "Node"),
                x=nd.get("x", 0),
                y=nd.get("y", 0),
                width=nd.get("width", 280),
                height=nd.get("height", 160),
                state=nd.get("state", "idle"),
                push_undo=False,
            )

        # Rebuild connections
        for cd in snap.get("connections", []):
            src_port = self._find_port(cd["source_node"], cd["source_port"])
            tgt_port = self._find_port(cd["target_node"], cd["target_port"])
            if src_port and tgt_port:
                conn = ConnectionGraphicsItem(
                    connection_id=cd["id"],
                    source_port=src_port,
                    target_port=tgt_port,
                )
                conn.update_path()
                self._scene.addItem(conn)
                self._connections[cd["id"]] = conn
                src_port.set_connected(True)
                tgt_port.set_connected(True)

    def _find_port(self, node_id: str, port_id: str) -> PortGraphicsItem | None:
        gnode = self._nodes.get(node_id)
        if gnode is None:
            return None
        for p in gnode.input_ports + gnode.output_ports:
            if p.port_id == port_id:
                return p
        return None

    def _push_undo(self) -> None:
        snap = self._snapshot()
        self._undo_stack.append(snap)
        if len(self._undo_stack) > self._undo_limit:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def undo(self) -> None:
        if not self._undo_stack:
            return
        self._redo_stack.append(self._snapshot())
        snap = self._undo_stack.pop()
        self._restore(snap)

    def redo(self) -> None:
        if not self._redo_stack:
            return
        self._undo_stack.append(self._snapshot())
        snap = self._redo_stack.pop()
        self._restore(snap)

    # ------------------------------------------------------------------
    # Serialisation helpers (to/from WorkflowData)
    # ------------------------------------------------------------------
    def to_workflow_data(self, name: str = "Untitled", wf_id: str | None = None) -> WorkflowData:
        nodes = []
        for nid, gn in self._nodes.items():
            nodes.append(NodeData(
                id=nid,
                node_type=gn.node_type,
                title=gn.title,
                x=gn.pos().x(),
                y=gn.pos().y(),
                width=gn._width,
                height=gn._height,
                state=gn.state,
            ))
        connections = []
        for cid, gc in self._connections.items():
            connections.append(ConnectionData(
                id=cid,
                source_node=gc.source_port.parent_node.node_id if gc.source_port else "",
                source_port=gc.source_port.port_id if gc.source_port else "",
                target_node=gc.target_port.parent_node.node_id if gc.target_port else "",
                target_port=gc.target_port.port_id if gc.target_port else "",
            ))
        return WorkflowData(
            id=wf_id or uuid.uuid4().hex,
            name=name,
            nodes=nodes,
            connections=connections,
        )

    def load_from_workflow_data(self, wf: WorkflowData) -> None:
        """Populate the canvas from a *WorkflowData* object."""
        # Clear
        for cid in list(self._connections.keys()):
            self._remove_connection(cid, push_undo=False)
        for nid in list(self._nodes.keys()):
            self.remove_node(nid, push_undo=False)

        for nd in wf.nodes:
            self.add_node(
                node_id=nd.id,
                node_type=nd.node_type,
                title=nd.title,
                x=nd.x,
                y=nd.y,
                width=nd.width,
                height=nd.height,
                config=nd.config,
                state=nd.state,
                push_undo=False,
            )

        for cd in wf.connections:
            src_port = self._find_port(cd.source_node, cd.source_port)
            tgt_port = self._find_port(cd.target_node, cd.target_port)
            if src_port and tgt_port:
                conn = ConnectionGraphicsItem(
                    connection_id=cd.id,
                    source_port=src_port,
                    target_port=tgt_port,
                )
                conn.update_path()
                self._scene.addItem(conn)
                self._connections[cd.id] = conn
                src_port.set_connected(True)
                tgt_port.set_connected(True)

        self.zoom_to_fit()
        self._undo_stack.clear()
        self._redo_stack.clear()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def clear_canvas(self) -> None:
        self._push_undo()
        for cid in list(self._connections.keys()):
            self._remove_connection(cid, push_undo=False)
        for nid in list(self._nodes.keys()):
            self.remove_node(nid, push_undo=False)

    def get_node(self, node_id: str) -> NodeGraphicsItem | None:
        return self._nodes.get(node_id)


# ===================================================================
# MiniMap
# ===================================================================

class MiniMap(QGraphicsView):
    """Small overview map shown in the bottom-right of the canvas."""

    def __init__(self, main_canvas: WorkflowCanvas, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.main_canvas = main_canvas
        self.setScene(main_canvas._scene)

        self.setFixedSize(200, 150)
        self.setRenderHints(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setInteractive(False)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setStyleSheet("""
            QGraphicsView {
                background-color: #16191f;
                border: 1px solid #2a3140;
                border-radius: 6px;
            }
        """)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

        # Periodically sync the viewport rectangle
        from PySide6.QtCore import QTimer
        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(250)
        self._sync_timer.timeout.connect(self._sync_view)
        self._sync_timer.start()

    def _sync_view(self) -> None:
        """Fit all items into the minimap and trigger a repaint."""
        items = [it for it in self.scene().items() if isinstance(it, NodeGraphicsItem)]
        if not items:
            return
        r = QRectF()
        for it in items:
            r = r.united(it.sceneBoundingRect())
        r.adjust(-100, -100, 100, 100)
        self.fitInView(r, Qt.AspectRatioMode.KeepAspectRatio)
        self.viewport().update()

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802
        """Draw a rectangle representing the main canvas viewport."""
        super().drawForeground(painter, rect)
        vp = self.main_canvas.mapToScene(self.main_canvas.viewport().rect())
        if vp.isEmpty():
            return
        pen = QPen(_C_ACCENT, 1, Qt.PenStyle.SolidLine)
        pen.setCosmetic(True)
        painter.setPen(pen)
        fill = QColor(_C_ACCENT)
        fill.setAlpha(20)
        painter.setBrush(QBrush(fill))
        painter.drawPolygon(vp)

    # Ignore all interaction
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        event.ignore()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        event.ignore()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        event.ignore()
