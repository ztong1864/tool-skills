#!/usr/bin/env python3
"""Controlled Auto-Research backend for the bundled PRISM feedback benchmark."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from run_acquisition_eval import evaluate

HERE = Path(__file__).resolve().parent
PRIMARY_METRIC = "acquisition_ncg_auc_mean"
RESULT_FIELDS = (
    "iteration",
    "candidate_id",
    "status",
    "kept",
    "estimator",
    "base_weight",
    "calibrated_transform",
    "explore_count",
    "shortlist_size",
    "similarity_threshold",
    "explore_until_round",
    "acquisition_ncg_auc_mean",
    "final_acquisition_ncg_mean",
    "cumulative_acquired_activity_mean",
    "summary",
    "rationale",
)

ESTIMATORS = {
    "RandomForestRegressor": {
        "import": "from sklearn.ensemble import RandomForestRegressor",
        "parameters": {"n_estimators", "min_samples_leaf", "max_features", "max_depth", "n_jobs"},
    },
    "ExtraTreesRegressor": {
        "import": "from sklearn.ensemble import ExtraTreesRegressor",
        "parameters": {"n_estimators", "min_samples_leaf", "max_features", "max_depth", "n_jobs"},
    },
    "HistGradientBoostingRegressor": {
        "import": "from sklearn.ensemble import HistGradientBoostingRegressor",
        "parameters": {"max_iter", "learning_rate", "max_leaf_nodes", "max_depth", "min_samples_leaf", "l2_regularization"},
    },
}


@dataclass(frozen=True)
class CandidateSpec:
    candidate_id: str
    estimator: str
    parameters: dict[str, Any]
    base_weight: float
    calibrated_transform: str = "clip"
    explore_count: int = 0
    shortlist_size: int = 150
    similarity_threshold: float = 0.80
    explore_until_round: int = 0
    summary: str = ""
    rationale: str = ""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dependency_versions() -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for package in ("numpy", "pandas", "scipy", "scikit-learn"):
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[package] = None
    return result


def validate_spec(spec: CandidateSpec, batch_size: int, rounds: int) -> None:
    if re.fullmatch(r"[A-Za-z0-9_.-]+", spec.candidate_id) is None:
        raise ValueError("candidate_id may contain only letters, numbers, underscores, dots, and hyphens")
    if spec.estimator not in ESTIMATORS:
        raise ValueError(f"estimator must be one of {sorted(ESTIMATORS)}")
    unknown = sorted(set(spec.parameters).difference(ESTIMATORS[spec.estimator]["parameters"]))
    if unknown:
        raise ValueError(f"unsupported parameters for {spec.estimator}: {unknown}")
    if "random_state" in spec.parameters:
        raise ValueError("random_state is controlled by the evaluator")
    if not 0.0 <= float(spec.base_weight) <= 1.0:
        raise ValueError("base_weight must be in [0, 1]")
    if spec.calibrated_transform not in {"clip", "rank", "sigmoid"}:
        raise ValueError("calibrated_transform must be clip, rank, or sigmoid")
    if not 0 <= int(spec.explore_count) <= 15:
        raise ValueError("explore_count must be between 0 and 15")
    if int(spec.explore_count) >= int(batch_size):
        raise ValueError("explore_count must be smaller than batch_size")
    if int(spec.shortlist_size) < int(batch_size) or int(spec.shortlist_size) > 500:
        raise ValueError("shortlist_size must be between batch_size and 500")
    if not 0.0 <= float(spec.similarity_threshold) <= 1.0:
        raise ValueError("similarity_threshold must be in [0, 1]")
    if not 0 <= int(spec.explore_until_round) <= int(rounds):
        raise ValueError("explore_until_round must be between 0 and configured rounds")
    if spec.explore_count > 0 and spec.explore_until_round == 0:
        raise ValueError("explore_until_round must be positive when explore_count is positive")
    for key in ("n_estimators", "max_iter"):
        if key in spec.parameters and not 1 <= int(spec.parameters[key]) <= 2000:
            raise ValueError(f"{key} must be between 1 and 2000")
    for key in ("learning_rate", "max_features"):
        if key in spec.parameters and isinstance(spec.parameters[key], (int, float)):
            if not 0.0 < float(spec.parameters[key]) <= 1.0:
                raise ValueError(f"{key} must be in (0, 1]")


def render_strategy(spec: CandidateSpec) -> str:
    estimator = ESTIMATORS[spec.estimator]
    parameter_lines = [f"        {key}={value!r}," for key, value in spec.parameters.items()]
    parameter_lines.append("        random_state=int(seed),")
    parameters = "\n".join(parameter_lines)
    if spec.calibrated_transform == "clip":
        transform = "np.clip(raw_prediction, 0.0, 1.0)"
    elif spec.calibrated_transform == "rank":
        transform = "pd.Series(raw_prediction).rank(pct=True, method='average').to_numpy()"
    else:
        transform = "1.0 / (1.0 + np.exp(-raw_prediction))"
    return f'''"""Auto-Research candidate {spec.candidate_id}."""

+from __future__ import annotations
+
+import numpy as np
+import pandas as pd
+{estimator["import"]}
+
+BASE_WEIGHT = {float(spec.base_weight)!r}
+EXPLORE_COUNT = {int(spec.explore_count)!r}
+SHORTLIST_SIZE = {int(spec.shortlist_size)!r}
+SIMILARITY_THRESHOLD = {float(spec.similarity_threshold)!r}
+EXPLORE_UNTIL_ROUND = {int(spec.explore_until_round)!r}
+
+
+def fit_strategy(observed_df: pd.DataFrame, feature_columns: list[str], seed: int):
+    train = observed_df.dropna(subset=feature_columns + ["activity_score"]).copy()
+    if len(train) < 10:
+        raise ValueError("Need at least 10 observed feedback rows to train the strategy.")
+    model = {spec.estimator}(
+{parameters}
+    )
+    model.fit(train[feature_columns], train["activity_score"].astype(float))
+    return model
+
+
+def score_candidates(model_state, candidate_df: pd.DataFrame, feature_columns: list[str], seed: int) -> pd.DataFrame:
+    del seed
+    scored = candidate_df.copy()
+    raw_prediction = model_state.predict(scored[feature_columns])
+    scored["calibrated_score"] = {transform}
+    scored["final_score"] = np.clip(
+        BASE_WEIGHT * scored["base_score"].astype(float)
+        + (1.0 - BASE_WEIGHT) * scored["calibrated_score"].astype(float),
+        0.0,
+        1.0,
+    )
+    return scored
+
+
+def _max_tanimoto(candidate: np.ndarray, selected: np.ndarray) -> float:
+    if selected.size == 0:
+        return 0.0
+    intersections = selected @ candidate
+    unions = selected.sum(axis=1) + candidate.sum() - intersections
+    similarities = np.divide(intersections, unions, out=np.zeros_like(intersections, dtype=float), where=unions > 0)
+    return float(similarities.max(initial=0.0))
+
+
+def acquire_candidates(scored_pool: pd.DataFrame, batch_size: int, round_index: int, seed: int) -> pd.DataFrame:
+    del seed
+    ordered = scored_pool.sort_values(["final_score", "candidate_id"], ascending=[False, True]).reset_index(drop=True)
+    explore = EXPLORE_COUNT if 0 < int(round_index) <= EXPLORE_UNTIL_ROUND else 0
+    if explore <= 0:
+        return ordered.head(int(batch_size)).copy().reset_index(drop=True)
+    explore = min(int(explore), int(batch_size) - 1)
+    top_count = int(batch_size) - explore
+    selected = ordered.head(top_count).copy()
+    shortlist = ordered.head(max(int(batch_size), int(SHORTLIST_SIZE))).iloc[top_count:].copy()
+    fp_columns = [column for column in ordered.columns if column.startswith("morgan_fp_")]
+    if not fp_columns or shortlist.empty:
+        return ordered.head(int(batch_size)).copy().reset_index(drop=True)
+    while len(selected) < min(int(batch_size), len(ordered)) and not shortlist.empty:
+        selected_fp = selected[fp_columns].to_numpy(dtype=float)
+        choices = []
+        for index, row in shortlist.iterrows():
+            max_similarity = _max_tanimoto(row[fp_columns].to_numpy(dtype=float), selected_fp)
+            choices.append((max_similarity > SIMILARITY_THRESHOLD, max_similarity, -float(row["final_score"]), str(row["candidate_id"]), index))
+        _, _, _, _, chosen_index = min(choices)
+        selected = pd.concat([selected, shortlist.loc[[chosen_index]]], ignore_index=True)
+        shortlist = shortlist.drop(index=chosen_index)
+    if len(selected) < min(int(batch_size), len(ordered)):
+        missing = int(batch_size) - len(selected)
+        remaining = ordered[~ordered["candidate_id"].astype(str).isin(set(selected["candidate_id"].astype(str)))]
+        selected = pd.concat([selected, remaining.head(missing)], ignore_index=True)
+    return selected.head(int(batch_size)).copy().reset_index(drop=True)
+'''.replace("\n+", "\n")


def append_result(path: Path, row: dict[str, Any]) -> None:
    exists = path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=RESULT_FIELDS, delimiter="\t")
        if not exists:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in RESULT_FIELDS})


def evaluate_path(strategy_path: Path, eval_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    return evaluate(
        HERE / "base_scored_oracle.csv",
        HERE / "feature_columns.json",
        HERE / "split_manifest.json",
        strategy_path,
        eval_dir,
        4684,
        int(manifest["rounds"]),
        int(manifest["batch_size"]),
        int(manifest["top_k"]),
    )


def load_manifest(output_root: Path) -> dict[str, Any]:
    path = output_root / "campaign_manifest.json"
    if not path.exists():
        raise ValueError(f"campaign is not initialized: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(output_root: Path, manifest: dict[str, Any]) -> None:
    manifest["updated_at"] = now_iso()
    write_json(output_root / "campaign_manifest.json", manifest)


def command_init(args: argparse.Namespace) -> dict[str, Any]:
    output_root = args.output_root.resolve()
    manifest_path = output_root / "campaign_manifest.json"
    if manifest_path.exists():
        return load_manifest(output_root)
    if min(args.rounds, args.batch_size, args.top_k, args.budget, args.patience) <= 0:
        raise ValueError("rounds, batch-size, top-k, budget, and patience must be positive")
    output_root.mkdir(parents=True, exist_ok=True)
    baseline_strategy = output_root / "baseline_strategy.py"
    best_strategy = output_root / "best_strategy.py"
    shutil.copyfile(args.strategy_path, baseline_strategy)
    shutil.copyfile(args.strategy_path, best_strategy)
    provisional = {
        "rounds": int(args.rounds),
        "batch_size": int(args.batch_size),
        "top_k": int(args.top_k),
    }
    baseline_summary = evaluate_path(baseline_strategy, output_root / "evaluations" / "baseline", provisional)
    baseline_winner = {
        "candidate_id": "baseline",
        "iteration": 0,
        "strategy_path": str(best_strategy),
        "eval_dir": str(output_root / "evaluations" / "baseline"),
        "spec": {"type": "baseline", "source": str(args.strategy_path.resolve())},
        "summary": baseline_summary,
    }
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "campaign_id": args.campaign_id,
        "status": "active",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "primary_metric": PRIMARY_METRIC,
        "direction": "higher",
        "rounds": int(args.rounds),
        "batch_size": int(args.batch_size),
        "top_k": int(args.top_k),
        "trial_budget": int(args.budget),
        "patience": int(args.patience),
        "completed_trials": 0,
        "consecutive_non_improvements": 0,
        "baseline": baseline_winner,
        "current_winner": baseline_winner,
        "dependency_versions": dependency_versions(),
        "frozen_inputs": {
            name: {"path": str((HERE / name).resolve()), "sha256": file_sha256(HERE / name)}
            for name in ("base_scored_oracle.csv", "feature_columns.json", "split_manifest.json", "protocol.py", "run_acquisition_eval.py", "autoresearch_backend.py", "guard_autoresearch.py", "search_space.json")
        },
        "locked_test_allowed": False,
    }
    save_manifest(output_root, manifest)
    append_result(
        output_root / "results.tsv",
        {
            "iteration": 0,
            "candidate_id": "baseline",
            "status": "ok",
            "kept": "true",
            PRIMARY_METRIC: baseline_summary[PRIMARY_METRIC],
            "final_acquisition_ncg_mean": baseline_summary["final_acquisition_ncg_mean"],
            "cumulative_acquired_activity_mean": baseline_summary["cumulative_acquired_activity_mean"],
            "summary": "Frozen starting strategy",
        },
    )
    return manifest


def command_trial(args: argparse.Namespace) -> dict[str, Any]:
    output_root = args.output_root.resolve()
    manifest = load_manifest(output_root)
    if manifest["status"] != "active":
        raise ValueError(f"campaign is not active: {manifest['status']}")
    iteration = int(manifest["completed_trials"]) + 1
    if iteration > int(manifest["trial_budget"]):
        raise ValueError("trial budget is exhausted")
    seen = set()
    results_path = output_root / "results.tsv"
    if results_path.exists():
        with results_path.open(encoding="utf-8", newline="") as stream:
            seen = {row["candidate_id"] for row in csv.DictReader(stream, delimiter="\t")}
    if args.candidate_id in seen:
        raise ValueError(f"candidate_id already evaluated: {args.candidate_id}")
    parameters = json.loads(args.parameters_json)
    if not isinstance(parameters, dict):
        raise ValueError("parameters-json must decode to an object")
    spec = CandidateSpec(
        candidate_id=args.candidate_id,
        estimator=args.estimator,
        parameters=parameters,
        base_weight=args.base_weight,
        calibrated_transform=args.calibrated_transform,
        explore_count=args.explore_count,
        shortlist_size=args.shortlist_size,
        similarity_threshold=args.similarity_threshold,
        explore_until_round=args.explore_until_round,
        summary=args.summary,
        rationale=args.rationale,
    )
    validate_spec(spec, int(manifest["batch_size"]), int(manifest["rounds"]))
    candidate_path = output_root / "candidates" / f"{spec.candidate_id}.py"
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_path.write_text(render_strategy(spec), encoding="utf-8")
    eval_dir = output_root / "evaluations" / spec.candidate_id
    summary = evaluate_path(candidate_path, eval_dir, manifest)
    current_metric = float(manifest["current_winner"]["summary"][PRIMARY_METRIC])
    candidate_metric = float(summary[PRIMARY_METRIC])
    kept = candidate_metric > current_metric + 1e-12
    if kept:
        shutil.copyfile(candidate_path, output_root / "best_strategy.py")
        manifest["current_winner"] = {
            "candidate_id": spec.candidate_id,
            "iteration": iteration,
            "strategy_path": str(output_root / "best_strategy.py"),
            "eval_dir": str(eval_dir),
            "spec": asdict(spec),
            "summary": summary,
        }
        manifest["consecutive_non_improvements"] = 0
    else:
        manifest["consecutive_non_improvements"] = int(manifest["consecutive_non_improvements"]) + 1
    manifest["completed_trials"] = iteration
    if iteration >= int(manifest["trial_budget"]):
        manifest["status"] = "completed_budget"
    elif int(manifest["consecutive_non_improvements"]) >= int(manifest["patience"]):
        manifest["status"] = "stopped_patience"
    save_manifest(output_root, manifest)
    record = {
        "iteration": iteration,
        "candidate_id": spec.candidate_id,
        "status": "ok",
        "kept": str(kept).lower(),
        **asdict(spec),
        PRIMARY_METRIC: candidate_metric,
        "final_acquisition_ncg_mean": summary["final_acquisition_ncg_mean"],
        "cumulative_acquired_activity_mean": summary["cumulative_acquired_activity_mean"],
    }
    append_result(results_path, record)
    with (output_root / "trials.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({**record, "metrics": summary, "completed_at": now_iso()}, ensure_ascii=False) + "\n")
    return {"status": "ok", "kept": kept, "iteration": iteration, "candidate_id": spec.candidate_id, **summary}


def paired_bootstrap(differences: np.ndarray, draws: int = 5000) -> tuple[float, float]:
    rng = np.random.default_rng(20260921)
    indices = rng.integers(0, len(differences), size=(draws, len(differences)))
    means = differences[indices].mean(axis=1)
    low, high = np.quantile(means, [0.025, 0.975])
    return float(low), float(high)


def command_freeze(args: argparse.Namespace) -> dict[str, Any]:
    output_root = args.output_root.resolve()
    manifest = load_manifest(output_root)
    baseline = pd.read_csv(Path(manifest["baseline"]["eval_dir"]) / "seed_acquisition_metrics.csv")
    winner = pd.read_csv(Path(manifest["current_winner"]["eval_dir"]) / "seed_acquisition_metrics.csv")
    paired = baseline.merge(winner, on="seed", suffixes=("_baseline", "_winner"), validate="one_to_one")
    differences = paired["acquisition_ncg_auc_winner"].to_numpy() - paired["acquisition_ncg_auc_baseline"].to_numpy()
    final_differences = paired["final_acquisition_ncg_winner"].to_numpy() - paired["final_acquisition_ncg_baseline"].to_numpy()
    ci_low, ci_high = paired_bootstrap(differences)
    mean_improvement = float(differences.mean())
    positive_fraction = float((differences > 0).mean())
    stable = mean_improvement > 0 and ci_low > 0 and positive_fraction >= 0.70 and float(final_differences.mean()) >= 0
    baseline_retained = manifest["current_winner"]["candidate_id"] == "baseline"
    if stable:
        selection_status = "stable_winner"
    elif baseline_retained:
        selection_status = "baseline_retained"
    elif mean_improvement > 0:
        selection_status = "exploratory"
    else:
        selection_status = "rejected"
    if selection_status == "exploratory" and not args.allow_exploratory:
        raise ValueError("best candidate is exploratory; pass --allow-exploratory to freeze it with that label")
    if selection_status == "rejected":
        raise ValueError("best candidate does not improve the baseline")
    if re.fullmatch(r"[A-Za-z0-9_.-]+", args.strategy_version) is None:
        raise ValueError("strategy-version contains unsupported characters")
    target = output_root / "frozen" / args.strategy_version
    if target.exists():
        raise ValueError(f"strategy version already exists: {target}")
    target.mkdir(parents=True)
    shutil.copyfile(output_root / "best_strategy.py", target / "strategy.py")
    write_json(target / "strategy_config.json", manifest["current_winner"]["spec"])
    comparison = {
        "selection_status": selection_status,
        "primary_metric": PRIMARY_METRIC,
        "baseline_mean": float(manifest["baseline"]["summary"][PRIMARY_METRIC]),
        "winner_mean": float(manifest["current_winner"]["summary"][PRIMARY_METRIC]),
        "mean_improvement": mean_improvement,
        "paired_bootstrap_95_ci": [ci_low, ci_high],
        "positive_seed_fraction": positive_fraction,
        "final_ncg_mean_improvement": float(final_differences.mean()),
        "seed_count": int(len(paired)),
    }
    write_json(target / "metrics_summary.json", {"winner": manifest["current_winner"]["summary"], "comparison": comparison})
    provenance = {
        "strategy_version": args.strategy_version,
        "created_at": now_iso(),
        "campaign_id": manifest["campaign_id"],
        "strategy_sha256": file_sha256(target / "strategy.py"),
        "frozen_inputs": manifest["frozen_inputs"],
        "dependency_versions": manifest["dependency_versions"],
        "rounds": manifest["rounds"],
        "batch_size": manifest["batch_size"],
        "top_k": manifest["top_k"],
    }
    write_json(target / "provenance.json", provenance)
    report = f"""# Strategy selection report

