# CentrifugeLoader To Cytomat_24H Rule

Use this rule when a fixed microplate centrifugation flow moves from `CentrifugeLoader [Spin]` to `Cytomat_24H [Load]`.

## Required Sequence

1. Run `CentrifugeLoader [Spin]` with `PCR_Plate1` in `Bucket 1`.
2. Run `CentrifugeLoader [Spin]` with `Balance_PCR` in `Bucket 2`.
3. Run `Cytomat_24H [Load]` with both `PCR_Plate1 GetMyOwnContainer` and `Balance_PCR GetMyOwnContainer`.

## Fixed Pattern

```javascript
CentrifugeLoader [Spin] 
	(...)
	PCR_Plate1 in 'CentrifugeLoader:Bucket 1' GetMyOwnContainer,
	Balance_PCR in 'CentrifugeLoader:Bucket 2' GetMyOwnContainer;

Cytomat_24H [Load] 
	(...)
	PCR_Plate1 GetMyOwnContainer,
	Balance_PCR GetMyOwnContainer;
```

## Notes

- The default container choice for this fixed flow is `PCR_Plate1` plus `Balance_PCR`.
- Do not drop `Balance_PCR` when building the immediate `Cytomat_24H [Load]` step after centrifugation.
- This is a workflow rule, not a replacement for the individual device templates.
