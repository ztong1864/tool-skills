# Process: FDU experiment plan generation

This process covers the planning branch of the main FDU flow, from user request to a Chinese experiment plan.

Use it when the task is still in the pre-device phase and the Agent needs to:

- parse the user experiment target,
- recommend candidate condition rows,
- calculate actual reagent amounts,
- generate numbered experimental steps,
- write a human-readable Chinese experiment plan.

Relevant steps:

1. `task-step:parse-experiment-request`
2. `task-step:recommend-experiment-conditions`
3. `checkpoint:review-recommendations`
4. `task-step:calculate-reagent-amounts`
5. `checkpoint:review-amounts`
6. `task-step:generate-numbered-steps`
7. `checkpoint:review-numbered-steps`
8. `task-step:write-experiment-plan`

Relevant artifacts and their roles:

- `artifact:user-experiment-request`: the user prompt or experiment target.
- `artifact:reaction-space-table`: optional bounded candidate-space table.
- `artifact:constraint-json`: internal parsed constraints.
- `artifact:recommendation-table`: candidate rows to show and confirm.
- `artifact:amount-table`: executable amounts table to confirm before step generation.
- `artifact:numbered-experiment-steps`: numbered wet-lab steps for user review.
- `artifact:experiment-plan-md`: final human-readable plan before step JSON conversion.

Important boundaries:

- `constraint-json` stays internal unless the user explicitly asks for it.
- `recommendation-table`, `amount-table`, and `numbered-experiment-steps` are confirmable artifacts.
- The Agent must stop at every listed checkpoint before continuing.
- This process ends before any step JSON, resource verification, or device protocol work.

Cross-cutting guard:

- `rule:risk-review-after-planning-output` applies after recommendation, amount calculation, and numbered-step generation produce their planning artifacts, before the corresponding user confirmation checkpoints.
- The Agent should use `fdu-risk-review` for safety risk, feasibility, device capability, and action boundary checks as part of the planning branch, not as a separate main route.
