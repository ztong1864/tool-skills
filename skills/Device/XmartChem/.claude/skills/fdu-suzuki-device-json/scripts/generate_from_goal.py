#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime

from scene_core import generate_protocol_from_goal
from scene_utils import OUTPUT_DIR, SceneGenerationError, write_json


TEST_GOAL = """
Generate a final device-executable JSON for a Suzuki coupling reaction to produce 4-phenylacetophenone from 4-bromoacetophenone and phenylboronic acid.

Use:
- 4-bromoacetophenone as the aryl halide
- phenylboronic acid as the boronic acid coupling partner
- PdCl2 as catalyst
- K2CO3 as base
- DMF or another suitable organic solvent from the resource list
- an internal standard solution if available

Constraints:
- Keep the aryl halide amount within 0.08-0.12 mmol
- Keep the boronic acid at 1.0-1.2 equivalents relative to the aryl halide
- Catalyst loading should be conservative and should not exceed 10 mol%
- Base should be between 1.5 and 3.0 equivalents
- Total liquid volume during the reaction stage should remain suitable for a 2 mL reactor
- Use only substances that exist in the resource list
- All quantities must be physically feasible and consistent with stock concentrations

Analytical requirement:
- After the reaction, add an internal standard if available
- Homogenize the mixture
- Prepare one filtered aliquot for HPLC analysis
""".strip()


def get_python_bin_hint() -> str:
    py3 = shutil.which("python3")
    py = shutil.which("python")
    return py3 or py or "python3"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate final device protocol JSON directly from a scene-level reaction goal."
    )
    parser.add_argument("--goal", type=str, default="", help="Natural-language reaction goal")
    parser.add_argument("--reaction-type", type=str, default="suzuki", help="Scene type. Current supported value: suzuki")
    parser.add_argument(
        "--allow-fallback-reagents",
        action="store_true",
        help="Allow generation attempt even when some resource capacity checks would fail",
    )
    parser.add_argument("--test", action="store_true", help="Run with built-in Suzuki example")
    args = parser.parse_args()

    if args.reaction_type.lower() != "suzuki":
        print("Only the suzuki scene is supported in this version.", file=sys.stderr)
        return 1

    goal_text = TEST_GOAL if args.test else (args.goal or "").strip()
    if not goal_text:
        print("Goal text must not be empty.", file=sys.stderr)
        print(f"Hint: use {get_python_bin_hint()} scripts/generate_from_goal.py --goal \"...\"", file=sys.stderr)
        return 1

    try:
        protocol = generate_protocol_from_goal(
            goal_text=goal_text,
            allow_fallback_reagents=args.allow_fallback_reagents,
        )
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUTPUT_DIR / f"generated_suzuki_protocol_{timestamp}.json"
        write_json(protocol, out_path)

        print(f"Protocol generated: {out_path}")
        print(f"Total steps: {len(protocol)}")
        print("Unit types:", [step.get("unit_type") for step in protocol])
        return 0

    except SceneGenerationError as e:
        print(f"Generation failed: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
