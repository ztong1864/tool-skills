#!/usr/bin/env python3
"""Compare RDKit drug-likeness output with the bundled acceptance fixture."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple


TEXT_COLUMNS = {"compound_id", "smiles", "status", "HBD", "HBA", "RotBonds", "Lipinski", "PAINS", "Brenk"}
NUMERIC_COLUMNS = {"MW", "cLogP", "TPSA", "QED"}


def read_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def compare_csv(actual: Path, expected: Path, atol: float = 1e-6):
    actual_header, actual_rows = read_csv(actual)
    expected_header, expected_rows = read_csv(expected)
    errors: List[str] = []
    max_error = 0.0
    if actual_header != expected_header:
        errors.append(f"header mismatch: {actual_header} != {expected_header}")
    if len(actual_rows) != len(expected_rows):
        errors.append(f"row count mismatch: {len(actual_rows)} != {len(expected_rows)}")

    for index, (got, want) in enumerate(zip(actual_rows, expected_rows), start=1):
        for column in expected_header:
            got_value = got.get(column, "")
            want_value = want.get(column, "")
            if column in NUMERIC_COLUMNS and got_value != "" and want_value != "":
                try:
                    got_number = float(got_value)
                    want_number = float(want_value)
                except ValueError:
                    errors.append(f"row {index} {column}: nonnumeric value")
                    continue
                if not math.isfinite(got_number) or not math.isfinite(want_number):
                    errors.append(f"row {index} {column}: nonfinite value")
                    continue
                difference = abs(got_number - want_number)
                max_error = max(max_error, difference)
                if difference > atol:
                    errors.append(f"row {index} {column}: {got_value} != {want_value}")
            elif got_value != want_value:
                errors.append(f"row {index} {column}: {got_value!r} != {want_value!r}")

    summary = {
        "valid": not errors,
        "rows": len(actual_rows),
        "columns": len(actual_header),
        "max_abs_error": max_error,
        "errors": errors,
    }
    return errors, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actual", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--atol", type=float, default=1e-6)
    args = parser.parse_args()
    errors, summary = compare_csv(args.actual, args.expected, args.atol)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
