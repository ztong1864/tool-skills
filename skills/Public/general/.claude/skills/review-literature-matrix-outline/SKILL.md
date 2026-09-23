---
name: review-literature-matrix-outline
description: Read every paper explicitly selected by the human reviewer, build a concise fixed-field literature matrix, and draft review outline options using the writing-rule skill.
---

# Review Literature Matrix Outline

## FounDryClaw Location Rules

When this skill runs inside FounDryClaw, do not assume the old `review-writer` repository path. Resolve locations in this order:

1. Use environment variables when present: `FOUNDRYCLAW_REVIEW_ROOT`, `FOUNDRYCLAW_REVIEW_LIBRARY_ROOT`, `FOUNDRYCLAW_REVIEW_PROJECTS_ROOT`, `FOUNDRYCLAW_MINERU_OUTPUT_ROOT`, `FOUNDRYCLAW_REVIEW_PDF_ROOT`, `FOUNDRYCLAW_REVIEW_SKILLS_ROOT`.
2. If the user provides `--review-root`, use it.
3. Otherwise treat the current FounDryClaw Claude workdir as the review root.
4. Store project artifacts under `<review-root>/review-projects/<project_id>/` and library metadata under `<review-root>/review-library/`.
5. Run bundled scripts by path relative to this skill folder, for example `python scripts/<script>.py`; the scripts contain a shared resolver for the paths above.

For lower-capability backend models: before running a script, identify `review_root` explicitly and pass `--review-root <review_root>` when uncertain. Never use `<review-root>` as a real path in FounDryClaw.

Goal: read selected papers and create the literature matrix plus outline options.

Boundary: this skill produces high-level structure (sections, purposes,
assigned papers, expected figures). It does NOT emit per-paragraph or
per-claim constraints; that is `review-section-blueprint`'s job.

## Inputs

```text
review-projects/<project_id>/00_discovery/selected_discovery_results.json
review-projects/<project_id>/00_discovery/topic_input.md
<review-root>/skills/review-section-blueprint/SKILL.md
<review-root>/skills/review-section-blueprint/references/rule_packs.json
<review-root>/examples/reference-reviews/template_summary.md (optional reference-review example)
```

For each paper, open:

```text
review-library/metadata/papers/<paper_id>.metadata.json
linked Markdown
linked PDF when choosing figures or checking chemistry
```

## Matrix Rules

For every selected paper, every matrix row must contain all fields:

```text
paper_id
title
authors
keywords
abstract
main_content
most_relevant_figure
```

Field requirements:

```text
keywords: use the 8 structured tag values from metadata.
abstract: use metadata abstract if reliable; if missing or poor, write "abstract unavailable or unreliable" and continue.
main_content: around 1000 English words; summarize the paper's actual work, not just the abstract.
most_relevant_figure: the figure/scheme/table that best reflects the principle or main work of the paper; include source label, caption, page hint, image path if available, and why it is relevant.
```

Do not fabricate missing field values. Do not omit any field. Do not exclude
a paper only because its abstract is poor.

External `web_papers` (SciAtlas/Crossref) from discovery are reference-only:
they do not get a local `paper_id` or become matrix rows. A search result
alone does not authorize a manuscript claim or citation; acquire, register,
and select the source through the normal workflow before using it as chapter
evidence.

## Automated Fact-Card Extraction (optional)

`scripts/enrich_matrix_facts.py` is available for automated, source-addressable
fact-card extraction, retry, and repair; it is a standalone alternative to
manually filling `main_content`/`most_relevant_figure` by hand, not a required
step. It takes an `--input` JSON payload of papers with `evidence_candidates`
(source-linked passages), and writes fact cards with verified support spans to
`--output`, tracking `--progress` and a resumable `--checkpoint`:

```bash
python skills/review-literature-matrix-outline/scripts/enrich_matrix_facts.py \
  --input review-projects/<project_id>/01_matrix_outline/fact_extraction_input.json \
  --output review-projects/<project_id>/01_matrix_outline/fact_extraction_result.json \
  --progress review-projects/<project_id>/01_matrix_outline/fact_extraction_progress.json \
  --checkpoint review-projects/<project_id>/01_matrix_outline/fact_extraction_checkpoint.json
```

It calls an OpenAI-compatible chat-completions endpoint configured through
`REVIEW_MATRIX_FACTS_API_KEY`/`REVIEW_MATRIX_FACTS_BASE_URL`/`REVIEW_MATRIX_FACTS_MODEL`
(falling back to the shared `REVIEW_WRITING_*`/`OPENAI_*` environment
variables); FounDryClaw has no internal task-token model gateway, unlike the
upstream review-writer Web application. Omit `--evidence-request`/
`--evidence-response`: they address a local on-demand retrieval mailbox that
has no standalone counterpart here, so extraction stays bounded to the
`evidence_candidates` already supplied in the input payload.

## Outline Rules

After the matrix is complete, use:

```text
review topic
literature matrix
review-section-blueprint writing rules / rule pack
template review organization summary
```

Create `2-3` outline options. Each option must include section titles, purpose, assigned papers, and expected figures.

The outline must imitate the template reviews' organization mode. Choose and name one primary structure:

```text
problem-progressive
category-coverage
entry-classified
reaction-type-classified
application-oriented
```

Each major section must have a clear review question, assigned papers, and scheme/figure plan. Do not make a plain title list.

## Outputs

Write under:

```text
review-projects/<project_id>/01_matrix_outline/
```

Required files:

```text
paper_reading_notes.json
literature_matrix.json
literature_matrix.csv
outline_options.md
matrix_outline_report.md
```

Stop after this stage for human outline selection. The preferred human artifact is:

```text
selected_outline.md
```

Keep major sections as level-2 headings (`## Section title` or
`## 1. Section title`) and add `Assigned papers: P001, P002.` for every major
section; this is the format Blueprint and later stages parse. When a
reference review supplies the organization, run it through
`review-reference-outline-template` first: only its hierarchy, section-role
sequence, and pacing may be reused, never its heading wording or scientific
content. Directly extracting headings from a reference review is unsafe and
must not be offered as a selectable outline.

## Outline Coverage Gate

A paper the matrix already covers must never silently disappear when the
outline is chosen. After writing or editing `selected_outline.md`, run:

```bash
python skills/review-literature-matrix-outline/scripts/check_outline_coverage.py \
  --review-root <review-root> \
  --project-id <project-id>
```

This writes `01_matrix_outline/outline_coverage_state.json`, comparing every
`paper_id` in `literature_matrix.json` against every `Assigned papers:` line
in `selected_outline.md`. Any matrix paper that is neither assigned nor
explicitly excluded is reported in `missing_paper_ids`, and the stage is not
treated as confirmed -- `review-writing-orchestrator` and
`review-section-blueprint` both gate on this file and will not proceed while
it is unresolved.

To deliberately drop a paper (rather than adding it to a section), record
why in the state file's `excluded_papers` list before re-running the
checker:

```json
{"paper_id": "P010", "reason": "background context, not central to the review's mechanism"}
```

An exclusion without a non-empty `reason` does not count -- there is no
local dashboard in FounDryClaw, so this file is the entire confirmation
record for this decision.
