---
name: enzyme-mutation-recommender
description: Recommend traceable enzyme mutation sites or mutation candidates for PylRS-derived noncanonical amino acid incorporation systems. Use when an assistant needs to analyze a user-provided enzyme sequence, infer existing mutations against reference sequences, query a maintained enzyme Wiki, propose exploitation and exploration sites for saturation mutagenesis or specific substitutions, or ingest new PylRS/N-terminal/linker/tRNA-binding-domain engineering literature into the Wiki.
---

# Enzyme Mutation Recommender

Use this skill to recommend mutation candidates from a user-provided enzyme sequence by reading the bundled enzyme Wiki. The Wiki is the source of biological knowledge; this SKILL.md only defines the reasoning workflow.

## Required Wiki Reads

Before giving any recommendation, read:

1. `references/enzyme-wiki/index.md` for navigation.
2. `references/enzyme-wiki/wiki-maintenance.md` for evidence and citation rules.
3. The relevant scaffold, site, mutation, mechanism, assay, substrate, and source-summary pages identified from the index.

Do not recommend from memory. Do not hardcode residues, mechanisms, or substrate rules from this file.

## Recommendation Workflow

1. Chassis analysis
   - Align the user sequence to the Wiki reference sequences.
   - Identify existing substitutions, insertions, deletions, truncations, linkers, or domain swaps.
   - Map every observed change to the numbering scheme used by the closest Wiki scaffold.
   - Query scaffold and site pages to infer the current physical state of the user's chassis from Wiki evidence.

2. Mechanism extraction
   - Search the Wiki for successful and failed mutation cases in related scaffolds, substrates, and assays.
   - Summarize the underlying physical and structural rules from the evidence pages.
   - Mark each rule as direct evidence, cross-paper synthesis, or hypothesis.
   - Note contradictions where the same mutation set has different effects in different scaffolds.

3. Site or mutation recommendation
   - Default to site-first recommendations for saturation mutagenesis when the user's experimental workflow screens all amino acid replacements at selected positions.
   - Use literature substitutions as evidence anchors for why a site is worth scanning, not as the final experimental instruction, unless the user explicitly asks for exact substitutions.
   - Produce exploitation recommendations: sites or mutation sets directly supported by Wiki cases and compatible with the user's chassis.
   - Produce exploration recommendations: new sites not directly validated in the Wiki, selected because the user's sequence contains residues matching the structural criteria derived in step 2.
   - For every candidate site or substitution, include scaffold context, source papers, mapping confidence, expected mechanism, risks, and suggested assay.

4. Active-learning anchor
   - End with the minimal experimental comparisons that would best update the Wiki for the next round.
   - Keep this section brief until the task-specific feedback board is created.

## Literature Ingestion Workflow

When adding new literature:

1. Create a source package directory under `references/enzyme-wiki/sources/` using a stable short source id, such as `S09-short-title-year/`.
2. Copy the immutable source PDF into that package as `paper.pdf`.
3. Create the maintained source summary as `summary.md` in the same package.
4. Update all affected scaffold, site, mutation, mechanism, assay, and substrate pages.
5. Preserve scaffold-specific numbering and map to reference numbering only when justified.
6. Record contradictions, failed transfers, assay incompatibilities, and open questions.
7. Append the ingest to `references/enzyme-wiki/log.md`.

Follow `references/enzyme-wiki/wiki-maintenance.md` for page formats and evidence rules.
