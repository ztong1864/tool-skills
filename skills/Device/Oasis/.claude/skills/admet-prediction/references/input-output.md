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

```bash
python scripts/admet_predict.py --input molecules.csv --output results.csv
python scripts/verify_output.py \
  --actual results.csv \
  --expected assets/expected_output.csv \
  --atol 1e-4
```
