# Drug-Likeness Skill handoff

## Purpose

This package provides a Codex skill and deterministic RDKit wrapper for descriptor calculation, Rule-of-Five assessment, QED, PAINS, and Brenk alerts.

## Install and run

```bash
conda env create -f environment.yml
conda activate druglikeness
python scripts/rdkit_assess.py \
  --input assets/test_molecules.csv \
  --output /tmp/druglikeness_output.csv
python scripts/verify_output.py \
  --actual /tmp/druglikeness_output.csv \
  --expected assets/expected_output.csv
```

## Acceptance status

- Local structure, pure input behavior, CSV contract, syntax, and fixture checks: covered by `tests/test_contract.py`.
- Server runtime acceptance: passed on 2026-09-30 in the existing `rdkit` conda environment with Python 3.10.12 and RDKit 2022.03.5.
- Acceptance fixture: 20 input rows, 19 valid molecules, 1 invalid SMILES, 13 output columns.
- Numerical verification: `valid=true`, `max_abs_error=0.0`, no NaN or Inf values.
- Scope: the packaged wrapper is runtime-validated in the existing server environment. A separate from-scratch environment reconstruction was not tested because the compute node could not access conda-forge.
