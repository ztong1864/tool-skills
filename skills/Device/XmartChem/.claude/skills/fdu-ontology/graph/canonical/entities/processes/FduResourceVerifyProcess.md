# Process: FDU resource verification and backfill

This process is responsible for turning merged step JSON into resource-aware step JSON by using the current resource snapshot as the source of truth. It also answers a read-only query of the workstation's current resources.

It has two modes:

- Verification and backfill (a step of `agent-flow:fdu-experiment-to-device-task`): needs merged step JSON.
- Read-only snapshot query (`agent-flow:fdu-resource-snapshot`): refreshes the snapshot and reports the resource list; needs no step JSON and changes none.

Use verification and backfill when the Agent already has merged step JSON and needs to:

- refresh or load the latest resource snapshot,
- verify resource availability and consistency,
- resolve aliases when the snapshot shows the same chemical under different names,
- backfill concrete resource information into the step JSON,
- produce a verification report for the user or downstream stages.

Use the read-only snapshot query when the user only wants to see what the workstation holds now (refresh the resource snapshot, list resources, count positions), without an experiment.

Relevant steps:

- `task-step:verify-and-fill-resources` (verification and backfill)
- `task-step:refresh-resource-snapshot` (read-only snapshot query)

Required input:

- `artifact:merged-step-json` (verification and backfill only; the read-only query needs none)

Produced artifacts:

- `artifact:resource-snapshot` (both modes; its `producer_step_id` names the verification step, and `task-step:refresh-resource-snapshot` also creates it)
- `artifact:verified-step-json` (verification and backfill only)
- `artifact:resource-verification-report` (verification and backfill only)

Relevant rule:

- `rule:resource-snapshot-is-source-of-truth`

Operational notes:

- The snapshot is not a decorative artifact; it is the reference used to decide whether a resource is available and which name should be used.
- If the verification report still shows missing, conflicting, or unusable resources after alias correction, the Agent must stop and report the issue before protocol orchestration.
- The backfilled `verified-step-json` is the only acceptable input to protocol orchestration.
- The read-only query reports the device's snapshot; if the device interface is unreachable it says so and gives no numbers, unless the user explicitly asks for the local cached snapshot, which must then be labelled as local and not current.
