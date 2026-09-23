import os
from typing import Optional, Set

from pipeline_src.llm.client import LLMClient
from pipeline_src.process.page_screening import screen_page_texts, extract_candidate_reactions
from pipeline_src.process.fact_processing import (
    extract_fact_records,
    build_paper_default_conditions,
    apply_paper_defaults,
    normalize_fact_records,
    postprocess_fact_records,
    deduplicate_fact_records,
    write_fact_records_csv,
)
from pipeline_src.utils.temp_header import load_reaction_columns
from pipeline_src.utils.io import ensure_dir, write_json

MAX_WORKERS = 10


def load_subset_ids(subset_ids: Optional[str], subset_file: Optional[str]) -> Set[str]:
    ids: Set[str] = set()
    if subset_ids:
        for part in subset_ids.split(","):
            val = part.strip()
            if val:
                ids.add(val)
    if subset_file:
        with open(subset_file, "r", encoding="utf-8") as f:
            for line in f:
                val = line.strip()
                if val:
                    ids.add(val)
    return ids


def collect_page_text_paths(pdf_in: str, subset_ids: Optional[str], subset_file: Optional[str], max_payloads: Optional[int]) -> list[str]:
    page_text_paths = []
    selected_ids = load_subset_ids(subset_ids, subset_file)
    if selected_ids:
        for pid in sorted(selected_ids):
            pid_dir = os.path.join(pdf_in, pid)
            if os.path.isdir(pid_dir):
                page_text_paths.extend(
                    os.path.join(pid_dir, name)
                    for name in sorted(os.listdir(pid_dir))
                    if name.lower().endswith(".txt") and "_page_" in name.lower()
                )
    else:
        page_text_paths = sorted(
            os.path.join(dirpath, name)
            for dirpath, _, filenames in os.walk(pdf_in)
            for name in filenames
            if name.lower().endswith(".txt") and "_page_" in name.lower()
        )
    if max_payloads:
        page_text_paths = page_text_paths[:max_payloads]
    return page_text_paths


def run_process_pipeline(
    *,
    llm: LLMClient,
    pdf_in: str,
    process_out: str,
    subset_ids: Optional[str] = None,
    subset_file: Optional[str] = None,
    max_payloads: Optional[int] = None,
    candidate_limit: Optional[int] = None,
    normalization_cfg: Optional[dict] = None,
    target_scope: Optional[dict] = None,
) -> dict:
    candidates_dir = os.path.join(process_out, "candidates")
    facts_dir = os.path.join(process_out, "facts")
    ensure_dir(candidates_dir)
    ensure_dir(facts_dir)

    page_text_paths = collect_page_text_paths(pdf_in, subset_ids, subset_file, max_payloads)
    if not page_text_paths:
        raise FileNotFoundError(f"No extracted PDF text found under {pdf_in}")

    reaction_columns = load_reaction_columns()
    print(f"[Process] reaction_columns={reaction_columns}", flush=True)

    print(f"\n=== [Process] Screen page text ===", flush=True)
    print(f"[Process] inputs={len(page_text_paths)}", flush=True)
    screen_page_texts(
        llm=llm,
        page_text_paths=page_text_paths,
        output_dir=candidates_dir,
        target_scope=target_scope,
        max_workers=MAX_WORKERS,
    )

    screened_path = os.path.join(candidates_dir, "candidates_raw.jsonl")
    candidate_path = os.path.join(candidates_dir, "candidates.json")
    print(f"\n=== [Process] Extract candidate reactions ===", flush=True)
    extract_candidate_reactions(
        llm=llm,
        screened_path=screened_path,
        output_path=candidate_path,
        target_scope=target_scope,
        candidate_limit=candidate_limit,
        max_workers=MAX_WORKERS,
    )

    facts_raw_path = os.path.join(facts_dir, "facts_raw.json")
    print(f"\n=== [Process] Extract fact records ===", flush=True)
    facts = extract_fact_records(
        llm=llm,
        candidate_path=candidate_path,
        output_path=facts_raw_path,
        reaction_columns=reaction_columns,
        max_workers=MAX_WORKERS,
    )
    print(f"[Process] facts_raw={len(facts)} -> {facts_raw_path}", flush=True)

    defaults_path = os.path.join(facts_dir, "default_conditions.json")
    print(f"\n=== [Process] Build paper defaults ===", flush=True)
    defaults = build_paper_default_conditions(
        llm=llm,
        facts_path=facts_raw_path,
        output_path=defaults_path,
        reaction_columns=reaction_columns,
        max_workers=MAX_WORKERS,
    )
    print(f"[Process] defaults={len(defaults)} -> {defaults_path}", flush=True)

    enriched = apply_paper_defaults(facts, defaults)
    facts_enriched_path = os.path.join(facts_dir, "facts_enriched.json")
    write_json(facts_enriched_path, enriched)
    print(f"[Process] facts_enriched={len(enriched)} -> {facts_enriched_path}", flush=True)

    normalized = normalize_fact_records(
        llm=llm,
        facts=enriched,
        defaults=defaults,
        reaction_columns=reaction_columns,
        max_workers=MAX_WORKERS,
    )
    facts_normalized_path = os.path.join(facts_dir, "facts_normalized.json")
    write_json(facts_normalized_path, normalized)
    print(f"[Process] facts_normalized={len(normalized)} -> {facts_normalized_path}", flush=True)

    facts_postprocessed = postprocess_fact_records(
        facts=normalized,
        normalization=normalization_cfg or {},
        target_scope=target_scope or {},
    )
    facts_postprocessed_path = os.path.join(facts_dir, "facts_postprocessed.json")
    write_json(facts_postprocessed_path, facts_postprocessed)
    print(f"[Process] facts_postprocessed={len(facts_postprocessed)} -> {facts_postprocessed_path}", flush=True)

    facts_lit_path = os.path.join(facts_dir, "facts_literature.json")
    print(f"\n=== [Process] Semantic dedup ===", flush=True)
    merged = deduplicate_fact_records(llm=llm, facts=facts_postprocessed, output_path=facts_lit_path)
    facts_csv_path = os.path.join(facts_dir, "facts_literature.csv")
    write_fact_records_csv(merged, facts_csv_path)
    print(f"[Process] facts_literature={len(merged)} -> {facts_lit_path}", flush=True)
    print(f"[Process] facts_literature.csv -> {facts_csv_path}", flush=True)

    return {
        "candidates_dir": candidates_dir,
        "facts_dir": facts_dir,
        "facts_raw_path": facts_raw_path,
        "facts_literature_path": facts_lit_path,
        "facts_literature_csv": facts_csv_path,
    }
