# Process: FDU risk review

This process is a cross-cutting guard, not a separate planning branch.

Use it to review the planning artifacts produced by planning-side steps before the corresponding user confirmation checkpoints:

1. `task-step:recommend-experiment-conditions`
2. `task-step:calculate-reagent-amounts`
3. `task-step:generate-numbered-steps`

What it checks:

- reaction feasibility,
- safety risk,
- device capability,
- action boundary,
- whether the current step should stop and ask for human adjustment.

Relevant skill:

- `fdu-risk-review`

Relevant rule:

- `rule:risk-review-after-planning-output`

Operational notes:

- Risk review is a guard between planning artifact generation and user confirmation, not a new main route.
- It should be visible in step-level checks and execution rules, and executed through `fdu-risk-review` after those guarded steps produce their artifacts.
- The review result is part of planning safety, but it should not replace the existing user checkpoints for recommendation, amounts, numbered steps, or the experiment plan.
