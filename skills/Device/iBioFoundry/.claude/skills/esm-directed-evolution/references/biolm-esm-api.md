# BioLM ESM Masked Prediction API

## Endpoint

Use:

```http
POST https://biolm.ai/api/v3/{model}/predict/
Authorization: Token YOUR_API_KEY
Content-Type: application/json
```

For Agent use, do not put the token in prompts, generated scripts, SKILL.md, or committed files. Prefer `BIOLM_API_KEY`, `BIOLM_API_KEY_FILE`, or `.agents/secrets/biolm.env`; the last path is intended to be git-ignored in this workspace.

Common model choices:

- `esm2-8m`: fast smoke tests and examples.
- `esm2-35m`: quick directed-evolution iteration.
- `esm2-150m`, `esm2-650m`, `esm2-3b`: larger models when ranking quality matters more than latency.

## Request

```json
{
  "items": [
    {
      "sequence": "MKTFFV<mask>LVLLLSGALAAPVA"
    }
  ]
}
```

Rules:

- Use the literal string `<mask>` for masked residues.
- Remove a terminal `*` stop symbol before submitting. BioLM accepts residue characters such as `ACDEFGHIKLMNPQRSTVWYBXZUO` and rejects `*`.
- Keep each sequence at or below the model's documented length limit, commonly 2048 residues for ESM-2 endpoints.
- Keep batches small; BioLM ESM-2 docs commonly describe batch limits around 5-8 sequences depending on endpoint/model.

## Response Shape

ESM-2 predictor responses contain:

```json
{
  "results": [
    {
      "logits": [[0.1, -0.3, 1.2]],
      "sequence_tokens": ["M", "K", "T", "<mask>"],
      "vocab_tokens": ["A", "C", "D"]
    }
  ]
}
```

Interpretation:

- `logits` is an array per masked position, with one score per vocabulary token.
- `vocab_tokens[i]` gives the token represented by `logits[*][i]`.
- Apply softmax to logits before comparing probabilities.

ESM-1v (`esm1v-all`) responses contain one candidate list per submodel, such as `esm1v-n1` through `esm1v-n5`. Each candidate has `token_str` and `score`. For user-facing output, average scores for each amino-acid token across submodels and omit the raw per-submodel lists unless debugging the API.

## Candidate Token Order

For directed evolution, use this default output order when present:

```text
A C D E F G H I K L M N P Q R S T V W Y X B Z U O - . <unk> <mask>
```

The first 20 are standard amino acids. The rest are ambiguous, rare, gap/stop-like, or model special tokens that may appear in ESM vocabularies. Drop unavailable tokens rather than inventing probabilities.

## Practical Interpretation

ESM masked probabilities estimate contextual sequence likelihood, not measured enzyme fitness. Use them to prioritize variant libraries, then combine with structural constraints, active-site knowledge, assay data, and diversity goals.
