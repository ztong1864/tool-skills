from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class ResolvedDisease:
    disease_id: str
    disease_name: str


def ensure_project_src(project_src: str | None = None) -> None:
    candidates = []
    if project_src:
        candidates.append(Path(project_src))
    import os
    if os.environ.get("KG_PROJECT_SRC"):
        candidates.append(Path(os.environ["KG_PROJECT_SRC"]))
    if os.environ.get("KG_PROJECT_ROOT"):
        candidates.append(Path(os.environ["KG_PROJECT_ROOT"]) / "src")
    candidates.extend([
        Path("/Users/lulu/Documents/year4/具身智能体/TCM_KG/KG-project/src"),
        Path("/slurm/home/yrd/fanlab/zhangjinlu/zjl_desktop/KG/PrimeKG/src"),
    ])
    for candidate in candidates:
        if candidate.exists() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
            break




def patch_torch_load_for_trusted_bundle() -> None:
    """Allow trusted local bundles saved with pandas/DataFrame payloads on PyTorch 2.6+."""
    try:
        import torch
    except Exception:
        return
    if getattr(torch.load, "_primekg_delivery_patched", False):
        return
    original_load = torch.load

    def trusted_load(*args, **kwargs):
        kwargs.setdefault("weights_only", False)
        return original_load(*args, **kwargs)

    trusted_load._primekg_delivery_patched = True
    torch.load = trusted_load


def resolve_device(device: str) -> str:
    device = (device or "auto").strip().lower()
    if device not in {"auto", "cpu", "cuda", "mps"}:
        raise ValueError("--device must be one of: auto, cpu, cuda, mps")
    if device == "cpu":
        return "cpu"
    try:
        import torch
    except Exception as exc:
        if device == "auto":
            return "cpu"
        raise RuntimeError(f"Cannot import torch while resolving device '{device}': {exc}") from exc
    if device == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is not available. Use --device auto or --device cpu, or run on a CUDA host.")
        return "cuda"
    if device == "mps":
        if not getattr(torch.backends, "mps", None) or not torch.backends.mps.is_available():
            raise RuntimeError("MPS is not available. Use --device auto or --device cpu.")
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def normalize_query(value: object) -> str:
    return " ".join(str(value).strip().split()).casefold()


def load_disease_catalog(prepared_dir: str | Path) -> pd.DataFrame:
    prepared = Path(prepared_dir)
    catalog_path = prepared / "disease_catalog.csv"
    if not catalog_path.exists():
        fallback = prepared / "supervised_diseases.csv"
        if fallback.exists():
            catalog_path = fallback
        else:
            raise FileNotFoundError(f"Missing disease catalog: {prepared / 'disease_catalog.csv'}")
    catalog = pd.read_csv(catalog_path, dtype=str).fillna("")
    required = {"disease_id", "disease_name"}
    missing = required - set(catalog.columns)
    if missing:
        raise ValueError(f"Disease catalog missing columns: {', '.join(sorted(missing))}")
    return catalog[["disease_id", "disease_name"]].drop_duplicates().reset_index(drop=True)


def resolve_disease(prepared_dir: str | Path, query: str) -> ResolvedDisease:
    query_text = str(query).strip()
    if not query_text:
        raise ValueError("Disease query is empty. Provide a disease_id or exact disease_name.")
    catalog = load_disease_catalog(prepared_dir)
    normalized = normalize_query(query_text)
    id_matches = catalog[catalog["disease_id"].map(normalize_query) == normalized]
    if not id_matches.empty:
        row = id_matches.iloc[0]
        return ResolvedDisease(str(row["disease_id"]), str(row["disease_name"]))
    name_matches = catalog[catalog["disease_name"].map(normalize_query) == normalized]
    if name_matches.empty:
        raise ValueError(f"Disease '{query_text}' was not found in disease_catalog.csv. Use a supported disease_id or exact disease_name.")
    unique = name_matches.drop_duplicates(subset=["disease_id"]).sort_values(["disease_name", "disease_id"])
    if len(unique) > 1:
        pairs = "; ".join(f"{r.disease_id}:{r.disease_name}" for r in unique.itertuples(index=False))
        raise ValueError(f"Disease name '{query_text}' is ambiguous. Matching disease entries: {pairs}. Use disease_id.")
    row = unique.iloc[0]
    return ResolvedDisease(str(row["disease_id"]), str(row["disease_name"]))


def read_id_list(path: str | Path) -> list[str]:
    ids = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        ids.append(value)
    return ids


