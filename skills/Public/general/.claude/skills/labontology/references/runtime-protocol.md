# LabOntology Runtime Protocol (reference)

Read this only when SKILL.md and the `do_next` field of an output are not enough. Every command runs from the conversation working directory as `python .claude/skills/labontology/scripts/labontology.py <command> --cache-dir labontology_workspace_cache ...`.

## Mission lifecycle

```text
bootstrap -> run [--plan a,b,c] -> act --ask-plan -> (user) resume --answer
          -> act --skill <id> -> waiting_agent -> resume --agent-completed --register-all
          -> waiting_human (step gate: show the result, end the turn) -> (user) resume --answer
          -> act --skill <next> ... -> act --complete
completed -> act --revise "<change>" --redo a,b -> act --skill a -> ... -> act --complete   (same mission)
```

With `--plan`, one plan step runs per turn: after each step that leaves steps open the Runtime waits for the user (`pending_ticket.step_gate`), and `act --skill` for the next step is refused until the user answered. `run --run-through` (only when the user asked for all steps at once) removes these pauses.

`act --revise "<the user's change>" --redo a,b` reopens a finished mission when the user changes a condition of the same task. Only the listed Workers run again (in the original order, one per turn, with step gates); their outputs go to `artifacts/rev<N>/` and replace the artifact ids, while the earlier files stay recorded. `mission.revisions` keeps each change, what was redone, what was kept and `kept_with_changed_inputs` (kept Workers that use a regenerated input: say why they stay valid, or redo them). A new, unrelated goal still gets `run`.

