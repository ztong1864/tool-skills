import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from pipeline_src.llm.client import LLMClient
from pipeline_src.llm.prompts import (
    TRIAGE_SYSTEM,
    TRIAGE_USER_TEMPLATE,
    CANDIDATE_SYSTEM,
    CANDIDATE_USER_TEMPLATE,
)
from pipeline_src.schemas.schema_defs import TRIAGE_SCHEMA, CANDIDATE_SCHEMA
from pipeline_src.utils.hash import hash_dict
from pipeline_src.utils.io import append_jsonl, read_jsonl, read_text, write_json


def _reset_jsonl(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8"):
        pass


def _family_scope_only(target_scope: Dict | None) -> Dict:
    if not target_scope:
        return {}
    return {
        key: value
        for key, value in target_scope.items()
        if key != "allowed_values"
    }


def _screen_one_page(
    *,
    llm: LLMClient,
    text_path: str,
    target_scope: Dict | None = None,
) -> Dict:
    page_text = read_text(text_path).strip()
    metadata = _page_metadata(text_path)
    provenance = {"text_path": text_path, **metadata}

    if not page_text:
        return {
            "keep": False,
            "record": {
                "text_path": text_path,
                "triage": {
                    "doc_type": "UNKNOWN",
                    "usefulness_score": 0.0,
                    "keep": False,
                    "keep_reason": "",
                    "drop_reason": "empty_text",
                    "suspected_system_tag": False,
                },
                "meta": {"cached": True, "errors": ["empty_text_skipped"]},
                **metadata,
            },
        }

    user_prompt = TRIAGE_USER_TEMPLATE.format(
        provenance=provenance,
        page_text=page_text,
        target_scope=json.dumps(_family_scope_only(target_scope), ensure_ascii=False, indent=2),
    )
    triage, meta = llm.chat_json(
        system_prompt=TRIAGE_SYSTEM,
        user_prompt=user_prompt,
        schema=TRIAGE_SCHEMA,
        cache_namespace="triage_v1",
    )
    record = {
        "text_path": text_path,
        "triage": triage,
        "meta": meta,
        **metadata,
    }
    doc_type = str(triage.get("doc_type", "")).upper()
    if doc_type in {"MECHANISM", "SPECTRA"}:
        triage["keep"] = False
        triage["drop_reason"] = f"doc_type_filtered:{doc_type}"
    if target_scope and not bool(triage.get("suspected_system_tag", False)):
        triage["keep"] = False
        triage["drop_reason"] = triage.get("drop_reason") or "target_scope_filtered"
    return {
        "keep": bool(triage.get("keep", False)),
        "record": record,
    }


def _page_metadata(text_path: str) -> Dict[str, str]:
    page_id = os.path.splitext(os.path.basename(text_path))[0]
    paper_id = page_id.split("_page_")[0] if "_page_" in page_id else page_id
    return {
        "paper_id": paper_id,
        "page_id": page_id,
    }


def screen_page_texts(
    *,
    llm: LLMClient,
    page_text_paths: List[str],
    output_dir: str,
    target_scope: Dict | None = None,
    max_workers: int | None = None,
) -> Dict[str, str]:
    keep_path = os.path.join(output_dir, "candidates_raw.jsonl")
    drop_path = os.path.join(output_dir, "junk_index.jsonl")
    _reset_jsonl(keep_path)
    _reset_jsonl(drop_path)

    results_map: Dict[str, str] = {}
    keep_records = []
    drop_records = []
    keep_n = 0
    drop_n = 0
    error_n = 0
    total = len(page_text_paths)

    worker_count = max_workers or min(10, max(1, len(page_text_paths)))
    print(f"[Process] screen start: total={total} workers={worker_count}", flush=True)
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {executor.submit(_screen_one_page, llm=llm, text_path=text_path, target_scope=target_scope): idx for idx, text_path in enumerate(page_text_paths, start=1)}
        completed = 0
        for future in as_completed(futures):
            idx = futures[future]
            text_path = page_text_paths[idx - 1]
            try:
                result = future.result()
            except Exception as exc:
                metadata = _page_metadata(text_path)
                result = {
                    "keep": False,
                    "record": {
                        "text_path": text_path,
                        "triage": {
                            "doc_type": "UNKNOWN",
                            "usefulness_score": 0.0,
                            "keep": False,
                            "keep_reason": "",
                            "drop_reason": f"screen_error:{type(exc).__name__}",
                            "suspected_system_tag": False,
                        },
                        "meta": {"cached": False, "errors": [str(exc)]},
                        **metadata,
                    },
                }
                error_n += 1
            record = result["record"]
            if result["keep"]:
                append_jsonl(keep_path, [record])
                results_map[text_path] = "keep"
                keep_n += 1
            else:
                append_jsonl(drop_path, [record])
                results_map[text_path] = "drop"
                drop_n += 1
            completed += 1
            if completed == 1 or completed == total or completed % 10 == 0:
                print(f"[Process] screen {completed}/{total}: keep={keep_n} drop={drop_n} errors={error_n}", flush=True)

    return results_map


def extract_candidate_reactions(
    *,
    llm: LLMClient,
    screened_path: str,
    output_path: str,
    target_scope: Dict | None = None,
    candidate_limit: Optional[int] = None,
    max_workers: int | None = None,
) -> List[Dict]:
    rows = read_jsonl(screened_path)
    total = len(rows)
    out_rows: List[Dict] = []
    if not rows:
        print(f"[Process] candidates start: total=0 workers=0", flush=True)
        write_json(output_path, [])
        return []

    def _extract_for_row(row: Dict) -> List[Dict]:
        page_text = read_text(row["text_path"]).strip()
        if not page_text:
            return []
        user_prompt = CANDIDATE_USER_TEMPLATE.format(
            page_text=page_text,
            target_scope=json.dumps(_family_scope_only(target_scope), ensure_ascii=False, indent=2),
        )
        result, meta = llm.chat_json(
            system_prompt=CANDIDATE_SYSTEM,
            user_prompt=user_prompt,
            schema=CANDIDATE_SCHEMA,
            cache_namespace="candidates_v1",
        )
        metadata = _page_metadata(row["text_path"])
        records = []
        for cand in result.get("candidates", []):
            records.append(
                {
                    "candidate_id": hash_dict({"text_path": row["text_path"], "reaction_id": cand.get("reaction_id")}),
                    "source_id": row["text_path"],
                    "text_path": row["text_path"],
                    "page_id": metadata["page_id"],
                    "paper_id": metadata["paper_id"],
                    "reaction_id": cand.get("reaction_id"),
                    "reaction_key_guess": cand.get("reaction_key_guess"),
                    "reactant_smiles": cand.get("reactant_smiles", []),
                    "product_smiles": cand.get("product_smiles", []),
                    "conditions_texts": cand.get("conditions_texts", []),
                    "additional_info_texts": cand.get("additional_info_texts", []),
                    "triage": row.get("triage", {}),
                    "meta": meta,
                }
            )
        return records

    worker_count = max_workers or min(10, max(1, len(rows)))
    print(f"[Process] candidates start: total={total} workers={worker_count}", flush=True)
    all_records: List[List[Dict]] = [None] * len(rows)  # type: ignore[list-item]
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {executor.submit(_extract_for_row, row): idx for idx, row in enumerate(rows)}
        completed = 0
        error_n = 0
        for future in as_completed(futures):
            idx = futures[future]
            try:
                all_records[idx] = future.result()
            except Exception as exc:
                all_records[idx] = []
                error_n += 1
                print(f"[Process] candidates error {completed + 1}/{total}: {type(exc).__name__}: {exc}", flush=True)
            completed += 1
            if completed == 1 or completed == total or completed % 10 == 0:
                current_count = sum(len(chunk or []) for chunk in all_records if chunk is not None)
                print(f"[Process] candidates {completed}/{total}: records={current_count} errors={error_n}", flush=True)

    for records in all_records:
        for record in records or []:
            out_rows.append(record)
            if candidate_limit is not None and len(out_rows) >= candidate_limit:
                break
        if candidate_limit is not None and len(out_rows) >= candidate_limit:
            break

    write_json(output_path, out_rows)
    return out_rows
