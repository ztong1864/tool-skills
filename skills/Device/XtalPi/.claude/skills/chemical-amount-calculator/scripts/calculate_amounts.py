#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[2]
KB_DIR = ROOT / "KB"
OUTPUT_DIR = ROOT / "output"
CACHE_FILE = KB_DIR / "pubchem_cache.json"

DEFAULT_CHEMICAL_SPACE = KB_DIR / "chemical_space.csv"

PUBCHEM_PROPS = "MolecularWeight,MolecularFormula,IUPACName"
ATOMIC_WEIGHTS = {
    "H": 1.008,
    "B": 10.81,
    "C": 12.011,
    "N": 14.007,
    "O": 15.999,
    "F": 18.998,
    "P": 30.974,
    "S": 32.06,
    "Cl": 35.45,
    "Br": 79.904,
    "I": 126.904,
    "Sc": 44.956,
    "Y": 88.906,
    "Ti": 47.867,
    "Zr": 91.224,
    "Hf": 178.49,
    "V": 50.942,
    "Nb": 92.906,
    "Ta": 180.948,
    "Cr": 51.996,
    "Mo": 95.95,
    "W": 183.84,
    "Mn": 54.938,
    "Co": 58.933,
    "Fe": 55.845,
    "Ni": 58.693,
    "Pd": 106.42,
    "Pt": 195.084,
    "Cu": 63.546,
    "Ag": 107.868,
    "Au": 196.967,
    "Zn": 65.38,
    "Cd": 112.414,
    "Al": 26.982,
    "Ga": 69.723,
    "In": 114.818,
    "Sb": 121.76,
}
FORMULA_ALIASES = {
    "OTf": "CF3O3S",
    "NTf2": "C2F6NO4S2",
    "OAc": "C2H3O2",
    "acac": "C5H7O2",
    "i-Pr": "C3H7",
    "MeCN": "C2H3N",
    "DME": "C4H10O2",
    "PPh3": "C18H15P",
    "bpy": "C10H8N2",
    "dppp": "C27H26P2",
    "cp": "C5H5",
    "DMS": "C2H6S",
}


class AmountCalculationError(Exception):
    pass


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value).strip()
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_key(value: Any) -> str:
    return normalize_text(value).lower().replace(" ", "")


def is_blank_value(value: Any) -> bool:
    text = normalize_text(value)
    return not text or text.lower() in {"none", "nan", "data"}


def parse_chemical_space_csv(path: Path) -> dict[str, dict[str, str]]:
    df = pd.read_csv(path)
    mapping: dict[str, dict[str, str]] = {}

    for _, row in df.iterrows():
        section = normalize_text(row.get("section"))
        cn_name = normalize_text(row.get("cn_name"))
        en_name = normalize_text(row.get("en_name"))
        abbr = normalize_text(row.get("abbr"))
        formula = normalize_text(row.get("formula"))
        smiles = normalize_text(row.get("smiles"))
        cas = normalize_text(row.get("cas"))
        density_g_ml = normalize_text(row.get("density_g_ml"))
        name = normalize_text(row.get("name")) or en_name or cn_name or formula
        if not cas:
            continue

        record = {
            "section": section,
            "cn_name": cn_name,
            "en_name": en_name or formula or name,
            "formula": formula,
            "smiles": smiles,
            "cas": cas,
            "density_g_ml": density_g_ml,
            "display_name": name,
        }
        names = [name, cn_name, en_name, abbr, formula, smiles, cas]
        if abbr and "/" in abbr:
            names.extend(part.strip() for part in abbr.split("/"))
        for item in names:
            key = normalize_key(item)
            if key:
                mapping[key] = record

    return mapping


