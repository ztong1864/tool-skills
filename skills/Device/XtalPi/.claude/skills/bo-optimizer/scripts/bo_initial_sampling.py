"""
Initial-sampling entrypoint for BO when no historical experiments are available.

This script mirrors the "no-history" path from `demo_cpu.ipynb`:
- build the reaction domain from descriptors
- instantiate `newEDBO`
- ask for an initial batch without `prev_res`

It is intentionally separate from `run_bo_next_round.py`, which requires a
historical BO table.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parent
SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from summit import Domain

from bayesian_optimization.condition_opt.EDBOplus.edbo import newEDBO
from bayesian_optimization.condition_opt.utils import descClass, get_reaction_space, get_target_value


def build_domain(desc_path: Path) -> Domain:
    reagent_types = ["tempo", "additive", "ratio", "solvent", "volume"]
    desc_class = descClass(desc_path)
    domain = Domain()
    domain = get_reaction_space(domain, desc_class, reagent_types=reagent_types)
    domain = get_target_value(domain)
    return domain


def resolve_output_path(output_path: Path | None, batch_size: int) -> Path:
    if output_path is not None:
        return output_path.resolve()
    formatted_date = datetime.now().strftime("%Y%m%d")
    return (SKILL_ROOT / "output" / f"initial_sampling_batch-{batch_size}_{formatted_date}.csv").resolve()


def run_initial_sampling(
    *,
    descriptors_dir: Path,
    batch_size: int = 10,
    seed: int = 1216,
    init_sampling_method: str = "LHS",
    output_path: Path | None = None,
) -> Path:
    if not descriptors_dir.exists():
        raise FileNotFoundError(f"Descriptors directory not found: {descriptors_dir}")

    domain = build_domain(descriptors_dir)
    edbo = newEDBO(domain=domain, seed=seed, init_sampling_method=init_sampling_method)
    results = edbo.suggest_experiments(batch_size=batch_size)

    out_csv = resolve_output_path(output_path, batch_size)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(out_csv, index=False)
    return out_csv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--descriptors-dir",
        default=None,
        help="Descriptor directory. Defaults to <skill-root>/output/descriptors.",
    )
    parser.add_argument("--output", default=None, help="Output CSV path.")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--seed", type=int, default=1216)
    parser.add_argument("--init-sampling-method", default="LHS", choices=["LHS", "CVT"])
    args = parser.parse_args()

    descriptors_dir = (
        Path(args.descriptors_dir).resolve()
        if args.descriptors_dir
        else (SKILL_ROOT / "output" / "descriptors").resolve()
    )
    output_path = Path(args.output).resolve() if args.output else None

    out_csv = run_initial_sampling(
        descriptors_dir=descriptors_dir,
        batch_size=args.batch_size,
        seed=args.seed,
        init_sampling_method=args.init_sampling_method,
        output_path=output_path,
    )
    print(f"[OK] wrote: {out_csv}")


if __name__ == "__main__":
    main()
