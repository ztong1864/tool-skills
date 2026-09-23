"""
Thin BO wrapper for a custom table schema.

This entrypoint keeps the existing BO implementation intact and only adapts
the input table shape to what `newEDBO` expects.

Expected table columns:
- batch_id
- metal_salt_1
- metal_salt_2
- chiral_amine
- molecular_sieve
- solvent
- yield
- select_tag

Descriptor files are expected to live in the descriptors directory with names
matching the categorical columns, for example:
- metal_salt_1_desc_datadf.csv
- metal_salt_2_desc_datadf.csv
- chiral_amine_desc_datadf.csv
- molecular_sieve_desc_datadf.csv
- solvent_desc_datadf.csv

Optional columns such as `metal_salt_2` and `molecular_sieve` may use `none`
to represent absence, but the corresponding descriptor CSVs still need a
`none` row if you want BO to recommend that state explicitly.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
from summit import Domain
from summit.domain import CategoricalVariable, ContinuousVariable
from summit.utils.dataset import DataSet

SCRIPTS_ROOT = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPTS_ROOT.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from bayesian_optimization.condition_opt.EDBOplus.edbo import newEDBO

DEFAULT_NONE_TOKEN = "none"


def _load_reaction_columns(temp_path: Path) -> list[str]:
    if not temp_path.exists():
        raise FileNotFoundError(f"Reaction header temp file not found: {temp_path}")
    with temp_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if isinstance(payload, list):
        cols = payload
    elif isinstance(payload, dict):
        cols = payload.get("reaction_columns") or payload.get("columns") or payload.get("headers") or []
    else:
        cols = []
    cleaned = [str(col).strip() for col in cols if str(col).strip()]
    if not cleaned:
        raise ValueError(f"No reaction columns found in temp file: {temp_path}")
    return cleaned


def _clean_category_value(value, *, none_token: str = DEFAULT_NONE_TOKEN) -> str:
    if pd.isna(value):
        return none_token
    text = str(value).strip()
    return text if text else none_token


def _normalize_reaction_frame(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col not in out.columns:
            raise KeyError(f"Missing required BO column: {col}")
        out[col] = out[col].map(_clean_category_value)
    return out


def _load_descriptor_table(desc_dir: Path, var_name: str) -> pd.DataFrame:
    path = desc_dir / f"{var_name}_desc_datadf.csv"
    if not path.exists():
        raise FileNotFoundError(f"Descriptor file not found: {path}")
    desc_df = pd.read_csv(path, index_col=0)
    desc_df.index = desc_df.index.map(_clean_category_value)
    return desc_df


def build_domain(desc_dir: Path, reagent_types: list[str]) -> Domain:
    domain = Domain()
    for var_name in reagent_types:
        desc_df = _load_descriptor_table(desc_dir, var_name)
        descriptors = DataSet.from_df(desc_df)
        domain += CategoricalVariable(
            name=var_name,
            description=var_name,
            levels=desc_df.index.tolist(),
            descriptors=descriptors,
        )
    domain += ContinuousVariable(name="yld", description="yld", bounds=[0, 100], is_objective=True, maximize=True)
    return domain


def resolve_desc_path(round_dir: Path, descriptors_dir: Path | None) -> Path:
    if descriptors_dir is not None:
        return descriptors_dir.resolve()

    round_desc = (round_dir / "descriptors").resolve()
    if round_desc.exists():
        return round_desc

    kb_desc = (SKILL_ROOT / "KB" / "descriptors").resolve()
    if kb_desc.exists():
        return kb_desc

    fallback_desc = (SCRIPTS_ROOT / "bayesian_optimization" / "descriptors").resolve()
    return fallback_desc


def resolve_output_path(round_dir: Path, output_path: Path | None) -> Path:
    if output_path is not None:
        return output_path.resolve()
    formatted_date = datetime.now().strftime("%Y%m%d")
    return (round_dir / f"edbo-results_batch-auto_{formatted_date}.csv").resolve()


def load_done_dataset(csv_path: Path, reaction_columns: list[str]) -> DataSet:
    df = pd.read_csv(csv_path)
    if "select_tag" not in df.columns:
        raise KeyError("Missing required BO column: select_tag")
    if "yield" not in df.columns:
        raise KeyError("Missing required BO column: yield")

    valid_mask = df["select_tag"].astype(str).str.lower().isin(["true", "1", "yes", "y"])
    df = df.loc[valid_mask].copy()
    df = _normalize_reaction_frame(df, reaction_columns)

    done = df[reaction_columns + ["yield"]].copy()
    done.columns = reaction_columns + ["yld"]
    done.reset_index(drop=True, inplace=True)
    return DataSet.from_df(done)


def run_bo_from_table(
    *,
    bo_table_path: Path,
    round_dir: Path,
    descriptors_dir: Path | None = None,
    output_path: Path | None = None,
    batch_size: int = 10,
    seed: int = 1216,
    init_sampling_method: str = "LHS",
    reaction_columns: list[str] | None = None,
) -> Path:
    if not bo_table_path.exists():
        raise FileNotFoundError(f"BO table not found: {bo_table_path}")

    reagent_types = reaction_columns or _load_reaction_columns(SKILL_ROOT / "KB" / "temp.json")
    desc_path = resolve_desc_path(round_dir, descriptors_dir)
    domain = build_domain(desc_path, reagent_types)
    done_dataset = load_done_dataset(bo_table_path, reagent_types)

    edbo = newEDBO(domain=domain, seed=seed, init_sampling_method=init_sampling_method)
    results = edbo.suggest_experiments(prev_res=done_dataset, batch_size=batch_size)

    out_csv = resolve_output_path(round_dir, output_path)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(out_csv, index=False)
    return out_csv


def main() -> None:
    default_reaction_columns = ",".join(_load_reaction_columns(SKILL_ROOT / "KB" / "temp.json"))
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bo-table",
        default=None,
        help="Historical BO table CSV. Defaults to <skill-root>/output/manual_conditions_round0.csv.",
    )
    parser.add_argument(
        "--round-dir",
        default=None,
        help="Round directory that contains descriptors/ and receives the BO output.",
    )
    parser.add_argument(
        "--descriptors-dir",
        default=None,
        help="Explicit descriptors directory. Defaults to <round-dir>/descriptors, then fallback descriptors.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output CSV path. Defaults to edbo-results_batch-auto_<date>.csv under round-dir.",
    )
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--seed", type=int, default=1216)
    parser.add_argument("--init-sampling-method", default="LHS", choices=["LHS", "CVT"])
    parser.add_argument(
        "--reaction-columns",
        default=default_reaction_columns,
        help="Comma-separated categorical columns in the BO table, in the same order as descriptors.",
    )
    args = parser.parse_args()

    round_dir = Path(args.round_dir).resolve() if args.round_dir else (SKILL_ROOT / "output").resolve()
    bo_table_path = (
        Path(args.bo_table).resolve()
        if args.bo_table
        else (round_dir / "manual_conditions_round0.csv").resolve()
    )
    descriptors_dir = Path(args.descriptors_dir).resolve() if args.descriptors_dir else None
    output_path = Path(args.output).resolve() if args.output else None
    reaction_columns = [col.strip() for col in args.reaction_columns.split(",") if col.strip()]
    if not reaction_columns:
        raise ValueError("--reaction-columns must contain at least one column name")

    out_csv = run_bo_from_table(
        bo_table_path=bo_table_path,
        round_dir=round_dir,
        descriptors_dir=descriptors_dir,
        output_path=output_path,
        batch_size=args.batch_size,
        seed=args.seed,
        init_sampling_method=args.init_sampling_method,
        reaction_columns=reaction_columns,
    )
    print(f"[OK] wrote: {out_csv}")


if __name__ == "__main__":
    main()
