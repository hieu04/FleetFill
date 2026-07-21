"""Stable, read-only recovery snapshots for ETS2 profile storage."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from fleetfill.domain import ProfileInfo


class ProfileSnapshotError(RuntimeError):
    """Raised before input when a complete, stable snapshot cannot be proven."""


@dataclass(frozen=True)
class ManifestEntry:
    size: int
    modified_ns: int
    sha256: str


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def directory_manifest(root: Path) -> dict[str, ManifestEntry]:
    if not root.is_dir():
        raise ProfileSnapshotError(f"Snapshot source directory is missing: {root}")
    manifest: dict[str, ManifestEntry] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        stat = path.stat()
        manifest[relative] = ManifestEntry(stat.st_size, stat.st_mtime_ns, _hash_file(path))
    return manifest


def _file_entry(path: Path) -> ManifestEntry:
    if not path.is_file():
        raise ProfileSnapshotError(f"Snapshot source file is missing: {path}")
    stat = path.stat()
    return ManifestEntry(stat.st_size, stat.st_mtime_ns, _hash_file(path))


def _content_manifest(manifest: dict[str, ManifestEntry]) -> dict[str, tuple[int, str]]:
    return {name: (entry.size, entry.sha256) for name, entry in manifest.items()}


def create_steam_cloud_snapshot(profile: ProfileInfo, destination: Path) -> dict:
    """Copy and verify every recovery surface for one Steam Cloud profile."""

    if not profile.is_steam_cloud:
        raise ProfileSnapshotError("A Steam Cloud snapshot requires a cloud profile.")
    if destination.exists():
        raise ProfileSnapshotError(f"Snapshot destination already exists: {destination}")
    if profile.companion_path is None or not profile.companion_path.is_dir():
        raise ProfileSnapshotError("The Documents-side Steam profile companion is missing.")
    if profile.steam_metadata_path is None or not profile.steam_metadata_path.is_file():
        raise ProfileSnapshotError("Steam remotecache.vdf metadata is missing.")
    required = (
        profile.path / "profile.sii",
        profile.path / "save" / "autosave" / "game.sii",
        profile.path / "save" / "autosave" / "info.sii",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise ProfileSnapshotError("Cloud profile is incomplete: " + ", ".join(missing))

    cloud_before = directory_manifest(profile.path)
    companion_before = directory_manifest(profile.companion_path)
    metadata_before = _file_entry(profile.steam_metadata_path)

    cloud_copy = destination / "steam-cloud-profile"
    companion_copy = destination / "documents-companion"
    metadata_copy = destination / "steam-metadata" / "remotecache.vdf"
    destination.mkdir(parents=True)
    shutil.copytree(profile.path, cloud_copy)
    shutil.copytree(profile.companion_path, companion_copy)
    metadata_copy.parent.mkdir(parents=True)
    shutil.copy2(profile.steam_metadata_path, metadata_copy)

    cloud_after = directory_manifest(profile.path)
    companion_after = directory_manifest(profile.companion_path)
    metadata_after = _file_entry(profile.steam_metadata_path)
    if cloud_before != cloud_after or companion_before != companion_after or metadata_before != metadata_after:
        raise ProfileSnapshotError("A cloud snapshot source changed while it was being copied.")

    cloud_copied = directory_manifest(cloud_copy)
    companion_copied = directory_manifest(companion_copy)
    metadata_copied = _file_entry(metadata_copy)
    if _content_manifest(cloud_before) != _content_manifest(cloud_copied):
        raise ProfileSnapshotError("The copied Steam Cloud profile failed hash verification.")
    if _content_manifest(companion_before) != _content_manifest(companion_copied):
        raise ProfileSnapshotError("The copied Documents companion failed hash verification.")
    if (metadata_before.size, metadata_before.sha256) != (
        metadata_copied.size,
        metadata_copied.sha256,
    ):
        raise ProfileSnapshotError("The copied Steam metadata failed hash verification.")

    report = {
        "profile_name": profile.name,
        "profile_id": profile.path.name,
        "authoritative_profile": str(profile.path.resolve()),
        "documents_companion": str(profile.companion_path.resolve()),
        "steam_metadata": str(profile.steam_metadata_path.resolve()),
        "snapshot": str(destination.resolve()),
        "cloud_files": len(cloud_before),
        "cloud_bytes": sum(entry.size for entry in cloud_before.values()),
        "companion_files": len(companion_before),
        "companion_bytes": sum(entry.size for entry in companion_before.values()),
        "metadata_bytes": metadata_before.size,
        "verified": True,
    }
    (destination / "snapshot-report.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    return report
