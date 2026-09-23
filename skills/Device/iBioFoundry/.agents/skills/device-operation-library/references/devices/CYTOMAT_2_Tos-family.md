# CYTOMAT_2_Tos Family

This file covers `CYTOMAT_2_Tos1` and `CYTOMAT_2_Tos2`. Select the exact device variant required by the experiment.

## Workflow Notes

- Before `CYTOMAT_2_Tos1 [Incubate]` or `CYTOMAT_2_Tos2 [Incubate]`, set the shake speeds with the same device variant unless the active protocol explicitly proves that the speed has already been set in the same process.
- Keep `Set Shake Speeds` before `Incubate` in shaking-incubation flows.
- Use the workflow rule `references/workflow-rules/cytomat-tos-shaking-incubation.md` for this prerequisite.

## Action: Set Shake Speeds

Description: set the shaking speed for the selected CYTOMAT_2_Tos tower before shaking incubation.

### CYTOMAT_2_Tos1

```javascript
CYTOMAT_2_Tos1 [Set Shake Speeds]
	(Tower1Speed = '900', Tower2Speed = '900', ReserveForIteration = 'As Is', 
	RunOnAbortedIteration = 'No', Duration = '00:00:00', 
	MinDelay = '00:00:00', MaxDelaySpecified = 'No', RequestedMaxDelay = '00:00:00', 
	SpoilIfMaxDelayExceeded = 'No', Enabled = 'Yes', SkipOnError = 'No');
```

### CYTOMAT_2_Tos2

```javascript
CYTOMAT_2_Tos2 [Set Shake Speeds]
	(Tower1Speed = '1000', Tower2Speed = '1000', ReserveForIteration = 'As Is',
	RunOnAbortedIteration = 'No', Duration = '00:00:00', MinDelay = '00:00:00', 
	MaxDelaySpecified = 'No', RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No');
```

## Action: Load

Description: move labware into the selected CYTOMAT_2_Tos shaking incubator.

### CYTOMAT_2_Tos1

```javascript
CYTOMAT_2_Tos1 [Load]
	(ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	Cell_Plate1 GetMyOwnContainer;
```

### CYTOMAT_2_Tos2

```javascript
CYTOMAT_2_Tos2 [Load]
	(ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	Cell_Plate1 GetMyOwnContainer;
```

Editable example placeholders:
- `Cell_Plate1`: example container name in these template blocks

## Action: Incubate

Description: incubate labware with the selected CYTOMAT_2_Tos shaking incubator for a specified duration.

### CYTOMAT_2_Tos1

```javascript
CYTOMAT_2_Tos1 [Incubate]
	(ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '01:00:00', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	Cell_Plate1 GetMyOwnContainer;
```

### CYTOMAT_2_Tos2

```javascript
CYTOMAT_2_Tos2 [Incubate]
	(ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:15:00', MinDelay = '00:00:00', MaxDelaySpecified = 'No',
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	Cell_Plate1 GetMyOwnContainer;
```

Editable example placeholders:
- `Tower1Speed`
- `Tower2Speed`
- `Duration`
- `Cell_Plate1`: example container name in these template blocks
