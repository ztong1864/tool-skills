# Rotanta460

Bucket centrifuge used for deep-well plate centrifugation. Use balance plates in the remaining rotor nests when a single sample plate is loaded.

## Action: Load

Description: load a sample plate and balancing plates into Rotanta460 rotor nests.

```javascript
Rotanta460 [Load]
	(ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	Cell_Plate1 in 'Rotanta460:Rotor Nest 1' GetMyOwnContainer,
	Balance_DWP1 in 'Rotanta460:Rotor Nest 2' GetMyOwnContainer,
	Balance_DWP2 in 'Rotanta460:Rotor Nest 3' GetMyOwnContainer,
	Balance_DWP3 in 'Rotanta460:Rotor Nest 4' GetMyOwnContainer;
```

Editable example placeholders:
- `Cell_Plate1`: example sample plate container name in this template block
- `Balance_DWP1`: example balance plate container name in this template block
- `Balance_DWP2`: example balance plate container name in this template block
- `Balance_DWP3`: example balance plate container name in this template block

## Action: Run

Description: run a Rotanta460 centrifugation program with specified spin parameters.

```javascript
Rotanta460 [Run]
	(ProgramRunMode = 'User Defined Run Parameters', SpinDuration = '00:05:00', 
	ProgramNumber = '0', RPM = '4000', RCF = '3756', Temperature = '20', 
	AccelerationLevel = '9', DecelerationLevel = '9', AvailableNests = 'Rotor Nest 1, Rotor Nest 2, Rotor Nest 3, Rotor Nest 4', 
	ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:10:00', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	Cell_Plate1 in 'Rotanta460:Rotor Nest 1' GetMyOwnContainer,
	Balance_DWP1 in 'Rotanta460:Rotor Nest 2' GetMyOwnContainer,
	Balance_DWP2 in 'Rotanta460:Rotor Nest 3' GetMyOwnContainer,
	Balance_DWP3 in 'Rotanta460:Rotor Nest 4' GetMyOwnContainer;
```

Editable example placeholders:
- `SpinDuration`
- `RPM`
- `RCF`
- `Temperature`
- `Duration`
- plate and balance container names in the block
- rotor nest assignments in the block