def parse_chemical_space_xlsx(path: Path) -> dict[str, dict[str, str]]:
    raw = pd.read_excel(path, header=None)
    section = ""
    mapping: dict[str, dict[str, str]] = {}

    for _, row in raw.iterrows():
        first = normalize_text(row.iloc[0] if len(row) > 0 else "")
        if not first:
            continue
        first_lower = first.lower()
        if first_lower in {"chiral amine", "solvent", "metal salts"}:
            section = first_lower
            continue
        if first_lower == "no":
            continue

        if section == "chiral amine":
            cn_name = normalize_text(row.iloc[1])
            en_name = normalize_text(row.iloc[2])
            smiles = normalize_text(row.iloc[3])
            cas = normalize_text(row.iloc[4])
            record = {
                "section": "chiral_amine",
                "cn_name": cn_name,
                "en_name": en_name,
                "formula": "",
                "smiles": smiles,
                "cas": cas,
                "density_g_ml": "",
                "display_name": en_name or cn_name,
            }
            names = [cn_name, en_name, smiles, cas]
        elif section == "solvent":
            cn_abbr = normalize_text(row.iloc[1])
            en_name = normalize_text(row.iloc[2])
            smiles = normalize_text(row.iloc[3])
            cas = normalize_text(row.iloc[4])
            record = {
                "section": "solvent",
                "cn_name": cn_abbr,
                "en_name": en_name,
                "formula": "",
                "smiles": smiles,
                "cas": cas,
                "density_g_ml": "",
                "display_name": cn_abbr or en_name,
            }
            names = [cn_abbr, en_name, smiles, cas]
            if "/" in cn_abbr:
                names.extend(part.strip() for part in cn_abbr.split("/"))
        elif section == "metal salts":
            formula = normalize_text(row.iloc[1])
            cas = normalize_text(row.iloc[2])
            record = {
                "section": "metal_salt",
                "cn_name": "",
                "en_name": formula,
                "formula": formula,
                "smiles": "",
                "cas": cas,
                "density_g_ml": "",
                "display_name": formula,
            }
            names = [formula, cas]
        else:
            continue

        if not record.get("cas"):
            continue
        for name in names:
            key = normalize_key(name)
            if key:
                mapping[key] = record

    return mapping


def parse_chemical_space(path: Path) -> dict[str, dict[str, str]]:
    if path.suffix.lower() == ".csv":
        return parse_chemical_space_csv(path)
    return parse_chemical_space_xlsx(path)


def load_cache(path: Path) -> dict[str, Any]:
    if path.exists():
        try:
            return read_json(path)
        except json.JSONDecodeError:
            print(f"Warning: PubChem cache is not valid JSON, ignoring it: {path}", file=sys.stderr)
    return {}


def fetch_pubchem(
    identifier: str,
    cache: dict[str, Any],
    timeout: int = 30,
    namespace: str = "name",
    quiet: bool = False,
) -> dict[str, Any] | None:
    key = normalize_key(identifier) if namespace == "name" else f"{namespace}:{normalize_key(identifier)}"
    if key in cache and cache[key] is not None:
        return cache[key]

    if namespace == "smiles":
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/{quote(identifier)}/property/{PUBCHEM_PROPS}/JSON"
    else:
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{quote(identifier)}/property/{PUBCHEM_PROPS}/JSON"
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 404:
            cache[key] = None
            return None
        response.raise_for_status()
        data = response.json()
        props = data["PropertyTable"]["Properties"][0]
        result = {
            "query": identifier,
            "cid": props.get("CID"),
            "molecular_formula": props.get("MolecularFormula"),
            "molecular_weight": float(props["MolecularWeight"]),
            "iupac_name": props.get("IUPACName"),
        }
        cache[key] = result
        return result
    except Exception as exc:
        if not quiet:
            print(f"PubChem lookup failed for {identifier!r}: {exc}", file=sys.stderr)
        return None


def pubchem_matches_formula(pubchem: dict[str, Any] | None, formula_weight: float | None, tolerance: float = 0.5) -> bool:
    if not pubchem or pubchem.get("molecular_weight") is None:
        return False
    if formula_weight is None:
        return True
    return abs(float(pubchem["molecular_weight"]) - formula_weight) <= tolerance


def warn_pubchem_mismatch(name: Any, source: str, pubchem: dict[str, Any], formula_weight: float | None) -> None:
    if formula_weight is None:
        return
    print(
        f"Warning: PubChem {source} result may not match {normalize_text(name)!r}: "
        f"pubchem_formula={pubchem.get('molecular_formula')}, "
        f"pubchem_mw={float(pubchem['molecular_weight']):.3f}, formula_mw={formula_weight:.3f}.",
        file=sys.stderr,
    )


def unique_pubchem_name_candidates(name: Any, record: dict[str, str] | None) -> list[str]:
    candidates: list[Any] = []
    if record:
        candidates.extend([record.get("display_name"), record.get("en_name"), record.get("cn_name"), record.get("formula")])
    candidates.append(name)

    seen: set[str] = set()
    output: list[str] = []
    for candidate in candidates:
        text = normalize_text(candidate)
        key = normalize_key(text)
        if key and key not in seen:
            seen.add(key)
            output.append(text)
    return output


