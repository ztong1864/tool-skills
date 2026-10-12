#!/usr/bin/env python3
"""Run the bundled PRISM primary LUAD smoke evaluation from any directory."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=17)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--output-dir", type=Path, default=HERE / "smoke_output")
    args = parser.parse_args()
    if args.rounds <= 0 or args.batch_size <= 0:
        parser.error("--rounds and --batch-size must be positive integers")
    top_k = args.batch_size if args.top_k is None else args.top_k
    if top_k <= 0:
        parser.error("--top-k must be a positive integer")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(HERE / "run_dev_eval.py"),
        "--base-scored-csv", str(HERE / "base_scored_oracle.csv"),
        "--feature-columns-json", str(HERE / "feature_columns.json"),
        "--split-manifest", str(HERE / "split_manifest.json"),
        "--strategy-path", str(HERE / "strategy.py"),
        "--output-dir", str(args.output_dir),
        "--results-tsv", str(args.output_dir / "results.tsv"),
        "--experiment-id", f"bundled_smoke_r{args.rounds}_b{args.batch_size}_k{top_k}",
        "--strategy-summary", "Bundled PRISM primary LUAD feedback smoke",
        "--kept", "smoke_only",
        "--expected-rows", "4684",
        "--rounds", str(args.rounds),
        "--batch-size", str(args.batch_size),
        "--top-k", str(top_k),
    ]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
