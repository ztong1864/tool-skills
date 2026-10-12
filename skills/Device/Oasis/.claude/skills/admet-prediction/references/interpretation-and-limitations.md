# Interpretation and limitations

## Field types

ADMET-AI v1 uses 41 TDC ADMET datasets: 31 classification tasks and 10 regression tasks. Classification outputs are probabilities of the named property or label. Regression outputs use the units and transformations of their source training datasets. Consult the ADMET-AI paper and TDC task documentation before assigning a unit or a favorable direction.

The 8 physicochemical fields are calculated descriptors, not neural-network predictions. The 49 DrugBank fields locate each descriptor or prediction relative to the approved-drug reference distribution; they are derived percentiles, not additional independent models and not pass/fail scores.

Do not combine endpoints into a single developability score unless the scoring rule, direction, thresholds, and validation are separately specified.

## Applicability and uncertainty

- This package does not provide an applicability-domain distance or reliability score.
- All syntactically valid SMILES can receive predictions, including structures far from the training chemical space.
- Unusual natural products, disconnected salts, mixtures, long hydrocarbons, organometallic structures, and extreme sizes require explicit extrapolation warnings.
- A DrugBank percentile is a reference-distribution comparison, not evidence of clinical safety or efficacy.
- Predicted DILI, hERG, AMES, CYP, exposure, clearance, or permeability values require experimental confirmation.
- ADMET-AI v1 and v2 use retrained, different models; their predictions are not interchangeable.

For article reporting, state the software version, endpoint name, classification/regression type, input standardization, invalid-input handling, and absence of an applicability-domain score.
