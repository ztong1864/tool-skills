#!/usr/bin/env python3
"""Validate a feedback task config and resolve one round's effective batch size."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL = (
    "task_name",
    "dataset_name",
    "disease_name",
    "candidate_table",
    "candidate_id_col",
    "target_col",
    "higher_is_better",
    "base_score_col",
    "smiles_col",
    "feature_columns_json",
    "activity_score_transform",
    "campaign",
    "strategy",
)


def positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a positive integer")
    try:
        numeric = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a positive integer") from exc
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{field} must be a positive integer")
    if isinstance(value, str) and value.strip() != str(numeric):
        raise ValueError(f"{field} must be a positive integer")
    if numeric <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return numeric


def nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a nonnegative integer")
    try:
        numeric = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a nonnegative integer") from exc
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{field} must be a nonnegative integer")
    if isinstance(value, str) and value.strip() != str(numeric):
        raise ValueError(f"{field} must be a nonnegative integer")
    if numeric < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return numeric


def validate_config(config: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_TOP_LEVEL if field not in config]
    if missing:
        raise ValueError(f"missing required config fields: {', '.join(missing)}")
    if config["higher_is_better"] is not True:
        raise ValueError("V1 canonical activity_score requires higher_is_better=true")

    transform = config["activity_score_transform"]
    if not isinstance(transform, dict) or not str(transform.get("version", "")).strip():
        raise ValueError("activity_score_transform.version is required")
    minimum = float(transform.get("minimum", math.nan))
    maximum = float(transform.get("maximum", math.nan))
    if minimum != 0.0 or maximum != 1.0:
        raise ValueError("V1 activity_score range must be [0, 1]")

    campaign = config["campaign"]
    if not isinstance(campaign, dict):
        raise ValueError("campaign must be an object")
    rounds = positive_int(campaign.get("num_rounds"), "campaign.num_rounds")
    positive_int(campaign.get("batch_size", 50), "campaign.batch_size")
    positive_int(campaign.get("max_total_candidates"), "campaign.max_total_candidates")

    schedule = campaign.get("round_batch_sizes", {})
    if not isinstance(schedule, dict):
        raise ValueError("campaign.round_batch_sizes must be an object")
    for key, value in schedule.items():
        round_number = positive_int(key, f"round_batch_sizes key {key!r}")
        if round_number > rounds:
            raise ValueError(f"round_batch_sizes round {round_number} exceeds campaign.num_rounds")
        positive_int(value, f"campaign.round_batch_sizes[{key!r}]")

    strategy = config["strategy"]
    if not isinstance(strategy, dict) or not str(strategy.get("strategy_version", "")).strip():
        raise ValueError("strategy.strategy_version is required")
    positive_int(strategy.get("min_feedback_to_fit", 30), "strategy.min_feedback_to_fit")


def resolve_batch_size(
    config: dict[str, Any],
    round_number: int,
    override: int | None,
    already_selected: int,
    remaining_candidates: int | None,
) -> dict[str, Any]:
    campaign = config["campaign"]
    num_rounds = positive_int(campaign["num_rounds"], "campaign.num_rounds")
    if round_number > num_rounds:
        raise ValueError(f"round {round_number} exceeds configured num_rounds={num_rounds}")

    if override is not None:
        if campaign.get("allow_runtime_batch_size_override", True) is not True:
            raise ValueError("runtime batch-size override is disabled by the task config")
        requested = positive_int(override, "--batch-size")
        source = "runtime_override"
    else:
        schedule = campaign.get("round_batch_sizes", {})
        if str(round_number) in schedule:
            requested = positive_int(schedule[str(round_number)], f"round_batch_sizes[{round_number}]")
            source = "round_schedule"
        else:
            requested = positive_int(campaign.get("batch_size", 50), "campaign.batch_size")
            source = "campaign_default"

    budget = positive_int(campaign["max_total_candidates"], "campaign.max_total_candidates")
    budget_remaining = max(0, budget - already_selected)
    caps = {"campaign_budget_remaining": budget_remaining}
    effective = min(requested, budget_remaining)
    if remaining_candidates is not None:
        caps["eligible_candidates_remaining"] = remaining_candidates
        effective = min(effective, remaining_candidates)

    cap_reasons = [name for name, value in caps.items() if value < requested]
    return {
        "round": round_number,
        "requested_batch_size": requested,
        "effective_batch_size": effective,
        "batch_size_source": source,
        "already_selected": already_selected,
        "caps": caps,
        "cap_applied": bool(cap_reasons),
        "cap_reasons": cap_reasons,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--round", type=int, default=1, dest="round_number")
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--already-selected", type=int, default=0)
    parser.add_argument("--remaining-candidates", type=int, default=None)
    parser.add_argument("--valid-feedback", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise ValueError("task config root must be a JSON object")
        validate_config(config)
        round_number = positive_int(args.round_number, "--round")
        already_selected = nonnegative_int(args.already_selected, "--already-selected")
        valid_feedback = nonnegative_int(args.valid_feedback, "--valid-feedback")
        remaining = None
        if args.remaining_candidates is not None:
            remaining = nonnegative_int(args.remaining_candidates, "--remaining-candidates")
        resolution = resolve_batch_size(
            config,
            round_number=round_number,
            override=args.batch_size,
            already_selected=already_selected,
            remaining_candidates=remaining,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc

    result = {
        "valid": True,
        "task_name": config["task_name"],
        "strategy_version": config["strategy"]["strategy_version"],
        "valid_feedback": valid_feedback,
        "feedback_model_enabled": valid_feedback >= int(config["strategy"].get("min_feedback_to_fit", 30)),
        **resolution,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
