#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Write the recommendation CSV correctly (quoting) and check every cell against the candidate space.

Usage:
  python scripts/write_recommendations.py --candidate-space <csv> --rows rows.json --output <csv>
  python scripts/write_recommendations.py --literature-status     (which literature PDFs exist; writes nothing)

rows.json is a list of rows; each row is either a list in column order or an object keyed by column name:
  [["ZnI2", "none", "L-脯氨酰胺", "4A MS", "乙腈"], ...]
Default columns: metal_salt_1, metal_salt_2, chiral_amine, molecular_sieve, solvent.
Cells may be a Chinese name, an English name, a metal-salt formula or an abbreviation from the candidate space
(never a mix of Chinese and English in one cell). `none` and fixed materials such as `4A MS` are always allowed.
Exit code 0 = file written and verified; 1 = unmatched cells or bad rows (nothing is written unless --allow-unknown).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

DEFAULT_COLUMNS = ["metal_salt_1", "metal_salt_2", "chiral_amine", "molecular_sieve", "solvent"]
SKILL_DIR = Path(__file__).resolve().parents[1]
LITERATURE_DIRS = ("KB/pdf_new", "KB/pdfs")
FIXED_OK = {"none", "4a ms", "4a", "ms", ""}


def norm(text: str) -> str:
    return "".join(str(text).split()).casefold()


def read_candidates(path: Path) -> dict[str, set[str]]:
    """Section -> accepted spellings, from the sectioned (header-less) or the flat candidate-space layout."""
    sections: dict[str, set[str]] = {}
    current = ""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle):
            cells = [cell.strip() for cell in row]
            filled = [cell for cell in cells if cell]
            if not filled:
                continue
            if len(filled) == 1 and not filled[0].isdigit():
                current = filled[0].casefold()
                sections.setdefault(current, set())
                continue
            if cells[0].casefold() in {"no", "section"} or not current and not cells[0].isdigit():
                continue
            if cells[0].isdigit():
                for cell in cells[1:4]:
                    if not cell:
                        continue
                    for part in {cell, *cell.split("/")}:
                        sections.setdefault(current, set()).add(norm(part))
    return sections


def section_for(column: str, sections: dict[str, set[str]]) -> set[str] | None:
    key = column.casefold()
    wanted = ("metal" if key.startswith("metal") else "amine" if "amine" in key else "solvent" if "solvent" in key else "")
    if not wanted:
        return None
    for name, names in sections.items():
        if wanted in name:
            return names
    return None


def literature_status() -> int:
    """One read-only check of the literature this skill can use, so the Agent never searches for PDFs."""
    folders, total = [], 0
    for relative in LITERATURE_DIRS:
        folder = SKILL_DIR / relative
        pdfs = sorted(path.name for path in folder.rglob("*") if path.suffix.lower() == ".pdf") if folder.is_dir() else []
        total += len(pdfs)
        folders.append({"folder": str(folder), "exists": folder.is_dir(), "pdf_count": len(pdfs), "pdfs": pdfs[:20]})
    note = ("Read the relevant PDFs listed here." if total else
            "No literature PDFs here. Unless the user uploaded a PDF for this task, recommend from the constraints, the "
            "candidate space, KB/output_format_example.csv and earlier outputs, and say once in the reply that this "
            "round has no literature basis. This is a normal result, not a failure.")
    print(json.dumps({"mode": "literature" if total else "no_literature", "pdf_count": total, "folders": folders,
                      "note": note}, ensure_ascii=False, indent=2))
    return 0


def _read_stdin_rows(timeout: float = 10.0) -> str | None:
    """--rows -: the rows piped on stdin, or None when nothing arrives. A tool runner can leave stdin open
    with nothing coming, and a plain read would then wait until the tool's own timeout (10 minutes)."""
    import threading

    box: list[str] = []
    reader = threading.Thread(target=lambda: box.append(sys.stdin.buffer.read().decode("utf-8-sig")), daemon=True)
    reader.start()
    reader.join(timeout)
    return box[0] if box and box[0].strip() else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--candidate-space")
    parser.add_argument("--rows", help="JSON file with the rows, or - for stdin")
    parser.add_argument("--output")
    parser.add_argument("--literature-status", action="store_true",
                        help="Only report which literature PDFs this skill can read (writes nothing)")
    parser.add_argument("--columns", default=",".join(DEFAULT_COLUMNS))
    parser.add_argument("--allow-unknown", action="store_true", help="write even when a cell is not in the candidate space")
    args = parser.parse_args()
    if args.literature_status:
        return literature_status()
    missing = [flag for flag, value in (("--candidate-space", args.candidate_space), ("--rows", args.rows),
                                        ("--output", args.output)) if not value]
    if missing:
        parser.error("the following arguments are required: " + ", ".join(missing))

    columns = [item.strip() for item in args.columns.split(",") if item.strip()]
    raw = _read_stdin_rows() if args.rows == "-" else Path(args.rows).read_text(encoding="utf-8-sig")
    if raw is None:
        print("--rows -: no rows arrived on stdin. Write the rows to a JSON file (for example rows.json in the "
              "mission artifact folder) and pass its path to --rows.", file=sys.stderr)
        return 1
    data = json.loads(raw)
    if not isinstance(data, list) or not data:
        print("rows must be a non-empty JSON list", file=sys.stderr)
        return 1
    sections = read_candidates(Path(args.candidate_space))
    rows: list[list[str]] = []
    problems: list[str] = []
    seen: set[tuple[str, ...]] = set()
    for number, item in enumerate(data, 1):
        if isinstance(item, dict):
            row = [str(item.get(column, "none")) for column in columns]
        elif isinstance(item, list):
            row = [str(cell) for cell in item]
        else:
            problems.append(f"row {number}: not a list or object")
            continue
        if len(row) != len(columns):
            problems.append(f"row {number}: {len(row)} cells, expected {len(columns)} ({', '.join(columns)})")
            continue
        for column, cell in zip(columns, row):
            names = section_for(column, sections)
            if names is None or norm(cell) in FIXED_OK:
                continue
            if norm(cell) not in names:
                problems.append(f"row {number}: {column} = {cell!r} is not in the candidate space")
        key = tuple(norm(cell) for cell in row)
        if key in seen:
            problems.append(f"row {number}: duplicate of an earlier row")
        seen.add(key)
        rows.append(row)
    if problems and not args.allow_unknown:
        print(json.dumps({"written": False, "problems": problems}, ensure_ascii=False, indent=2))
        return 1
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        writer.writerows(rows)
    with out.open(encoding="utf-8-sig", newline="") as handle:  # verify what was written
        widths = {len(row) for row in csv.reader(handle)}
    if widths != {len(columns)}:
        print(f"verification failed: column counts {sorted(widths)}", file=sys.stderr)
        return 1
    print(json.dumps({"written": True, "path": str(out), "rows": len(rows), "columns": columns,
                      "warnings": problems}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
