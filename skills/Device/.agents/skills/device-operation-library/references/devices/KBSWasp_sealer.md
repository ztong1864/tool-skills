# KBSWasp_sealer

Sealing action for breathable film.

## Action: Seal

Description: seal a plate with breathable film on the KBS Wasp sealer.

```javascript
KBSWasp_sealer [Seal]
	(SealingTemperature = '155', ReserveForIteration = 'As Is', 
	RunOnAbortedIteration = 'No', Duration = '00:00:02', MinDelay = '00:00:00', 
	MaxDelaySpecified = 'No', RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	Cell_Plate1 in 'KBSWasp_sealer:Nest' GetMyOwnContainer;
```

Editable example placeholders:
- `Cell_Plate1`: example container name in this template block
