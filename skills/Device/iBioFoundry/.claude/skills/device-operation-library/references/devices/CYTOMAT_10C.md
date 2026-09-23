# CYTOMAT_10C

## Action: Load

Description: move labware into the CYTOMAT_10C incubator or storage position.

```javascript
CYTOMAT_10C [Load]
	(ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	Cell_Plate1 GetMyOwnContainer;
```

Editable example placeholders:
- `Cell_Plate1`: example container name in this template block

## Action: Incubate

Description: incubate labware in CYTOMAT_10C for a specified duration.

```javascript
CYTOMAT_10C [Incubate]
	(ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '01:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	Cell_Plate1 GetMyOwnContainer;
```

Editable example placeholders:
- `Duration`
- `Cell_Plate1`: example container name in this template block
