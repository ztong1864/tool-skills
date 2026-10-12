#!/usr/bin/env python3
"""PRISM evaluator adapter for model-agnostic AutoResearch Core."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from autoresearch_backend import CandidateSpec, render_strategy, validate_spec
from run_acquisition_eval import evaluate

HERE = Path(__file__).resolve().parent


def evaluate_strategy(strategy_path: Path, output_dir: Path, rounds: int, batch_size: int, top_k: int) -> dict:
    eval_dir = output_dir / "evaluation"
    summary = evaluate(
        HERE / "base_scored_oracle.csv",
        HERE / "feature_columns.json",
        HERE / "split_manifest.json",
        strategy_path,
        eval_dir,
        4684,
        rounds,
        batch_size,
        top_k,
    )
    return {
        **summary,
        "artifacts": [str(strategy_path.resolve()), str((eval_dir / "summary.json").resolve())],
    }


def proposal_to_spec(payload: dict, batch_size: int, rounds: int) -> CandidateSpec:
    spec = CandidateSpec(
        candidate_id=payload["candidate_id"],
        estimator=payload["estimator"],
        parameters=payload["parameters"],
        base_weight=float(payload["base_weight"]),
        calibrated_transform=payload.get("calibrated_transform", "clip"),
        explore_count=int(payload.get("explore_count", 0)),
        shortlist_size=int(payload.get("shortlist_size", 150)),
        similarity_threshold=float(payload.get("similarity_threshold", 0.8)),
        explore_until_round=int(payload.get("explore_until_round", 0)),
        summary=payload.get("summary", ""),
        rationale=payload.get("rationale", ""),
    )
    validate_spec(spec, batch_size, rounds)
    return spec


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("baseline", "trial"):
        item = sub.add_parser(name)
        item.add_argument("--output-dir", type=Path, required=True)
        item.add_argument("--rounds", type=int, required=True)
        item.add_argument("--batch-size", type=int, required=True)
        item.add_argument("--top-k", type=int, required=True)
        if name == "trial":
            item.add_argument("--proposal", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    strategy_path = args.output_dir / "strategy.py"
    if args.command == "baseline":
        shutil.copy2(HERE / "strategy.py", strategy_path)
    else:
        proposal = json.loads(args.proposal.read_text(encoding="utf-8"))
        if not isinstance(proposal, dict):
            raise SystemExit("ERROR: proposal must be a JSON object")
        spec = proposal_to_spec(proposal, args.batch_size, args.rounds)
        strategy_path.write_text(render_strategy(spec), encoding="utf-8")
    result = evaluate_strategy(strategy_path, args.output_dir, args.rounds, args.batch_size, args.top_k)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
