"""Simple latest-backup support for the active compact graph."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..fsutil import remove_tree
from ..graph import validate


GRAPH_FILES = ("ontology.jsonl", "source-index.json", "cache-manifest.json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_files(root: Path, label: str) -> None:
    missing = [name for name in GRAPH_FILES if not (root / name).is_file()]
    if missing:
        raise ValueError(f"{label} is incomplete: missing {missing}")


def has_graph(root: Path) -> bool:
    return all((root / name).is_file() for name in GRAPH_FILES)


def _validate_graph_root(root: Path) -> None:
    try:
        json.loads((root / "source-index.json").read_text(encoding="utf-8"))
        manifest = json.loads((root / "cache-manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"graph metadata is invalid: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != "labontology.workspace-cache.v1":
        raise ValueError("graph metadata has an unsupported cache schema")
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        result = validate(system_dir=root)
    if result != 0:
        raise ValueError("graph validation failed")


def fresh_staging(cache: Path, purpose: str) -> Path:
    """Return an empty staging directory beside the cache (same filesystem)."""
    staging = cache.parent / f".{cache.name}-{purpose}-build"
    remove_tree(staging)
    staging.mkdir(parents=True)
    return staging


def replace_graph_files(source_dir: Path, cache: Path, *, rollback_dir: Path | None = None) -> None:
    """Move the three graph files into the live cache, manifest last.

    Mission records under ``runs/`` are never copied or moved. If a replacement
    fails part-way, files already replaced are restored from ``rollback_dir``;
    for a new cache they are removed again so the cache stays empty.
    """
    cache.mkdir(parents=True, exist_ok=True)
    replaced: list[str] = []
    try:
        for name in GRAPH_FILES:
            os.replace(source_dir / name, cache / name)
            replaced.append(name)
    except BaseException:
        for name in replaced:
            if rollback_dir is not None and (rollback_dir / name).is_file():
                shutil.copy2(rollback_dir / name, cache / name)
            else:
                (cache / name).unlink(missing_ok=True)
        raise


def publish_graph(cache_dir: Path, records: list[dict[str, Any]], index: dict[str, Any],
                  manifest: dict[str, Any], *, reason: str, purpose: str = "graph") -> dict[str, Any] | None:
    """Validate a new graph in staging, back up the active one, then swap files in."""
    cache = Path(cache_dir).resolve()
    staging = fresh_staging(cache, purpose)
    try:
        (staging / "ontology.jsonl").write_text(
            "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8"
        )
        (staging / "source-index.json").write_text(
            json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (staging / "cache-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        _validate_graph_root(staging)
        backup = backup_active_graph(cache, reason) if has_graph(cache) else None
        (cache / "runs").mkdir(parents=True, exist_ok=True)
        replace_graph_files(staging, cache, rollback_dir=cache / ".backup" if backup else None)
        _prune_generated(cache)
        return backup
    finally:
        with contextlib.suppress(OSError):
            remove_tree(staging)


def _prune_generated(cache: Path) -> None:
    """The cache is generated: drop stale top-level entries, never runs/ or the backup."""
    for entry in cache.iterdir():
        if entry.name not in {*GRAPH_FILES, "runs", ".backup"}:
            with contextlib.suppress(OSError):
                remove_tree(entry)


def backup_active_graph(cache_dir: Path, reason: str) -> dict[str, Any]:
    cache = Path(cache_dir).resolve()
    _require_files(cache, "active graph")
    backup = cache / ".backup"
    staging = fresh_staging(cache, "backup")
    try:
        files = {}
        for name in GRAPH_FILES:
            source = cache / name
            destination = staging / name
            shutil.copy2(source, destination)
            files[name] = {"path": name, "sha256": _sha256(destination),
                           "size_bytes": destination.stat().st_size}
        remove_tree(backup)
        staging.replace(backup)
    except Exception:
        with contextlib.suppress(OSError):
            remove_tree(staging)
        raise
    return {
        "backup_dir": str(backup),
        "reason": reason,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }


def restore_active_graph(cache_dir: Path) -> dict[str, Any]:
    cache = Path(cache_dir).resolve()
    backup = cache / ".backup"
    _require_files(backup, "incomplete backup")
    staging = fresh_staging(cache, "restore")
    snapshot: Path | None = None
    try:
        for name in GRAPH_FILES:
            shutil.copy2(backup / name, staging / name)
        _validate_graph_root(staging)
        if has_graph(cache):
            snapshot = fresh_staging(cache, "restore-snapshot")
            for name in GRAPH_FILES:
                shutil.copy2(cache / name, snapshot / name)
        replace_graph_files(staging, cache, rollback_dir=snapshot)
    finally:
        for folder in (staging, snapshot):
            if folder is not None:
                with contextlib.suppress(OSError):
                    remove_tree(folder)
    return {"cache_dir": str(cache), "restored": sorted(GRAPH_FILES)}
