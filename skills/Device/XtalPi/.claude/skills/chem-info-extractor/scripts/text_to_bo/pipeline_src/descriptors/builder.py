import os
import re
from typing import Dict, List, Tuple

import pandas as pd

from pipeline_src.utils.io import ensure_dir, write_json


def _load_desc(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path, index_col=0)


def _dummy_row(columns: List[str]) -> pd.Series:
    if not columns:
        return pd.Series({"dummy": 0})
    return pd.Series({col: 0 for col in columns})


def _numeric_row(var_name: str, level: str, columns: List[str]) -> pd.Series | None:
    text = str(level).strip().lower()
    num_match = re.search(r"(\d+(?:\.\d+)?)", text)
    number = float(num_match.group(1)) if num_match else None
    if var_name == "tempo" and number is not None:
        mol_percent = number if "mol%" in text else (number * 100 if "equiv" in text else number)
        equiv = number if "equiv" in text else mol_percent / 100.0
        row = {col: 0 for col in columns}
        if "mol_percent" in row:
            row["mol_percent"] = mol_percent
        if "equiv" in row:
            row["equiv"] = equiv
        return pd.Series(row)
    if var_name == "ratio" and number is not None:
        if "mol%" in text:
            equiv = number / 100.0
            mol_percent = number
        else:
            equiv = number
            mol_percent = number * 100.0
        row = {col: 0 for col in columns}
        if "equiv" in row:
            row["equiv"] = equiv
        if "mol_percent" in row:
            row["mol_percent"] = mol_percent
        return pd.Series(row)
    if var_name == "volume" and number is not None:
        row = {col: 0 for col in columns}
        if "volume_mL" in row:
            row["volume_mL"] = number
        return pd.Series(row)
    return None


def build_descriptors(
    *,
    facts: List[Dict],
    schema: Dict,
    template_dir: str,
    output_dir: str,
    manifest_path: str,
) -> Dict:
    ensure_dir(output_dir)
    manifest = {"variables": []}

    for var in schema["variables"]:
        name = var["name"]
        fact_field = var["fact_field"]
        desc_file = var["desc_file"]
        template_path = os.path.join(template_dir, desc_file)
        desc_df = _load_desc(template_path)

        levels = sorted({f.get(fact_field) for f in facts if f.get(fact_field)})
        reused = []
        dummy = []
        output_rows = []

        if not desc_df.empty:
            columns = list(desc_df.columns)
        else:
            columns = ["dummy"]

        for level in levels:
            if not desc_df.empty and level in desc_df.index:
                output_rows.append(desc_df.loc[level])
                reused.append(level)
            else:
                numeric = _numeric_row(name, level, columns)
                if numeric is not None:
                    output_rows.append(numeric)
                    dummy.append(level)
                else:
                    output_rows.append(_dummy_row(columns))
                    dummy.append(level)

        if levels:
            out_df = pd.DataFrame(output_rows, index=levels)
        else:
            out_df = pd.DataFrame(columns=columns)

        out_path = os.path.join(output_dir, desc_file)
        out_df.to_csv(out_path)

        manifest["variables"].append(
            {
                "name": name,
                "levels": levels,
                "reused_levels": reused,
                "dummy_levels": dummy,
                "desc_file": desc_file,
            }
        )

    write_json(manifest_path, manifest)
    return manifest
