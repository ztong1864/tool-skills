# FreedomEVO Liquid-Handling Pre-run

Use this rule when deciding whether to insert `FreedomEVO [RunScript]` with `LYY_chenwanyi_inheco.esc` before another FreedomEVO liquid-handling script.

## Rule

- Consider running `LYY_chenwanyi_inheco.esc` immediately before a substantive FreedomEVO liquid-handling script when the active experiment mapping shows this pattern or when the liquid-handling method likely depends on deck/liquid-handling environment preparation.
- Do not blindly insert it before every FreedomEVO script. Decide from the validated reference pattern, method family, and surrounding workflow.
- If the active experiment mapping explicitly omits the preparation step before a method, preserve that omission unless a newer validated rule says otherwise.

## Validated Reference Pattern

In the DH5a plasmid construction reference script:

- Run the preparation script before `AI_Pre_Plasmid_PCR_1_Plate.esc`.
- Run the preparation script before `AI_addDpnI.esc`.
- Run the preparation script before `AI_Pre_Transforming.esc`.
- Do not run the preparation script before `AI_AddLB.esc`.

## Preparation Action

```javascript
FreedomEVO [RunScript]
	(SetVars = 'No', ScriptName = 'LYY_chenwanyi_inheco.esc', 
	MaximumOperationTime = '00:20:00', WaitMethod = 'Yes', 
	ReserveForIteration = 'As Is', RunOnAbortedIteration = 'No', 
	Duration = '00:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No');
```
