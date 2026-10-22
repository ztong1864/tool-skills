from __future__ import annotations

import argparse
import json
from pathlib import Path

from .inference import score_disease, load_disease_catalog


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PrimeKG Graph CGI e50 delivery scoring")
    subparsers = parser.add_subparsers(dest="command", required=True)

    score = subparsers.add_parser("score", help="Score PrimeKG candidate drugs for one supported disease")
    score.add_argument("--bundle-dir", required=True)
    score.add_argument("--prepared-dir", required=True)
    score.add_argument("--disease", required=True, help="disease_id or exact disease_name from disease_catalog.csv")
    score.add_argument("--output", required=True)
    score.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "mps"])
    score.add_argument("--top-k", type=int, default=0, help="0 means all candidate drugs")
    score.add_argument("--candidate-drugbank-ids", default=None, help="Optional text file, one candidate DrugBank ID per line")
    score.add_argument("--project-src", default=None, help="Optional path to original KG-project/src")

    diseases = subparsers.add_parser("list-diseases", help="Export supported disease catalog")
    diseases.add_argument("--prepared-dir", required=True)
    diseases.add_argument("--output", required=False)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "score":
        scores = score_disease(
            bundle_dir=args.bundle_dir,
            prepared_dir=args.prepared_dir,
            disease=args.disease,
            output=args.output,
            top_k=args.top_k,
            device=args.device,
            candidate_drugbank_ids=args.candidate_drugbank_ids,
            project_src=args.project_src,
        )
        print(json.dumps({
            "status": "ok",
            "command": "score",
            "rows": int(len(scores)),
            "disease": str(args.disease),
            "output": str(Path(args.output)),
        }, ensure_ascii=False))
        return

    if args.command == "list-diseases":
        catalog = load_disease_catalog(args.prepared_dir)
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            catalog.to_csv(args.output, index=False)
            output = str(Path(args.output))
        else:
            print(catalog.to_csv(index=False), end="")
            output = "stdout"
        print(json.dumps({"status": "ok", "command": "list-diseases", "rows": int(len(catalog)), "output": output}, ensure_ascii=False))
        return

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
