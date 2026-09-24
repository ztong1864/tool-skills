---
name: review-metadata-prep
description: Prepare a MinerU-parsed review-writing paper library for metadata review. Use when Codex needs to extract or validate required paper metadata and eight fixed LLM classification tags from PDF/Markdown/content_list outputs.
---

# Review Metadata Prep

## FounDryClaw Location Rules

When this skill runs inside FounDryClaw, do not assume the old `review-writer` repository path. Resolve locations in this order:

1. Use environment variables when present: `FOUNDRYCLAW_REVIEW_ROOT`, `FOUNDRYCLAW_REVIEW_LIBRARY_ROOT`, `FOUNDRYCLAW_REVIEW_PROJECTS_ROOT`, `FOUNDRYCLAW_MINERU_OUTPUT_ROOT`, `FOUNDRYCLAW_REVIEW_PDF_ROOT`, `FOUNDRYCLAW_REVIEW_SKILLS_ROOT`.
2. If the user provides `--review-root`, use it.
3. Otherwise treat the current FounDryClaw Claude workdir as the review root.
4. Store project artifacts under `<review-root>/review-projects/<project_id>/` and library metadata under `<review-root>/review-library/`.
5. Run bundled scripts by path relative to this skill folder, for example `python scripts/<script>.py`; the scripts contain a shared resolver for the paths above.

For lower-capability backend models: before running a script, identify `review_root` explicitly and pass `--review-root <review_root>` when uncertain. Never use `<review-root>` as a real path in FounDryClaw.

Use this skill to implement the writing-preparation stage for a review-writing agent.

The skill assumes PDFs have already been parsed by MinerU and that a `mineru-outputs/manifest.json` exists.

Do not enter plan mode for this skill. Go directly into the Workflow steps below and start running them.

## Workflow

1. Build paper metadata:

```bash
python <review-root>/skills/review-metadata-prep/scripts/prepare_metadata.py \
  --review-root <review-root> \
  --mineru-output <review-root>/mineru-outputs \
  --pdf-root <review-root>/source-paper/<your-subfolder> \
  --discover-from-pdf-root \
  --append-registry
```

Use `--discover-from-pdf-root` when `manifest.json` only records the latest MinerU batch.
Use `--append-registry` when adding a new source-paper folder to an existing library.
`review-library/metadata/extraction_prompts/` and the `papers/`/`registry/` scaffold
are created automatically on first run; no manual seeding is needed.

2. Generate the eight structured tags. This step is mandatory, not optional —
`prepare_metadata.py` alone (even with `--use-llm`) only fills bibliographic fields
well; the eight `structured_tags` must be produced by `batch_llm_retag_metadata.py`
(see LLM Mode below).

3. Validate metadata:

```bash
python <review-root>/skills/review-metadata-prep/scripts/validate_metadata.py \
  --review-root <review-root>
```

4. Launch the local review dashboard from the separate view module when human audit is needed:

```bash
python <review-root>/view/serve_review_dashboard.py \
  --review-root <review-root> \
  --host 127.0.0.1 \
  --port 8765
```

Open:

```text
http://127.0.0.1:8765/library
```

## LLM Mode

By default, `prepare_metadata.py` uses deterministic fallback rules so the pipeline can run without API credentials.

For useful classification tags, use LLM mode. The LLM extracts required bibliographic fields and exactly eight structured tags:

```text
product
substrate
catalyst_or_method
organometallic_partner
ligand_or_chiral_source
leaving_group
reaction_type
document_scope
```

Each tag value must be selected from the active shared taxonomy profile under the matching category, or `not specified`. The built-in default is the empty `general_academic` profile (`rules = []` — no domain vocabulary at all, so every category legitimately has nothing but `not specified` to choose from). `llm_retag_metadata.py`/`batch_llm_retag_metadata.py` auto-detect a better-fitting profile instead of using that empty default: they sample existing papers' title/abstract and call `suggest_taxonomy_profile()` on it, which matches keywords (e.g. "enantioselective"/"asymmetric catalysis"/"cross-coupling" → `chemistry_general`; "allene"/"联烯" → `allene`) and prints the profile it picked (`Taxonomy profile: ...`) at startup — check that line if tags come back empty. Force a specific profile with `REVIEW_TAXONOMY_PROFILE`, or point `REVIEW_CLASSIFICATION_RULES` at an absolute or workspace-relative Python rules file. Metadata must record the active taxonomy path and SHA-256 identity.

