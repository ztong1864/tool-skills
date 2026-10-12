"""Generated candidate strategy: stage_b_random_forest_n300."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor


BASE_WEIGHT = 0.5


def fit_strategy(observed_df: pd.DataFrame, feature_columns: list[str], seed: int):
    train = observed_df.dropna(subset=feature_columns + ["activity_score"]).copy()
    if len(train) < 10:
        raise ValueError("Need at least 10 observed feedback rows to train the strategy.")
    model = RandomForestRegressor(
        n_estimators=300,
        min_samples_leaf=3,
        max_features=0.7,
        n_jobs=-1,
        random_state=int(seed),
    )
    model.fit(train[feature_columns], train["activity_score"].astype(float))
    return model


def score_candidates(model_state, candidate_df: pd.DataFrame, feature_columns: list[str], seed: int) -> pd.DataFrame:
    del seed
    scored = candidate_df.copy()
    scored["calibrated_score"] = np.clip(model_state.predict(scored[feature_columns]), 0.0, 1.0)
    scored["final_score"] = np.clip(
        BASE_WEIGHT * scored["base_score"].astype(float)
        + (1.0 - BASE_WEIGHT) * scored["calibrated_score"].astype(float),
        0.0,
        1.0,
    )
    return scored


def acquire_candidates(scored_pool: pd.DataFrame, batch_size: int, round_index: int, seed: int) -> pd.DataFrame:
    del round_index, seed
    return (
        scored_pool.sort_values(["final_score", "candidate_id"], ascending=[False, True])
        .head(int(batch_size))
        .copy()
        .reset_index(drop=True)
    )
