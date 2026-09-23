# Input Sources

Use these workspace files as references when this skill is invoked.

## Main Input

- `.agents/skills/constraint-parser/output/parsed_constraints_2026-05-14-16-08-55.json`

Use this JSON as the primary source of user constraints and reaction context. Derive candidate-condition variables from its `items` array, and use them to form complete recommendation rows rather than isolated candidate lists.

## Literature PDFs

- `.agents/skills/literature-experiment-recommender/KB/pdf_new/`
- `.agents/skills/literature-experiment-recommender/KB/pdfs/`

Read relevant PDFs or extracted text when available. Prefer literature patterns directly connected to the reaction context and constraints in the main input JSON. Do not assume a fixed reaction type when the user input does not specify one.

## Candidate Space

- User-provided `chemical_space.csv` or another explicit `.csv` candidate-space path. Current test input: `.agents/skills/constraint-parser/output/chemical_space.csv`.
- Fallback only when no CSV candidate-space file is provided: `KB/chemical_space.csv`.

Only recommend candidates present in the active candidate-space CSV file. If the user provides a CSV file, it is authoritative and `KB/chemical_space.csv` must not be used for candidate selection except as an explicit fallback requested by the user.

The expected columns follow the existing `chemical_space.csv` schema: `section`, `no`, `recommendation_name`, `cn_name`, `en_name`, `abbr`, `formula`, `smiles`, `cas`, and `notes`.

Each output value must exactly match either the Chinese name or the English name from the active candidate-space CSV. Do not combine Chinese and English names in one cell.

Fixed materials may be filled from the user constraints, literature, or output format example even when they are not listed in the candidate-space CSV. For example, if molecular sieve is part of the design, `molecular_sieve` may use `4A MS`; use `none` only when the design explicitly omits that material or there is no basis to include it.

If the user constraints state that a variable or fixed material may be included or omitted, decide per recommendation row whether to include it based on the literature context, reagent/substrate properties, solvent, and overall condition combination. Do not mechanically set the whole column to only one state, and do not force both states by a fixed ratio when the condition logic supports only one.

## Recommendation Behavior

Generate complete candidate-condition combinations. Each row should represent one executable condition set assembled from compatible candidates, not a single candidate or a copied row from the chemical-space CSV. Prefer diverse combinations across variable columns while staying consistent with the user constraints and literature context.

## Output Format Reference

- `KB/output_format_example.csv`

Use the same column style when it matches the main input JSON, but do not copy its columns blindly. If the reference format conflicts with the main input JSON, the main input JSON wins.

## Output Path

- `.agents/skills/literature-experiment-recommender/output/literature_recommendations_<YYYYMMDD>.csv`
