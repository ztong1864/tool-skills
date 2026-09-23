# Clariostar

Read this file for the device action itself.  
If the plate enters `Clariostar`, also read [../workflow-rules/clariostar-rotation.md](../workflow-rules/clariostar-rotation.md).

## Action: Run Protocol

Description: run a plate-reader measurement protocol on the Clariostar.

```javascript
Clariostar [Run Protocol]
	(ProtocolName = 'DS_OD650', InputPath = 'C:\\Program Files (x86)\\BMG\\CLARIOstar\\User\\Definit', 
	OutputPath = '\\\\Desktop-dlcnovg\\d\\BMG_Output_Data\\ZFL', 
	OutputName = 'ZFL_YJJ_plate4_Ite_<ITER#>', OverrideAsciiExportPath = 'No',
	AddDateToAsciiExportPath = 'No', ReserveForIteration = 'As Is', 
	RunOnAbortedIteration = 'No', Duration = '00:00:59', MinDelay = '00:00:00', 
	MaxDelaySpecified = 'No', RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	BMG_Plate1 'Unlidded' in 'Clariostar:Nest' HoldLid GetMyOwnContainer;
```

Editable example placeholders:
- `ProtocolName`
- `OutputName`
- `BMG_Plate1`: example plate container name in this template block
