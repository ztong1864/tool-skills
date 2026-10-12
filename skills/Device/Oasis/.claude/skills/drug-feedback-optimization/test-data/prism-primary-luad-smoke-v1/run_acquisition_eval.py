#!/usr/bin/env python3
"""Evaluate a feedback strategy with oracle-normalized cumulative acquisition gain."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from protocol import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_EXPECTED_ROWS,
    DEFAULT_ROUNDS,
    DEFAULT_TOP_K,
    load_and_validate_manifest,
    load_inputs,
    load_strategy_module,
    run_protocol,
    write_json,
)

HERE = Path(__file__).resolve().parent


def build_acquisition_metrics(
    all_metrics: pd.DataFrame,
    scored: pd.DataFrame,
    manifest: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    activities = scored.set_index("candidate_id")["activity_score"].astype(float)
    curve_rows: list[dict[str, float | int]] = []
    seed_rows: list[dict[str, float | int]] = []
    for split in manifest["seeds"]:
        seed = int(split["seed"])
        oracle = activities.loc[list(map(str, split["acquisition_pool_ids"]))].sort_values(ascending=False).to_numpy()
        seed_metrics = all_metrics[(all_metrics["seed"] == seed) & (all_metrics["round"] > 0)].sort_values("round")
        cumulative_activity = 0.0
        cumulative_budget = 0
        weighted_ncg = 0.0
        final_ncg = float("nan")
        for row in seed_metrics.itertuples(index=False):
            acquired = int(row.acquired_rows)
            acquired_sum = float(row.acquired_activity_mean) * acquired
            cumulative_activity += acquired_sum
            cumulative_budget += acquired
            oracle_sum = float(oracle[:cumulative_budget].sum())
            ncg = cumulative_activity / oracle_sum if oracle_sum > 0 else float("nan")
            weighted_ncg += ncg * acquired
            final_ncg = ncg
            curve_rows.append(
                {
                    "seed": seed,
                    "round": int(row.round),
                    "acquired_rows": acquired,
                    "cumulative_budget": cumulative_budget,
                    "acquired_activity_sum": acquired_sum,
                    "cumulative_acquired_activity": cumulative_activity,
                    "oracle_cumulative_activity": oracle_sum,
                    "acquisition_ncg": ncg,
                }
            )
        if cumulative_budget == 0:
            raise ValueError(f"Seed {seed} acquired no candidates.")
        seed_rows.append(
            {
                "seed": seed,
                "acquisition_ncg_auc": weighted_ncg / cumulative_budget,
                "final_acquisition_ncg": final_ncg,
                "cumulative_acquired_activity": cumulative_activity,
                "total_acquired": cumulative_budget,
            }
        )
    curve = pd.DataFrame(curve_rows)
    per_seed = pd.DataFrame(seed_rows)
    summary = {
        "acquisition_ncg_auc_mean": float(per_seed["acquisition_ncg_auc"].mean()),
        "acquisition_ncg_auc_std": float(per_seed["acquisition_ncg_auc"].std()),
        "final_acquisition_ncg_mean": float(per_seed["final_acquisition_ncg"].mean()),
        "final_acquisition_ncg_std": float(per_seed["final_acquisition_ncg"].std()),
        "cumulative_acquired_activity_mean": float(per_seed["cumulative_acquired_activity"].mean()),
        "total_acquired_per_seed": int(per_seed["total_acquired"].iloc[0]),
    }
    return curve, per_seed, summary


def evaluate(
    base_scored_csv: Path,
    feature_columns_json: Path,
    split_manifest: Path,
    strategy_path: Path,
    output_dir: Path,
    expected_rows: int,
    rounds: int,
    batch_size: int,
    top_k: int,
) -> dict[str, Any]:
    scored, feature_columns = load_inputs(base_scored_csv, feature_columns_json, expected_rows=expected_rows)
    manifest = load_and_validate_manifest(split_manifest, scored)
    strategy = load_strategy_module(strategy_path)
    all_metrics, aggregate, ranking_summary = run_protocol(
        scored,
        feature_columns,
        manifest,
        strategy,
        evaluation_partition="dev",
        rounds=rounds,
        batch_size=batch_size,
        top_k=top_k,
        allow_non_greedy_acquisition=True,
    )
    curve, per_seed, acquisition_summary = build_acquisition_metrics(all_metrics, scored, manifest)
    summary: dict[str, Any] = {
        "status": "ok",
        "dataset": "PRISM_primary_LUAD",
        "evaluation_partition": "dev",
        "primary_metric": "acquisition_ncg_auc_mean",
        "rounds": int(rounds),
        "batch_size": int(batch_size),
        "top_k": int(top_k),
        **acquisition_summary,
        "ranking_metrics": ranking_summary,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    all_metrics.to_csv(output_dir / "all_round_metrics.csv", index=False)
    aggregate.to_csv(output_dir / "aggregate_round_metrics.csv", index=False)
    curve.to_csv(output_dir / "acquisition_curve.csv", index=False)
    per_seed.to_csv(output_dir / "seed_acquisition_metrics.csv", index=False)
    write_json(output_dir / "summary.json", summary)
    write_json(
        output_dir / "run_manifest.json",
        {
            "base_scored_csv": str(base_scored_csv.resolve()),
            "feature_columns_json": str(feature_columns_json.resolve()),
            "split_manifest": str(split_manifest.resolve()),
            "strategy_path": str(strategy_path.resolve()),
            "rounds": int(rounds),
            "batch_size": int(batch_size),
            "top_k": int(top_k),
            "seeds": [int(item["seed"]) for item in manifest["seeds"]],
            "labels_visible_to_strategy": False,
        },
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-scored-csv", type=Path, default=HERE / "base_scored_oracle.csv")
    parser.add_argument("--feature-columns-json", type=Path, default=HERE / "feature_columns.json")
    parser.add_argument("--split-manifest", type=Path, default=HERE / "split_manifest.json")
    parser.add_argument("--strategy-path", type=Path, default=HERE / "strategy.py")
    parser.add_argument("--output-dir", type=Path, default=HERE / "acquisition_eval_output")
    parser.add_argument("--expected-rows", type=int, default=DEFAULT_EXPECTED_ROWS)
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if min(args.rounds, args.batch_size, args.top_k) <= 0:
        raise SystemExit("ERROR: rounds, batch-size, and top-k must be positive")
    summary = evaluate(
        args.base_scored_csv,
        args.feature_columns_json,
        args.split_manifest,
        args.strategy_path,
        args.output_dir,
        args.expected_rows,
        args.rounds,
        args.batch_size,
        args.top_k,
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
