"""Fixed evaluator for autoresearch-style PRISM primary LUAD strategy search."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import mean_absolute_error, mean_squared_error, ndcg_score
from sklearn.model_selection import train_test_split


DATASET_NAME = "PRISM_primary_LUAD"
TARGET_COL = "activity_score"
DEFAULT_EXPECTED_ROWS = 4684
DEFAULT_SEEDS = tuple(range(42, 52))
DEFAULT_ROUNDS = 10
DEFAULT_BATCH_SIZE = 50
DEFAULT_TOP_K = 50
FORBIDDEN_FEATURE_COLUMNS = {
    "median_logfold_change",
    "mean_logfold_change",
    "q25_logfold_change",
    "q75_logfold_change",
    "activity_score",
    "active_label",
    "n_measurements",
    "n_cell_lines",
    "n_replicate_treatments",
}
REQUIRED_COLUMNS = {"candidate_id", "base_score", TARGET_COL, "median_logfold_change"}


def _json_default(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if np.isnan(value) else float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")


def load_strategy_module(strategy_path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("prism_primary_autoresearch_strategy", strategy_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import strategy module from {strategy_path}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for function_name in ("fit_strategy", "score_candidates", "acquire_candidates"):
        if not callable(getattr(module, function_name, None)):
            raise ValueError(f"Strategy module is missing callable {function_name}().")
    return module


def validate_feature_columns(feature_columns: list[str]) -> None:
    duplicated = sorted({column for column in feature_columns if feature_columns.count(column) > 1})
    if duplicated:
        raise ValueError(f"Feature columns contain duplicates: {duplicated}.")
    leaked = sorted(FORBIDDEN_FEATURE_COLUMNS.intersection(feature_columns))
    if leaked:
        raise ValueError(f"Forbidden feedback/leakage columns requested as strategy inputs: {leaked}.")
    if "base_score" not in feature_columns:
        raise ValueError("Feature columns must include base_score.")


def load_inputs(base_scored_csv: Path, feature_columns_json: Path, expected_rows: int = DEFAULT_EXPECTED_ROWS) -> tuple[pd.DataFrame, list[str]]:
    scored = pd.read_csv(base_scored_csv, low_memory=False)
    scored["candidate_id"] = scored["candidate_id"].astype(str)
    feature_columns = json.loads(feature_columns_json.read_text(encoding="utf-8"))
    if not isinstance(feature_columns, list) or not all(isinstance(column, str) for column in feature_columns):
        raise ValueError("Feature columns JSON must contain a list of column names.")
    validate_feature_columns(feature_columns)
    missing = sorted((REQUIRED_COLUMNS.union(feature_columns)).difference(scored.columns))
    if missing:
        raise ValueError(f"Base-scored input is missing required columns: {missing}.")
    if int(expected_rows) > 0 and len(scored) != int(expected_rows):
        raise ValueError(f"Expected {expected_rows} candidate rows, found {len(scored)}.")
    if scored["candidate_id"].duplicated().any():
        raise ValueError("Base-scored input contains duplicate candidate_id values.")
    return scored.reset_index(drop=True), feature_columns


def _activity_bins(df: pd.DataFrame, n_bins: int) -> pd.Series:
    ranked = df[TARGET_COL].rank(method="first")
    return pd.qcut(ranked, q=min(int(n_bins), len(df)), labels=False, duplicates="drop").astype(int)


def _stratified_take(df: pd.DataFrame, test_size: float, seed: int, n_bins: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    split_df = df.copy()
    split_df["_activity_bin"] = _activity_bins(split_df, n_bins=n_bins)
    first, second = train_test_split(
        split_df,
        test_size=float(test_size),
        random_state=int(seed),
        stratify=split_df["_activity_bin"].astype(int),
    )
    return (
        first.drop(columns=["_activity_bin"]).reset_index(drop=True),
        second.drop(columns=["_activity_bin"]).reset_index(drop=True),
    )


def generate_split_manifest(
    scored: pd.DataFrame,
    seeds: Iterable[int] = DEFAULT_SEEDS,
    locked_test_fraction: float = 0.10,
    dev_fraction_in_visible: float = 0.10,
    warm_start_fraction_in_feedback: float = 0.10,
    stratify_bins: int = 10,
) -> dict[str, Any]:
    split_entries = []
    all_ids = set(scored["candidate_id"].astype(str))
    for seed in seeds:
        visible, locked_test = _stratified_take(scored, locked_test_fraction, int(seed), stratify_bins)
        feedback_remainder, dev_validation = _stratified_take(visible, dev_fraction_in_visible, int(seed) + 100_000, stratify_bins)
        acquisition_pool, warm_start = _stratified_take(
            feedback_remainder,
            warm_start_fraction_in_feedback,
            int(seed) + 200_000,
            stratify_bins,
        )
        groups = {
            "locked_test_ids": locked_test["candidate_id"].astype(str).tolist(),
            "dev_validation_ids": dev_validation["candidate_id"].astype(str).tolist(),
            "warm_start_ids": warm_start["candidate_id"].astype(str).tolist(),
            "acquisition_pool_ids": acquisition_pool["candidate_id"].astype(str).tolist(),
        }
        group_sets = [set(group) for group in groups.values()]
        if set.union(*group_sets) != all_ids or sum(len(group) for group in group_sets) != len(all_ids):
            raise RuntimeError(f"Invalid split partition generated for seed {seed}.")
        split_entries.append({"seed": int(seed), **groups})
    return {
        "dataset": DATASET_NAME,
        "rows_total": int(len(scored)),
        "target_col": TARGET_COL,
        "stratify": "activity_score_quantile_10bin",
        "stratify_bins": int(stratify_bins),
        "locked_test_fraction": float(locked_test_fraction),
        "dev_fraction_in_visible": float(dev_fraction_in_visible),
        "warm_start_fraction_in_feedback": float(warm_start_fraction_in_feedback),
        "seeds": split_entries,
    }


def load_and_validate_manifest(path: Path, scored: pd.DataFrame) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("dataset") != DATASET_NAME or manifest.get("target_col") != TARGET_COL:
        raise ValueError("Split manifest does not describe PRISM primary LUAD activity_score data.")
    if int(manifest.get("rows_total", -1)) != len(scored):
        raise ValueError("Split manifest row count does not match input data.")
    known_ids = set(scored["candidate_id"].astype(str))
    for entry in manifest.get("seeds", []):
        groups = [
            set(map(str, entry[key]))
            for key in ("locked_test_ids", "dev_validation_ids", "warm_start_ids", "acquisition_pool_ids")
        ]
        if set.union(*groups) != known_ids or sum(len(group) for group in groups) != len(known_ids):
            raise ValueError(f"Split manifest partition is invalid for seed {entry.get('seed')}.")
    return manifest


def _subset(scored: pd.DataFrame, candidate_ids: list[str]) -> pd.DataFrame:
    order = {candidate_id: index for index, candidate_id in enumerate(candidate_ids)}
    subset = scored[scored["candidate_id"].isin(order)].copy()
    subset["_split_order"] = subset["candidate_id"].map(order)
    return subset.sort_values("_split_order").drop(columns=["_split_order"]).reset_index(drop=True)


def _observed_for_strategy(df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    return df[["candidate_id", *feature_columns, TARGET_COL]].copy()


def _candidates_for_strategy(df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    return df[["candidate_id", *feature_columns]].copy()


def _score_private_rows(
    strategy_module: ModuleType,
    model_state: Any,
    private_df: pd.DataFrame,
    feature_columns: list[str],
    seed: int,
) -> pd.DataFrame:
    public_df = _candidates_for_strategy(private_df, feature_columns)
    strategy_scores = strategy_module.score_candidates(model_state, public_df, feature_columns, int(seed))
    if not isinstance(strategy_scores, pd.DataFrame):
        raise ValueError("score_candidates() must return a pandas DataFrame.")
    required = {"candidate_id", "final_score"}
    missing = sorted(required.difference(strategy_scores.columns))
    if missing:
        raise ValueError(f"score_candidates() result is missing required columns: {missing}.")
    if strategy_scores["candidate_id"].astype(str).duplicated().any():
        raise ValueError("score_candidates() returned duplicate candidate IDs.")
    returned_ids = set(strategy_scores["candidate_id"].astype(str))
    expected_ids = set(public_df["candidate_id"].astype(str))
    if returned_ids != expected_ids:
        raise ValueError("score_candidates() must return exactly the requested candidate IDs.")
    safe_scores = strategy_scores[["candidate_id", "final_score"]].copy()
    safe_scores["candidate_id"] = safe_scores["candidate_id"].astype(str)
    safe_scores["final_score"] = pd.to_numeric(safe_scores["final_score"], errors="raise")
    if not np.isfinite(safe_scores["final_score"]).all():
        raise ValueError("score_candidates() returned non-finite final_score values.")
    if "calibrated_score" in strategy_scores.columns:
        safe_scores["calibrated_score"] = pd.to_numeric(strategy_scores["calibrated_score"], errors="raise")
    return private_df.merge(safe_scores, on="candidate_id", how="left", validate="one_to_one")


def _evaluate(df: pd.DataFrame, score_col: str, prefix: str, top_k: int) -> dict[str, float]:
    scores = df[score_col].astype(float)
    activities = df[TARGET_COL].astype(float)
    k = min(int(top_k), len(df))
    ordered = df.sort_values([score_col, "candidate_id"], ascending=[False, True]).head(k)
    mean_activity = float(activities.mean())
    pearson = pearsonr(activities, scores).statistic if len(df) > 1 and activities.nunique() > 1 and scores.nunique() > 1 else float("nan")
    spearman = spearmanr(activities, scores).correlation if len(df) > 1 else float("nan")
    return {
        f"{prefix}_rows": float(len(df)),
        f"{prefix}_ndcg_at_{int(top_k)}": float(ndcg_score([activities.to_numpy()], [scores.to_numpy()], k=k)),
        f"{prefix}_top{int(top_k)}_true_activity_mean": float(ordered[TARGET_COL].mean()),
        f"{prefix}_top{int(top_k)}_activity_lift_vs_mean": float(ordered[TARGET_COL].mean() / mean_activity) if mean_activity else float("nan"),
        f"{prefix}_top{int(top_k)}_median_logfold_change": float(ordered["median_logfold_change"].median()),
        f"{prefix}_rmse": float(np.sqrt(mean_squared_error(activities, scores))),
        f"{prefix}_mae": float(mean_absolute_error(activities, scores)),
        f"{prefix}_pearson": 0.0 if pd.isna(pearson) else float(pearson),
        f"{prefix}_spearman": 0.0 if pd.isna(spearman) else float(spearman),
    }


def _selected_metrics(selected: pd.DataFrame) -> dict[str, float]:
    if selected.empty:
        return {
            "acquired_rows": 0.0,
            "acquired_activity_mean": float("nan"),
            "acquired_median_logfold_change": float("nan"),
            "acquired_base_rank_top50_count": float("nan"),
            "acquired_base_rank_median": float("nan"),
            "acquired_base_rank_percentile_mean": float("nan"),
            "acquired_base_rank_percentile_min": float("nan"),
            "acquired_base_rank_percentile_max": float("nan"),
        }
    metrics = {
        "acquired_rows": float(len(selected)),
        "acquired_activity_mean": float(selected[TARGET_COL].mean()),
        "acquired_median_logfold_change": float(selected["median_logfold_change"].median()),
    }
    if "base_rank" in selected.columns:
        base_rank = pd.to_numeric(selected["base_rank"], errors="coerce")
        metrics["acquired_base_rank_top50_count"] = float((base_rank <= 50).sum())
        metrics["acquired_base_rank_median"] = float(base_rank.median())
    else:
        metrics["acquired_base_rank_top50_count"] = float("nan")
        metrics["acquired_base_rank_median"] = float("nan")
    if "base_rank_percentile" in selected.columns:
        percentile = pd.to_numeric(selected["base_rank_percentile"], errors="coerce")
        metrics["acquired_base_rank_percentile_mean"] = float(percentile.mean())
        metrics["acquired_base_rank_percentile_min"] = float(percentile.min())
        metrics["acquired_base_rank_percentile_max"] = float(percentile.max())
    else:
        metrics["acquired_base_rank_percentile_mean"] = float("nan")
        metrics["acquired_base_rank_percentile_min"] = float("nan")
        metrics["acquired_base_rank_percentile_max"] = float("nan")
    return metrics


def _select_candidates(
    strategy_module: ModuleType,
    scored_pool: pd.DataFrame,
    batch_size: int,
    round_index: int,
    seed: int,
    reference_random: bool,
    allow_non_greedy_acquisition: bool,
) -> pd.DataFrame:
    expected = (
        scored_pool.sort_values(["final_score", "candidate_id"], ascending=[False, True])
        .head(int(batch_size))
        .copy()
        .reset_index(drop=True)
    )
    if reference_random:
        return scored_pool.sample(n=min(int(batch_size), len(scored_pool)), random_state=int(seed) + int(round_index)).reset_index(drop=True)
    public_scored = scored_pool.drop(columns=list(FORBIDDEN_FEATURE_COLUMNS.intersection(scored_pool.columns)), errors="ignore")
    selected = strategy_module.acquire_candidates(public_scored, int(batch_size), int(round_index), int(seed))
    if not isinstance(selected, pd.DataFrame) or "candidate_id" not in selected.columns:
        raise ValueError("acquire_candidates() must return a DataFrame containing candidate_id.")
    chosen_ids = selected["candidate_id"].astype(str).tolist()
    expected_count = min(int(batch_size), len(scored_pool))
    if len(chosen_ids) != expected_count or len(set(chosen_ids)) != expected_count:
        raise ValueError("acquire_candidates() must return the required number of unique candidates.")
    pool_ids = set(scored_pool["candidate_id"].astype(str))
    if not set(chosen_ids).issubset(pool_ids):
        raise ValueError("acquire_candidates() returned candidates outside the remaining pool.")
    if not allow_non_greedy_acquisition:
        expected_ids = expected["candidate_id"].astype(str).tolist()
        if chosen_ids != expected_ids:
            raise ValueError("Invalid strategy: acquisition must be Greedy Top-K by final_score.")
        return expected
    order = {candidate_id: index for index, candidate_id in enumerate(chosen_ids)}
    return (
        scored_pool[scored_pool["candidate_id"].astype(str).isin(order)]
        .assign(_acquisition_order=lambda frame: frame["candidate_id"].astype(str).map(order))
        .sort_values("_acquisition_order")
        .drop(columns=["_acquisition_order"])
        .reset_index(drop=True)
    )


def run_one_seed(
    scored: pd.DataFrame,
    feature_columns: list[str],
    split_entry: dict[str, Any],
    strategy_module: ModuleType,
    evaluation_partition: str,
    rounds: int = DEFAULT_ROUNDS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    top_k: int = DEFAULT_TOP_K,
    reference_random: bool = False,
    allow_non_greedy_acquisition: bool = False,
) -> pd.DataFrame:
    if evaluation_partition not in {"dev", "locked_test"}:
        raise ValueError("evaluation_partition must be 'dev' or 'locked_test'.")
    prefix = "dev" if evaluation_partition == "dev" else "locked_test"
    eval_key = "dev_validation_ids" if evaluation_partition == "dev" else "locked_test_ids"
    seed = int(split_entry["seed"])
    observed = _subset(scored, split_entry["warm_start_ids"])
    pool = _subset(scored, split_entry["acquisition_pool_ids"])
    evaluation = _subset(scored, split_entry[eval_key])
    selected_ids: set[str] = set()
    metric_rows: list[dict[str, Any]] = []

    model_state = strategy_module.fit_strategy(_observed_for_strategy(observed, feature_columns), feature_columns, seed)
    evaluation_scored = _score_private_rows(strategy_module, model_state, evaluation, feature_columns, seed)
    metric_rows.append(
        {
            "seed": seed,
            "round": 0,
            "observed_rows": int(len(observed)),
            "remaining_pool_rows": int(len(pool)),
            **_selected_metrics(pd.DataFrame()),
            **_evaluate(evaluation_scored, "final_score", prefix, top_k),
        }
    )
    for round_index in range(1, int(rounds) + 1):
        if pool.empty:
            break
        pool_scored = _score_private_rows(strategy_module, model_state, pool, feature_columns, seed + round_index)
        selected = _select_candidates(
            strategy_module,
            pool_scored,
            batch_size,
            round_index,
            seed,
            reference_random,
            allow_non_greedy_acquisition,
        )
        new_ids = set(selected["candidate_id"].astype(str))
        if selected_ids.intersection(new_ids):
            raise RuntimeError("A candidate was acquired more than once.")
        selected_ids.update(new_ids)
        observed = pd.concat([observed, selected], ignore_index=True)
        pool = pool[~pool["candidate_id"].isin(new_ids)].reset_index(drop=True)
        model_state = strategy_module.fit_strategy(_observed_for_strategy(observed, feature_columns), feature_columns, seed + round_index)
        evaluation_scored = _score_private_rows(strategy_module, model_state, evaluation, feature_columns, seed + round_index)
        metric_rows.append(
            {
                "seed": seed,
                "round": int(round_index),
                "observed_rows": int(len(observed)),
                "remaining_pool_rows": int(len(pool)),
                **_selected_metrics(selected),
                **_evaluate(evaluation_scored, "final_score", prefix, top_k),
            }
        )
    return pd.DataFrame(metric_rows)


def aggregate_metrics(all_metrics: pd.DataFrame) -> pd.DataFrame:
    numeric_columns = [column for column in all_metrics.select_dtypes(include=[np.number]).columns if column not in {"seed", "round"}]
    grouped = all_metrics.groupby("round", as_index=True)[numeric_columns].agg(["mean", "std"]).reset_index()
    grouped.columns = [column if isinstance(column, str) else f"{column[0]}_{column[1]}".rstrip("_") for column in grouped.columns]
    return grouped


def run_protocol(
    scored: pd.DataFrame,
    feature_columns: list[str],
    manifest: dict[str, Any],
    strategy_module: ModuleType,
    evaluation_partition: str,
    rounds: int = DEFAULT_ROUNDS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    top_k: int = DEFAULT_TOP_K,
    reference_random: bool = False,
    allow_non_greedy_acquisition: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    validate_feature_columns(feature_columns)
    metric_frames = [
        run_one_seed(
            scored,
            feature_columns,
            entry,
            strategy_module,
            evaluation_partition,
            rounds,
            batch_size,
            top_k,
            reference_random,
            allow_non_greedy_acquisition,
        )
        for entry in manifest["seeds"]
    ]
    all_metrics = pd.concat(metric_frames, ignore_index=True)
    aggregate = aggregate_metrics(all_metrics)
    prefix = "dev" if evaluation_partition == "dev" else "locked_test"
    final_metrics = all_metrics[all_metrics["round"] == int(rounds)]
    summary = {
        "evaluation_partition": evaluation_partition,
        "reference_random": bool(reference_random),
        "primary_metric": f"round{int(rounds)}_{prefix}_ndcg_at_{int(top_k)}_mean",
        f"round{int(rounds)}_{prefix}_ndcg_at_{int(top_k)}_mean": float(final_metrics[f"{prefix}_ndcg_at_{int(top_k)}"].mean()),
        f"round{int(rounds)}_{prefix}_ndcg_at_{int(top_k)}_std": float(final_metrics[f"{prefix}_ndcg_at_{int(top_k)}"].std()),
        f"round{int(rounds)}_{prefix}_top{int(top_k)}_true_activity_mean": float(final_metrics[f"{prefix}_top{int(top_k)}_true_activity_mean"].mean()),
        f"round{int(rounds)}_{prefix}_top{int(top_k)}_median_logfold_change": float(final_metrics[f"{prefix}_top{int(top_k)}_median_logfold_change"].mean()),
        f"round{int(rounds)}_{prefix}_acquired_base_rank_top50_count_mean": float(final_metrics["acquired_base_rank_top50_count"].mean()),
        f"round{int(rounds)}_{prefix}_acquired_base_rank_median_mean": float(final_metrics["acquired_base_rank_median"].mean()),
        f"round{int(rounds)}_{prefix}_acquired_base_rank_percentile_mean": float(final_metrics["acquired_base_rank_percentile_mean"].mean()),
        f"round{int(rounds)}_{prefix}_spearman_mean": float(final_metrics[f"{prefix}_spearman"].mean()),
        f"round{int(rounds)}_{prefix}_pearson_mean": float(final_metrics[f"{prefix}_pearson"].mean()),
        f"round{int(rounds)}_{prefix}_rmse_mean": float(final_metrics[f"{prefix}_rmse"].mean()),
        f"round{int(rounds)}_{prefix}_mae_mean": float(final_metrics[f"{prefix}_mae"].mean()),
    }
    return all_metrics, aggregate, summary
