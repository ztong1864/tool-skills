"""
Workspace-level BO entrypoint that consumes a BO table and produces next-round suggestions.

This file lives outside `text_to_bo` so the two halves of the workflow are
physically separated:
- `text_to_bo/pipeline_src/pipeline/prepare_bo_table.py` builds the BO table.
- `bayesian_optimization/condition_opt/run_bo_next_round.py` consumes it.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

SCRIPTS_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = Path(__file__).resolve().parents[3]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from summit import Domain
from summit.domain import CategoricalVariable, ContinuousVariable
from summit.utils.dataset import DataSet

from bayesian_optimization.condition_opt.EDBOplus.edbo import newEDBO
from bayesian_optimization.condition_opt.utils import descClass


def build_domain(desc_path: Path) -> Domain:
    desc = descClass(desc_path)
    desc_dict = desc.get_desc_df()

    domain = Domain()
    reagent_types = ["tempo", "additive", "ratio", "solvent", "volume"]
    for tp in reagent_types:
        levels = desc_dict[tp].index.tolist()
        descriptors = DataSet.from_df(desc_dict[tp])
        domain += CategoricalVariable(name=tp, description=tp, levels=levels, descriptors=descriptors)

    domain += ContinuousVariable(name="yld", description="yld", bounds=[0, 100], is_objective=True, maximize=True)
    return domain


def load_done_dataset(csv_path: Path) -> DataSet:
    df = pd.read_csv(csv_path)
    df = df[df["select_tag"].astype(str).str.lower().isin(["true", "1", "yes", "y"])]

    done = df[["tempo", "additive", "ratio", "solvent", "volume", "yield"]].copy()
    done.columns = ["tempo", "additive", "ratio", "solvent", "volume", "yld"]
    done.reset_index(drop=True, inplace=True)
    return DataSet.from_df(done)


def resolve_desc_path(round_dir: Path, descriptors_dir: Path | None) -> Path:
    if descriptors_dir is not None:
        return descriptors_dir.resolve()

    round_desc = (round_dir / "descriptors").resolve()
    if round_desc.exists():
        return round_desc

    fallback_desc = (SCRIPTS_ROOT / "bayesian_optimization" / "descriptors").resolve()
    return fallback_desc


def resolve_output_path(round_dir: Path, output_path: Path | None) -> Path:
    if output_path is not None:
        return output_path.resolve()
    formatted_date = datetime.now().strftime("%Y%m%d")
    return (round_dir / f"edbo-results_batch-auto_{formatted_date}.csv").resolve()


def run_bo_from_table(
    *,
    bo_table_path: Path,
    round_dir: Path,
    descriptors_dir: Path | None = None,
    output_path: Path | None = None,
    batch_size: int = 10,
    seed: int = 1216,
    init_sampling_method: str = "LHS",
) -> Path:
    if not bo_table_path.exists():
        raise FileNotFoundError(f"BO table not found: {bo_table_path}")

    desc_path = resolve_desc_path(round_dir, descriptors_dir)
    domain = build_domain(desc_path)
    done_dataset = load_done_dataset(bo_table_path)

    edbo = newEDBO(domain=domain, seed=seed, init_sampling_method=init_sampling_method)
    results = edbo.suggest_experiments(prev_res=done_dataset, batch_size=batch_size)

    out_csv = resolve_output_path(round_dir, output_path)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(out_csv, index=False)
    return out_csv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bo-table",
        default=None,
        help="Path to manual_conditions_new.csv or another BO table CSV.",
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
    args = parser.parse_args()

    round_dir = Path(args.round_dir).resolve() if args.round_dir else (SKILL_ROOT / "output").resolve()
    bo_table_path = (
        Path(args.bo_table).resolve()
        if args.bo_table
        else (round_dir / "manual_conditions_round0.csv").resolve()
    )
    descriptors_dir = Path(args.descriptors_dir).resolve() if args.descriptors_dir else None
    output_path = Path(args.output).resolve() if args.output else None

    out_csv = run_bo_from_table(
        bo_table_path=bo_table_path,
        round_dir=round_dir,
        descriptors_dir=descriptors_dir,
        output_path=output_path,
        batch_size=args.batch_size,
        seed=args.seed,
        init_sampling_method=args.init_sampling_method,
    )
    print(f"[OK] wrote: {out_csv}")


if __name__ == "__main__":
    main()

