"""
Historical-data BO entrypoint.

This is a thin wrapper around `condition_opt/run_bo_next_round.py`, placed in
`scripts/` for convenience so users can run the historical-data flow from a
more discoverable path.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from bayesian_optimization.condition_opt.run_bo_next_round import run_bo_from_table


def main() -> None:
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
    args = parser.parse_args()

    skill_root = SCRIPTS_ROOT.parent
    round_dir = Path(args.round_dir).resolve() if args.round_dir else (skill_root / "output").resolve()
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
