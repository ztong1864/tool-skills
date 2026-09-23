# FreedomEVO

## Workflow Notes

- FreedomEVO is a liquid-handling workstation. The concrete meaning of `FreedomEVO [RunScript]` is determined by the `ScriptName` program; do not treat FreedomEVO as a single-function device.
- Before a real liquid-handling `FreedomEVO [RunScript]`, consider whether the deck or liquid-handling program requires the preparation script `LYY_chenwanyi_inheco.esc`.
- Use the workflow rule `references/workflow-rules/freedomevo-liquid-handling-prerun.md` when deciding whether to insert this preparation step.
- `Tips_MCA*` tips are high-throughput head tips. When they are consumed on FreedomEVO, use the `ends 'FreedomEVO:Waste'` container routing form shown below.
- `Tips_Liha*` tips are normally staged after use rather than routed to `FreedomEVO:Waste`; use the default labware destination workflow rule.

## Action: Load

Description: place labware on the FreedomEVO deck.

```javascript
FreedomEVO [Load] 
	(ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	03_48DWP_1 in 'FreedomEVO:Nest 9' GetMyOwnContainer;
```

Editable example placeholders:
- `03_48DWP_1`: example container name in this template block

## Action: RunScript

Description: run a FreedomEVO liquid-handling workstation script.

```javascript
FreedomEVO [RunScript]
	(SetVars = 'No', ScriptName = 'ZFL_KD_addLysis_step7.esc', MaximumOperationTime = '00:50:00',
	WaitMethod = 'Yes', ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	03_48DWP_1 in 'FreedomEVO:Nest 9' GetMyOwnContainer,
	03_48DWP_2 in 'FreedomEVO:Nest 10' GetMyOwnContainer,
	Cell_Plate1 in 'FreedomEVO:Nest 11' GetMyOwnContainer;
```

Editable example placeholders:
- `ScriptName`
- `MaximumOperationTime`
- all container names in the block
- all `FreedomEVO:Nest X` nest assignments in the block

## Known RunScript Programs

### `AI_Pre_Plasmid_PCR_1_Plate.esc`

Purpose: prepare whole-plasmid PCR reaction liquid.

Deck layout:
- `FreedomEVO:Nest 1`: reagent plate containing primers.
- `FreedomEVO:Nest 2`: new `PCR_Plate1`.
- `FreedomEVO:Nest 3`: new `Tips_Liha50`.
- `FreedomEVO:Nest 5`: new `Tips_MCA50`; after use, discard with `ends 'FreedomEVO:Waste'`.

After the program, all labware except the consumed `Tips_MCA50` returns to or remains at its original position.

### `AI_addDpnI.esc`

Purpose: add DpnI to the previous product plate.

Deck layout:
- `FreedomEVO:Nest 1`: previous product `PCR_Plate1`.
- `FreedomEVO:Nest 3`: new `Tips_Liha10`.

### `AI_Pre_Transforming.esc`

Purpose: prepare chemical transformation reaction liquid using DH5a competent cells.

Deck layout:
- `FreedomEVO:Nest 1`: previous product `PCR_Plate1`.
- `FreedomEVO:Nest 2`: new `PCR_Plate2`.
- `FreedomEVO:Nest 3`: new `Tips_Liha50`.
- `FreedomEVO:Nest 4`: new `Tips_Liha50`.

### `AI_AddLB.esc`

Purpose: add transformed product to LB medium to prepare recovery reaction liquid.

Deck layout:
- `FreedomEVO:Nest 1`: previous product `PCR_Plate2`.
- `FreedomEVO:Nest 2`: 96 deep-well culture plate containing LB medium.
- `FreedomEVO:Nest 3`: new `Tips_Liha50`.

### Example: RunScript With MCA Tips To Waste

Description: run a FreedomEVO script that consumes MCA tips and routes the used MCA tip box to FreedomEVO waste.

Use this container syntax when a `Tips_MCA*` box is consumed by a FreedomEVO script.

```javascript
FreedomEVO [RunScript]
	(SetVars = 'No', ScriptName = 'AI_Pre_Plasmid_PCR_1_Plate.esc', 
	MaximumOperationTime = '00:50:00', WaitMethod = 'Yes', 
	ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No')
	Primer1 in 'FreedomEVO:Nest 1' GetMyOwnContainer,
	PCR_Plate1 in 'FreedomEVO:Nest 2' GetMyOwnContainer,
	Tips_Liha50_1 in 'FreedomEVO:Nest 3' GetMyOwnContainer,
	Tips_MCA50_1 in 'FreedomEVO:Nest 5' ends 'FreedomEVO:Waste' GetMyOwnContainer;
```

### Example: Run Inheco Preparation Script

Description: run the Inheco temperature-control preparation script before selected FreedomEVO liquid-handling programs.

```javascript
FreedomEVO [RunScript]
	(SetVars = 'No', ScriptName = 'LYY_chenwanyi_inheco.esc', 
	MaximumOperationTime = '00:20:00', WaitMethod = 'Yes', 
	ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No');
```
