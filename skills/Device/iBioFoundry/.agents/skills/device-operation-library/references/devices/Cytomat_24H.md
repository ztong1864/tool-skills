# Cytomat_24H

## Action: Load

Description: move labware, tips, or balance plates into the Cytomat_24H storage position.

When this action follows `CentrifugeLoader [Spin]` in the fixed PCR microplate centrifugation flow, carry both the sample plate and the balancing plate into `Cytomat_24H [Load]`.

```javascript
Cytomat_24H [Load] 
	(ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	PCR_Plate1 GetMyOwnContainer,
	Balance_PCR GetMyOwnContainer;
```

Editable example placeholders:
- `PCR_Plate1`: example sample plate container name in this template block
- `Balance_PCR`: example balancing plate container name in this template block
