# Assay Comparability

## Reporter Assays

| Assay | Used in | Measures | Caveats |
|---|---|---|---|
| sfGFP amber suppression fluorescence | S01, S03, S04, S05, S06, S07 | In-cell stop codon suppression and full-length protein expression | Conflates aaRS activity, tRNA charging, translation, protein folding, expression, and fluorescence effects. |
| YFP(TAG) expression | S08 | ncAA incorporation into a reporter protein | Better secondary validation than colony color, but still an expression proxy. |
| LacZ(2xTAG) white/blue screen | S08 | qualitative suppression of two TAG codons | High-throughput first pass; not enough alone for quantitative claims. |
| beta-galactosidase PNP-Gal assay | S08 | quantitative reporter enzyme activity | Useful for comparing variants in one system; not directly comparable to sfGFP intensity. |
| aminoacylation kinetics | S03, S04, S07 | kcat, Km, kcat/Km for amino acid and/or tRNA | Stronger mechanistic evidence but usually available only for selected variants. |
| mass spectrometry of purified reporter | S05, S06, S08 | incorporation identity and specificity | Validates product identity but not necessarily activity ranking. |
| structural crystallography | S04 | physical contacts and domain interface geometry | Usually limited to selected constructs and may not capture full dynamic state. |
| molecular dynamics | S01 for PedH, S07 for PylRS variants | simulated dynamics and interaction hypotheses | Treat as mechanistic support, not direct wet-lab activity evidence. |

## Comparability Rule

Do not rank variants across papers solely by raw fluorescence or reporter output. Compare variants directly only when assay, host, plasmid/promoter context, substrate concentration, reporter, and normalization are sufficiently similar.

