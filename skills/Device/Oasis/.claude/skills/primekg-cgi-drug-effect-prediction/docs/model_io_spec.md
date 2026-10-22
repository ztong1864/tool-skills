# Model I/O Spec

## Supported Task

Score fitted PrimeKG/KG candidate drugs for one supported disease using the packaged Graph CGI e50 indication model.

## Inputs

| Field | Required | Description |
|---|---|---|
| `bundle_dir` | yes | Directory containing `best_bundle.pt` or `bundle.pt`. |
| `prepared_dir` | yes | Directory containing `candidate_pool.csv`, `disease_catalog.csv`, and mechanism edge CSVs. |
| `disease` | yes | `disease_id` or exact `disease_name`. |
| `device` | no | `auto`, `cpu`, `cuda`, or `mps`. |
| `top_k` | no | `0` means all candidates; positive integer means first K. |
| `candidate_drugbank_ids` | no | Optional file with one DrugBank ID per line. Every ID must exist in `candidate_pool.csv`. |

## Disease Resolution

The resolver first matches `disease_id` exactly after whitespace normalization and case folding. If no ID matches, it matches `disease_name` exactly with the same normalization. Ambiguous names are rejected and the caller must use disease ID.

## Output CSV

```text
disease_id,disease_name,rank,drugbank_id,drug_name,indication_score,has_cgi,has_drug_protein_target
```

`indication_score` is the sigmoid-transformed model output used for ranking within the supported candidate pool. It is not a clinical probability.

## Error Behavior

- Unknown disease: fail with a supported-disease error.
- Ambiguous disease name: fail and list candidate disease IDs.
- Unknown DrugBank ID in optional candidate file: fail; this version does not support cold-start drugs.
- Missing model files: fail before scoring.
- Unavailable explicit device, such as `cuda` without CUDA: fail with a device error.
