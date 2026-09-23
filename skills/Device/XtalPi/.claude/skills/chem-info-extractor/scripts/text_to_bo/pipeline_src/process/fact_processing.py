import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

from pipeline_src.llm.client import LLMClient
from pipeline_src.llm.prompts import (
    DEFAULT_SYSTEM,
    build_default_user_prompt,
    FACT_SYSTEM,
    build_fact_user_prompt,
    MERGE_SYSTEM,
    MERGE_USER_TEMPLATE,
    NORMALIZE_SYSTEM,
    build_normalize_user_prompt,
)
from pipeline_src.normalizers.levels import normalize_solvent, parse_yield_percent
from pipeline_src.schemas.schema_defs import DEFAULT_SCHEMA, FACT_SCHEMA, MERGE_SCHEMA, NORMALIZE_SCHEMA
from pipeline_src.utils.hash import hash_dict
from pipeline_src.utils.io import read_json, read_text, write_csv, write_json


def _as_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "null"}:
        return None
    return text


def _alias_lookup(value: str, alias: Dict[str, str] | None = None) -> str | None:
    if not alias:
        return None
    if value in alias:
        return alias[value]
    low = value.lower()
    for key, mapped in alias.items():
        if str(key).strip().lower() == low:
            return mapped
    return None


def _normalize_label(value, *, alias: Dict[str, str] | None = None, default_if_missing: str | None = None) -> str | None:
    text = _as_text(value)
    if text is None:
        return default_if_missing
    if text.lower() == "none":
        return default_if_missing or "none"
    alias_value = _alias_lookup(text, alias)
    if alias_value is not None:
        return alias_value
    return text


def _normalize_optional_none(value, *, alias: Dict[str, str] | None = None) -> str:
    normalized = _normalize_label(value, alias=alias, default_if_missing="none")
    return normalized or "none"


def _normalize_yield_value(value, *, fallback_texts: List[str] | None = None) -> float | None:
    if value is None:
        for text in fallback_texts or []:
            parsed = parse_yield_percent(text)
            if parsed is not None:
                return parsed
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    parsed = parse_yield_percent(text)
    if parsed is not None:
        return parsed
    for fallback in fallback_texts or []:
        parsed = parse_yield_percent(fallback)
        if parsed is not None:
            return parsed
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def extract_fact_records(
    *,
    llm: LLMClient,
    candidate_path: str,
    output_path: str,
    reaction_columns: List[str],
    max_workers: int | None = None,
) -> List[Dict]:
    candidates = read_json(candidate_path)
    total = len(candidates)
    skipped_text_error = 0

    def _extract_one(cand: Dict) -> Dict | None:
        source_id = cand["source_id"]
        page_text = read_text(cand["text_path"])
        if not page_text.strip():
            return None

        doc_type = (cand.get("triage") or {}).get("doc_type", "UNKNOWN")
        user_prompt = build_fact_user_prompt(
            reaction_columns,
            source_id=source_id,
            doc_type=doc_type,
            default_conditions="null",
            page_text=page_text,
            candidate=json.dumps({"candidate": cand}, ensure_ascii=False, indent=2),
        )
        result, meta = llm.chat_json(
            system_prompt=FACT_SYSTEM,
            user_prompt=user_prompt,
            schema=FACT_SCHEMA,
            cache_namespace="fact_extract_v2",
        )
        record = result.get("record", {})
        record["record_id"] = record.get("record_id") or hash_dict({"source_id": source_id, "reaction_id": cand.get("reaction_id")})
        record["source_id"] = source_id
        record["paper_id"] = record.get("paper_id") or cand.get("paper_id") or _guess_paper_id(source_id)
        record["doc_type"] = record.get("doc_type") or doc_type
        return {
            **record,
            "missing_fields": result.get("missing_fields", []),
            "confidence": result.get("confidence", 0.0),
            "evidence": result.get("evidence", {}),
            "meta": meta,
        }

    worker_count = max_workers or min(10, max(1, len(candidates)))
    print(f"[Process] facts start: total={total} workers={worker_count}", flush=True)
    facts: List[Dict] = [None] * len(candidates)  # type: ignore[list-item]
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {executor.submit(_extract_one, cand): idx for idx, cand in enumerate(candidates)}
        completed = 0
        error_count = 0
        for future in as_completed(futures):
            idx = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = None
                error_count += 1
                print(f"[Process] facts error {completed + 1}/{total}: {type(exc).__name__}: {exc}", flush=True)
            if result is None:
                skipped_text_error += 1
            else:
                facts[idx] = result
            completed += 1
            if completed == 1 or completed == total or completed % 10 == 0:
                current_count = sum(1 for item in facts if item is not None)
                print(f"[Process] facts {completed}/{total}: extracted={current_count} skipped={skipped_text_error} errors={error_count}", flush=True)

    facts = [fact for fact in facts if fact is not None]
    write_json(output_path, facts)
    return facts


