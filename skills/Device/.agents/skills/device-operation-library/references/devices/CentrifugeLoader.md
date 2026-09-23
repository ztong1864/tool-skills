# CentrifugeLoader

This device normally requires a balancing plate in the paired bucket.

## Action: Load

Description: place a plate or balance plate into a specified CentrifugeLoader bucket.

```javascript
CentrifugeLoader [Load]
	(ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	PCR_Plate1 in 'CentrifugeLoader:Bucket 1' GetMyOwnContainer;
```

Editable example placeholders:
- `PCR_Plate1`: example plate container name in this template block
- `CentrifugeLoader:Bucket 1`: bucket nest may be changed to another approved bucket required by the workflow

## Action: Spin

Description: centrifuge the loaded plate with its required balancing plate.

```javascript
CentrifugeLoader [Spin] 
	(VelocityPercent = '80', AccelerationPercent = '80', DecelerationPercent = '80', 
	TimerMode = 'Time at Speed', SpinDuration = '00:02:00', BucketNumberToLoad = 'Bucket 1 and 2', 
	ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:02:00', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	PCR_Plate1 in 'CentrifugeLoader:Bucket 1' GetMyOwnContainer,
	Balance_PCR in 'CentrifugeLoader:Bucket 2' GetMyOwnContainer;
```

Editable example placeholders:
- `VelocityPercent`
- `AccelerationPercent`
- `DecelerationPercent`
- `SpinDuration`
- `Duration`
- `PCR_Plate1`: example sample plate container name in this template block
- `Balance_PCR`: example balancing plate container name in this template block
