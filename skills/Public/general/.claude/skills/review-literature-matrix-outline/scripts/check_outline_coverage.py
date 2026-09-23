#!/usr/bin/env python3
"""Verify every literature-matrix paper survives into the selected outline.

FounDryClaw has no dashboard: this is the file-based confirmation step for the
matrix/outline hand-off, mirroring review-topic-paper-discovery's
human_check_state.json convention. Run this after selected_outline.md is
written (or edited); it writes outline_coverage_state.json, which
review-writing-orchestrator's project_status.py and
review-section-blueprint's init_section_blueprint.py both gate on.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _review_runtime.paths import resolve_review_root, resolve_review_writer_core_root

_CORE_ROOT = resolve_review_writer_core_root(anchor=Path(__file__))
if _CORE_ROOT is not None and str(_CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(_CORE_ROOT))
from review_writer_core.outline_coverage import outline_coverage_report  # noqa: E402


INSTRUCTIONS = (
    "No local dashboard exists in FounDryClaw. Either add each missing paper_id "
    "to the right section's \"Assigned papers:\" line in selected_outline.md and "
    "re-run this script, or add {\"paper_id\": \"<id>\", \"reason\": \"<why>\"} to "
    "this file's excluded_papers list and re-run. Once missing_paper_ids is "
    "empty, this file is confirmed automatically."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(args: argparse.Namespace) -> int:
    review_root = resolve_review_root(args.review_root, anchor=Path(__file__))
    stage_dir = review_root / "review-projects" / args.project_id / "01_matrix_outline"
    matrix_path = stage_dir / "literature_matrix.json"
    outline_path = stage_dir / "selected_outline.md"
    state_path = stage_dir / "outline_coverage_state.json"

    if not matrix_path.exists():
        raise SystemExit(f"literature_matrix.json not found: {matrix_path}")
    if not outline_path.exists():
        raise SystemExit(f"selected_outline.md not found: {outline_path}")

    matrix = read_json(matrix_path)
    outline_text = outline_path.read_text(encoding="utf-8", errors="ignore")

    # Preserve any excluded_papers a human already recorded across reruns.
    previous_state = read_json(state_path) or {}
    excluded_papers = previous_state.get("excluded_papers") or []

    report = outline_coverage_report(matrix, outline_text, excluded_papers)
    confirmed = not report["missing_paper_ids"]

    state = {
        "project_id": args.project_id,
        "status": "confirmed" if confirmed else "blocked",
        "confirmed_at": utc_now() if confirmed else None,
        "human_confirmed": confirmed,
        "instructions": INSTRUCTIONS,
        "checked_at": utc_now(),
        "matrix_sha256": sha256_file(matrix_path),
        "outline_sha256": sha256_file(outline_path),
        "matrix_paper_ids": report["matrix_paper_ids"],
        "outline_paper_ids": report["outline_paper_ids"],
        "excluded_papers": excluded_papers,
        "missing_paper_ids": report["missing_paper_ids"],
    }
    write_json(state_path, state)

    if args.json:
        print(json.dumps(state, ensure_ascii=False, indent=2))
    else:
        print(f"Wrote {state_path}")
        print(f"Matrix papers: {len(report['matrix_paper_ids'])}")
        print(f"Outline papers: {len(report['outline_paper_ids'])}")
        if report["missing_paper_ids"]:
            print(f"Missing paper_ids (not in outline, not excluded): {report['missing_paper_ids']}")
        else:
            print("All matrix papers are accounted for. Confirmed.")

    return 1 if report["missing_paper_ids"] else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check that every literature_matrix.json paper is assigned somewhere in "
        "selected_outline.md (or explicitly excluded with a reason), and write "
        "outline_coverage_state.json."
    )
    parser.add_argument("--review-root", default=None)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def main() -> int:
    return run(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
