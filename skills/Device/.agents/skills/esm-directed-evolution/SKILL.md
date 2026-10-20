---
name: esm-directed-evolution
description: Score amino-acid substitutions at masked positions of an enzyme or protein with a local ESM-2 protein language model (Meta fair-esm, runs on the server's CPU, no online service or key). Trigger when a user gives a protein sequence with <mask> tokens, or a wild type and residue positions, and wants amino-acid probabilities, mutation candidate rankings, local library design, or a probability vector over the 20 standard amino acids plus special tokens (定向进化、突变位点氨基酸概率、ESM-2 掩码预测).
---

# ESM Directed Evolution

Predicts, for each masked position of a protein, how likely each amino acid is under the ESM-2 protein
language model, computed locally with the model installed in this skill's Python environment. It replaces
the earlier BioLM-based version: no BioLM account, key or network access is involved.

## Quick start

Run the bundled script from the workspace (the chat's `python` runs it in this skill's environment):

```bash
python .claude/skills/esm-directed-evolution/scripts/esm_mask_probabilities.py \
  --sequence "MKTFFV<mask>LVLLLSGALAAPVA" \
  --output-json outputs/masked_probs.json
```

Common variants:

- Wild type plus positions (1-based) instead of typing `<mask>`; the output then names the wild-type residue
  and labels candidates like `A45V`:
  `--sequence "<wild-type sequence>" --positions 45,120 --standard-only`
- Each position on its own (the others keep the wild type): add `--independent` (needs `--positions`).
  Without it all masked positions are predicted together in one pass.
- Sequence from a file: `--fasta path/to/file.fasta` (or a GenBank `.gb`/`.gbk` file), `--record <id>` to pick
  a record other than the first.
- Coding DNA: add `--translate` (standard genetic code; the DNA must be whole codons).
- Probabilities over only the output tokens: `--renormalize-selected`. More or fewer candidates per position:
  `--top N` (default 5).
- `--mock` checks the output format with made-up numbers and no model; never report its numbers as results.

## Model

- Installed: **esm2-35m** (ESM-2, 35 million parameters, 12 layers), the default `--model`.
- Larger ESM-2 models (`esm2-150m`, `esm2-650m`, ...) and ESM-1v are not installed. If the user asks for one,
  say so and use esm2-35m, or tell them an administrator can add the model (it is a download entry of the
  `iBioFoundry/esm` environment in `venv/packages.json`). The script's error message lists what is installed.
- Do not pip install packages, download model files or call an online service to work around a missing model
  or environment: report the script's message and that it needs an administrator (需要管理员处理).

## Input rules

- One protein chain of at most 1022 residues: letters `ACDEFGHIKLMNPQRSTVWY` (plus `X B Z U O`) and `<mask>`.
  For a longer protein, pass the domain around the positions of interest and say so.
- A terminal `*` is removed; an internal `*`, spaces, digits or a FASTA header in `--sequence` are refused
  with a message (use `--fasta` for files).
- Use either `<mask>` in the sequence or `--positions`, not both.

## Output contract

JSON (printed, and written to `--output-json` when given):

- `model`, `engine` (fair-esm version, local CPU), `sequence` (with `<mask>`), `masking` (`joint` or
  `independent`), `token_order` (20 standard amino acids, then `X B Z U O - . <unk> <mask>` unless
  `--standard-only` or `--tokens`), optional `record` and `notes`.
- `positions`: one object per mask, in sequence order:
  - `mask_index`, `position` (1-based residue number), `wild_type` (with `--positions`);
  - `probabilities`: token → probability, softmax over the model's whole vocabulary then filtered to
    `token_order` (so they may sum to slightly less than 1), or renormalized with `--renormalize-selected`;
  - `selected_probability_mass`, `renormalized`;
  - `top_standard`: the best standard amino acids, each with `probability` and, when the wild type is known,
    `mutation` (e.g. `A45V`) and `log_ratio_vs_wild_type` (log p(mutant) − log p(wild type));
  - `wild_type_probability` and `wild_type_rank` when the wild type is known.

## Using the results in directed evolution

- These are model likelihoods under the learned sequence context, not measured fitness or activity. Say so.
- Use the top amino acids as exploitation candidates; lower-probability but chemically plausible substitutions
  are exploration candidates only with structural or functional support.
- A positive `log_ratio_vs_wild_type` means the model finds the mutant more likely than the wild type at that
  site; it is a ranking aid, not a stability or activity prediction.
- esm2-35m is the smallest useful ESM-2 model: rankings are coarse. Combine them with active-site knowledge,
  structure, assay data and diversity goals before proposing a library.

Read `references/esm-local.md` for the model table, vocabulary, how the numbers are computed and how a larger
model is added.
