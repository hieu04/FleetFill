"""Runtime paths shared by source and packaged FleetFill builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    """Return the read-only application resource root."""

    override = os.environ.get("FLEETFILL_RESOURCE_ROOT")
    if override:
        return Path(override).resolve()
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root).resolve()
    return Path(__file__).resolve().parents[2]


def data_root(resources: Path | None = None) -> Path:
    """Return a writable root for run history, evidence, and recovery copies."""

    override = os.environ.get("FLEETFILL_DATA_ROOT")
    if override:
        return Path(override).resolve()
    if is_frozen():
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return (base / "FleetFill").resolve()
    return (resources or resource_root()) / "research" / "output"


def python_executable() -> Path:
    """Return Python in source builds and the packaged worker when frozen."""

    override = os.environ.get("FLEETFILL_WORKER_EXECUTABLE")
    if override:
        return Path(override).resolve()
    if is_frozen():
        return Path(sys.executable).with_name("FleetFillWorker.exe").resolve()
    return Path(sys.executable).resolve()


def node_executable() -> Path:
    """Return the bundled Node runtime when packaged, otherwise the PATH command."""

    override = os.environ.get("FLEETFILL_NODE_EXECUTABLE")
    if override:
        return Path(override).resolve()
    if is_frozen():
        return resource_root() / "runtime" / "node.exe"
    return Path("node")
