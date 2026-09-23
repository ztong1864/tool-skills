---
name: esm-directed-evolution
description: Use BioLM ESM/ESM-2 masked-language-model APIs for protein directed evolution tasks. Trigger when a user provides an enzyme or protein sequence containing one or more mask tokens and wants amino acid substitution probabilities, mutation candidate rankings, local library design, or a probability vector over the 20 standard amino acids plus selected special tokens.
---

# ESM Directed Evolution

## Workflow

1. Confirm the input is a single protein sequence or a small batch of sequences containing at least one literal `<mask>` token.
2. Remove a terminal `*` stop symbol before calling BioLM; BioLM accepts amino-acid residue tokens only and rejects `*`.
3. Use BioLM's masked prediction endpoint for an ESM model, usually `esm2-35m` for quick iteration or `esm2-650m`/larger for higher-quality ranking.
4. Convert the returned masked-position logits into probabilities with softmax.
5. Report full probability vectors in the exact token order used by the script.
6. For directed evolution, prefer ranking standard amino acids first; keep special tokens only when the user explicitly wants the full filtered vocabulary.

## Quick Start

Use the bundled script for deterministic API calls and probability formatting:

```powershell
python .claude\skills\esm-directed-evolution\scripts\biolm_esm_mask_probabilities.py `
  --sequence "MKTFFV<mask>LVLLLSGALAAPVA" `
  --model esm2-35m `
  --output-json outputs\masked_probs.json
```

Do not ask the user to paste the BioLM key into a prompt. Resolve credentials in this order:

1. `--api-key` for a one-off override.
2. `BIOLM_API_KEY` environment variable.
3. `--api-key-file` or `BIOLM_API_KEY_FILE`.
4. `.claude\secrets\biolm.env`, which is git-ignored and should contain `BIOLM_API_KEY=...`.

Prefer the project-local secret file for repeat Agent use on this workspace:

```powershell
New-Item -ItemType Directory -Force .claude\secrets
Set-Content .claude\secrets\biolm.env "BIOLM_API_KEY=your-token-here"
```

For offline validation of parsing and formatting:

```powershell
python .claude\skills\esm-directed-evolution\scripts\biolm_esm_mask_probabilities.py --mock
```

## Output Contract

Return or save JSON with:

- `model`: BioLM model name.
- `sequence`: input masked sequence.
- `token_order`: selected output tokens, defaulting to the 20 standard amino acids followed by common ESM special/ambiguous symbols when present.
- `positions`: one object per `<mask>` in API order, containing `probabilities` and `selected_probability_mass`.

Use `--renormalize-selected` when the vector must sum to 1 over the selected candidate tokens. Without it, probabilities are softmaxed over the full BioLM vocabulary and then filtered; the selected token probabilities may sum to less than 1.

For `esm1v-all`, BioLM returns five ESM-1v submodel candidate lists. The bundled script must average scores across the submodels and output only the averaged 20-amino-acid vector, not the raw per-submodel response or a truncated top-k list.

## BioLM Notes

Read `references/biolm-esm-api.md` when implementing custom calls, changing models, or troubleshooting response shapes.

Important defaults:

- Endpoint: `https://biolm.ai/api/v3/{model}/predict/`
- Authorization header: `Authorization: Token <BIOLM_API_KEY>`
- Payload: `{"items": [{"sequence": "...<mask>..."}]}`
- Response fields: `results[].logits`, `results[].vocab_tokens`, `results[].sequence_tokens`
- Strip a trailing `*` from user-provided protein sequences before API submission.
- ESM-1v response fields differ from ESM-2; aggregate `esm1v-n*` candidate scores by token and report only the mean.

## Directed Evolution Use

For a masked enzyme sequence, interpret each mask independently unless the user asks for combinatorial design. For each mask:

- Use the top standard amino acids as exploitation candidates.
- Use lower-probability but chemically plausible substitutions as exploration candidates only if supported by structural or functional context.
- Do not claim the ESM probability is experimental fitness; describe it as model likelihood under learned sequence context.
