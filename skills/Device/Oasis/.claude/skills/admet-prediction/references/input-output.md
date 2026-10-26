# Input and output contract

## Input

Use a UTF-8 CSV containing `compound_id` and `smiles`. Override these names with `--id-col` and `--smiles-col`. Other fields are ignored. Input order and duplicate identifiers are preserved.

Blank, whitespace-only, unparsable, and zero-atom SMILES are retained as `INVALID_SMILES` rows and are not sent to ADMET-AI.

## Output

The output contains 101 unique columns:

- 3 wrapper fields: `smiles`, `compound_id`, `status`.
- 8 calculated descriptors: `molecular_weight`, `logP`, `hydrogen_bond_acceptors`, `hydrogen_bond_donors`, `Lipinski`, `QED`, `stereo_centers`, and `tpsa`.
- 41 ADMET-AI model predictions: 31 classification tasks and 10 regression tasks.
- 49 fields ending in `_drugbank_approved_percentile`, one for each descriptor or prediction value.

`status` is `OK` or `INVALID_SMILES`. An invalid row has empty CSV fields for all 98 result columns. When read with pandas using default options, those empty fields normally become missing/NaN values.

The exact ordered schema is the header of `assets/expected_output.csv`. The wrapper refuses a model result whose columns do not match that schema.

## Commands

Predict for your own molecules, from the workspace. In a LabOntology mission, write the input CSV
outside the mission's `artifacts/` folder: that folder is for the step's declared outputs, and an
input sitting beside the result leaves `resume --register-all` unable to tell which file is which.

```bash
python .claude/skills/admet-prediction/scripts/admet_predict.py --input molecules.csv --output outputs/results.csv
```

`verify_output.py` is not part of that run. It checks this installation against the bundled acceptance
fixture, so `--actual` must be a result produced from `assets/test_molecules.csv` and nothing else.
Pointed at a result for any other molecules it always reports `valid: false` with a row-count mismatch
and large value differences, which says nothing about that result. Run it only to confirm the
environment reproduces the fixture, and write its output into the workspace, never into the skill folder:

```bash
python .claude/skills/admet-prediction/scripts/admet_predict.py \
  --input .claude/skills/admet-prediction/assets/test_molecules.csv \
  --output outputs/admet_acceptance.csv
python .claude/skills/admet-prediction/scripts/verify_output.py \
  --actual outputs/admet_acceptance.csv \
  --expected .claude/skills/admet-prediction/assets/expected_output.csv \
  --atol 1e-4
```

Reading that result: the 8 calculated descriptors and the 41 model predictions must match within
`1e-4`. The 49 `_drugbank_approved_percentile` fields may differ by a few hundredths of a percentile
point, because they are positions within the bundled DrugBank reference rather than model outputs. On
2026-10-26 this installation reported `valid: false` with 97 such differences and `max_abs_error`
0.0388, every one of them a percentile field, and passed at `--atol 0.1`. Treat that as a healthy
environment. Failures in a descriptor or prediction column, or a larger percentile gap, are not.
