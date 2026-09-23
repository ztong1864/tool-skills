import os
from pathlib import Path

from pipeline_src.bo.table_builder import build_bo_table
from pipeline_src.descriptors.builder import build_descriptors
from pipeline_src.utils.temp_header import load_reaction_columns
from pipeline_src.utils.io import ensure_dir, read_json


def _apply_temp_header(schema: dict, project_root: str) -> dict:
    temp_path = Path(project_root).resolve().parent.parent / "KB" / "temp.json"
    reaction_columns = load_reaction_columns(temp_path)

    updated = dict(schema)
    updated["bo_table"] = dict(updated.get("bo_table", {}))
    updated["bo_table"]["columns"] = [
        "batch_id",
        *reaction_columns,
        "yield",
        "select_tag",
    ]
    updated["variables"] = [
        {
            "name": col,
            "kind": "categorical",
            "fact_field": col,
            "desc_file": f"{col}_desc_datadf.csv",
        }
        for col in reaction_columns
    ]
    updated["targets"] = [{"name": "yield", "fact_field": "yield_percent"}]
    updated["required_fields_for_select"] = [*reaction_columns, "yield_percent"]
    return updated


def run_publish_pipeline(
    *,
    schema: dict,
    process_in: str,
    publish_out: str,
    project_root: str,
    template_dir: str | None = None,
) -> dict:
    schema = _apply_temp_header(schema, project_root)
    desc_dir = os.path.join(publish_out, "descriptors")
    bo_inputs_dir = os.path.join(publish_out, "bo_inputs")
    ensure_dir(desc_dir)
    ensure_dir(bo_inputs_dir)

    facts_lit_path = os.path.join(process_in, "facts", "facts_literature.json")
    if not os.path.exists(facts_lit_path):
        raise FileNotFoundError(f"facts_literature.json not found: {facts_lit_path}")
    merged = read_json(facts_lit_path)

    manifest_path = os.path.join(desc_dir, "space_manifest.json")
    print(f"\n=== [Publish] Build descriptors ===", flush=True)
    template_dir = template_dir or os.path.join(project_root, "templates", "descriptors_metal_salt_chiral_amine")
    build_descriptors(
        facts=merged,
        schema=schema,
        template_dir=template_dir,
        output_dir=desc_dir,
        manifest_path=manifest_path,
    )
    print(f"[Publish] manifest -> {manifest_path}", flush=True)

    bo_table_path = os.path.join(bo_inputs_dir, "manual_conditions_round0.csv")
    print(f"\n=== [Publish] Build BO table ===", flush=True)
    build_bo_table(
        facts=merged,
        schema=schema,
        desc_dir=desc_dir,
        output_csv=bo_table_path,
        batch_id=0,
    )
    print(f"[Publish] bo_table -> {bo_table_path}", flush=True)

    return {
        "desc_dir": desc_dir,
        "bo_inputs_dir": bo_inputs_dir,
        "manifest_path": manifest_path,
        "bo_table_path": bo_table_path,
    }