- Strategy version: `{args.strategy_version}`
- Selection status: `{selection_status}`
- Winner candidate: `{manifest['current_winner']['candidate_id']}`
- Primary metric: `{PRIMARY_METRIC}`
- Baseline mean: `{comparison['baseline_mean']:.8f}`
- Winner mean: `{comparison['winner_mean']:.8f}`
- Mean paired improvement: `{mean_improvement:.8f}`
- Paired bootstrap 95% CI: `[{ci_low:.8f}, {ci_high:.8f}]`
- Positive seed fraction: `{positive_fraction:.2%}`
- Final NCG mean improvement: `{comparison['final_ncg_mean_improvement']:.8f}`

This strategy was selected only on the fixed development protocol. Locked-test or prospective evidence is not included.
"""
    (target / "selection_report.md").write_text(report, encoding="utf-8")
    return {"status": "frozen", "strategy_version": args.strategy_version, "output_dir": str(target), **comparison}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    init = subparsers.add_parser("init")
    init.add_argument("--output-root", type=Path, default=HERE / "autoresearch-results")
    init.add_argument("--campaign-id", default="prism_primary_luad_v1")
    init.add_argument("--strategy-path", type=Path, default=HERE / "strategy.py")
    init.add_argument("--rounds", type=int, default=10)
    init.add_argument("--batch-size", type=int, default=50)
    init.add_argument("--top-k", type=int, default=50)
    init.add_argument("--budget", type=int, default=30)
    init.add_argument("--patience", type=int, default=8)
    trial = subparsers.add_parser("trial")
    trial.add_argument("--output-root", type=Path, default=HERE / "autoresearch-results")
    trial.add_argument("--candidate-id", required=True)
    trial.add_argument("--estimator", choices=sorted(ESTIMATORS), required=True)
    trial.add_argument("--parameters-json", required=True)
    trial.add_argument("--base-weight", type=float, required=True)
    trial.add_argument("--calibrated-transform", choices=["clip", "rank", "sigmoid"], default="clip")
    trial.add_argument("--explore-count", type=int, default=0)
    trial.add_argument("--shortlist-size", type=int, default=150)
    trial.add_argument("--similarity-threshold", type=float, default=0.80)
    trial.add_argument("--explore-until-round", type=int, default=0)
    trial.add_argument("--summary", required=True)
    trial.add_argument("--rationale", required=True)
    status = subparsers.add_parser("status")
    status.add_argument("--output-root", type=Path, default=HERE / "autoresearch-results")
    freeze = subparsers.add_parser("freeze")
    freeze.add_argument("--output-root", type=Path, default=HERE / "autoresearch-results")
    freeze.add_argument("--strategy-version", required=True)
    freeze.add_argument("--allow-exploratory", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "init":
            result = command_init(args)
        elif args.command == "trial":
            result = command_trial(args)
        elif args.command == "status":
            result = load_manifest(args.output_root.resolve())
        else:
            result = command_freeze(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