def build_paper_default_conditions(
    *,
    llm: LLMClient,
    facts_path: str,
    output_path: str,
    reaction_columns: List[str],
    max_workers: int | None = None,
) -> List[Dict]:
    facts = read_json(facts_path)
    grouped: Dict[str, List[Dict]] = {}
    for fact in facts:
        paper_id = fact.get("paper_id", "unknown")
        grouped.setdefault(paper_id, []).append(fact)

    items = list(grouped.items())
    total = len(items)
    defaults_all: List[Dict] = []

    def _build_for_paper(item):
        paper_id, records = item
        user_prompt = build_default_user_prompt(reaction_columns, records=records)
        result, _ = llm.chat_json(
            system_prompt=DEFAULT_SYSTEM,
            user_prompt=user_prompt,
            schema=DEFAULT_SCHEMA,
            cache_namespace="default_conditions_v2",
        )
        out = []
        for default in result.get("defaults", []):
            default["paper_id"] = paper_id
            out.append(default)
        return out

    worker_count = max_workers or min(10, max(1, len(items)))
    print(f"[Process] defaults start: total={total} workers={worker_count}", flush=True)
    ordered_defaults: List[List[Dict]] = [None] * len(items)  # type: ignore[list-item]
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {executor.submit(_build_for_paper, item): idx for idx, item in enumerate(items)}
        completed = 0
        error_count = 0
        for future in as_completed(futures):
            idx = futures[future]
            try:
                ordered_defaults[idx] = future.result()
            except Exception as exc:
                ordered_defaults[idx] = []
                error_count += 1
                print(f"[Process] defaults error {completed + 1}/{total}: {type(exc).__name__}: {exc}", flush=True)
            completed += 1
            if completed == 1 or completed == total or completed % 5 == 0:
                current_count = sum(len(chunk or []) for chunk in ordered_defaults if chunk is not None)
                print(f"[Process] defaults {completed}/{total}: total_defaults={current_count} errors={error_count}", flush=True)

    for chunk in ordered_defaults:
        defaults_all.extend(chunk or [])

    write_json(output_path, defaults_all)
    return defaults_all


def apply_paper_defaults(facts: List[Dict], defaults: List[Dict]) -> List[Dict]:
    # Paper-level defaults are too broad for mixed full-synthesis/SI documents:
    # a single PDF can contain unrelated preparation, workup, and target-reaction
    # steps. Keep the stage as an explicit no-op unless future defaults carry a
    # page/table scope that can be matched safely.
    if defaults:
        return [dict(fact) for fact in facts]

    defaults_by_paper: Dict[str, List[Dict]] = {}
    for default in defaults:
        defaults_by_paper.setdefault(default.get("paper_id"), []).append(default)

    enriched: List[Dict] = []
    fill_fields = ["metal_salt_1", "metal_salt_2", "chiral_amine", "molecular_sieve", "solvent"]
    for fact in facts:
        paper_defaults = defaults_by_paper.get(fact.get("paper_id"), [])
        merged = dict(fact)
        for default in paper_defaults[:1]:
            for key in fill_fields:
                if merged.get(key) is None and default.get(key) is not None:
                    merged[key] = default[key]
                    merged.setdefault("notes", "")
                    merged["notes"] += f" | filled_by_default:{key}"
        enriched.append(merged)
    return enriched


