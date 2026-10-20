# LabOntology Runtime Protocol (reference)

Read this only when SKILL.md and the `do_next` field of an output are not enough. Every command runs from the conversation working directory as `python .claude/skills/labontology/scripts/labontology.py <command> --cache-dir labontology_workspace_cache ...`.

## Mission lifecycle

```text
run [--plan a,b,c | --flow F --until S] -> act --ask-plan            (end the turn)
(user replies) -> act --skill <id> -> waiting_agent -> resume --agent-completed --register-all
          -> waiting_human (step pause: show the result, end the turn)
(user replies) -> act --skill <next> ... -> act --complete
completed -> act --revise "<change>" --redo a,b -> act --skill a -> ... -> act --complete   (same mission)
```

`run` and `inspect` prepare the workflow library themselves (the same quick check as `bootstrap`); `bootstrap` is only needed to initialise LabOntology on request.

**The user's reply.** When the mission waits for the user's answer to a question (plan confirmation, a step pause, `act --ask`), the user's next message is the answer. In that turn run the next command from `do_next` (usually `act --skill <next step>`, or `act --cancel` to stop): the Runtime records the message as the answer before it acts. FounDryClaw passes each message's turn id (`FOUNDRYCLAW_TURN_ID`) and text (`FOUNDRYCLAW_USER_MESSAGE`). In the turn that asked the question, `act` is refused ("the user has not answered this question yet"): show the result, relay the question and end the turn. Without a turn id (CLI, offline) record the reply first with `resume --answer "<the user's exact message>"`. An approval (a Skill whose manifest sets `requires_confirmation`, or a significant-impact decision) is never taken from the turn: it needs `resume --confirm` or `--reject` with the user's reply.

With `--plan`, one plan step runs per turn: after each step that leaves steps open the Runtime waits for the user (`pending_ticket.step_gate`), and the next step runs once the user has replied. `run --run-through` (only when the user asked for all steps at once) removes these pauses.

With `--flow <id> [--until <stop>]` the plan comes from an experiment flow the device's ontology Skill declares (`experiment_flows.yaml`, see references/experiment-flows.md; `inspect --skills` lists them under `experiment_flows`). Each step contributes its Skill and then its review Skill, so a Skill can appear more than once (`plan_progress` shows a review with its `label`). The Runtime pauses only after the steps marked with a pause (`plan_progress[].pause`), not after every step. When the plan reaches its stop, `do_next` gives the flow's question there (for example whether to create the device task) and the next step's command for when the user agrees. A revision of a flow mission redoes the listed steps in flow order, each with its review and pause. A review that does not pass (reported with `--agent-failed` and its findings) makes the mission ask the user what to change (`pending_ticket.review_failed`); after the reply, `do_next` reruns the reviewed Skill with the change and then the review. The review is not retried on the same result. A reply that only answers the review's question (confirms a fact, chooses an option) runs the review again with the answer instead (`act --skill <review>`).

Before the plan is finished (for example at a step pause, when the user asks to redo the step that just finished), `act --revise "<the user's change>" --redo a` goes back to the earliest listed step that is done. That step and every later step already done open again in the same mission (a flow review comes with the step it reviews), and the plan continues from there with its pauses. At a pause the user's message is recorded as the reply. The earlier results stay recorded until the new outputs replace them. Write those under a new file name in `artifact_dir` (for example with `_v2`); an output identical to the earlier one is refused. Steps not done yet and review steps cannot be listed.

`act --revise "<the user's change>" --redo a,b` reopens a finished mission when the user changes a condition of the same task. Only the listed Skills run again (in the original order, one per turn, with step pauses); their outputs go to `artifacts/rev<N>/` and replace the artifact ids, while the earlier files stay recorded. `mission.revisions` keeps each change, what was redone, what was kept and `kept_with_changed_inputs` (kept Skills that use a regenerated input: say why they stay valid, or redo them). A new, unrelated goal still gets `run`.

