# Interpretation and limitations

## What the fields support

The wrapper computes descriptors and deterministic structural-rule outputs. `Lipinski=1` means all four configured Rule-of-Five thresholds pass: MW ≤ 500, cLogP ≤ 5, HBD ≤ 5, and HBA ≤ 10. It is a heuristic screen for oral-drug-like property ranges, not a fifth experimental measurement.

QED combines several calculated properties into a 0–1 drug-likeness estimate. A higher value indicates greater similarity to the property distribution encoded by QED; it does not establish potency, selectivity, exposure, safety, or clinical success.

PAINS and Brenk matches are structural alerts. Report them as reasons for review, orthogonal assays, or chemical inspection. Natural products, polyphenols, reactive motifs, and complex scaffolds may match without being universally unusable.

## Required warnings

- A syntactically valid SMILES is not necessarily an appropriate small-molecule drug candidate.
- Disconnected salts, mixtures, metal-containing structures, long hydrocarbons, and extreme molecular sizes require manual review.
- These rules have no learned training-set applicability-domain score.
- The result does not predict ADMET, efficacy, disease relevance, targets, or perturbational mechanism.
- A molecule that fails the Rule of Five can still be a drug; a molecule that passes can still fail development.

For natural-product projects, preserve the raw descriptors and alerts, then combine them with experimental evidence and an explicitly separate ADMET assessment.
