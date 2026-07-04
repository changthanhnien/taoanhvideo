# ui/workflow/models.py
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class NodeData:
    """A single node in the workflow graph."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    node_type: str = ""
    title: str = "Node"
    x: float = 0.0
    y: float = 0.0
    width: float = 280.0
    height: float = 160.0
    config: dict[str, Any] = field(default_factory=dict)
    state: str = "idle"  # idle | running | success | error | waiting

    # ------------------------------------------------------------------
    def validate_state(self) -> None:
        allowed = ("idle", "running", "success", "error", "waiting")
        if self.state not in allowed:
            self.state = "idle"


@dataclass
class ConnectionData:
    """A directed edge between two ports."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    source_node: str = ""
    source_port: str = ""
    target_node: str = ""
    target_port: str = ""


@dataclass
class WorkflowData:
    """Top-level workflow document."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = "Untitled Workflow"
    nodes: list[NodeData] = field(default_factory=list)
    connections: list[ConnectionData] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_favorite: bool = False


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def serialize_workflow(wf: WorkflowData) -> dict:
    """Convert a *WorkflowData* tree into a plain dict safe for JSON."""
    return asdict(wf)


def deserialize_workflow(data: dict) -> WorkflowData:
    """Reconstruct a *WorkflowData* from a plain dict."""
    nodes = [NodeData(**n) for n in data.get("nodes", [])]
    connections = [ConnectionData(**c) for c in data.get("connections", [])]
    return WorkflowData(
        id=data.get("id", uuid.uuid4().hex),
        name=data.get("name", "Untitled Workflow"),
        nodes=nodes,
        connections=connections,
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
        is_favorite=data.get("is_favorite", False),
    )


# ---------------------------------------------------------------------------
# Persistence – filesystem helpers
# ---------------------------------------------------------------------------

_WORKFLOWS_DIR: Path | None = None


def _workflows_dir() -> Path:
    """Return (and lazily create) the workflows storage directory."""
    global _WORKFLOWS_DIR
    if _WORKFLOWS_DIR is None:
        from config.constants import DATA_DIR
        _WORKFLOWS_DIR = DATA_DIR / "workflows"
    _WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
    return _WORKFLOWS_DIR


def set_workflows_dir(base: str | Path) -> None:
    """Override the base directory (useful when the app root differs)."""
    global _WORKFLOWS_DIR
    _WORKFLOWS_DIR = Path(base) / "workflows"
    _WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)


def _wf_path(wf_id: str) -> Path:
    return _workflows_dir() / f"{wf_id}.json"


def save_workflow(wf: WorkflowData) -> Path:
    """Persist *wf* to disk and return the file path."""
    wf.updated_at = datetime.now(timezone.utc).isoformat()
    path = _wf_path(wf.id)
    path.write_text(json.dumps(serialize_workflow(wf), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_workflow(wf_id: str) -> WorkflowData:
    """Load a single workflow by its id.  Raises *FileNotFoundError*."""
    path = _wf_path(wf_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    return deserialize_workflow(data)


def list_workflows() -> list[WorkflowData]:
    """Return every persisted workflow (lightweight metadata load)."""
    results: list[WorkflowData] = []
    wdir = _workflows_dir()
    for fp in sorted(wdir.glob("*.json"), key=os.path.getmtime, reverse=True):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            results.append(deserialize_workflow(data))
        except (json.JSONDecodeError, KeyError):
            continue
    return results


def delete_workflow(wf_id: str) -> bool:
    """Delete a workflow file.  Returns *True* if it existed."""
    path = _wf_path(wf_id)
    if path.exists():
        path.unlink()
        return True
    return False
