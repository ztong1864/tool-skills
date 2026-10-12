#!/usr/bin/env python3
"""Calculate RDKit descriptors, Rule-of-Five status, QED, PAINS, and Brenk alerts."""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


FIELDNAMES = [
    "compound_id",
    "smiles",
    "status",
    "MW",
    "cLogP",
    "HBD",
    "HBA",
    "TPSA",
    "RotBonds",
    "QED",
    "Lipinski",
    "PAINS",
    "Brenk",
]


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


def build_catalogs():
    from rdkit.Chem.FilterCatalog import FilterCatalog, FilterCatalogParams

    pains_params = FilterCatalogParams()
    pains_params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS)
    brenk_params = FilterCatalogParams()
    brenk_params.AddCatalog(FilterCatalogParams.FilterCatalogs.BRENK)
    return FilterCatalog(pains_params), FilterCatalog(brenk_params)


def invalid_record(compound_id: str, smiles: str) -> Dict[str, object]:
    return {"compound_id": compound_id, "smiles": smiles, "status": "INVALID_SMILES"}


def assess_molecule(compound_id: str, smiles: str, pains_catalog, brenk_catalog) -> Dict[str, object]:
    if is_blank_smiles(smiles):
        return invalid_record(compound_id, smiles)

    from rdkit import Chem
    from rdkit.Chem import Descriptors, QED

    molecule = Chem.MolFromSmiles(smiles.strip())
    if molecule is None or molecule.GetNumAtoms() == 0:
        return invalid_record(compound_id, smiles)

    mw = Descriptors.MolWt(molecule)
    logp = Descriptors.MolLogP(molecule)
    hbd = Descriptors.NumHDonors(molecule)
    hba = Descriptors.NumHAcceptors(molecule)
    return {
        "compound_id": compound_id,
        "smiles": smiles,
        "status": "OK",
        "MW": round(mw, 4),
        "cLogP": round(logp, 4),
        "HBD": hbd,
        "HBA": hba,
        "TPSA": round(Descriptors.TPSA(molecule), 4),
        "RotBonds": Descriptors.NumRotatableBonds(molecule),
        "QED": round(QED.qed(molecule), 6),
        "Lipinski": int(mw <= 500 and logp <= 5 and hbd <= 5 and hba <= 10),
        "PAINS": int(pains_catalog.HasMatch(molecule)),
        "Brenk": int(brenk_catalog.HasMatch(molecule)),
    }


def write_output(path: Path, rows: Sequence[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smiles-col", default="smiles")
    parser.add_argument("--id-col", default="compound_id")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        rows = read_input(args.input, args.id_col, args.smiles_col)
        pains_catalog, brenk_catalog = build_catalogs()
        started = time.time()
        results = [
            assess_molecule(row["compound_id"], row["smiles"], pains_catalog, brenk_catalog)
            for row in rows
        ]
        write_output(args.output, results)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc

    valid = sum(row.get("status") == "OK" for row in results)
    invalid = len(results) - valid
    pains = sum(row.get("PAINS") == 1 for row in results)
    brenk = sum(row.get("Brenk") == 1 for row in results)
    print(
        f"Input rows: {len(results)} | Valid: {valid} | Invalid: {invalid} | "
        f"PAINS+: {pains} | Brenk+: {brenk} | Elapsed: {time.time() - started:.3f}s"
    )
    print(f"Output: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
