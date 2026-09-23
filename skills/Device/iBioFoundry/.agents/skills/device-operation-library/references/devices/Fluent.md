# Fluent

## Action: Load

Description: place labware and tips on the Fluent deck.

```javascript
Fluent [Load]
	(ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	Cell_Plate2 in 'Fluent:Nest 1' GetMyOwnContainer,
	Tips_Liha200_2 in 'Fluent:Nest 3' GetMyOwnContainer,
	8Well_Plate_1 'Lidded' in 'Fluent:Nest 5' GetMyOwnContainer;
```

Editable example placeholders:
- `Cell_Plate2`: example plate container name in this template block
- `Tips_Liha200_2`: example tips container name in this template block
- `8Well_Plate_1`: example lidded eight-well plate container name in this template block

## Action: RunMethod

Description: run a Fluent liquid-handling method.

```javascript
Fluent [RunMethod] 
	(SetVars = 'No', MethodName = 'ZFL_DS_pickolo_1_SBSplate_1_96DWP',
	MaximumOperationTime = '00:50:00', ReserveForIteration = 'As Is', 
	RunOnAbortedIteration = 'No', Duration = '00:00:01', MinDelay = '00:00:00', 
	MaxDelaySpecified = 'No', RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	Cell_Plate1 in 'Fluent:Nest 1' GetMyOwnContainer;
```

Editable example placeholders:
- `MethodName`
- `MaximumOperationTime`
- plate and tips container names in the load block
- `Cell_Plate1`: example plate container name in this template block

## Known Liquid-Handling Programs

### `AI_Plating_afterTransform_8well_plate.esc`

Use this as a Fluent liquid-handling program, not a FreedomEVO `RunScript`.

Purpose: perform plating after transformation by spreading recovered culture from the LB-containing 96 deep-well plate onto four 8-well plates.

Deck layout:
- `Fluent:Nest 1`: previous product 96 deep-well culture plate containing LB medium.
- `Fluent:Nest 3`: new `Tips_Liha200`.
- `Fluent:Nest 5`: new 8-well culture plate.
- `Fluent:Nest 6`: new 8-well culture plate.
- `Fluent:Nest 7`: new 8-well culture plate.
- `Fluent:Nest 8`: new 8-well culture plate.
