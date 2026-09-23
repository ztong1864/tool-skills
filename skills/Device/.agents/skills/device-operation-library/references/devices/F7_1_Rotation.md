# F7_1_Rotation

Rotation action used with plate reorientation.

## Action: Rotate

Description: rotate or reorient a lidded plate before or after another device action.

```javascript
F7_1_Rotation [Rotate]
	(ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	BMG_Plate1 'Lidded' in 'F7_1_Rotation:Nest' GetMyOwnContainer;
```

Editable example placeholders:
- `BMG_Plate1`: example plate container name in this template block

If used with `Clariostar`, also read [../workflow-rules/clariostar-rotation.md](../workflow-rules/clariostar-rotation.md).
