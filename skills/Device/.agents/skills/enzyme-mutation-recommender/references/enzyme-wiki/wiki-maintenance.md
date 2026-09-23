# Wiki Maintenance Rules

## Architecture

- `sources/` contains one directory per source paper. Each source package keeps immutable original evidence beside maintained derived notes:
  - `sources/Sxx-short-title-year/paper.pdf`: immutable source PDF.
  - `sources/Sxx-short-title-year/summary.md`: maintained source summary and extraction notes.
  - Optional supplements, extracted tables, or structure files may be added inside the same package with explicit names.
- `scaffolds/` records protein backgrounds, domain boundaries, sequence origins, and known variant families.
- `sites/` records residue positions only with an explicit numbering scheme.
- `mutations/` records evidence units: scaffold + mutation + substrate + assay + effect + source.
- `mechanisms/` synthesizes physical and structural rules from evidence units.
- `assays-and-substrates/` records how readouts and substrates compare.
- `tasks/` is reserved for user-specific recommendation boards and feedback history.

## Evidence Model

Every mutation entry must include:

- Source id and source-summary link, normally `sources/Sxx-short-title-year/summary.md`.
- Original PDF link when a claim requires direct audit of the source evidence.
- Original scaffold and source sequence context.
- Numbering system used in the source.
- Mapping status to MmPylRS wild-type numbering when possible.
- Mutation or mutation set.
- Substrate and assay/readout.
- Observed effect and effect size when reported.
- Mechanistic interpretation labeled as direct evidence, cross-paper synthesis, or hypothesis.
- Caveats, including scaffold-specific failures and assay incompatibility.

Do not add free-floating claims such as "this mutation improves activity" without scaffold, substrate, assay, and source context.

## Mechanism Labels

- Direct evidence: the paper experimentally measures or structurally observes the mechanism.
- Cross-paper synthesis: multiple sources support a coherent rule, but no single source directly proves the complete rule.
- Hypothesis: plausible interpretation needed for recommendation, but not directly demonstrated.
- Contradiction/context boundary: evidence shows a mechanism or mutation does not transfer cleanly across scaffolds, substrates, or assays.

## Adding a New Paper

1. Create `sources/S09-short-title-year/`.
2. Copy the immutable source PDF to `sources/S09-short-title-year/paper.pdf`.
3. Create `sources/S09-short-title-year/summary.md` with bibliographic metadata, scaffold, mutations, substrates, assays, results, mechanisms, and caveats.
4. Add any supplements or extracted tables into the same source package with descriptive filenames.
5. Update `sources/index.md` and the main Wiki `index.md`.
6. Update `scaffolds/` if the paper uses a new enzyme origin, chimera, domain boundary, or parent variant.
7. Update `sites/` only after declaring the paper's numbering system and mapping confidence.
8. Update `mutations/evidence-matrix.md` with one row per evidence unit.
9. Update mechanism pages with direct evidence, synthesis, contradiction, or open question entries.
10. Update `assays-and-substrates/` if new assays or substrates appear.
11. Append a dated entry to `log.md`.

## Recommendation Use

Before recommending candidates, the agent must read the index, the relevant scaffold page, the mutation evidence matrix, and all source summaries linked by candidate evidence. Recommendations must cite source ids and explain whether each mechanism is direct evidence, cross-paper synthesis, or hypothesis.
