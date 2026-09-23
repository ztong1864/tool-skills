import os
from typing import Dict, List, Tuple

import pandas as pd

from pipeline_src.utils.io import ensure_dir, write_csv


def _load_desc_levels(desc_dir: str, desc_file: str) -> List[str]:
    path = os.path.join(desc_dir, desc_file)
    if not os.path.exists(path):
        return []
    df = pd.read_csv(path, index_col=0)
    return df.index.tolist()


def build_bo_table(
    *,
    facts: List[Dict],
    schema: Dict,
    desc_dir: str,
    output_csv: str,
    batch_id: int = 0,
) -> List[Dict]:
    levels_by_var = {}
    for var in schema["variables"]:
        levels_by_var[var["name"]] = set(_load_desc_levels(desc_dir, var["desc_file"]))

    rows = []
    for fact in facts:
        row = {"batch_id": batch_id, "select_tag": True}
        for var in schema["variables"]:
            value = fact.get(var["fact_field"])
            row[var["name"]] = value
            if value is None or value not in levels_by_var[var["name"]]:
                row["select_tag"] = False
        for target in schema["targets"]:
            row[target["name"]] = fact.get(target["fact_field"])
            if row[target["name"]] is None:
                row["select_tag"] = False
        rows.append(row)

    ensure_dir(os.path.dirname(output_csv))
    write_csv(output_csv, rows, schema["bo_table"]["columns"])
    return rows
