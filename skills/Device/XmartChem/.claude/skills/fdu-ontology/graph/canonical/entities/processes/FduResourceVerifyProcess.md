# Process: FDU resource verification and backfill

This process is responsible for turning merged step JSON into resource-aware step JSON by using the current resource snapshot as the source of truth.

Use it when the Agent already has merged step JSON and needs to:

- refresh or load the latest resource snapshot,
- verify resource availability and consistency,
- resolve aliases when the snapshot shows the same chemical under different names,
- backfill concrete resource information into the step JSON,
- produce a verification report for the user or downstream stages.

Relevant step:

- `task-step:verify-and-fill-resources`

Required input:

- `artifact:merged-step-json`

Produced artifacts:

- `artifact:resource-snapshot`
- `artifact:verified-step-json`
- `artifact:resource-verification-report`

Relevant rule:

- `rule:resource-snapshot-is-source-of-truth`

Operational notes:

- The snapshot is not a decorative artifact; it is the reference used to decide whether a resource is available and which name should be used.
- If the verification report still shows missing, conflicting, or unusable resources after alias correction, the Agent must stop and report the issue before protocol orchestration.
- The backfilled `verified-step-json` is the only acceptable input to protocol orchestration.