A redone Worker only sees the change if its inputs carry it. `mission.revisions[-1].inputs_from_kept` lists the inputs of redone Workers that come from kept Workers (for example `artifact:parsed-constraints` from constraint-parser): when the change is in such an input (a condition of the user's instruction), run `act --revise` again with that producer in `--redo`; a new `--revise` replaces a revision that is not finished yet. Before registering a redone step, check that its new output contains the change; an output identical to the previous one is refused. `act --complete` is refused until every redo step is done; `act --cancel` during a revision drops only that change (the mission returns to the results from before it, `applied: false`).

`run`, `act`, `resume` and `context` all return the current context. Its important fields: `mission.status`, `mission.artifacts` (id -> path), `plan_progress`, `do_next`, `skills` (candidate Workers with `missing_inputs`), `pending_ticket.question`, `prepared_skill.path`, `worker_cycle`, `retry_candidates`, `artifact_dir`. Outputs are compacted (no snapshots); `context --full` prints everything.

Status values: `awaiting_decision` (choose the next action), `waiting_agent` (a Worker action is issued: do the work), `waiting_human` (a question or an approval is pending), `completed`, `cancelled`, `running` (interrupted: use `reconcile`).

## Commands

| Command | Purpose |
|---|---|
| `bootstrap` | Prepare or reuse the workspace graph (skipped after two runs in 10 minutes). |
| `inspect --skills` | List available Workers (id, short description). |
| `run --goal G [--plan a,b,c [--run-through]] [--input-artifact ID=PATH]... [--new-mission]` | Create a mission. Refused while another mission waits for the user's answer, unless `--new-mission`. |
| `act --skill ID [--retry-of ACTION]` | Issue one Worker action (decision file written by the Runtime). Workers whose `manifest.yaml` sets `requires_confirmation` pause in `waiting_human`. |
| `act --ask "Q"` / `--ask-plan` | Ask the user; `--ask-plan` builds the confirmation question from the mission plan. |
| `act --complete` / `--cancel` | Close the mission (complete is refused while a Worker file is unregistered or a revision step is not redone; `--cancel` during a revision drops only that change). |
| `act --revise "<change>" --redo a,b` | Reopen a finished mission for a change to the same task; redo only those Workers (replaces an unfinished revision). |
| `act --decision-file F` | Advanced: submit a hand-written decision JSON. |
| `resume --answer "<user's exact message>" [--confirm\|--reject]` | Record the user's reply. Approvals (a Worker action waiting for confirmation) need `--confirm` or `--reject`. |
| `resume --agent-completed --register-all --summary S` | Report a finished Worker; registers every unregistered file in `artifact_dir` (declared outputs by name, the rest as extra artifacts; during a revision only `artifacts/rev<N>/`). |
| `resume --agent-failed --summary S` | Report a real failure (error text). Optionally `--provide-artifact ID=PATH` for explicit registration. |
| `reconcile --outcome ... --summary S` | Settle an interrupted (`running`) action from external evidence. |
| `prepare-skill --skill-id ID` | Record a Worker document without acting (`act --skill` does this for you). |
| `describe-skill --skill-id ID`, `missions`, `status`, `context [--full]` | Read-only queries (`status` returns the same short digest as a repeated `context`). |
| `suggest-maintenance`, `maintain-graph --patch-file F --reason R`, `restore-backup` | Reviewed graph maintenance (see below). |

## Rules the Runtime enforces

- A Worker action needs its input artifacts (`missing_inputs` must be empty) and capabilities; otherwise report the missing condition.
- `assessment.impact` is `routine` or `significant`; any `uncertainties`/`authenticity_gaps` pause the mission for the user. `act --skill` writes `routine` with none.
- `complete` is refused while files in `artifact_dir` are unregistered and until a Worker succeeded.
- Retrying a failed read-only Worker needs `--retry-of <failed action>` and stays within the Worker's retry limit (`retry_candidates`).
- An identical `resume` repeated within a minute is refused (`repeat_guard`); `resume` when nothing waits is an error that names the next step.
- One user message answers one question. In FounDryClaw every user message has its own turn id: once an answer of this turn is recorded, a second `resume --answer` in the same turn is refused, and `do_next` says so. A new question (the next step gate) waits for the user's next message: write the reply and end the turn.
- Refusals print only the reason on stderr (exit 2), without the usage text.
- `resume --answer` refuses the Skill-loading text ("Base directory for this skill: ..."): only the user's own message is an answer.
- A declared output whose file has another name is matched by its extension; if it still cannot be matched, the error lists the candidate files and the exact `--provide-artifact <id>=<path>` to use.
- `run --input-artifact parsed_constraints.json=PATH` is also registered under the id a Worker declares (`artifact:parsed-constraints`); `input_ids` shows the mapping.
- A plan with a single step needs no `--ask-plan` confirmation.
- A skipped `bootstrap` lists `active_missions` (recent missions with their status and next step).
- Repeated identical `context` calls return a short digest with the same `do_next`.

## No matching Worker and agent_fallback

`match_found: false` -> tell the user the task has not started and why (`coverage_diagnostic.user_message`). For routine, read-only work you may ask (`act --ask`) whether the Agent may do it directly; only after the user says yes may you submit an `agent_fallback` decision (`--decision-file`, `side_effect_level: read_only`, `assessment.impact: routine`, `assessment.authorization` = the user's approval). The result is recorded as `agent_native`, never as a Worker result. One approval allows one fallback.

## Failures

- `bootstrap` failure: stop and say the workflow library is unavailable. `skipped_workers` / `skipped_duplicates` matter only if they affect the task; never edit a Worker.
- Worker or script failure: report the real error with `--agent-failed`; do not retry silently. If a downstream Worker failed because an upstream file is bad, re-run the upstream Worker (`act --skill upstream`), then retry the downstream one.
- Worker document changed since it was recorded: run `act --skill` again (it records the current document).

## Graph maintenance

`suggest-maintenance` is read-only. `maintain-graph --patch-file <cache-dir>/runs/maintenance-patch.json --reason "<reviewed reason>"` applies only validated low-risk patches and keeps one latest backup; `restore-backup` restores it. Do not modify Worker SKILL.md files, device commands, parameters, approvals or mission history this way.
