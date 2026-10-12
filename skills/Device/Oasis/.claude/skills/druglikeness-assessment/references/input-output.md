# Input and output contract

## Input

Use a UTF-8 CSV with one row per structure. Required columns default to:

```csv
compound_id,smiles
aspirin,CC(=O)OC1=CC=CC=C1C(=O)O
```

Override the column names with `--id-col` and `--smiles-col`. Other input columns are ignored. Row order and duplicate IDs are preserved. Blank, whitespace-only, unparsable, and zero-atom SMILES are returned as `INVALID_SMILES` rather than dropped.

## Output

The output has exactly 13 columns:

| Column | Meaning |
|---|---|
| `compound_id` | Input identifier |
| `smiles` | Original input text |
| `status` | `OK` or `INVALID_SMILES` |
| `MW` | RDKit molecular weight, Da |
| `cLogP` | Wildman-Crippen cLogP implementation in RDKit |
| `HBD`, `HBA` | Hydrogen-bond donor and acceptor counts |
| `TPSA` | Topological polar surface area, Å² |
| `RotBonds` | Rotatable-bond count |
| `QED` | RDKit quantitative estimate of drug-likeness, 0–1 |
| `Lipinski` | `1` only when all four configured thresholds pass |
| `PAINS`, `Brenk` | `1` when the corresponding RDKit catalog matches |

Result fields after `status` are empty for invalid SMILES.

## Commands

```bash
python scripts/rdkit_assess.py --input molecules.csv --output results.csv
python scripts/verify_output.py \
  --actual results.csv \
  --expected assets/expected_output.csv
```
