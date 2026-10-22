#!/usr/bin/env python3
"""Verify all files listed in the handoff SHA-256 manifest, without dependencies."""

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    manifest = ROOT / "MANIFEST.sha256"
    if not manifest.is_file():
        raise SystemExit("MANIFEST.sha256 is missing")
    checked = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        path = ROOT / relative
        if not path.is_file() or sha256(path) != expected:
            raise SystemExit(f"Missing or changed file: {relative}")
        checked += 1
    print(f"Package verified: {checked} files match SHA-256")


if __name__ == "__main__":
    main()
