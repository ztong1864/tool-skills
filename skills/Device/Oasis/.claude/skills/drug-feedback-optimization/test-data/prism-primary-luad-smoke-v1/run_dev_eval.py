#!/usr/bin/env python3
"""Run development-only evaluation for an editable PRISM primary LUAD strategy."""

from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from protocol import DEFAULT_BATCH_SIZE, DEFAULT_EXPECTED_ROWS, DEFAULT_ROUNDS, DEFAULT_TOP_K, load_and_validate_manifest, load_inputs, load_strategy_module, run_protocol, write_json


HERE = Path(__file__).resolve().parent
DEFAULT_BASE_SCORED_CSV = Path("output/prism_primary_luad_active_learning/feedback_calibrator_round10_acq50_top50/base_scored_oracle.csv")
DEFAULT_FEATURE_COLUMNS_JSON = Path("output/prism_primary_luad_active_learning/feedback_calibrator_round10_acq50_top50/feature_columns.json")
DEFAULT_SPLIT_MANIFEST = Path("output/prism_primary_luad_autoresearch/splits/split_manifest.json")
DEFAULT_OUTPUT_DIR = Path("output/prism_primary_luad_autoresearch/dev_runs/current")
DEFAULT_RESULTS_TSV = Path("output/prism_primary_luad_autoresearch/results.tsv")
RESULT_FIELDS = [
    "experiment_id",
    "timestamp",
    "strategy_summary",
    "status",
    "round10_dev_ndcg_at_50_mean",
    "round10_dev_ndcg_at_50_std",
    "round10_dev_top50_true_activity_mean",
    "round10_dev_top50_median_logfold_change",
    "round10_dev_acquired_base_rank_top50_count_mean",
    "round10_dev_acquired_base_rank_median_mean",
    "round10_dev_acquired_base_rank_percentile_mean",
    "round10_dev_spearman_mean",
    "elapsed_seconds",
    "kept",
]


def append_result(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=RESULT_FIELDS, delimiter="\t")
        if not exists:
            writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in RESULT_FIELDS})


def main() -> None:
    parser = argparse.ArgumentParser(description="Run development evaluation for PRISM primary LUAD strategy search.")
    parser.add_argument("--base-scored-csv", type=Path, default=DEFAULT_BASE_SCORED_CSV)
    parser.add_argument("--feature-columns-json", type=Path, default=DEFAULT_FEATURE_COLUMNS_JSON)
    parser.add_argument("--split-manifest", type=Path, default=DEFAULT_SPLIT_MANIFEST)
    parser.add_argument("--strategy-path", type=Path, default=HERE / "strategy.py")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--results-tsv", type=Path, default=DEFAULT_RESULTS_TSV)
    parser.add_argument("--experiment-id", default="baseline_gradient_boosting_weight_0.5")
    parser.add_argument("--strategy-summary", default="GradientBoostingRegressor with 0.5 base-score fusion")
    parser.add_argument("--kept", default="candidate")
    parser.add_argument("--reference-random", action="store_true", help="Run a non-search random acquisition reference baseline.")
    parser.add_argument("--expected-rows", type=int, default=DEFAULT_EXPECTED_ROWS)
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument(
        "--allow-non-greedy-acquisition",
        action="store_true",
        help="Allow acquire_candidates() to choose any valid unique batch instead of enforcing greedy Top-K by final_score.",
    )
    args = parser.parse_args()
    start = time.monotonic()
    status = "ok"
    summary: dict[str, object] = {}
    try:
        scored, feature_columns = load_inputs(args.base_scored_csv, args.feature_columns_json, expected_rows=args.expected_rows)
        manifest = load_and_validate_manifest(args.split_manifest, scored)
        strategy_module = load_strategy_module(args.strategy_path)
        all_metrics, aggregate, summary = run_protocol(
            scored,
            feature_columns,
            manifest,
            strategy_module,
            evaluation_partition="dev",
            rounds=args.rounds,
            batch_size=args.batch_size,
            top_k=args.top_k,
            reference_random=args.reference_random,
            allow_non_greedy_acquisition=args.allow_non_greedy_acquisition,
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        all_metrics.to_csv(args.output_dir / "all_round_metrics.csv", index=False)
        aggregate.to_csv(args.output_dir / "aggregate_round_metrics.csv", index=False)
        write_json(args.output_dir / "summary.json", summary)
        write_json(
            args.output_dir / "run_manifest.json",
            {
                "base_scored_csv": str(args.base_scored_csv),
                "feature_columns_json": str(args.feature_columns_json),
                "split_manifest": str(args.split_manifest),
                "strategy_path": str(args.strategy_path),
                "evaluation_partition": "dev",
                "reference_random": bool(args.reference_random),
                "allow_non_greedy_acquisition": bool(args.allow_non_greedy_acquisition),
                "rounds": int(args.rounds),
                "batch_size": int(args.batch_size),
                "top_k": int(args.top_k),
                "seeds": [entry["seed"] for entry in manifest["seeds"]],
            },
        )
    except ValueError:
        status = "invalid"
        raise
    except Exception:
        status = "failed"
        raise
    finally:
        elapsed = time.monotonic() - start
        append_result(
            args.results_tsv,
            {
                "experiment_id": args.experiment_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "strategy_summary": args.strategy_summary,
                "status": status,
                "round10_dev_ndcg_at_50_mean": summary.get("round10_dev_ndcg_at_50_mean", ""),
                "round10_dev_ndcg_at_50_std": summary.get("round10_dev_ndcg_at_50_std", ""),
                "round10_dev_top50_true_activity_mean": summary.get("round10_dev_top50_true_activity_mean", ""),
                "round10_dev_top50_median_logfold_change": summary.get("round10_dev_top50_median_logfold_change", ""),
                "round10_dev_acquired_base_rank_top50_count_mean": summary.get("round10_dev_acquired_base_rank_top50_count_mean", ""),
                "round10_dev_acquired_base_rank_median_mean": summary.get("round10_dev_acquired_base_rank_median_mean", ""),
                "round10_dev_acquired_base_rank_percentile_mean": summary.get("round10_dev_acquired_base_rank_percentile_mean", ""),
                "round10_dev_spearman_mean": summary.get("round10_dev_spearman_mean", ""),
                "elapsed_seconds": elapsed,
                "kept": args.kept,
            },
        )
    print(json.dumps({"status": status, **summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
