"""Small filesystem helpers shared by the Creator and Runtime modules."""
from __future__ import annotations

import os
import shutil
import stat
import sys
import time
from contextlib import contextmanager
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4


# Folders that never belong to a Skill's contract. They are skipped when Skill
# sources are scanned, parsed, or hashed so that tool caches and version-control
# metadata cannot slow down or invalidate the workspace cache.
IGNORED_DIRS = frozenset({
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".tox",
})


def _retry_writable(function: Any, path: str, _error: Any) -> None:
    os.chmod(path, stat.S_IWRITE)
    function(path)


def remove_tree(path: Path) -> None:
    """Delete a file or directory tree, including files marked read-only."""
    path = Path(path)
    if path.is_dir() and not path.is_symlink():
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=_retry_writable)
        else:  # pragma: no cover - Python 3.11
            shutil.rmtree(path, onerror=_retry_writable)
    elif path.exists() or path.is_symlink():
        try:
            path.unlink()
        except PermissionError:
            os.chmod(path, stat.S_IWRITE)
            path.unlink()


def atomic_write_text(path: Path, text: str) -> None:
    """Write UTF-8 text so readers see either the old or the new content."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        for attempt in range(5):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                # Windows briefly locks files that are being scanned or read.
                if attempt == 4:
                    raise
                time.sleep(0.05 * (attempt + 1))
    finally:
        temporary.unlink(missing_ok=True)


def iter_files(root: Path, pattern: str = "*") -> Iterator[Path]:
    """Yield files below root in a stable order, skipping IGNORED_DIRS."""
    root = Path(root)
    if not root.is_dir():
        return
    for current, directories, files in os.walk(root):
        directories[:] = sorted(name for name in directories if name not in IGNORED_DIRS)
        for name in sorted(files):
            if fnmatch(name, pattern):
                yield Path(current) / name


def iter_dirs(root: Path) -> Iterator[Path]:
    """Yield root and every directory below it, skipping IGNORED_DIRS."""
    root = Path(root)
    if not root.is_dir():
        return
    for current, directories, _ in os.walk(root):
        directories[:] = sorted(name for name in directories if name not in IGNORED_DIRS)
        yield Path(current)


@contextmanager
def file_lock(path: Path, *, timeout: float = 60.0, stale_after: float = 600.0,
              poll: float = 0.1) -> Iterator[None]:
    """Hold an exclusive lock file; a lock older than stale_after is abandoned."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    while True:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except (FileExistsError, PermissionError):
            try:
                age = time.time() - path.stat().st_mtime
            except FileNotFoundError:
                continue
            if age > stale_after:
                path.unlink(missing_ok=True)
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Another LabOntology command is still running: {path}") from None
            time.sleep(poll)
    try:
        os.write(descriptor, f"{os.getpid()}\n".encode("ascii"))
    finally:
        os.close(descriptor)
    try:
        yield
    finally:
        path.unlink(missing_ok=True)
