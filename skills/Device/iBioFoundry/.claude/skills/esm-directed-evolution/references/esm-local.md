# Local ESM-2 models (fair-esm)

## Source

- Code: Meta's [facebookresearch/esm](https://github.com/facebookresearch/esm), package `fair-esm` 2.0.0,
  MIT licence. The repository was archived on 2024-08-01 and still installs and runs with current PyTorch.
- Weights: Meta's `https://dl.fbaipublicfiles.com/fair-esm/models/<name>.pt`, each with a small
  `.../regression/<name>-contact-regression.pt` (only used for contact prediction; fair-esm warns without it).
- The weights live with the ESM service (its own `models/`, or wherever `ESM_MODELS_DIR` points), fetched by
  the service's `scripts/fetch_models.py` and checked against their sha256. Nothing on the FounDryClaw side
  holds a model file or torch: this skill's script posts the sequence to the service and prints the answer.
  It finds the service at `ESM_SERVICE_BASE_URL` (default `http://127.0.0.1:8789`, or `--base-url`), and the
  service keeps the checkpoint in memory between calls, so a question costs about 0.05 s instead of a load.

## ESM-2 models

| `--model` | File | Layers | Parameters | File size |
|---|---|---|---|---|
| `esm2-8m` | `esm2_t6_8M_UR50D` | 6 | 8M | 0.03 GB |
| `esm2-35m` | `esm2_t12_35M_UR50D` | 12 | 35M | 0.13 GB |
| `esm2-150m` | `esm2_t30_150M_UR50D` | 30 | 150M | 0.59 GB |
| `esm2-650m` | `esm2_t33_650M_UR50D` | 33 | 650M | 2.60 GB |
| `esm2-3b` | `esm2_t36_3B_UR50D` | 36 | 3B | 5.68 GB |
| `esm2-15b` | `esm2_t48_15B_UR50D` | 48 | 15B | large; not practical on a CPU |

Which of them are installed is the service's business, not this skill's: `--list-models` says, and normally
only esm2-35m is. ESM-1v (five 650M models, 7.8 GB each as downloaded) is not offered at all; the ESM authors
expect ESM-2 to predict variant effects about as well as ESM-1v.

## Vocabulary and token order

Every ESM-2 model has the same 33-token vocabulary:
`<cls> <pad> <eos> <unk> L A G V S E R T I D P K Q N F Y M H W C X B U Z O . - <null_1> <mask>`.

Default output order: `A C D E F G H I K L M N P Q R S T V W Y`, then `X B Z U O - . <unk> <mask>`.
`--standard-only` keeps the first 20; `--tokens` sets any order (tokens not in the vocabulary are dropped).

## How the numbers are computed

1. The sequence is tokenized with a start token before and an end token after it; each `<mask>` is the model's
   mask token.
2. One forward pass gives logits over the 33 tokens at every position. At each masked position the logits go
   through a softmax over the whole vocabulary, then the requested tokens are picked out
   (`selected_probability_mass` is their sum; `--renormalize-selected` divides by it).
3. Joint masking (default): all masks in one pass, each prediction sees the other positions masked.
   Independent (`--positions ... --independent`): one pass per position with the others at their wild type,
   the usual masked-marginal setup for single-mutant scoring.
4. `log_ratio_vs_wild_type` = ln p(mutant) − ln p(wild type) at that masked position.

## Adding a model (administrator)

On the host that runs the ESM service:

```bash
python scripts/fetch_models.py --list            # the names it knows
python scripts/fetch_models.py esm2-650m         # weights plus the small contact-regression file
```

The files land in the service's `models/` (`--models-dir` or `ESM_MODELS_DIR` to put them elsewhere), an
interrupted download continues where it stopped, and the sha256 is checked for every model whose checksum is
recorded in `esm_service/models.py`. The service loads a model on first use and keeps it in memory: memory
needed is about the file size (650M: about 2.6 GB), and `ESM_SERVICE_MAX_LOADED_MODELS` decides how many stay
loaded at once. Restarting the service is not needed for a newly added file, only for a changed setting.
