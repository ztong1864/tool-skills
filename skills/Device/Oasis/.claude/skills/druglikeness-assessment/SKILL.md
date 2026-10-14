---
name: druglikeness-assessment
description: Use when assessing SMILES-based small-molecule drug-likeness with RDKit descriptors, Lipinski Rule of Five, QED, PAINS, or Brenk structural alerts; do not use it as efficacy, ADMET, or experimental validation.
---

# Drug-Likeness Assessment

Use the bundled RDKit wrapper to calculate reproducible descriptors and rule-based alerts from a CSV of molecular SMILES.

## Run the assessment

1. Read [references/input-output.md](references/input-output.md) when preparing an input file or consuming the output schema.
2. The platform runs this skill's scripts in its dedicated RDKit 2022.03.5 environment automatically. Do not use conda, install packages, or call another interpreter; if the run reports that the environment is not set up, tell the user it needs an administrator.
   A plain `python -c` run from the workspace root uses the platform's default environment, not this one. To check this skill's environment or package versions, run the check from the skill folder: `cd .claude/skills/druglikeness-assessment && python -c "import rdkit, sys; print(rdkit.__version__, sys.prefix)"`.
3. From the workspace, run `python .claude/skills/druglikeness-assessment/scripts/rdkit_assess.py --input <molecules.csv> --output outputs/<results>.csv`.
4. Check the process exit code and retain invalid rows. Do not silently discard or repair SMILES.
5. Interpret Rule-of-Five, QED, PAINS, and Brenk results using [references/interpretation-and-limitations.md](references/interpretation-and-limitations.md).

## Preserve the evidence boundary

- Report descriptors and structural alerts as computational assessments, not evidence that a molecule is efficacious, safe, bioavailable, or clinically developable.
- Treat PAINS and Brenk matches as review flags. Never reject a molecule solely because one filter matches.
- Flag disconnected salts, inorganic structures, extreme-size molecules, and unusual natural products as requiring manual review even when their SMILES is syntactically valid.
- Do not describe this rule-based method as having a learned applicability domain.

For manuscript attribution and licensing, read [references/citations-and-licenses.md](references/citations-and-licenses.md). For transfer to another machine, read [HANDOFF.md](HANDOFF.md).