Inside a FounDryClaw chat session, `--base-url`/`--api-key`/`--model` are usually
unnecessary: these scripts first try to resolve the invoking user's own saved
`OPENAI-API-KEY` provider (configured under Settings → 密钥管理) automatically,
and only fall back to the flags/env vars below when that isn't configured or is
explicitly overridden. An explicit `--base-url`/`--api-key` always wins over the
saved provider, for manual debugging.

Outside FounDryClaw (standalone use), enable LLM enhancement by setting:

```bash
export OPENAI_API_KEY=...
```

Then run:

```bash
python <review-root>/skills/review-metadata-prep/scripts/prepare_metadata.py \
  --review-root <review-root> \
  --mineru-output <review-root>/mineru-outputs \
  --pdf-root <review-root>/source-paper/<your-subfolder> \
  --discover-from-pdf-root \
  --append-registry \
  --use-llm \
  --model gpt-6-luna \
  --reasoning-effort high \
  --wire-api responses
```

Use `--wire-api chat-completions` instead of the default `responses` if the configured
base URL does not support the Responses API for this model.

LLM extraction is constrained to the first-page blocks, title/author/abstract candidates, and early Markdown context. Do not send full papers unless explicitly needed.

To refresh only the eight LLM tags on an existing library without rebuilding paper IDs or paths
(inside FounDryClaw, omit `--base-url`/`--api-key`/`--model` — see above):

```bash
python <review-root>/skills/review-metadata-prep/scripts/llm_retag_metadata.py \
  --review-root <review-root> \
  --reasoning-effort high \
  --wire-api responses
```

Use `--paper-id <paper_id>` (repeatable) to retag one or a few specific papers instead of the
whole library — useful when remediating a small number of failures (see Remediation below).

For a full-library refresh, prefer the resumable batch runner. It processes three papers per round by default, skips already successful LLM-tagged papers, writes progress after every paper, and retries failures:

```bash
python <review-root>/skills/review-metadata-prep/scripts/batch_llm_retag_metadata.py \
  --review-root <review-root> \
  --batch-size 3 \
  --max-attempts 5 \
  --retry-delay 30 \
  --sleep-seconds 0.5 \
  --wire-api responses
```

Use `--force` only when existing successful LLM tags should be overwritten. Use `--retry-forever` only when the API failures are known to be transient.

Useful options:

```text
--paper-id P001
--limit 5
--base-url <openai-compatible-base-url>
--api-key <key>
--reasoning-effort high
--wire-api responses|chat-completions
--sleep-seconds 0.5
```

Outputs:

```text
review-library/metadata/llm_retag_report.json
review-library/metadata/llm_retag_report.md
review-library/metadata/llm_retag_batch_report.json
review-library/metadata/llm_retag_batch_report.md
```

If old metadata files need the new `structured_tags` field before LLM retagging:

```bash
python <review-root>/skills/review-metadata-prep/scripts/backfill_structured_tags.py \
  --review-root <review-root>
```

This only writes `not specified` placeholders for schema compatibility. It does not replace LLM tagging.

## Outputs

The skill writes:

```text
review-library/
  registry/
    papers.jsonl
  metadata/
    papers/<paper_id>.metadata.json
    metadata_validation.json
    metadata_validation.md
    extraction_prompts/
      metadata_extraction_system.md
      metadata_schema.json
```

## Metadata Rules

Each paper metadata JSON must include:

```text
paper_id
slug
title
authors
year
journal
doi
abstract
structured_tags
source_paths
extraction
human_review
quality
```

Every extracted field should carry:

```text
value
source
confidence
human_checked
```

