# FDU Ontology Schema

This schema defines an Agent-facing task ontology for FDU experiment automation. Its primary job is to guide the Agent through each step, each data artifact, required user checkpoints, safety rules, and only the device semantics needed at the equipment stage.

It is intentionally not a full equipment knowledge base. The schema keeps only the entities needed for Agent execution decisions and the minimal device semantics needed near protocol generation.

## Layers

### Agent Execution Layer

Default query layer. It answers:

- What process is the user asking for?
- Which step should the Agent run now?
- Which skill should be called?
- What input data is required?
- What output data will be produced?
- Should the Agent stop for user confirmation?
- Which rules constrain this step?

Entities:

- `Process`
- `AgentFlow`
- `TaskStep`
- `DataArtifact`
- `Checkpoint`
- `ExecutionRule`
- `Condition`

### Artifact Semantics Layer

Explains what each file or object means, not only where it is.

Entity:

- `DataArtifact`

Required semantics include format, producer, consumers, user visibility, confirmation requirement, path hints, and key fields or columns.

### Device Semantics Layer

Expanded only when working with step JSON, resource verification, protocol orchestration, or device submission.

Entities:

- `DeviceAction`
- `Resource`
- `Instrument`
- `Property`

## Core Entities

### Process

A user-facing task scenario. A `Process` points the Agent to the correct `AgentFlow`.

Examples:

- FDU experiment target to device task
- FDU resource verification
- FDU protocol orchestration
- FDU device task creation

### AgentFlow

An executable Agent route composed of ordered `TaskStep` nodes.

Important fields:

- `id`
- `name`
- `description`
- `entry_process_id`
- `steps`
- `start_step_id`

### TaskStep

One Agent action. It usually calls a skill, but may also represent inspection, decision, or confirmation.

Important fields:

- `id`
- `name`
- `step_kind`: `skill_call`, `checkpoint`, `decision`, or `inspection`
- `skill_name`
- `input_artifact_ids`
- `output_artifact_ids`
- `requires_user_confirmation_before`
- `requires_user_confirmation_after`
- `failure_policy`
- `agent_should_check`

### DataArtifact

A data object flowing between steps.

Important fields:

- `id`
- `name`
- `format`: `json`, `csv`, `markdown`, `directory`, or `text`
- `producer_step_id`
- `consumer_step_ids`
- `user_visible`
- `must_confirm`
- `path_hint`
- `required_fields`
- `required_columns`
- `agent_meaning`

### Checkpoint

A mandatory user-confirmation point.

Important fields:

- `id`
- `name`
- `after_step_id`
- `shown_artifact_ids`
- `required`
- `resume_step_id`
- `blocking_rule_id`

### ExecutionRule

A hard rule that constrains one or more steps or a whole flow.

Important fields:

- `id`
- `name`
- `scope`
- `content`
- `applies_to_ids`
- `severity`

### Resource

Sample, reagent, consumable, device resource, layout position, or resource snapshot object needed by resource verification and device execution.

### Condition

A precondition or experimental condition that must be checked before a step can advance.

Examples:

- approved recommendations
- approved amount table
- resource verification passed
- supported device actions only
- approved device task creation

### Property

A semantic property used to explain data fields, resources, device actions, conditions, or instruments.

Examples:

- `substance`
- `layout_code`
- `unit_position`
- `add_weight`
- `add_volume`
- `temperature`
- `reaction_duration`
- `resource_availability`

### Instrument

A device module or equipment abstraction that supports one or more `DeviceAction` nodes.

Examples:

- FDU solid dispenser
- FDU liquid handler
- FDU magnetic stirrer
- FDU filter module
- FDU high-filter module

### DeviceAction

A real device action type represented in step JSON or protocol JSON.

Current canonical actions:

| DeviceAction | FDU unit_type | Generator skill |
| --- | --- | --- |
| `device-action:add-solid` | `exp_add_solid` | `fdu-add-solid-json` |
| `device-action:add-liquid` | `exp_pipetting` | `fdu-add-liquid-json` |
| `device-action:reaction-control` | `exp_magnetic_stirrer` | `fdu-reaction-control-json` |
| `device-action:filter` | `exp_filtering_samples` | `fdu-filter-json` |
| `device-action:high-filter` | `exp_high_filtering_samples` | `fdu-high-filter-json` |

## Core Relations

Agent task ontology relations:

- `AgentFlow -startsWith-> TaskStep`
- `TaskStep -nextStep-> TaskStep`
- `TaskStep -requiresInput-> DataArtifact`
- `TaskStep -createsOutput-> DataArtifact`
- `TaskStep -pausesAt-> Checkpoint`
- `TaskStep -requiresResource-> Resource`
- `TaskStep -requiresCondition-> Condition`
- `DataArtifact -hasCondition-> Condition`
- `DataArtifact -containsAction-> DeviceAction`
- `DeviceAction -usesInstrument-> Instrument`
- `Instrument -supportsAction-> DeviceAction`
- `Resource | DeviceAction | Condition | Instrument -hasProperty-> Property`
- `ExecutionRule -appliesTo-> AgentFlow | TaskStep | Checkpoint | DataArtifact`

## Main Agent Flow

Canonical flow:

`agent-flow:fdu-experiment-to-device-task`

Route:

1. `task-step:parse-experiment-request`
2. `task-step:recommend-experiment-conditions`
3. `checkpoint:review-recommendations`
4. `task-step:calculate-reagent-amounts`
5. `checkpoint:review-amounts`
6. `task-step:generate-numbered-steps`
7. `checkpoint:review-numbered-steps`
8. `task-step:write-experiment-plan`
9. `task-step:convert-plan-to-step-json`
10. `task-step:merge-step-json`
11. `task-step:verify-and-fill-resources`
12. `task-step:orchestrate-device-protocol`
13. `checkpoint:approve-device-task-creation`
14. `task-step:create-device-task`
15. Optional: `task-step:monitor-device-task`

## Modeling Rules

- Use `TaskStep` for Agent actions.
- Use `DataArtifact` for data contracts. A path without semantics is not enough.
- User-visible artifacts with `must_confirm=true` must be routed through `Checkpoint`.
- Any step with `requiresCondition` must verify the target `Condition` before running.
- `fdu-device-run` must be blocked by a checkpoint unless the user has explicitly confirmed device task creation.
- Starting device execution is separate from creating a device task and requires an explicit user request.
- `fdu-execution-monitoring` is an optional read-only follow-up after task creation and must not perform any device control action.
- Planning-side artifacts are additionally guarded by `rule:risk-review-after-planning-output`, which uses `fdu-risk-review` after recommendation, amount, and numbered-step artifacts are generated and before the Agent asks the user to confirm them.
- Expand `DeviceAction`, `Instrument`, and `Resource` only at step JSON, resource verification, protocol orchestration, or device submission stages.
