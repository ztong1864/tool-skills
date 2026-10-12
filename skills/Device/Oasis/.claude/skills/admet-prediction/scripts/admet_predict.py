#!/usr/bin/env python3
"""Run ADMET-AI v1.4.0 on a CSV while preserving input order and invalid rows."""

from __future__ import annotations

import argparse
import csv
import sys
import time
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Sequence


BASE_COLUMNS = ["smiles", "compound_id", "status"]
DEFAULT_SCHEMA = Path(__file__).resolve().parents[1] / "assets" / "expected_output.csv"


def is_blank_smiles(value: Optional[str]) -> bool:
    return value is None or not str(value).strip()


def read_input(path: Path, id_col: str, smiles_col: str) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        if smiles_col not in fields:
            raise ValueError(f"SMILES column '{smiles_col}' not found; available: {fields}")
        if id_col not in fields:
            raise ValueError(f"ID column '{id_col}' not found; available: {fields}")
        return [
            {"compound_id": row.get(id_col, ""), "smiles": row.get(smiles_col, "")}
            for row in reader
        ]


def load_result_columns(schema_path: Path) -> List[str]:
    with schema_path.open(newline="", encoding="utf-8-sig") as handle:
        header = next(csv.reader(handle), [])
    if header[:3] != BASE_COLUMNS or len(header) != 101 or len(set(header)) != 101:
        raise ValueError(f"invalid ADMET schema in {schema_path}")
    return header[3:]


def assemble_output(
    rows: Sequence[Dict[str, str]],
    valid_indices: Sequence[int],
    predictions: Sequence[Dict[str, object]],
    result_columns: Sequence[str],
) -> List[Dict[str, object]]:
    if len(valid_indices) != len(predictions):
        raise ValueError(
            f"prediction row count {len(predictions)} does not match valid input count {len(valid_indices)}"
        )
    prediction_by_index = dict(zip(valid_indices, predictions))
    output: List[Dict[str, object]] = []
    for index, row in enumerate(rows):
        record: Dict[str, object] = {
            "smiles": row["smiles"],
            "compound_id": row["compound_id"],
            "status": "OK" if index in prediction_by_index else "INVALID_SMILES",
        }
        if index in prediction_by_index:
            prediction = prediction_by_index[index]
            missing = [column for column in result_columns if column not in prediction]
            extra = [column for column in prediction if column not in result_columns]
            if missing or extra:
                raise ValueError(f"prediction schema mismatch; missing={missing}, extra={extra}")
            record.update({column: prediction[column] for column in result_columns})
        else:
            record.update({column: "" for column in result_columns})
        output.append(record)
    return output


def classify_smiles(rows: Sequence[Dict[str, str]]):
    from rdkit import Chem

    valid_indices: List[int] = []
    valid_smiles: List[str] = []
    for index, row in enumerate(rows):
        smiles = row["smiles"]
        if is_blank_smiles(smiles):
            continue
        molecule = Chem.MolFromSmiles(smiles.strip())
        if molecule is None or molecule.GetNumAtoms() == 0:
            continue
        valid_indices.append(index)
        valid_smiles.append(smiles.strip())
    return valid_indices, valid_smiles


def predict_batches(smiles: Sequence[str], batch_size: int, result_columns: Sequence[str]):
    import pandas as pd
    from admet_ai import ADMETModel

    warnings.filterwarnings("ignore", message=".*weights_only.*", category=FutureWarning)
    model = ADMETModel()
    batches = []
    for start in range(0, len(smiles), batch_size):
        batches.append(model.predict(smiles=list(smiles[start : start + batch_size])))
    frame = pd.concat(batches, ignore_index=True)
    columns = list(frame.columns)
    if columns != list(result_columns):
        if set(columns) != set(result_columns):
            missing = [column for column in result_columns if column not in columns]
            extra = [column for column in columns if column not in result_columns]
            raise ValueError(f"model output schema mismatch; missing={missing}, extra={extra}")
        frame = frame[list(result_columns)]
    return frame.to_dict(orient="records")


def write_output(path: Path, rows: Sequence[Dict[str, object]], result_columns: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=BASE_COLUMNS + list(result_columns))
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smiles-col", default="smiles")
    parser.add_argument("--id-col", default="compound_id")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.batch_size <= 0:
        raise SystemExit("ERROR: --batch-size must be a positive integer")
    try:
        rows = read_input(args.input, args.id_col, args.smiles_col)
        result_columns = load_result_columns(args.schema)
        valid_indices, valid_smiles = classify_smiles(rows)
        started = time.time()
        predictions = predict_batches(valid_smiles, args.batch_size, result_columns) if valid_smiles else []
        output = assemble_output(rows, valid_indices, predictions, result_columns)
        write_output(args.output, output, result_columns)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc

    print(
        f"Input rows: {len(rows)} | Valid: {len(valid_indices)} | "
        f"Invalid: {len(rows) - len(valid_indices)} | Columns: {len(BASE_COLUMNS) + len(result_columns)} | "
        f"Elapsed: {time.time() - started:.3f}s"
    )
    print(f"Output: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
