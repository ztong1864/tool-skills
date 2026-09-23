# Combi

## Action: Load

Description: place a plate on the Combi dispenser nest.

```javascript
Combi [Load] 
	(ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	Cell_Plate3 in 'Combi:Nest' GetMyOwnContainer;
```

Editable example placeholders:

`Cell_Plate3`: example source/target container name in this template block

## Action: Dispense

Description: dispense liquid into the loaded plate with the Combi dispenser.

```javascript
Combi [Dispense] 
	(CassetteID = '0', DispenseVolume = '50', FirstCol = '0', FirstRow = '0', 
	LastCol = '0', LastRow = '0', PlateType = '96 standard (15mm)', 
	DispenseOrder = 'No', Fluid = 'Default Fluid', PrimeVolume = '1000', 
	PrimeEnabled = 'No', PumpSpeed = '50', DispenseHeight = '4600', 
	DispenseXOffset = '0', DispenseYOffset = '0', DefaultToColumn1 = 'Yes', 
	Column_1 = '800', Column_2 = '800', Column_3 = '800', Column_4 = '800', 
	Column_5 = '800', Column_6 = '800', Column_7 = '800', Column_8 = '800', 
	Column_9 = '800', Column_10 = '800', Column_11 = '800', Column_12 = '800', 
	Column_13 = '800', Column_14 = '800', Column_15 = '800', Column_16 = '800', 
	Column_17 = '800', Column_18 = '800', Column_19 = '800', Column_20 = '800', 
	Column_21 = '800', Column_22 = '800', Column_23 = '800', Column_24 = '800', 
	Column_25 = '800', Column_26 = '800', Column_27 = '800', Column_28 = '800', 
	Column_29 = '800', Column_30 = '800', Column_31 = '800', Column_32 = '800', 
	Column_33 = '800', Column_34 = '800', Column_35 = '800', Column_36 = '800', 
	Column_37 = '800', Column_38 = '800', Column_39 = '800', Column_40 = '800', 
	Column_41 = '800', Column_42 = '800', Column_43 = '800', Column_44 = '800', 
	Column_45 = '800', Column_46 = '800', Column_47 = '800', Column_48 = '800', 
	ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:00:10', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	Cell_Plate2 in 'Combi:Nest' GetMyOwnContainer;
```

Editable example placeholders:
- `DispenseVolume`
- `Column_1` through `Column_48`
- `Cell_Plate2`: example source/target container name in this template block
