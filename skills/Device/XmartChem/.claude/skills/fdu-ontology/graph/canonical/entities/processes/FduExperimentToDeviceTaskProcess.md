# Process: FDU experiment target to device task

This is the umbrella FDU process for taking a user experiment target from natural language to a confirmed device task.

Use this process when the request may span multiple stages, for example:

- parsing constraints from the user request,
- recommending executable condition rows,
- calculating reagent amounts,
- generating numbered wet-lab steps,
- writing a Chinese experiment plan,
- converting and merging step JSON,
- verifying resources,
- orchestrating protocol JSON,
- creating a device task,
- optionally monitoring the created task without controlling it.

Canonical flow:

- `agent-flow:fdu-experiment-to-device-task`

Default route:

1. `task-step:parse-experiment-request`
2. `task-step:recommend-experiment-conditions`
3. `checkpoint:review-recommendations`
4. `task-step:calculate-reagent-amounts`
5. `checkpoint:review-amounts`
6. `task-step:generate-numbered-steps`
7. `checkpoint:review-numbered-steps`
8. `task-step:write-experiment-plan`
9. `task-step:merge-step-json`
10. `task-step:verify-and-fill-resources`
11. `task-step:orchestrate-device-protocol`
12. `checkpoint:approve-device-task-creation`
13. `task-step:create-device-task`
14. Optional: `task-step:monitor-device-task`

What the Agent must track:

- the current stage and next executable skill,
- which `DataArtifact` is required now,
- which artifact must be shown to the user,
- where confirmation is mandatory,
- which `ExecutionRule` blocks progression,
- when device semantics become relevant.

Hard rules:

- Stop at every `Checkpoint`.
- Do not bypass user-visible artifacts with `must_confirm=true`.
- Do not reach `fdu-device-run` without explicit user approval.
- Do not enable device start unless the user explicitly requests execution.
- If monitoring is requested after task creation, use `fdu-execution-monitoring` as a read-only step only.

This process is the top-level entry for `Process` lookup. Specialized subprocesses split the same flow into planning, resource verification, protocol orchestration, and device task creation.