def expand_formula_aliases(formula: str) -> str:
    expanded = normalize_text(formula)
    for alias in sorted(FORMULA_ALIASES, key=len, reverse=True):
        expanded = expanded.replace(alias, f"({FORMULA_ALIASES[alias]})")
    expanded = expanded.replace("[", "(").replace("]", ")").replace("{", "(").replace("}", ")")
    return expanded


def molecular_weight_from_formula(formula: Any) -> float | None:
    text = expand_formula_aliases(normalize_text(formula))
    if not text:
        return None

    index = 0

    def parse_group() -> dict[str, float] | None:
        nonlocal index
        counts: dict[str, float] = {}
        while index < len(text):
            char = text[index]
            if char == "(":
                index += 1
                inner = parse_group()
                if inner is None:
                    return None
                multiplier = parse_number()
                for element, count in inner.items():
                    counts[element] = counts.get(element, 0.0) + count * multiplier
            elif char == ")":
                index += 1
                return counts
            elif char.isupper():
                element = char
                index += 1
                if index < len(text) and text[index].islower():
                    element += text[index]
                    index += 1
                if element not in ATOMIC_WEIGHTS:
                    return None
                counts[element] = counts.get(element, 0.0) + parse_number()
            elif char in "+-·." or char.isspace():
                index += 1
            else:
                return None
        return counts

    def parse_number() -> float:
        nonlocal index
        start = index
        while index < len(text) and (text[index].isdigit() or text[index] == "."):
            index += 1
        return float(text[start:index]) if index > start else 1.0

    counts = parse_group()
    if counts is None or index != len(text):
        return None
    return sum(ATOMIC_WEIGHTS[element] * count for element, count in counts.items())


def parse_mmol_from_note(note: Any) -> float | None:
    text = normalize_text(note)
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*mmol", text, flags=re.IGNORECASE)
    return float(match.group(1)) if match else None


def find_basis_mmol(constraints: dict[str, Any]) -> tuple[float, str]:
    for item in constraints.get("items", []):
        if item.get("group") == "substrate" and item.get("equivalent") == 1:
            mmol = parse_mmol_from_note(item.get("note"))
            if mmol is not None:
                return mmol, item.get("name") or "basis substrate"
    for item in constraints.get("items", []):
        mmol = parse_mmol_from_note(item.get("note"))
        if mmol is not None:
            return mmol, item.get("name") or "basis item"
    raise AmountCalculationError("Could not find basis mmol from constraint JSON notes.")


def format_number(value: float) -> str:
    if abs(value) >= 100:
        return f"{value:.1f}".rstrip("0").rstrip(".")
    if abs(value) >= 10:
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{value:.3f}".rstrip("0").rstrip(".")


def format_quantity(quantity: Any) -> str:
    if not isinstance(quantity, dict):
        return ""
    value = quantity.get("value")
    unit = quantity.get("unit")
    if value is None or not unit:
        return ""
    return f"{format_number(float(value))} {unit}"


def format_mass_from_equiv(equiv: Any, molecular_weight: float | None, basis_mmol: float) -> str:
    if equiv is None or molecular_weight is None:
        return ""
    mg = basis_mmol * float(equiv) * float(molecular_weight)
    return f"{format_number(mg)} mg"


def calc_mass_mg(equiv: Any, molecular_weight: float | None, basis_mmol: float) -> float | None:
    if equiv is None or molecular_weight is None:
        return None
    return basis_mmol * float(equiv) * float(molecular_weight)


def format_volume_from_mass(mass_mg: float | None, density_g_ml: Any) -> str:
    if mass_mg is None:
        return ""
    density_text = normalize_text(density_g_ml)
    if not density_text:
        return ""
    try:
        density = float(density_text)
    except ValueError:
        return ""
    if density <= 0:
        return ""
    volume_ul = mass_mg / density
    if volume_ul >= 1000:
        return f"{format_number(volume_ul / 1000)} mL"
    return f"{format_number(volume_ul)} uL"


def build_constraint_items(constraints: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in constraints.get("items", []) if classify_constraint_item(item) == "substrate"]