Use `human_review` for audit status and notes. Local paper retrieval uses only the eight values inside `structured_tags`; do not generate or rely on legacy `keywords`, `llm_tags`, `human_tags`, or category compatibility fields.

## Human Audit Dashboard

The dashboard code lives outside this skill:

```text
<review-root>/view/
```

The dashboard is a local review console, not the source of truth. The source of truth is the JSON file on disk.

The dashboard should support:

```text
paper list
PDF preview
MinerU Markdown preview
metadata view
JSON editing
save metadata
mark reviewed
basic search by title, author, keyword, tag
```

## Validation

Run validation after extraction and after manual edits. Treat these as blocking issues:

```text
missing paper_id
missing title
missing authors
missing year
missing abstract
missing structured_tags
missing any of the eight structured tag keys
missing source PDF
missing Markdown
missing metadata JSON
invalid JSON
```

Treat these as review warnings:

```text
missing journal
missing DOI
missing structured_tags
structured tag value is not specified
low confidence title
low confidence abstract
not human reviewed
```

### Remediation

When `metadata_validation.md` lists blocking issues for specific papers:

- `missing_authors` / `missing_year` / `missing_abstract`: re-run LLM extraction for just
  that paper with `llm_retag_metadata.py --paper-id <paper_id>`. If the field is genuinely
  absent from the source PDF (e.g. a preprint with no formal abstract), edit the paper's
  metadata JSON by hand and set `human_checked: true` on that field so validation stops
  flagging it, then set `human_review.status` accordingly.
- `invalid_structured_tag_<key>`: the LLM returned a label that is not in the active
  taxonomy profile's allowed list for that category. Re-run `llm_retag_metadata.py
  --paper-id <paper_id>`; if it recurs, the paper may need a `human_review` entry marking
  it `needs_manual_entry` so it is not silently skipped in downstream stages.
- If every structured tag for every paper reads `not specified`, this has three
  independent possible causes seen in practice, in the order to check them —
  fixing only one and re-running can still leave the symptom unchanged if
  another is also present:
  1. **No real taxonomy loaded.** The default `general_academic` profile is
     intentionally empty, so `not specified` is the only legitimate choice
     under it. Check the run's own startup line: `Taxonomy profile: ...`
     should say `chemistry_general` or `allene` (auto-detected from existing
     papers' title/abstract), not `general_academic`. If auto-detection picked
     the wrong one for this paper set, force it with
     `REVIEW_TAXONOMY_PROFILE=chemistry_general` (or point
     `REVIEW_CLASSIFICATION_RULES` at a custom rules file).
  2. **A deterministic fallback ran, not the LLM.** Confirm `structured_tags.source`
     in a sample metadata file starts with `llm` — a fallback-only run without
     `--use-llm` legitimately leaves every tag `not specified` with a non-`llm`
     source. Necessary but **not sufficient**: see #3, which presents with an
     `llm_...` source too.
  3. **The merge silently discarded a good LLM result.** `merge_llm()` only
     overwrites the stored `structured_tags` when the new result's confidence is
     `>=` the previously stored confidence. If some earlier run stamped an empty
     all-`not specified` result with a high confidence (e.g. `0.99` — this
     happened when the taxonomy was empty per #1, or a request was malformed),
     every later retag's genuinely correct result (confidence ~0.95) can lose
     that comparison and get silently thrown away — even though the API call
     itself returned real, differentiated tags and the script reports `ok`.
     Nothing errors, so this is easy to miss. Diagnostic: check the *stored*
     `structured_tags.confidence` on an affected paper — a suspiciously high
     value on an all-`not specified` result is the signature. `merge_llm()` now
     special-cases this (an all-`not specified` stored value always yields to a
     fresh result regardless of confidence), so once #1 is also fixed, a plain
     retag should self-heal without any manual JSON editing. If it still doesn't,
     don't trust the script's "ok" report alone — make one raw API call by hand
     with the same payload (`build_llm_payload(...)`) and diff its response
     against what actually landed on disk.
