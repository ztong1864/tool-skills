# Cytomat_2C425

## Action: Load

Description: move labware into the Cytomat_2C425 low-temperature storage or incubation position.

```javascript
Cytomat_2C425 [Load] 
	(ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	Cell_Plate1 GetMyOwnContainer;
```

Editable example placeholders:
- `Cell_Plate1`: example container name in this template block

## Action: Incubate

Description: incubate labware in Cytomat_2C425 for a specified duration.

```javascript
Cytomat_2C425 [Incubate] 
	(ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '01:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No',
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	Cell_Plate1 GetMyOwnContainer;
```

Editable example placeholders:
- `Duration`
- `Cell_Plate1`: example container name in this template block
