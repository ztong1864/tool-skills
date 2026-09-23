# ATC Family

This file merges `ATC_1`, `ATC_2`, and `ATC_3`.

Use the exact device variant required by the experiment. Only the device name and `MaximumOperationDuration` differ across the current templates.

## Action: Load

Description: place a PCR plate into the selected ATC thermocycler nest.

### ATC_1

```javascript
ATC_1 [Load] 
	(ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	PCR_Plate1 in 'ATC_1:Nest' GetMyOwnContainer;
```

### ATC_2

```javascript
ATC_2 [Load] 
	(ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	PCR_Plate1 in 'ATC_2:Nest' GetMyOwnContainer;
```

### ATC_3

```javascript
ATC_3 [Load] 
	(ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	PCR_Plate1 in 'ATC_3:Nest' GetMyOwnContainer;
```

Editable example placeholders:
- `PCR_Plate1`: example PCR plate container name in these template blocks

## Action: Run Protocol

Description: run a thermocycler protocol on the selected ATC device.

### ATC_1

```javascript
ATC_1 [Run Protocol] 
	(ProtocolFolderPath = 'C:\\Users\\DELL\\Desktop\\ATC PCR template\\ZFL', 
	ProtocolName = 'KD_heatlysis.xml', CustomCoverTemperature = '95', 
	MaximumOperationDuration = '00:30:00', ReserveForIteration = 'As Is', 
	RunOnAbortedIteration = 'No', Duration = '00:00:01', MinDelay = '00:00:00', 
	MaxDelaySpecified = 'No', RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	PCR_Plate1 in 'ATC_1:Nest' GetMyOwnContainer;
```

### ATC_2

```javascript
ATC_2 [Run Protocol] 
	(ProtocolFolderPath = 'C:\\Users\\DELL\\Desktop\\ATC PCR template\\ZFL', 
	ProtocolName = 'KD_heatlysis.xml', CustomCoverTemperature = '95',  
	MaximumOperationDuration = '00:40:00', ReserveForIteration = 'As Is', 
	RunOnAbortedIteration = 'No', Duration = '00:00:01', MinDelay = '00:00:00', 
	MaxDelaySpecified = 'No', RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	PCR_Plate1 in 'ATC_2:Nest' GetMyOwnContainer;
```

### ATC_3

```javascript
ATC_3 [Run Protocol] 
	(ProtocolFolderPath = 'C:\\Users\\DELL\\Desktop\\ATC PCR template\\ZFL', 
	ProtocolName = 'KD_heatlysis.xml', CustomCoverTemperature = '95', 
	MaximumOperationDuration = '00:30:00', ReserveForIteration = 'As Is', 
	RunOnAbortedIteration = 'No', Duration = '00:00:01', MinDelay = '00:00:00', 
	MaxDelaySpecified = 'No', RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	PCR_Plate1 in 'ATC_3:Nest' GetMyOwnContainer;
```

Editable example placeholders:
- `ProtocolName`
- `CustomCoverTemperature`
- `MaximumOperationDuration`
- `PCR_Plate1`: example PCR plate container name in this template block

Fixed notes:
- `ProtocolFolderPath` stays `C:\\Users\\DELL\\Desktop\\ATC PCR template\\ZFL`
