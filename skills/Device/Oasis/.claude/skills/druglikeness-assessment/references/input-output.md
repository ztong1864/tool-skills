# Input and output contract

## Input

Use a UTF-8 CSV with one row per structure. Required columns default to:

```csv
compound_id,smiles
aspirin,CC(=O)OC1=CC=CC=C1C(=O)O
```

Override the column names with `--id-col` and `--smiles-col`. Other input columns are ignored. Row order and duplicate IDs are preserved. Blank, whitespace-only, unparsable, and zero-atom SMILES are returned as `INVALID_SMILES` rather than dropped.

## Output

The output has exactly 13 columns:

| Column | Meaning |
|---|---|
| `compound_id` | Input identifier |
| `smiles` | Original input text |
| `status` | `OK` or `INVALID_SMILES` |
| `MW` | RDKit molecular weight, Da |
| `cLogP` | Wildman-Crippen cLogP implementation in RDKit |
| `HBD`, `HBA` | Hydrogen-bond donor and acceptor counts |
| `TPSA` | Topological polar surface area, Å² |
| `RotBonds` | Rotatable-bond count |
| `QED` | RDKit quantitative estimate of drug-likeness, 0–1 |
| `Lipinski` | `1` only when all four configured thresholds pass |
| `PAINS`, `Brenk` | `1` when the corresponding RDKit catalog matches |

Result fields after `status` are empty for invalid SMILES.

## Commands

Assess your own molecules, from the workspace. In a LabOntology mission, write the input CSV outside
the mission's `artifacts/` folder: that folder is for the step's declared outputs, and an input
sitting beside the result leaves `resume --register-all` unable to tell which file is which.

```bash
python .claude/skills/druglikeness-assessment/scripts/rdkit_assess.py --input molecules.csv --output outputs/results.csv
```

`verify_output.py` is not part of that run. It checks this installation against the bundled acceptance
fixture, so `--actual` must be a result produced from `assets/test_molecules.csv` and nothing else.
Pointed at a result for any other molecules it always reports `valid: false` with a row-count mismatch
and large value differences, which says nothing about that result. Run it only to confirm the
environment reproduces the fixture, and write its output into the workspace, never into the skill folder:

```bash
python .claude/skills/druglikeness-assessment/scripts/rdkit_assess.py \
  --input .claude/skills/druglikeness-assessment/assets/test_molecules.csv \
  --output outputs/druglikeness_acceptance.csv
python .claude/skills/druglikeness-assessment/scripts/verify_output.py \
  --actual outputs/druglikeness_acceptance.csv \
  --expected .claude/skills/druglikeness-assessment/assets/expected_output.csv
```
