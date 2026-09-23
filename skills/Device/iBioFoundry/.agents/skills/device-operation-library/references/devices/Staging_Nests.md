# Staging_Nests

## Action: Load

Description: move labware to staging nests for temporary holding.

```javascript
Staging_Nests [Load] 
	(ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	03_48DWP_1 GetMyOwnContainer,
	03_48DWP_2 GetMyOwnContainer;
```

Editable example placeholders:
- `03_48DWP_1`: example container name in this template block
- `03_48DWP_2`: example container name in this template block

## Action: Incubate

Description: hold labware on staging nests for a specified duration.

```javascript
Staging_Nests [Incubate] 
	(ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:15:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No',
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	03_48DWP_1 GetMyOwnContainer,
	03_48DWP_2 GetMyOwnContainer;
```

Editable example placeholders:
- `Duration`
- `03_48DWP_1`: example container name in this template block
