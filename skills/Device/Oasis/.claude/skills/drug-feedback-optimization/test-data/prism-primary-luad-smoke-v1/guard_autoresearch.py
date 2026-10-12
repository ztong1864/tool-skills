#!/usr/bin/env python3
"""Guard fixed evaluator inputs and the editable strategy interface."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

from protocol import load_strategy_module

HERE = Path(__file__).resolve().parent
FROZEN = (
    "base_scored_oracle.csv",
    "feature_columns.json",
    "split_manifest.json",
    "protocol.py",
    "run_acquisition_eval.py",
    "autoresearch_backend.py",
    "search_space.json",
    "guard_autoresearch.py",
    "generic_evaluator.py",
)
FORBIDDEN_IMPORT_ROOTS = {"requests", "urllib", "httpx", "socket", "subprocess"}
FORBIDDEN_SOURCE_TOKENS = {
    "median_logfold_change",
    "mean_logfold_change",
    "active_label",
    "n_measurements",
    "locked_test_ids",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy-path", type=Path, default=HERE / "strategy.py")
    args = parser.parse_args()
    expected = {}
    for line in (HERE / "frozen_inputs.sha256").read_text(encoding="utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        expected[name.strip()] = digest
    for name in FROZEN:
        actual = sha256(HERE / name)
        if actual != expected.get(name):
            raise SystemExit(f"ERROR: frozen input changed: {name}")
    source = args.strategy_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(args.strategy_path))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    blocked = sorted(imported.intersection(FORBIDDEN_IMPORT_ROOTS))
    if blocked:
        raise SystemExit(f"ERROR: strategy imports forbidden modules: {blocked}")
    leaked = sorted(token for token in FORBIDDEN_SOURCE_TOKENS if token in source)
    if leaked:
        raise SystemExit(f"ERROR: strategy references forbidden private fields: {leaked}")
    load_strategy_module(args.strategy_path)
    print(json.dumps({"status": "ok", "guard": "passed"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
