# Clariostar Rotation Rule

Use this rule whenever a plate is measured on `Clariostar`.

## Required Sequence

1. Run `F7_1_Rotation [Rotate]` before entering `Clariostar`.
2. Run `Clariostar [Run Protocol]` with the plate as `'Unlidded'` and `HoldLid`.
3. Run `F7_1_Rotation [Rotate]` again after leaving `Clariostar`.

## Fixed Pattern

```javascript
F7_1_Rotation [Rotate]
	(ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	Plate1 'Lidded' in 'F7_1_Rotation:Nest' GetMyOwnContainer;

Clariostar [Run Protocol]
	(...)
	Plate1 'Unlidded' in 'Clariostar:Nest' HoldLid GetMyOwnContainer;

F7_1_Rotation [Rotate]
	(ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	Plate1 'Lidded' in 'F7_1_Rotation:Nest' GetMyOwnContainer;
```

## Notes

- This is a workflow rule, not a single-device template.
- Do not duplicate this full rule into device reference files.
- This rule governs device-action lid handling only.
- Write the plate's `Acquire` binding according to `container-and-status-rules/references/lid-management.md`.
