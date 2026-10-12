# ADMET Prediction Skill handoff

## Purpose

This package provides a Codex skill and wrapper around ADMET-AI v1.4.0. It preserves invalid inputs, fixes a 101-column schema, and separates descriptors, model predictions, and DrugBank percentiles.

## Install and run on the Linux server

```bash
conda env create -f environment-base.yml
conda activate admet-prediction
WHEELHOUSE=/path/to/admet_ai_wheels bash scripts/install_offline.sh
python scripts/admet_predict.py \
  --input assets/test_molecules.csv \
  --output /tmp/admet_output.csv
python scripts/verify_output.py \
  --actual /tmp/admet_output.csv \
  --expected assets/expected_output.csv \
  --atol 1e-4
```

## Acceptance status

- Local structure, assembly logic, schema, manifest portability, and syntax checks: covered by `tests/test_contract.py`.
- Server runtime acceptance: passed on 2026-09-30 in the existing `admet-ai-v1` conda environment with ADMET-AI 1.4.0, Chemprop 1.6.1, PyTorch 2.5.0+cpu, and RDKit 2024.3.2.
- Acceptance fixture: 20 input rows, 19 valid molecules, 1 invalid SMILES, 101 output columns.
- Numerical verification: `valid=true`, `max_abs_error=0.0` at `atol=1e-4`, no NaN or Inf values.
- Scope: the packaged wrapper is runtime-validated in the existing server environment. Clean offline reconstruction from the 68-wheel wheelhouse remains unverified.

The wheelhouse is Linux x86-64 material and is intentionally excluded from the portable skill archive. Do not attempt to install it on macOS.
