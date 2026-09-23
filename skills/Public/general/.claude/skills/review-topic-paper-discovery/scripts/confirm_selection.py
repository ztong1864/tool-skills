#!/usr/bin/env python3
"""Apply the user's chat-confirmed Discovery selection.

FounDryClaw has no Discovery dashboard and normal users cannot write files in
the workdir, so the human check happens in chat: the agent asks which papers to
drop, then runs this script. It prunes the excluded papers/keywords from
``selected_discovery_results.json`` and marks both confirmation files in one
step, so the two can never disagree.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _review_runtime.paths import resolve_review_root  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def split_list(raw: str) -> list[str]:
    return [x.strip() for x in re.split(r"[,;\n，；、\s]+", raw or "") if x.strip()]


def split_keywords(raw: str) -> list[str]:
    # Keywords may contain spaces, so only split on list separators.
    return [x.strip() for x in re.split(r"[,;\n，；、]+", raw or "") if x.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-root", default=None)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--exclude-papers", default="", help="paper_ids to drop, e.g. P011,P033")
    parser.add_argument("--keep-only", default="", help="keep only these paper_ids (drops all others)")
    parser.add_argument("--exclude-keywords", default="", help="keyword groups to drop")
    parser.add_argument("--exclude-web", default="", help="1-based indexes into web_papers to drop")
    parser.add_argument("--note", default="", help="user's reason / wording, recorded for audit")
    parser.add_argument("--dry-run", action="store_true", help="print the result without writing")
    args = parser.parse_args()

    review_root = resolve_review_root(args.review_root, anchor=Path(__file__))
    out_dir = Path(review_root) / "review-projects" / args.project_id / "00_discovery"
    selected_path = out_dir / "selected_discovery_results.json"
    state_path = out_dir / "human_check_state.json"
    if not selected_path.is_file():
        print(f"ERROR: {selected_path} not found; run discover.py first.", file=sys.stderr)
        return 2

    selected = read_json(selected_path)
    local_papers: list[dict[str, Any]] = list(selected.get("local_papers") or [])
    known_ids = {str(p.get("paper_id")) for p in local_papers if p.get("paper_id")}

    exclude_ids = {x.upper() for x in split_list(args.exclude_papers)}
    keep_only = {x.upper() for x in split_list(args.keep_only)}
    unknown = sorted((exclude_ids | keep_only) - {i.upper() for i in known_ids})
    if unknown:
        print(f"ERROR: unknown paper_id(s): {', '.join(unknown)}. Known: {', '.join(sorted(known_ids))}",
              file=sys.stderr)
        return 2
    if keep_only:
        exclude_ids |= {i.upper() for i in known_ids if i.upper() not in keep_only}

    exclude_keywords = {k.casefold() for k in split_keywords(args.exclude_keywords)}
    known_keywords = {str(k.get("keyword") or "").casefold() for k in selected.get("keywords") or []}
    unknown_kw = sorted(exclude_keywords - known_keywords)
    if unknown_kw:
        print(f"ERROR: unknown keyword(s): {', '.join(unknown_kw)}", file=sys.stderr)
        return 2

    # A paper matched only by excluded keywords has no remaining reason to stay.
    kept_papers: list[dict[str, Any]] = []
    excluded_papers: list[dict[str, Any]] = []
    for paper in local_papers:
        pid = str(paper.get("paper_id") or "")
        matched = [k for k in paper.get("matched_keywords") or [] if str(k).casefold() not in exclude_keywords]
        if pid.upper() in exclude_ids:
            excluded_papers.append({"paper_id": pid, "title": paper.get("title"), "reason": "user_excluded"})
        elif exclude_keywords and paper.get("matched_keywords") and not matched:
            excluded_papers.append({"paper_id": pid, "title": paper.get("title"), "reason": "only_excluded_keywords"})
        else:
            kept_papers.append({**paper, "matched_keywords": matched or paper.get("matched_keywords") or []})
    if not kept_papers:
        print("ERROR: this selection would leave no local papers; ask the user to keep at least one.",
              file=sys.stderr)
        return 2

    web_papers: list[dict[str, Any]] = list(selected.get("web_papers") or [])
    drop_web = set()
    for raw in split_list(args.exclude_web):
        if not raw.isdigit() or not 1 <= int(raw) <= len(web_papers):
            print(f"ERROR: --exclude-web index {raw!r} out of range 1..{len(web_papers)}", file=sys.stderr)
            return 2
        drop_web.add(int(raw) - 1)
    web_papers = [
        w for i, w in enumerate(web_papers)
        if i not in drop_web and str(w.get("matched_keyword") or "").casefold() not in exclude_keywords
    ]

    kept_ids = {p["paper_id"] for p in kept_papers}
    groups = selected.get("groups") or {}
    for field, buckets in groups.items():
        if not isinstance(buckets, dict):
            continue
        for value in list(buckets):
            ids = [i for i in buckets[value].get("paper_ids") or [] if i in kept_ids]
            if ids:
                buckets[value] = {**buckets[value], "count": len(ids), "paper_ids": ids}
            else:
                del buckets[value]

    now = utc_now()
    selected.update({
        "keywords": [k for k in selected.get("keywords") or []
                     if str(k.get("keyword") or "").casefold() not in exclude_keywords],
        "local_papers": kept_papers,
        "web_papers": web_papers,
        "groups": groups,
        "excluded_papers": (selected.get("excluded_papers") or []) + excluded_papers,
        "human_confirmed": True,
        "confirmed_at": now,
        "confirmation_channel": "chat",
    })
    if args.note:
        selected["confirmation_note"] = args.note

    state = read_json(state_path) if state_path.is_file() else {"project_id": args.project_id}
    state.update({
        "status": "confirmed",
        "confirmed_at": now,
        "confirmation_channel": "chat",
        "kept_local_papers": len(kept_papers),
        "excluded_local_papers": [p["paper_id"] for p in excluded_papers],
    })

    summary = (f"Kept {len(kept_papers)} local papers, excluded {len(excluded_papers)}"
               f" ({', '.join(p['paper_id'] for p in excluded_papers) or 'none'}); "
               f"{len(web_papers)} web papers remain.")
    if args.dry_run:
        print("[dry-run] " + summary)
        return 0
    write_json(selected_path, selected)
    write_json(state_path, state)
    print("Discovery confirmed. " + summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
