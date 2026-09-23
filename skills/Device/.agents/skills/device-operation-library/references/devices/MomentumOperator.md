# MomentumOperator

## Action: Manual

Description: show a manual operator task or pause instruction inside the Momentum workflow.

```javascript
MomentumOperator [Manual] 
	(PauseSystem = 'No', EmailListLabel = '<Select Emails>...', 
	TaskAction = 'Show', ShowAsError = 'Yes', TaskName = '5000 rpm, 4degree,15min Centrifuge',
	TaskTimeout = '00:00:00', AllowCancellation = 'No', EmailList = 'weibin.zou@thermofisher.com~false;fei.liu2@thermofisher.com~false', 
	Duration = '00:00:01', MinDelay = '00:00:00', MaxDelaySpecified = 'No', 
	RequestedMaxDelay = '00:00:00', SpoilIfMaxDelayExceeded = 'No', 
	Enabled = 'Yes', SkipOnError = 'No');
```

Editable example placeholders:
- `TaskName`
