from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from .encoders import DiseaseEncoder, DrugEncoder
from .model import TorchPrimeKGIndicationRanker, resolve_runtime_device


REQUIRED_BUNDLE_KEYS = {
    "candidate_pool",
    "disease_catalog",
    "model_state",
    "disease_encoder_state",
    "drug_encoder_state",
    "manifest",
}


@dataclass(frozen=True)
class ResolvedDisease:
    disease_id: str
    disease_name: str


@dataclass
class IndicationInferenceBundle:
    candidate_pool: pd.DataFrame
    disease_catalog: pd.DataFrame
    model: TorchPrimeKGIndicationRanker
    disease_encoder: DiseaseEncoder
    drug_encoder: DrugEncoder
    manifest: dict
    device: str


def _normalize_query(value: object) -> str:
    return " ".join(str(value).strip().split()).casefold()


def _validate_bundle_payload(payload: dict) -> None:
    missing = REQUIRED_BUNDLE_KEYS - set(payload.keys())
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"Bundle is missing required keys: {missing_text}")


def load_bundle(bundle_dir: str | Path) -> IndicationInferenceBundle:
    base = Path(bundle_dir)
    bundle_path = base / "bundle.pt"
    payload = torch.load(bundle_path, weights_only=False, map_location=torch.device('cpu') )
    _validate_bundle_payload(payload)
    disease_catalog = payload["disease_catalog"]
    if not isinstance(disease_catalog, pd.DataFrame):
        disease_catalog = pd.DataFrame(disease_catalog)
    device = resolve_runtime_device(payload.get("device"))
    return IndicationInferenceBundle(
        candidate_pool=payload["candidate_pool"],
        disease_catalog=disease_catalog,
        model=TorchPrimeKGIndicationRanker.from_state(payload["model_state"], device=device),
        disease_encoder=DiseaseEncoder.from_state(payload["disease_encoder_state"]),
        drug_encoder=DrugEncoder.from_state(payload["drug_encoder_state"]),
        manifest=payload["manifest"],
        device=device,
    )


def resolve_disease(bundle: IndicationInferenceBundle, query: str) -> ResolvedDisease:
    query_text = str(query).strip()
    if not query_text:
        raise ValueError("Disease query is empty. Please provide a disease_id or exact disease_name.")

    catalog = (
        bundle.disease_catalog[["disease_id", "disease_name"]]
        .fillna("")
        .astype(str)
        .drop_duplicates(subset=["disease_id", "disease_name"])
        .reset_index(drop=True)
    )
    normalized_query = _normalize_query(query_text)

    id_matches = catalog[catalog["disease_id"].map(_normalize_query) == normalized_query]
    if not id_matches.empty:
        row = id_matches.iloc[0]
        return ResolvedDisease(disease_id=str(row["disease_id"]), disease_name=str(row["disease_name"]))

    name_matches = catalog[catalog["disease_name"].map(_normalize_query) == normalized_query]
    if name_matches.empty:
        raise ValueError(
            f"Disease '{query_text}' was not found. Please provide a known disease_id or exact disease_name."
        )

    unique_matches = name_matches.drop_duplicates(subset=["disease_id"]).sort_values(["disease_name", "disease_id"])
    if len(unique_matches) > 1:
        disease_ids = ", ".join(unique_matches["disease_id"].astype(str).tolist())
        raise ValueError(f"Disease name '{query_text}' is ambiguous. Matching disease_ids: {disease_ids}")

    row = unique_matches.iloc[0]
    return ResolvedDisease(disease_id=str(row["disease_id"]), disease_name=str(row["disease_name"]))


def _build_pair_matrix(bundle: IndicationInferenceBundle, disease_id: str, pool: pd.DataFrame) -> np.ndarray:
    disease_emb = bundle.disease_encoder.transform([disease_id] * len(pool))
    drug_emb = bundle.drug_encoder.transform(pool[["drugbank_id", "smiles"]])
    return np.hstack([disease_emb, drug_emb, disease_emb * drug_emb]).astype(np.float32)


def score_all_candidates(bundle: IndicationInferenceBundle, disease_query: str) -> pd.DataFrame:
    resolved = resolve_disease(bundle, disease_query)
    if not bundle.disease_encoder.has_disease(resolved.disease_id):
        raise ValueError(f"Disease '{resolved.disease_id}' is not available in the fitted disease encoder.")

    pool = bundle.candidate_pool[["drugbank_id", "drug_name", "smiles"]].copy()
    if pool.empty:
        return pd.DataFrame(
            columns=[
                "disease_id",
                "disease_name",
                "rank",
                "drugbank_id",
                "drug_name",
                "smiles",
                "indication_score",
            ]
        )

    pair_matrix = _build_pair_matrix(bundle, resolved.disease_id, pool)
    scores = bundle.model.predict_scores(pair_matrix)
    pool["disease_id"] = resolved.disease_id
    pool["disease_name"] = resolved.disease_name
    pool["indication_score"] = scores.astype(float)
    ranked = pool.sort_values(["indication_score", "drugbank_id"], ascending=[False, True]).reset_index(drop=True)
    ranked["rank"] = np.arange(1, len(ranked) + 1, dtype=np.int64)
    return ranked[
        [
            "disease_id",
            "disease_name",
            "rank",
            "drugbank_id",
            "drug_name",
            "smiles",
            "indication_score",
        ]
    ]
