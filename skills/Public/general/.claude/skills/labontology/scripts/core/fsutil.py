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

# Trees a Skill package carries with it that are not the Skill's own interface: the original model source,
# vendored dependencies and source archives. Their READMEs and scripts describe other programs, so the
# Creator must not read a Skill's command, parameters or outputs from them (a handoff package's experiment
# README would otherwise become the Skill's required outputs). They stay part of the package at runtime,
# which is why IGNORED_DIRS leaves them alone.
VENDORED_DIRS = frozenset({
    "model_source", "runtime_deps", "source_archives", "vendor", "third_party", "site-packages",
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


def iter_interface_files(root: Path, pattern: str = "*") -> Iterator[Path]:
    """Yield the files that describe the Skill itself, skipping VENDORED_DIRS as well."""
    root = Path(root)
    for path in iter_files(root, pattern):
        if VENDORED_DIRS.isdisjoint(path.relative_to(root).parts[:-1]):
            yield path


def iter_dirs(root: Path) -> Iterator[Path]:
    """Yield root and every directory below it, skipping IGNORED_DIRS."""
    root = Path(root)
    if not root.is_dir():
        return
    for current, directories, _ in os.walk(root):
        directories[:] = sorted(name for name in directories if name not in IGNORED_DIRS)
        yield Path(current)


# A lock file is empty only between its creation and its holder writing the PID.
EMPTY_LOCK_GRACE = 2.0


def _lock_owner(path: Path) -> int | None:
    """The PID written in a lock file, or None when it has none (still being created, or unreadable)."""
    try:
        text = path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeDecodeError):
        return None
    return int(text) if text.isdigit() else None


def _process_running(pid: int) -> bool:
    """Whether a process with this PID is running. When in doubt it is: the lock is then waited for."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == 5  # ERROR_ACCESS_DENIED: it exists, owned by someone else
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:  # PermissionError: it exists, owned by someone else
        return True
    return True


def _remove_abandoned_lock(path: Path, seen: os.stat_result) -> bool:
    """Delete the abandoned lock file inspected as `seen`, unless another waiter has replaced it meanwhile.
    False when it could not be deleted (the caller then waits instead of retrying at once)."""
    try:
        current = path.stat()
        if (current.st_mtime_ns, current.st_size) == (seen.st_mtime_ns, seen.st_size):
            path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        return False
    return True


@contextmanager
def file_lock(path: Path, *, timeout: float = 60.0, stale_after: float = 600.0,
              poll: float = 0.1) -> Iterator[None]:
    """Hold an exclusive lock file. A lock is abandoned when the process that wrote it has ended (a command
    killed by a stopped chat turn or a timeout cannot remove its lock), when it stayed empty past
    EMPTY_LOCK_GRACE, or, for a PID reused by another process, once it is older than stale_after."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    while True:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except (FileExistsError, PermissionError):
            try:
                seen = path.stat()
            except FileNotFoundError:
                continue
            except OSError:  # e.g. Windows, while the lock file is being deleted: still held
                seen = None
            owner = _lock_owner(path) if seen is not None else None
            if seen is not None:
                age = time.time() - seen.st_mtime
                if (age > stale_after or (owner is None and age > EMPTY_LOCK_GRACE)
                        or (owner is not None and not _process_running(owner))):
                    if _remove_abandoned_lock(path, seen):
                        continue
            if time.monotonic() >= deadline:
                holder = f" (pid {owner} is still running)" if owner is not None else ""
                raise TimeoutError(f"Another LabOntology command is still running: {path}{holder}") from None
            time.sleep(poll)
    try:
        os.write(descriptor, f"{os.getpid()}\n".encode("ascii"))
    finally:
        os.close(descriptor)
    try:
        yield
    finally:
        path.unlink(missing_ok=True)
