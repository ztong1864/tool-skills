# XPeel

## Action: Remove Seal

Description: remove the seal film from a plate on the XPeel nest.

```javascript
XPeel [Remove Seal] 
	(ParameterSet = 'Set 4 - Location: default, Speed: slow', AdhereTime = '2.5', 
	PeelTimeOut = '00:00:35', ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	Primer1 in 'XPeel:Nest' GetMyOwnContainer;
```

Editable example placeholders:
- `Primer1`: example reagent-plate container name in this template block

For first-use applicability, read [../workflow-rules/reagent-plate-first-use-unsealing.md](../workflow-rules/reagent-plate-first-use-unsealing.md).
For multiple plates, also read [../workflow-rules/single-nest-device-occupancy.md](../workflow-rules/single-nest-device-occupancy.md).
