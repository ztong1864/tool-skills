---
name: admet-prediction
description: Use when predicting SMILES-based physicochemical and ADMET properties with ADMET-AI v1.4.0, including DrugBank percentiles; do not use it as experimental or clinical confirmation or silently substitute ADMET-AI v2.
---

# ADMET Prediction

Use the bundled wrapper with the dedicated CPU-only ADMET-AI v1.4.0 environment. Preserve the model version because v1 and v2 are different workflows and their outputs must not be mixed.

## Run prediction

1. Read [references/input-output.md](references/input-output.md) before preparing inputs or parsing the 101-column result.
2. The platform runs this skill's scripts in its dedicated ADMET-AI v1.4.0 CPU environment automatically (平台自动用本技能固定的 ADMET-AI 环境运行). Do not use conda, install packages, or call another interpreter; if the run reports that the environment is not set up, tell the user it needs an administrator.
   A plain `python -c` run from the workspace root uses the platform's default environment, not this one (工作区根目录下直接运行的 `python -c` 用的是平台默认环境). To check this skill's environment or package versions, run the check from the skill folder: `cd .claude/skills/admet-prediction && python -c "import admet_ai, torch, sys; from importlib.metadata import version; print(version('admet_ai'), torch.__version__, sys.prefix)"`.
3. From the workspace, run `python .claude/skills/admet-prediction/scripts/admet_predict.py --input <molecules.csv> --output outputs/<results>.csv`.
4. Retain `INVALID_SMILES` rows and all empty result fields; do not impute failed predictions.
5. Interpret classification probabilities, regression values, and DrugBank percentiles using [references/interpretation-and-limitations.md](references/interpretation-and-limitations.md).

## Preserve the evidence boundary

- Separate 8 calculated descriptors, 41 model-predicted endpoints, and 49 derived DrugBank percentile fields.
- Do not invent units or thresholds. Use method-native values when the bundled references do not establish a unit or transformation.
- State that ADMET-AI v1 has no bundled applicability-domain score. Highlight extrapolation risk for unusual natural products, salts, mixtures, and extreme structures.
- Treat predictions as prioritization evidence, not experimental safety, pharmacokinetic, clinical, or regulatory evidence.

For citations, upstream licenses, and data-license boundaries, read [references/citations-and-licenses.md](references/citations-and-licenses.md). For transfer, read [HANDOFF.md](HANDOFF.md).
