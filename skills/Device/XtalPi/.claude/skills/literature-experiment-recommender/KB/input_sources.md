# Input Sources

Use these workspace files as references when this skill is invoked.

## Main Input

- `.claude/skills/constraint-parser/output/parsed_constraints_2026-04-27-13-31-19.json`

Use this JSON as the primary source of user constraints and reaction context. Derive output CSV columns primarily from its `items` array.

## Literature PDFs

- `.claude/skills/literature-experiment-recommender/KB/pdf_new/`
- `.claude/skills/literature-experiment-recommender/KB/pdfs/`

Read relevant PDFs or extracted text when available. Prefer literature patterns directly connected to ATA, asymmetric alkynylation/propargylation, phenylacetylene, aldehydes, Lewis acid/copper/zinc/silver co-catalysis, chiral amino alcohol ligands, molecular sieves, and solvent effects.

## Candidate Space

- `KB/chemical_space.csv`

Only recommend candidates present in this file.

## Output Format Reference

- `.claude/skills/bo-optimizer/output/ata_top10_recommendations_20260427.csv`

Use the same naming style when it matches the main input JSON, but do not copy its columns blindly. If the reference format conflicts with the main input JSON, the main input JSON wins.

## Output Path

- `.claude/skills/literature-experiment-recommender/output/ata_literature_top10_recommendations_20260427.csv`
