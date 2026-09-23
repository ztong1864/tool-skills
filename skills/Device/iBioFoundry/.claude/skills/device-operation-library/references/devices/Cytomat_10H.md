# Cytomat_10H

## Action: Load

Description: move labware into the Cytomat_10H hotel or storage position.

```javascript
Cytomat_10H [Load] 
	(ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	Cell_Plate1 GetMyOwnContainer;
```

Editable example placeholders:
- `Cell_Plate1`: example container name in this template block
