# Model Architecture

Current model: `primekg_cgi_graph_graph_only_e50`.

## Data Branches

| Data | Model Path | Output |
|---|---|---|
| SMILES | RDKit/DGL molecular graph + NNConv | `drug_global`, `atom_tokens` |
| Disease graph | DGL heterograph over disease/protein/phenotype/compound | `disease_global`, `disease_tokens`, protein and compound embeddings |
| Drug-protein target edges | Mechanism pooling over protein embeddings | `mechanism_emb` |
| CGI-U / CGI-D edges | Graph edges from compound to protein | `compound_global` after graph propagation |

## Fusion

The model uses multi-token cross-attention from disease tokens to atom tokens, then concatenates disease, molecular, interaction, mechanism, and Graph CGI compound representations. The MLP scoring head outputs an indication logit, which the delivery wrapper converts with sigmoid to `indication_score`.

## Best Configuration

```text
split_mode=pair
use_graph_cgi=1
use_perturbation_branch=0
use_drug_protein_branch=1
use_ppi=1
interaction_mode=multitoken_cross_attention
max_atom_tokens=80
max_protein_tokens=16
best_epoch=27
```

The supervision label edges are not inserted into the disease graph; they are used only for training the scoring head.


## Implementation Note

The current handoff source branch is `feature/cgi-graph-e50-handoff-clean`. In that branch, the Graph CGI model package carries its own lightweight helper modules for runtime imports, sampling, metrics, diagnostics, SMILES alignment and SMILES-to-DGL graph construction. This reduces hidden coupling to earlier baseline packages while preserving the same model behavior.
