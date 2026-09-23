from __future__ import annotations

import argparse
import json
from pathlib import Path

from .inference import load_bundle, score_all_candidates


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PrimeKG indication-only delivery inference")
    subparsers = parser.add_subparsers(dest="command", required=True)

    score = subparsers.add_parser("score", help="Score all candidate molecules for one disease")
    score.add_argument("--bundle-dir", required=True)
    score.add_argument("--disease", required=True)
    score.add_argument("--output", required=True)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "score":
        bundle = load_bundle(args.bundle_dir)
        scores = score_all_candidates(bundle, args.disease)
        scores.to_csv(Path(args.output), index=False)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "command": "score",
                    "rows": int(len(scores)),
                    "disease": str(args.disease),
                    "output": str(Path(args.output)),
                },
                ensure_ascii=False,
            )
        )
        return

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