A redone Skill only sees the change if its inputs carry it. `mission.revisions[-1].inputs_from_kept` lists the inputs of redone Skills that come from kept Skills (for example `artifact:parsed-constraints` from constraint-parser): when the change is in such an input (a condition of the user's instruction), run `act --revise` again with that producer in `--redo`; a new `--revise` replaces a revision that is not finished yet. Before registering a redone step, check that its new output contains the change; an output identical to the previous one is refused. `act --complete` is refused until every redo step is done; `act --cancel` during a revision drops only that change (the mission returns to the results from before it, `applied: false`).

`run`, `act`, `resume` and `context` all return the current context. Its important fields: `mission.status`, `mission.artifacts` (id -> path), `plan_progress`, `do_next`, `skills` (candidate Skills with `missing_inputs`), `coverage_diagnostic`, `pending_ticket.question`, `prepared_skill.path`, `execution_cycle`, `retry_candidates`, `artifact_dir`, and `notice` (a command that changed nothing says so). Outputs are compacted (no snapshots); `context --full` prints everything.

Status values: `awaiting_decision` (choose the next action), `waiting_agent` (a Skill action is issued: do the work), `waiting_human` (a question or an approval is pending), `completed`, `cancelled`, `running` (interrupted: use `reconcile`).

`coverage_diagnostic.status`: `candidate_found` (Skills matched the goal by name, description, declared contract or document; the best five are in `skills`), `candidate_review` (nothing matched the goal's words: `skills` lists every registered Skill with its `document`; read the ones that could fit before deciding), `no_registered_skill` (no usable Skill is registered).

## Commands

| Command | Purpose |
|---|---|
| `inspect --skills` | List available Skills (id, short description) and the declared experiment flows (`experiment_flows`: steps, pauses ⏸, stops). Prepares the library when needed. |
| `run --goal G [--plan a,b,c [--run-through]] [--input-artifact ID=PATH]... [--new-mission]` | Create a mission (prepares the library when needed). A `--plan` made only of steps of a declared experiment flow gets the flow's reviews and pauses, in the flow's order. Refused while another mission of this conversation waits for the user's answer, unless `--new-mission`. |
| `run --goal G --flow ID [--until STOP]` | Create a mission whose plan is the experiment flow up to STOP (default: the flow's `default_stop`). Not together with `--plan`. |
| `act --skill ID [--retry-of ACTION] [--input ID=PATH]` | Issue one Skill action (decision file written by the Runtime). Records the turn's message first when a question waits for it. Skills whose `manifest.yaml` sets `requires_confirmation` pause in `waiting_human`. The same act for the Skill already issued changes nothing and says so in `notice`. |
| `act --ask "Q"` / `--ask-plan` | Ask the user; `--ask-plan` builds the confirmation question from the mission plan. |
| `act --complete` / `--cancel` | Close the mission (complete is refused while a Skill file is unregistered or a revision step is not redone; `--cancel` during a revision drops only that change). |
| `act --revise "<change>" --redo a,b` | Reopen a finished mission for a change to the same task; redo only those Skills (replaces an unfinished revision). On a plan not finished yet: go back to the earliest listed step that is done (it and the later done steps run again). |
| `act --decision-file F` | Advanced: submit a hand-written decision JSON. |
| `resume --confirm\|--reject --answer "<user's exact reply>"` | Decide an approval. |
| `resume --answer "<user's exact message>"` | Record a reply explicitly (needed only without a turn id). Sent when nothing waits for an answer, it changes nothing and says so in `notice`. |
| `resume --agent-completed --register-all --summary S` | Report a finished Skill; registers every unregistered file in `artifact_dir` (declared outputs by name, the rest as extra artifacts; during a revision only `artifacts/rev<N>/`). |
| `resume --agent-failed --summary S` | Report a real failure (error text). Optionally `--provide-artifact ID=PATH` for explicit registration. |
| `reconcile --outcome ... --summary S` | Settle an interrupted (`running`) action from external evidence. |
| `prepare-skill --skill-id ID` | Record a Skill document without acting (`act --skill` does this for you). |
| `describe-skill --skill-id ID`, `missions`, `status`, `context [--full]` | Read-only queries (`status` returns the same short digest as a repeated `context`). |
| `bootstrap` | Prepare or reuse the workspace graph explicitly (skipped after two runs in 10 minutes). |
| `suggest-maintenance`, `maintain-graph --patch-file F --reason R`, `restore-backup` | Reviewed graph maintenance (see below). |

## Rules the Runtime enforces

- A Skill action needs its input artifacts (`missing_inputs` must be empty) and capabilities; otherwise report the missing condition.
- `assessment.impact` is `routine` or `significant`; any `uncertainties`/`authenticity_gaps` pause the mission for the user. `act --skill` writes `routine` with none.
- `complete` is refused while files in `artifact_dir` are unregistered and until a Skill succeeded.
- Retrying a failed read-only Skill needs `--retry-of <failed action>` and stays within the Skill's retry limit (`retry_candidates`). A failed review of an experiment flow is not a retry candidate: the reviewed Skill runs again first.
- `resume --register-all` refuses while files of the pending step sit outside its folder, listing them: in a folder named like the mission's with the id typed wrong (`runs/<id cut short>/...`), or in an `artifacts/rev<N>/` folder no revision uses. Move them into `artifact_dir`, under a new name if one of that name is there, then resume again.
- A `resume` that comes within a few seconds of its `act` (the same batch of tool calls) is refused: the work cannot have been done yet. Run resume on its own after the work.
- `act --cancel` is refused once every plan step is done: end the mission with `act --complete` (the results stay).
- `act --ask-plan` is refused once the plan is confirmed or its steps have started.
- A review verdict (`verdict: ...`) sent as the result of a step that is not a review is refused.
- A review step of a flow reports its own verdict: `--provide-artifact` of the reviewed step's files, or a `--summary` identical to the reviewed step's, is refused.
- A step pause and a review that did not pass put the step's `--summary` into the question to the user, so write it in Chinese. The question leaves out a review's `stage:` and `checked:` parts and shows `verdict:`, `findings:` and `required_action:` as 结论, 发现 and 需要的处理.
- One user message answers one question, asked before it: a question asked in this turn, or a second question after this turn's message already answered one, waits for the user's next message (`act` and `resume --answer` are refused with "the user has not answered this question yet"; FounDryClaw ends the turn with the question).
- The very same `resume` sent three times within a minute is refused (`repeat_guard`).
- Refusals print only the reason on stderr (exit 2), without the usage text.
- `resume --answer` refuses the Skill-loading text ("Base directory for this skill: ..."): only the user's own message is an answer.
- A declared output whose file has another name is matched by its extension; if it still cannot be matched, the error lists the candidate files and the exact `--provide-artifact <id>=<path>` to use.
- `run --input-artifact parsed_constraints.json=PATH` is also registered under the id a Skill declares (`artifact:parsed-constraints`); `input_ids` shows the mapping.
- A plan with a single step needs no `--ask-plan` confirmation.
- A skipped `bootstrap` lists `active_missions` (recent missions with their status and next step).
- Repeated identical `context` calls return a short digest with the same `do_next`.

## No matching Skill and agent_fallback

`coverage_diagnostic.status` `candidate_review`: read the documents of the listed Skills that could fit before deciding that none applies. If none fits (also when some Skills matched only loosely, `candidate_found`), or the status is `no_registered_skill`, tell the user the task has not started and why (`coverage_diagnostic.user_message`). For routine, read-only work you may ask (`act --ask`) whether the Agent may do it directly. That question approves the fallback only when it is asked before any Skill action of the mission and the mission has no plan (a plan confirmation or step pause never does); only after the user says yes may you submit an `agent_fallback` decision (`--decision-file`, `side_effect_level: read_only`, `assessment.impact: routine`, `assessment.authorization` = the user's approval). The result is recorded as `agent_native`, never as a Skill result. One approval allows one fallback.

## Failures

- Library preparation failure (`run`, `inspect` or `bootstrap`): stop and say the workflow library is unavailable. `skipped_skills` / `skipped_duplicates` matter only if they affect the task; never edit a Skill.
- Skill or script failure: report the real error with `--agent-failed`; do not retry silently. If a downstream Skill failed because an upstream file is bad, re-run the upstream Skill (`act --skill upstream`), then retry the downstream one.
- Skill document changed since it was recorded: run `act --skill` again (it records the current document).

## Graph maintenance

`suggest-maintenance` is read-only. `maintain-graph --patch-file <cache-dir>/runs/maintenance-patch.json --reason "<reviewed reason>"` applies only validated low-risk patches and keeps one latest backup; `restore-backup` restores it. Do not modify Skill SKILL.md files, device commands, parameters, approvals or mission history this way.
