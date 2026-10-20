# Local ESM-2 models (fair-esm)

## Source

- Code: Meta's [facebookresearch/esm](https://github.com/facebookresearch/esm), package `fair-esm` 2.0.0,
  MIT licence. The repository was archived on 2024-08-01 and still installs and runs with current PyTorch.
- Weights: Meta's `https://dl.fbaipublicfiles.com/fair-esm/models/<name>.pt`, each with a small
  `.../regression/<name>-contact-regression.pt` (only used for contact prediction; fair-esm warns without it).
- On FounDryClaw the files live in `venv/iBioFoundry/esm/models/`, fetched by `venv/build_envs.py` from the
  `downloads` of the `iBioFoundry/esm` environment in `venv/packages.json` and checked against their sha256.
  The script finds them as `models/` of the Python environment it runs in (`--models-dir` or `ESM_MODELS_DIR`
  override that).

## ESM-2 models

| `--model` | File | Layers | Parameters | File size | Installed |
|---|---|---|---|---|---|
| `esm2-8m` | `esm2_t6_8M_UR50D` | 6 | 8M | 0.03 GB | no |
| `esm2-35m` | `esm2_t12_35M_UR50D` | 12 | 35M | 0.13 GB | **yes** |
| `esm2-150m` | `esm2_t30_150M_UR50D` | 30 | 150M | 0.59 GB | no |
| `esm2-650m` | `esm2_t33_650M_UR50D` | 33 | 650M | 2.60 GB | no |
| `esm2-3b` | `esm2_t36_3B_UR50D` | 36 | 3B | 5.68 GB | no |

ESM-1v (five 650M models, 7.8 GB each as downloaded) is not installed. The ESM authors expect ESM-2 to predict
variant effects about as well as ESM-1v.

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

Add both files to the `downloads` of `iBioFoundry/esm` in `venv/packages.json`:

```json
{"url": "https://dl.fbaipublicfiles.com/fair-esm/models/esm2_t33_650M_UR50D.pt",
 "path": "models/esm2_t33_650M_UR50D.pt", "sha256": "<sha256 of the file>"},
{"url": "https://dl.fbaipublicfiles.com/fair-esm/regression/esm2_t33_650M_UR50D-contact-regression.pt",
 "path": "models/esm2_t33_650M_UR50D-contact-regression.pt", "sha256": "<sha256 of the file>"}
```

then run `python3 venv/build_envs.py iBioFoundry/esm`. Memory needed is about the file size (650M: about
2.6 GB of RAM on the CPU).
