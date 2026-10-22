---
name: esm-directed-evolution
description: Score amino-acid substitutions at masked positions of an enzyme or protein with a local ESM-2 protein language model (Meta fair-esm, runs on the server's CPU, no online service or key). Trigger when a user gives a protein sequence with <mask> tokens, or a wild type and residue positions, and wants amino-acid probabilities, mutation candidate rankings, local library design, or a probability vector over the 20 standard amino acids plus special tokens (定向进化、突变位点氨基酸概率、ESM-2 掩码预测). Asking only whether the ESM service is reachable or which models are installed is a read-only check of this skill's own environment rather than an experiment, so run this skill's --health or --list-models directly and report the output, without a LabOntology mission (ESM 服务是否可用、装了哪些模型).
---

# ESM Directed Evolution

Predicts, for each masked position of a protein, how likely each amino acid is under the ESM-2 protein
language model. The model runs on the lab's own server: the ESM service keeps an ESM-2 checkpoint in
memory and this skill's script asks it over HTTP, the way the TRACE Lab tools work. No account, no key and
no online service are involved, and this skill needs no Python packages of its own.

## Quick start

Run the bundled script from the workspace (the chat's `python` runs it; the standard library is enough):

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
- Service status: `--health` and `--list-models` (see "Status queries" below; they need no LabOntology
  mission). Run one of them first when a call fails.

## Status queries (no mission)

`--health` and `--list-models` only read the service's own state: whether it is up, which model is loaded,
on which device, and which model files are installed.

```bash
python .claude/skills/esm-directed-evolution/scripts/esm_mask_probabilities.py --health
python .claude/skills/esm-directed-evolution/scripts/esm_mask_probabilities.py --list-models
```

These are checks of this skill's own environment, not laboratory tasks: **run them directly and do not
create a LabOntology mission for them.** A question such as "is the ESM service up?" or "which models are
installed?" is answered by running the command above and reporting what it says. Neither command scores a
sequence, writes a file or changes anything, so there is nothing for a mission to record — and a mission
started for one cannot be completed, because LabOntology expects a Skill step to leave output files behind.

If a mission was already created for a status question, close it (`act --complete`) instead of leaving it
waiting; then answer from the command's output.

Scoring a sequence is a different matter: that is the skill's real work and goes through LabOntology as
usual, with the result registered as the step's output file (`--output-json`).

## Model

- The ESM service holds the model files; `--list-models` says which are installed (a status query, see
  above). Normally that is
  **esm2-35m** (ESM-2, 35 million parameters, 12 layers), which is also the default `--model`.
- Larger ESM-2 models (`esm2-150m`, `esm2-650m`, ...) and ESM-1v are usually not installed. If the user asks
  for one, say so and use esm2-35m, or tell them an administrator can add it on the service's host
  (`python scripts/fetch_models.py esm2-650m` there). The error message lists what is installed.
- The service runs as its own process. If the script reports that it cannot be reached, report that and that
  it needs an administrator (需要管理员处理). Do not pip install packages, download model files, start the
  service yourself or call an online service to work around a missing model or an unreachable service.

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
  `--standard-only` or `--tokens`), `elapsed_s` (the service's own timing), optional `record` and `notes`.
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