def load_feature_flags(prepared_dir: str | Path) -> pd.DataFrame:
    prepared = Path(prepared_dir)
    candidate = pd.read_csv(prepared / "candidate_pool.csv", dtype=str).fillna("")
    cgi_ids: set[str] = set()
    target_ids: set[str] = set()
    cgi_path = prepared / "drug_perturbation_edges.csv"
    target_path = prepared / "drug_protein_edges.csv"
    if cgi_path.exists():
        cgi_ids = set(pd.read_csv(cgi_path, usecols=["drugbank_id"], dtype=str)["drugbank_id"].dropna().astype(str))
    if target_path.exists():
        target_ids = set(pd.read_csv(target_path, usecols=["drugbank_id"], dtype=str)["drugbank_id"].dropna().astype(str))
    flags = candidate[["drugbank_id"]].drop_duplicates().copy()
    flags["has_cgi"] = flags["drugbank_id"].isin(cgi_ids)
    flags["has_drug_protein_target"] = flags["drugbank_id"].isin(target_ids)
    return flags


def validate_allowed_drugs(prepared_dir: str | Path, allowed_ids: Iterable[str]) -> list[str]:
    requested = [str(x).strip() for x in allowed_ids if str(x).strip()]
    candidate = pd.read_csv(Path(prepared_dir) / "candidate_pool.csv", usecols=["drugbank_id"], dtype=str)
    valid = set(candidate["drugbank_id"].dropna().astype(str))
    unknown = sorted(set(requested) - valid)
    if unknown:
        preview = ", ".join(unknown[:20])
        suffix = "" if len(unknown) <= 20 else f" ... (+{len(unknown) - 20} more)"
        raise ValueError(
            "Unknown DrugBank IDs outside current candidate_pool.csv: "
            f"{preview}{suffix}. This handoff does not support KG-external cold-start drugs."
        )
    return requested


def score_disease(
    bundle_dir: str | Path,
    prepared_dir: str | Path,
    disease: str,
    output: str | Path | None = None,
    top_k: int = 0,
    device: str = "auto",
    candidate_drugbank_ids: str | Path | None = None,
    project_src: str | None = None,
) -> pd.DataFrame:
    ensure_project_src(project_src)
    try:
        from primekg_graph_indication_multitoken_cgi_graph.inference import load_inference_bundle, predict_for_disease
    except Exception as exc:
        raise RuntimeError(
            "Cannot import primekg_graph_indication_multitoken_cgi_graph. Set KG_PROJECT_SRC to the original KG-project/src path. "
            f"Original error: {exc}"
        ) from exc

    prepared = Path(prepared_dir)
    bundle = Path(bundle_dir)
    if not (bundle / "best_bundle.pt").exists() and not (bundle / "bundle.pt").exists():
        raise FileNotFoundError(f"Missing best_bundle.pt and bundle.pt in bundle dir: {bundle}")
    if not (prepared / "candidate_pool.csv").exists():
        raise FileNotFoundError(f"Missing candidate_pool.csv in prepared dir: {prepared}")

    resolved = resolve_disease(prepared, disease)
    runtime_device = resolve_device(device)
    patch_torch_load_for_trusted_bundle()
    inference_bundle = load_inference_bundle(bundle, device=runtime_device)

    candidate_pool = inference_bundle.candidate_pool.copy()
    all_allowed = candidate_pool["drugbank_id"].astype(str).tolist()
    if candidate_drugbank_ids:
        all_allowed = validate_allowed_drugs(prepared, read_id_list(candidate_drugbank_ids))

    k_arg = None if int(top_k or 0) <= 0 else int(top_k)
    scored = predict_for_disease(
        disease_id=resolved.disease_id,
        candidate_pool=candidate_pool,
        model=inference_bundle.model,
        allowed_drugs=all_allowed,
        top_k=k_arg,
        bundle_dir=bundle,
        split_name="test",
    )
    if scored.empty:
        result = pd.DataFrame(columns=[
            "disease_id", "disease_name", "rank", "drugbank_id", "drug_name", "indication_score", "has_cgi", "has_drug_protein_target"
        ])
    else:
        result = scored.copy()
        result.insert(0, "rank", range(1, len(result) + 1))
        result.insert(0, "disease_name", resolved.disease_name)
        result.insert(0, "disease_id", resolved.disease_id)
        flags = load_feature_flags(prepared)
        result = result.merge(flags, on="drugbank_id", how="left")
        result["has_cgi"] = result["has_cgi"].fillna(False).astype(bool)
        result["has_drug_protein_target"] = result["has_drug_protein_target"].fillna(False).astype(bool)
        result = result[[
            "disease_id", "disease_name", "rank", "drugbank_id", "drug_name", "indication_score", "has_cgi", "has_drug_protein_target"
        ]]
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(output, index=False)
    return result