def item_text(item: dict[str, Any]) -> str:
    parts = [normalize_text(item.get(key)) for key in ("name", "raw_text", "note", "group")]
    return normalize_key(" ".join(part for part in parts if part))


def classify_constraint_item(item: dict[str, Any]) -> str:
    text = item_text(item)
    group = normalize_text(item.get("group")).lower()
    if "substrate" in group or "底物" in text:
        return "substrate"
    if "solvent" in group or "溶剂" in text or "婧跺墏" in text:
        return "solvent"
    if "分子筛" in text or "molecularsieve" in text or "4åms" in text or "鍒嗗瓙" in text:
        return "molecular_sieve"
    if "金属盐" in text or "metalsalt" in text or "閲戝睘" in text:
        return "metal_salt"
    if "手性胺" in text or "chiralamine" in text or "鎵嬫" in text:
        return "chiral_amine"
    return ""


def build_constraints_by_role(constraints: dict[str, Any]) -> dict[str, dict[str, Any]]:
    roles: dict[str, dict[str, Any]] = {}
    for item in constraints.get("items", []):
        role = classify_constraint_item(item)
        if role and role not in roles:
            roles[role] = item
    return roles


def resolve_record(name: Any, chemical_space: dict[str, dict[str, str]]) -> dict[str, str] | None:
    if is_blank_value(name):
        return None
    return chemical_space.get(normalize_key(name))


def molecular_weight_for_name(
    name: Any,
    chemical_space: dict[str, dict[str, str]],
    cache: dict[str, Any],
    allow_name_fallback: bool = False,
) -> tuple[float | None, dict[str, str] | None]:
    record = resolve_record(name, chemical_space)
    formula_weight = molecular_weight_from_formula(record.get("formula")) if record else None

    if record and record.get("cas"):
        cas_pubchem = fetch_pubchem(record["cas"], cache, quiet=formula_weight is not None)
        if pubchem_matches_formula(cas_pubchem, formula_weight):
            return float(cas_pubchem["molecular_weight"]), record
        if cas_pubchem:
            warn_pubchem_mismatch(name, "CAS", cas_pubchem, formula_weight)

    if allow_name_fallback or record:
        for candidate in unique_pubchem_name_candidates(name, record):
            name_pubchem = fetch_pubchem(candidate, cache, quiet=formula_weight is not None)
            if pubchem_matches_formula(name_pubchem, formula_weight):
                return float(name_pubchem["molecular_weight"]), record
            if name_pubchem:
                warn_pubchem_mismatch(name, f"name {candidate!r}", name_pubchem, formula_weight)

    if formula_weight is not None:
        print(f"Warning: using formula-derived molecular weight for {normalize_text(name)!r}.", file=sys.stderr)
        return formula_weight, record
    return None, record


def split_direct_quantity(quantity: Any) -> tuple[str, str]:
    text = format_quantity(quantity)
    if not text:
        return "", ""
    unit = normalize_text(quantity.get("unit")).lower() if isinstance(quantity, dict) else ""
    if unit in {"mg", "g"}:
        return text, ""
    if unit in {"ul", "μl", "µl", "ml", "l"}:
        return "", text
    return "", ""


def combine_amount(solid_weight: str, liquid_volume: str) -> str:
    return liquid_volume or solid_weight


def amounts_for_bo_cell(
    column: str,
    value: Any,
    constraints_by_role: dict[str, dict[str, Any]],
    chemical_space: dict[str, dict[str, str]],
    cache: dict[str, Any],
    basis_mmol: float,
) -> tuple[str, str]:
    if is_blank_value(value):
        return "", ""

    name = normalize_text(value)
    lower_col = column.lower()

    if "molecular_sieve" in lower_col:
        item = constraints_by_role.get("molecular_sieve")
        return split_direct_quantity(item.get("quantity")) if item else ("", "")

    if "solvent" in lower_col:
        item = constraints_by_role.get("solvent")
        return split_direct_quantity(item.get("quantity")) if item else ("", "")

    equiv = None
    physical_state = "solid"
    if "metal_salt" in lower_col:
        item = constraints_by_role.get("metal_salt")
        equiv = item.get("equivalent") if item else None
        physical_state = item.get("physical_state") if item else "solid"
    elif "chiral_amine" in lower_col:
        item = constraints_by_role.get("chiral_amine")
        equiv = item.get("equivalent") if item else None
        physical_state = item.get("physical_state") if item else "solid"

    molecular_weight, record = molecular_weight_for_name(name, chemical_space, cache)
    mass_mg = calc_mass_mg(equiv, molecular_weight, basis_mmol)
    if physical_state == "liquid":
        volume = format_volume_from_mass(mass_mg, record.get("density_g_ml") if record else "")
        return "", volume
    return (f"{format_number(mass_mg)} mg" if mass_mg is not None else ""), ""


