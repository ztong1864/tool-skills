#!/usr/bin/env python3
"""Deterministic proposer used to verify AutoResearch Core without a model API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=HERE / "generic_proposal_catalog.json")
    args = parser.parse_args()
    context = json.load(sys.stdin)
    evaluated = set(context.get("evaluated_candidate_ids", []))
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    for proposal in catalog:
        if proposal["candidate_id"] not in evaluated:
            print(json.dumps(proposal, ensure_ascii=False))
            return 0
    print(json.dumps({"action": "stop", "reason": "All catalog candidates have been evaluated."}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
