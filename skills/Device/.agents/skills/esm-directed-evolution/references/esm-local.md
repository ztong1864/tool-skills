# The scoring engine behind this skill

Scoring happens on the **ProEngAgent service**, not here. The script sends the wild-type sequence, the service
scores every single substitution of the whole protein with ESM-2 650M in one pass over the wild type
(zero-shot, wild-type marginals), and the script reads the positions that were asked for out of the scan it
gets back. This skill holds no weights, no torch and no fair-esm, and the local ESM service that used to do
this work has been retired (see "What changed" below).

## The API this skill uses

Address: `PROENGAGENT_BASE_URL` (an administrator's setting on the server, passed into the chat environment).
Nothing here hardcodes a host.

| Call | Purpose |
|---|---|
| `GET {base}/api/general/tools` | The catalog. `--health` reads it and reports the scoring tool's entry, which names the model. |
| `POST {base}/api/general/tool/multievolve_api` | The scan. Body `{"inputs": {"sequence": "<wild type>"}}`. |
| `GET {base}/api/upload/file?path=<file>` | Brings the scan CSV here. The answer's `downloads` entry carries this URL. |
| `POST {base}/api/general/tool/read_file` | Fallback for the CSV when the download URL fails. |

The request model is `{"inputs": {...}}` — that is the service's own `ToolExecuteRequest`, confirmed against
its `/openapi.json`, not a guess. The answer is `{"success", "output", "error", "downloads"}`; `output` carries
`top_mutations` (the best 20 only), `n_mutations_scored`, `output_file`, `elapsed_sec` and `output_dir`. The
top-20 list is not enough for a chosen position, which is why the script always fetches the full scan.

Measured on 2026-11-12: a 21-residue sequence scored 399 substitutions in 6.7 s, a 454-residue enzyme 8,626 in
6.5 s, round trip about 11 s in both cases — the cost is one forward pass, not one per position. Two identical
calls returned identical scores to every decimal.

## The scan file

`me_zeroshot_scan.csv`, sorted best first:

```
mutations,model_1_logratio,average_model_logratio,model_1_pass,total_model_pass
M40C,3.244958,3.244958,1,1
```

`mutations` is `<wild type><1-based position><substitution>`; the log-ratio columns are the score, in natural
log units, of that substitution against the wild type at that site. The wild type itself is not a row: under
wild-type marginals its own score is 0 by definition. A positive score means the model prefers the
substitution. The script prefers `average_model_logratio` and falls back to `model_1_logratio`.

## How this skill's numbers come out of that file

For each position asked about, the script takes the 19 substitution scores, adds the wild type at 0, and then:

- `log_ratio_vs_wild_type` is the score as reported;
- `probabilities` is the softmax of those 20 values, so it is a distribution over the 20 standard amino acids
  at that position — a ranking aid, not the model's absolute token probability;
- `wild_type_rank` is 1 plus the number of substitutions scoring above 0;
- `top_standard` is the best `--top` of the 20, the wild type included.

It also checks that the scan's wild-type letter at each position matches the sequence that was sent, and stops
if the numbering disagrees — that mismatch is the usual sign that a construct, a domain or a different isoform
was scored.

## Wild-type marginals are not masked marginals

The retired local service masked each position and read the model's distribution at the mask. This service
runs one pass over the unmasked wild type and reads logit differences. Both answer "which substitutions does
ESM-2 prefer here", and both put the wild type first at a conserved site, but the numbers and even the order
differ. Measured on the same 21-residue test sequence at position 7 (wild type `A`):

| engine | order |
|---|---|
| ProEngAgent, ESM-2 650M, wild-type marginals | A7L −3.384, A7S −3.643, A7V −3.784, A7T −3.857 |
| retired local service, esm2-150m, masked marginals | A7A 0.3465, A7V 0.1332, A7T 0.1086, A7L 0.1078 |

So a number from an earlier round scored by the local service cannot be compared with a number from this
engine, and a test baseline taken under one of them has to be re-measured under the other.

## What changed when the local service was retired

- `--model`, `--tokens` and `--models-dir` are refused with a message: the service picks the model.
- `--independent`, `--standard-only` and `--renormalize-selected` are accepted and ignored, with a note in the
  answer: this engine always scores every substitution in one wild-type pass over the 20 standard amino acids.
- `<mask>` in a sequence is refused: scoring needs the wild-type residue, so the wild type plus `--positions`
  is the way to ask.
- The 1022-residue input limit is gone; a long protein simply produces a large scan.
- `elapsed_s` is still the service's own timing, and `round_trip_s` is added.
- The local service's model table, model files and `fetch_models.py` no longer apply to this skill. Its code
  remains in the `ESM_service` repository if it is ever needed again.

## Failure modes worth knowing

- **Unreachable service.** The address is on the lab network and has been seen down (a 6 s timeout) and up
  (0.1 s) on the same day. The script reports it and says an administrator is needed; it never falls back to
  another engine, so a round is never half-scored by two different models.
- **`reliability: experimental`.** The catalog marks the scoring tool that way. Say so when a decision rests
  on it.
- **Two names, one tool.** The catalog lists `multievolve_api` and `multi_evolve_api` with the same
  description and behaviour. This skill uses `multievolve_api`.
- **Other tools on that service.** Its catalog also offers stability predictors (`Pythia_Mut`,
  `ddgun_predict`, `imutant2_predict`, `foldx_stability`, `rosetta_ddg`), folding and embedding
  (`esm_fold`, `esm3_embed`) and document helpers. They are outside this skill: scoring substitutions is what
  it does, and anything else needs its own skill.
