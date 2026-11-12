---
name: esm-directed-evolution
description: Score amino-acid substitutions at chosen positions of an enzyme or protein with ESM-2 through the ProEngAgent service (its multievolve_api tool, ESM-2 650M, wild-type marginals, reached over HTTP at PROENGAGENT_BASE_URL; no local model and no key in this skill). Trigger when a user gives a wild-type protein sequence and residue positions and wants substitution scores, mutation candidate rankings, a library for one round of directed evolution, or a ranking of the 20 standard amino acids at a site (定向进化、突变位点打分、ESM 零样本评分). Asking only whether the scoring service is reachable or which model it offers is a read-only check of this skill's own environment rather than an experiment, so run this skill's --health directly and report the output, without a LabOntology mission (ESM 服务是否可用、用的是哪个模型).
---

# ESM Directed Evolution

Scores, for each position asked about, how the 20 standard amino acids rank against the wild-type residue
under ESM-2. The scoring runs on the **ProEngAgent service** (`multievolve_api`: ESM-2 650M, zero-shot,
wild-type marginals), which this skill's script reaches over HTTP at `PROENGAGENT_BASE_URL`. There is no model
file, no torch and no local scoring service on this side, and the script needs no Python packages of its own.

One call scores every single substitution of the whole protein in one pass, so asking about three positions
costs the same as asking about all of them. The script keeps the positions that were asked for and saves the
service's full scan CSV beside the JSON, so the registered artifact carries the whole scan.

## Quick start

Run the bundled script from the workspace (the chat's `python` runs it; the standard library is enough):

```bash
python .claude/skills/esm-directed-evolution/scripts/esm_mask_probabilities.py \
  --fasta uploads/enzyme_wt.fasta --positions 2,61,62 --top 5 \
  --output-json outputs/enzyme_esm.json
```

Common variants:

- Sequence on the command line instead of a file: `--sequence "<wild-type sequence>" --positions 45,120`.
- A record other than the first in a multi-record FASTA: `--record <id>`.
- Coding DNA in a GenBank `.gb`/`.gbk` file: add `--translate` (its `/translation` is used when present,
  otherwise the ORIGIN is translated with the standard code).
- More or fewer candidates per position: `--top N` (default 5; the wild type is one of them).
- Every position of the scan instead of a few: leave `--positions` out.
- Where the scan CSV lands: `--scan-csv <path>` (default: beside `--output-json`).
- Service status: `--health` (see "Status queries"). Run it first when a call fails.

## Status queries (no mission)

`--health` (and `--list-models`, which does the same) reads the service's catalog only: whether it answers,
how many tools it offers, and which scoring tool and model it reports.

```bash
python .claude/skills/esm-directed-evolution/scripts/esm_mask_probabilities.py --health
```

These are checks of this skill's own environment, not laboratory tasks: **run them directly and do not create
a LabOntology mission for them.** A question such as "is the ESM service up?" or "which model is it using?" is
answered by running the command above and reporting what it says. It scores nothing, writes no file and
changes nothing, so there is nothing for a mission to record — and a mission started for one cannot be
completed, because LabOntology expects a Skill step to leave output files behind.

If a mission was already created for a status question, close it (`act --complete`) instead of leaving it
waiting; then answer from the command's output.

Scoring a sequence is a different matter: that is the skill's real work and goes through LabOntology as usual,
with the result registered as the step's output file (`--output-json`), together with the scan CSV.

## Model and service

- The service decides the model; this skill carries no weights. `--health` prints the catalog entry, which
  names it (currently ESM-2 650M, wild-type marginals). Report the model from that entry or from the `model`
  field of the answer — never from this document.
- `--model`, `--tokens` and `--models-dir` are gone, and the script says so if they are passed: the model is
  the service's, and the scan covers the 20 standard amino acids. If another model is wanted, an administrator
  changes the service.
- The catalog marks the scoring tool `reliability: experimental`. Mention that when a result is reported for a
  decision that depends on it.
- The service is reached over the lab network. If the script reports that it cannot be reached, or the service
  refuses the call, **report that and that it needs an administrator** (需要管理员处理), and stop. Do not pip
  install packages, download model weights, start a local scoring service, or call a different online service
  to work around it.
- The scan runs on the service's host and its result file lives there; the script copies that file here. Do
  not read other paths on that host and do not pass workspace paths of its other tools around.

## Input rules

- One protein chain of the 20 standard amino acids, as the wild type. `X B Z U O`, spaces, digits, a FASTA
  header in `--sequence`, or `<mask>` are refused with a message: this engine scores against the residue that
  is there, so the wild-type sequence plus `--positions` is the way to ask.
- `--positions` are 1-based residue numbers of that sequence. The script checks each one against the wild-type
  letter in the scan and stops if the numbering disagrees.
- There is no fixed length limit on this side. A long protein simply makes a large scan (454 residues → 8,626
  substitutions, a few seconds); if the service refuses a sequence, report its message rather than trimming
  the protein silently.

## Output contract

JSON (printed, and written to `--output-json` when given), plus the scan CSV beside it:

- `service`, `engine` (`ProEngAgent multievolve_api, wild-type marginals, remote`), `model`, `sequence`,
  `sequence_from`, `masking`, `probability_meaning`, `token_order` (the 20 standard amino acids),
  `n_mutations_scored`, `scan_csv` (local), `remote_scan_file`, `elapsed_s` (the service's own timing),
  `round_trip_s`.
- `positions`: one object per position asked about, in order:
  - `position` (1-based), `wild_type`, `substitutions_scored` (19 when the scan is complete);
  - `probabilities`: amino acid → probability, the softmax of the log ratios over the 20 standard amino acids
    at that position (`selected_probability_mass` 1.0, `renormalized` true);
  - `top_standard`: the best amino acids, each with `probability`, `mutation` (e.g. `R61S`) and
    `log_ratio_vs_wild_type` as the service reported it; the wild type appears with a log ratio of 0;
  - `wild_type_probability`, and `wild_type_rank` = 1 plus the number of substitutions the model scores above
    the wild type.

## Using the results in directed evolution

- These are zero-shot language-model scores under the learned sequence context, not measured fitness, activity
  or stability. Say so when reporting them.
- `log_ratio_vs_wild_type` is what the service computes; the probability is a ranking aid within one position.
  Do not compare these numbers with masked-marginal probabilities from another service or an earlier round
  scored by a different engine — the scoring scheme differs, and so does the order.
- A positive `log_ratio_vs_wild_type` means the model finds that substitution more likely than the wild type
  at that site. Those are the exploitation candidates; lower-scoring but chemically plausible substitutions
  are exploration candidates only with structural or functional support.
- Combine the ranking with active-site knowledge, structure, assay data and diversity goals before proposing a
  library, and keep the round's scan CSV with the library so the choice stays checkable.

Read `references/esm-local.md` for what the service computes, how the probability and the wild-type rank are
derived from its scan, and what changed when the local ESM service was retired.