def amounts_for_constraint_item(
    item: dict[str, Any],
    chemical_space: dict[str, dict[str, str]],
    cache: dict[str, Any],
    basis_mmol: float,
) -> tuple[str, str]:
    direct_solid, direct_liquid = split_direct_quantity(item.get("quantity"))
    if direct_solid or direct_liquid:
        return direct_solid, direct_liquid
    molecular_weight, record = molecular_weight_for_name(item.get("name") or "", chemical_space, cache, allow_name_fallback=True)
    mass_mg = calc_mass_mg(item.get("equivalent"), molecular_weight, basis_mmol)
    if item.get("physical_state") == "liquid":
        volume = format_volume_from_mass(mass_mg, record.get("density_g_ml") if record else "")
        return "", volume
    return (f"{format_number(mass_mg)} mg" if mass_mg is not None else ""), ""


def add_amount_columns(
    bo_df: pd.DataFrame,
    constraints: dict[str, Any],
    chemical_space: dict[str, dict[str, str]],
    cache: dict[str, Any],
    basis_mmol: float,
) -> pd.DataFrame:
    constraints_by_role = build_constraints_by_role(constraints)
    substrate_items = build_constraint_items(constraints)

    output = pd.DataFrame(index=bo_df.index)

    for idx, item in enumerate(substrate_items, start=1):
        col = f"substrate_{idx}"
        output[col] = item.get("name")
        solid, liquid = amounts_for_constraint_item(item, chemical_space, cache, basis_mmol)
        output[f"{col}_amount"] = combine_amount(solid, liquid)

    for column in bo_df.columns:
        output[column] = bo_df[column]
        split_amounts = [
            amounts_for_bo_cell(column, value, constraints_by_role, chemical_space, cache, basis_mmol)
            for value in bo_df[column]
        ]
        output[f"{column}_amount"] = [combine_amount(solid, liquid) for solid, liquid in split_amounts]

    data_rows = bo_df.apply(lambda row: all(normalize_text(value).upper() == "DATA" for value in row), axis=1)
    output = output.loc[~data_rows].reset_index(drop=True)

    return output


def default_output_path() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return OUTPUT_DIR / f"chemical_amount_{timestamp}.csv"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Add calculated mass/volume columns to recommendation CSV.")
    parser.add_argument("--constraints", required=True, help="constraint-parser JSON path.")
    parser.add_argument("--recommendations-csv", required=True, help="Recommendation CSV path.")
    parser.add_argument("--chemical-space", default=str(DEFAULT_CHEMICAL_SPACE), help="chemical_space.csv or chemical_space.xlsx path.")
    parser.add_argument("--output", default="", help="Output CSV path.")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        constraints_path = Path(args.constraints)
        recommendations_csv_path = Path(args.recommendations_csv)
        chemical_space_path = Path(args.chemical_space)

        constraints = read_json(constraints_path)
        bo_df = pd.read_csv(recommendations_csv_path)
        chemical_space = parse_chemical_space(chemical_space_path)
        cache = load_cache(CACHE_FILE)
        basis_mmol, basis_name = find_basis_mmol(constraints)

        output_df = add_amount_columns(bo_df, constraints, chemical_space, cache, basis_mmol)
        out_path = Path(args.output) if args.output else default_output_path()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        output_df.to_csv(out_path, index=False, encoding="utf-8-sig")
        try:
            write_json(cache, CACHE_FILE)
        except OSError as exc:
            print(f"Warning: could not update PubChem cache {CACHE_FILE}: {exc}", file=sys.stderr)

        print(f"Output CSV generated: {out_path}")
        print(f"Recommendations: {recommendations_csv_path}")
        print(f"Constraints: {constraints_path}")
        print(f"Basis: {basis_name}, {basis_mmol:g} mmol")
        print(f"Rows: {len(output_df)}; columns: {len(output_df.columns)}")
        return 0
    except Exception as exc:
        print(f"Amount calculation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