def postprocess_fact_records(
    *,
    facts: List[Dict],
    normalization: Dict,
    target_scope: Dict | None = None,
    exclude_doc_types: List[str] | None = None,
) -> List[Dict]:
    if not facts:
        return []
    exclude = {d.upper() for d in (exclude_doc_types or ["MECHANISM", "SPECTRA"])}
    metal_salt_alias = normalization.get("metal_salt_alias", {})
    amine_alias = normalization.get("chiral_amine_alias", {})
    sieve_alias = normalization.get("molecular_sieve_alias", {})
    solvent_alias = normalization.get("solvent_alias", {})
    prefer_isolated = bool(normalization.get("yield_prefer_isolated", True))

    processed: List[Dict] = []
    for fact in facts:
        doc_type = str(fact.get("doc_type", "")).upper()
        if doc_type in exclude:
            continue

        rec = dict(fact)
        evidence = rec.get("evidence") or {}
        notes = rec.get("notes") or ""

        rec["metal_salt_1"] = _normalize_label(
            rec.get("metal_salt_1") or evidence.get("metal_salt_1"),
            alias=metal_salt_alias,
        )
        rec["metal_salt_2"] = _normalize_optional_none(
            rec.get("metal_salt_2") or evidence.get("metal_salt_2"),
            alias=metal_salt_alias,
        )
        rec["chiral_amine"] = _normalize_label(
            rec.get("chiral_amine") or evidence.get("chiral_amine"),
            alias=amine_alias,
        )
        rec["molecular_sieve"] = _normalize_optional_none(
            rec.get("molecular_sieve") or evidence.get("molecular_sieve"),
            alias=sieve_alias,
        )

        solvent_value = rec.get("solvent") or evidence.get("solvent")
        rec["solvent"] = normalize_solvent(solvent_value, solvent_alias) if solvent_value is not None else None

        yield_texts = []
        for key in ("yield_percent",):
            val = evidence.get(key)
            if val is not None:
                yield_texts.append(str(val))
        if prefer_isolated and "isolated" not in " ".join(yield_texts).lower():
            yield_texts.append(notes)
        rec["yield_percent"] = _normalize_yield_value(rec.get("yield_percent"), fallback_texts=yield_texts)

        if rec.get("metal_salt_2") is None:
            rec["metal_salt_2"] = "none"
        if rec.get("molecular_sieve") is None:
            rec["molecular_sieve"] = "none"

        processed.append(rec)

    by_paper: Dict[str, List[Dict]] = {}
    for rec in processed:
        # Only fill within the same extracted page/source, never across a whole paper.
        by_paper.setdefault(rec.get("source_id") or rec.get("page_id") or "unknown", []).append(rec)

    fill_fields = ["metal_salt_1", "metal_salt_2", "chiral_amine", "molecular_sieve", "solvent"]
    for _, group in by_paper.items():
        unique_values: Dict[str, object] = {}
        for field in fill_fields:
            values = {g.get(field) for g in group if g.get(field) not in (None, "", "nan")}
            if len(values) == 1:
                unique_values[field] = next(iter(values))
        if not unique_values:
            continue
        for g in group:
            for field, value in unique_values.items():
                if g.get(field) in (None, "", "nan"):
                    g[field] = value
                    g["notes"] = (g.get("notes") or "") + f" | postprocess_fill:{field}"

    return processed


