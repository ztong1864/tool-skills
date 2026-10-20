"""Compare the solvent of each condition row with the planned reaction temperature.

Read-only. For the recommendation and amount reviews of fdu-risk-review: it names the rows whose solvent boils below
the reaction temperature (for example tetrahydrofuran, about 66 C, at 70 C), so the verdict does not depend on a
boiling point remembered or not in that run. Boiling points come from KB/solvent_boiling_points.csv.

Usage:
  python scripts/check_boiling_points.py --table <recommendation or amount CSV> --constraints <constraint JSON>
  python scripts/check_boiling_points.py --table <CSV> --temperature 70
Prints one JSON object; exit code 0 whatever the result, 2 when a file cannot be read.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

BOILING_POINTS = Path(__file__).resolve().parent.parent / "KB" / "solvent_boiling_points.csv"
TEMPERATURE = re.compile(r"(-?\d+(?:\.\d+)?)\s*(?:℃|°\s*C|摄氏度)", re.IGNORECASE)
EMPTY = {"", "none", "无", "不加", "不加入", "null", "nan"}


def normalize(name: str) -> str:
    """Case, width and separators do not matter: '1,4-Dioxane', '1，4-二氧六环 ' and 'THF' match their table entries."""
    text = unicodedata.normalize("NFKC", name).strip().lower()
    return re.sub(r"[\s\-‐–—_,，·]", "", text)


def load_boiling_points() -> dict[str, tuple[str, float]]:
    table: dict[str, tuple[str, float]] = {}
    with BOILING_POINTS.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            names = [name for name in (row.get("names") or "").split("|") if name.strip()]
            for name in names:
                table[normalize(name)] = (names[0], float(row["boiling_point_c"]))
    return table


def reaction_temperature(constraints: Path | None, given: float | None) -> tuple[float | None, list[float]]:
    """The planned reaction temperature: --temperature, else the highest temperature in the instruction text."""
    if given is not None:
        return given, [given]
    if constraints is None:
        return None, []
    data = json.loads(constraints.read_text(encoding="utf-8-sig"))
    texts = [str(data.get("source_text") or "")]
    texts += [str(item.get("raw_text") or "") for item in data.get("items") or [] if isinstance(item, dict)]
    found = sorted({float(value) for text in texts for value in TEMPERATURE.findall(text)})
    return (max(found) if found else None), found


def solvents_in(cell: str) -> list[str]:
    """One cell may hold a mixture ('1,4-二氧六环/水（4:1）'): each part, without ratios or notes in brackets."""
    parts = re.split(r"\s*[/／;；+＋]\s*", unicodedata.normalize("NFKC", cell))
    cleaned = []
    for part in parts:
        part = re.sub(r"[(（][^)）]*[)）]", "", part)
        part = re.sub(r"\s*\d+(?:\.\d+)?\s*[:：]\s*\d+(?:\.\d+)?\s*$", "", part).strip()
        if part.lower() not in EMPTY:
            cleaned.append(part)
    return cleaned


def solvent_columns(header: list[str]) -> list[str]:
    return [name for name in header if name.strip().lower().startswith("solvent")
            and not name.strip().lower().endswith(("_amount", "_volume", "_mass"))]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--table", required=True, help="Recommendation or amount CSV with a solvent column.")
    parser.add_argument("--constraints", help="constraint-parser JSON; the reaction temperature is read from it.")
    parser.add_argument("--temperature", type=float, help="Reaction temperature in C (instead of --constraints).")
    args = parser.parse_args(argv)
    try:
        boiling_points = load_boiling_points()
        temperature, found = reaction_temperature(Path(args.constraints) if args.constraints else None, args.temperature)
        with Path(args.table).open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = solvent_columns(reader.fieldnames or [])
            rows = list(reader)
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False), file=sys.stderr)
        return 2

    below, unknown = [], []
    for number, row in enumerate(rows, 1):
        for column in columns:
            for solvent in solvents_in(row.get(column) or ""):
                entry = boiling_points.get(normalize(solvent))
                if entry is None:
                    unknown.append({"row": number, "solvent": solvent})
                elif temperature is not None and entry[1] < temperature:
                    below.append({"row": number, "solvent": solvent, "name": entry[0], "boiling_point_c": entry[1]})

    if below:
        result = "block"
        groups = "、".join(dict.fromkeys(str(item["row"]) for item in below))
        names = "、".join(dict.fromkeys(f"{item['name']}（沸点约 {item['boiling_point_c']:g} ℃）" for item in below))
        message = f"第 {groups} 组的溶剂{names}，低于反应温度 {temperature:g} ℃"
    elif not columns:
        result, message = "needs_human_review", "表中没有 solvent 列，无法检查溶剂沸点"
    elif temperature is None:
        result, message = "needs_human_review", "约束中没有找到反应温度，无法比较溶剂沸点"
    elif unknown:
        result = "needs_human_review"
        message = "沸点表中没有这些溶剂：" + "、".join(dict.fromkeys(item["solvent"] for item in unknown))
    else:
        result, message = "pass", f"所有溶剂的沸点都不低于反应温度 {temperature:g} ℃"
    print(json.dumps({
        "result": result,
        "message": message,
        "reaction_temperature_c": temperature,
        "temperatures_found_c": found,
        "solvent_columns": columns,
        "checked_rows": len(rows),
        "rows_below_reaction_temperature": below,
        "unknown_solvents": unknown,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
