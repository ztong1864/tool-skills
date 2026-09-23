# Process: FDU protocol orchestration

This process converts verified, resource-filled step JSON into device-executable protocol JSON.

Use it only after resource verification has completed successfully and the step JSON is ready to be lowered into device actions.

Relevant step:

- `task-step:orchestrate-device-protocol`

Required input:

- `artifact:verified-step-json`

Produced artifact:

- `artifact:device-protocol-json`

Relevant device actions:

- `device-action:add-solid`
- `device-action:add-liquid`
- `device-action:reaction-control`
- `device-action:filter`
- `device-action:high-filter`

What the Agent should check here:

- every step maps to a supported `DeviceAction`,
- resource information is present where required,
- the protocol output remains consistent with the verified step JSON,
- no unsupported device semantics are introduced,
- the user-visible protocol summary is suitable for approval before device task creation.

The Agent should only proceed to `task-step:create-device-task` after `checkpoint:approve-device-task-creation`.