def normalize_fact_records(
    *,
    llm: LLMClient,
    facts: List[Dict],
    defaults: List[Dict],
    reaction_columns: List[str],
    exclude_doc_types: List[str] | None = None,
    max_workers: int | None = None,
) -> List[Dict]:
    if not facts:
        return []
    exclude = {d.upper() for d in (exclude_doc_types or ["MECHANISM", "SPECTRA"])}
    defaults_by_paper: Dict[str, List[Dict]] = {}
    for default in defaults:
        defaults_by_paper.setdefault(default.get("paper_id"), []).append(default)

    by_paper: Dict[str, List[Dict]] = {}
    for rec in facts:
        by_paper.setdefault(rec.get("paper_id", "unknown"), []).append(rec)

    normalized_records: List[Dict] = []

    def _normalize_one(rec: Dict, context: Dict) -> Dict | None:
        doc_type = str(rec.get("doc_type", "")).upper()
        if doc_type in exclude:
            return None
        user_prompt = build_normalize_user_prompt(
            reaction_columns,
            paper_context=context,
            record={"record": rec, "evidence": rec.get("evidence", {})},
        )
        result, meta = llm.chat_json(
            system_prompt=NORMALIZE_SYSTEM,
            user_prompt=user_prompt,
            schema=NORMALIZE_SCHEMA,
            cache_namespace="normalize_v2",
        )
        normalized = result.get("normalized", {})

        out = dict(rec)
        out["metal_salt_1"] = _normalize_label(_as_text(normalized.get("metal_salt_1")), alias=None, default_if_missing=out.get("metal_salt_1"))
        out["metal_salt_2"] = _normalize_optional_none(_as_text(normalized.get("metal_salt_2")), alias=None)
        out["chiral_amine"] = _normalize_label(_as_text(normalized.get("chiral_amine")), alias=None, default_if_missing=out.get("chiral_amine"))
        out["molecular_sieve"] = _normalize_optional_none(_as_text(normalized.get("molecular_sieve")), alias=None)
        solvent_norm = _as_text(normalized.get("solvent"))
        out["solvent"] = normalize_solvent(solvent_norm, None) if solvent_norm is not None else out.get("solvent")
        out["yield_percent"] = _normalize_yield_value(normalized.get("yield_percent"), fallback_texts=[str(rec.get("yield_percent") or ""), str(rec.get("notes") or "")])
        out["notes"] = (out.get("notes") or "") + f" | llm_normalize:{result.get('notes', '')}"
        out["normalization_meta"] = meta
        return out

    worker_count = max_workers or min(10, max(1, sum(len(v) for v in by_paper.values())))
    ordered_records: List[Dict] = [None] * sum(len(v) for v in by_paper.values())  # type: ignore[list-item]
    tasks = []
    idx = 0
    for paper_id, records in by_paper.items():
        context = _paper_context(records, defaults_by_paper.get(paper_id, []))
        for rec in records:
            tasks.append((idx, rec, context))
            idx += 1

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {executor.submit(_normalize_one, rec, context): idx for idx, rec, context in tasks}
        completed = 0
        total = len(tasks)
        error_count = 0
        print(f"[Process] normalize start: total={total} workers={worker_count}", flush=True)
        for future in as_completed(futures):
            idx = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = None
                error_count += 1
                print(f"[Process] normalize error {completed + 1}/{total}: {type(exc).__name__}: {exc}", flush=True)
            if result is not None:
                ordered_records[idx] = result
            completed += 1
            if completed == 1 or completed == total or completed % 10 == 0:
                current_count = sum(1 for item in ordered_records if item is not None)
                print(f"[Process] normalize {completed}/{total}: normalized={current_count} errors={error_count}", flush=True)

    normalized_records = [rec for rec in ordered_records if rec is not None]
    return normalized_records


def deduplicate_fact_records(
    *,
    llm: LLMClient,
    facts: List[Dict],
    output_path: str,
) -> List[Dict]:
    if not facts:
        write_json(output_path, [])
        return []

    user_prompt = MERGE_USER_TEMPLATE.format(records=facts)
    result, _ = llm.chat_json(
        system_prompt=MERGE_SYSTEM,
        user_prompt=user_prompt,
        schema=MERGE_SCHEMA,
        cache_namespace="merge_v2",
    )
    merge_groups = result.get("merge_groups", [])
    record_map = {f["record_id"]: f for f in facts}
    merged_ids = set()
    merged_records = []

    for group in merge_groups:
        record_ids = group.get("record_ids", [])
        representative_id = group.get("representative_id")
        if not record_ids or representative_id not in record_map:
            continue
        base = dict(record_map[representative_id])
        for rid in record_ids:
            if rid == representative_id:
                continue
            other = record_map.get(rid, {})
            for key, value in other.items():
                if base.get(key) is None and value is not None:
                    base[key] = value
            merged_ids.add(rid)
        merged_records.append(base)
        merged_ids.add(representative_id)

    for rid, record in record_map.items():
        if rid not in merged_ids:
            merged_records.append(record)

    write_json(output_path, merged_records)
    return merged_records


def write_fact_records_csv(facts: List[Dict], output_csv: str) -> None:
    if not facts:
        write_csv(output_csv, [], [])
        return
    fieldnames = list(facts[0].keys())
    write_csv(output_csv, facts, fieldnames)


def _paper_context(records: List[Dict], defaults: List[Dict]) -> Dict:
    fields = ["metal_salt_1", "metal_salt_2", "chiral_amine", "molecular_sieve", "solvent"]
    context = {"unique_values": {}, "defaults": defaults}
    for field in fields:
        values = {r.get(field) for r in records if r.get(field) not in (None, "", "nan")}
        context["unique_values"][field] = sorted(values, key=lambda value: str(value))[:10]
    return context


def _guess_paper_id(source_id: str) -> str:
    base = os.path.basename(source_id)
    return base.split(".")[0]
