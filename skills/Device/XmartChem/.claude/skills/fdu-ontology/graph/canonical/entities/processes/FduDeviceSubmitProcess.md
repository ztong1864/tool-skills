# Process: FDU device task creation

This process submits the final device protocol to the FDU device API and records the submission result.

Use it only when the protocol JSON is already prepared and the user has explicitly approved device task creation.

Relevant step:

- `task-step:create-device-task`
- Optional follow-up: `task-step:monitor-device-task`

Required input:

- `artifact:device-protocol-json`

Produced artifact:

- `artifact:device-submit-result`
- Optional follow-up artifact: `artifact:device-monitor-result`

Required checkpoint:

- `checkpoint:approve-device-task-creation`

Relevant rules:

- `rule:no-device-task-without-user-approval`
- `rule:no-device-start-without-explicit-start-request`
- `rule:monitoring-is-read-only`

Operational notes:

- Creating a device task and starting execution are separate actions.
- `fdu-device-run` defaults to task creation only.
- Starting execution requires an explicit user request and must not be inferred from earlier confirmation.
- The submit result is evidence of API submission, not evidence that the experiment has already run.
- After the task exists, `fdu-execution-monitoring` may continuously read task status and push alerts, but it must not control the device task.
