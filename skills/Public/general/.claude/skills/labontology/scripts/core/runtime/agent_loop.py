"""One-action execution loop directed by the host Agent, not an embedded LLM."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ExecutionPolicySpec, MissionState, SkillSpec
from .state_store import StateStore
from .text import search_terms


def _artifact_paths(artifacts: dict[str, str]) -> dict[str, str]:
    result = {}
    for name, value in artifacts.items():
        path = Path(value).expanduser().resolve()
        if not path.exists():
            raise ValueError(f"Artifact does not exist: {name}={path}")
        result[name] = str(path)
    return result


def _materialize_artifacts(artifacts: dict[str, str], artifact_dir: Path) -> dict[str, str]:
    """Copy Agent-provided outputs into the mission-owned artifact directory."""
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir = artifact_dir.resolve()
    result: dict[str, str] = {}
    for artifact_id, source_value in artifacts.items():
        source = Path(source_value).resolve()
        if source == artifact_dir or artifact_dir in source.parents:
            # Already written into the mission-owned directory: record it in place.
            result[artifact_id] = str(source)
            continue
        if source.is_dir() and source in artifact_dir.parents:
            raise ValueError(f"Artifact folder contains the mission directory; provide the output itself: {artifact_id}")
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", artifact_id.split(":", 1)[-1]).strip("._") or "artifact"
        destination = artifact_dir / f"{safe_id}__{source.name}"
        if source != destination.resolve():
            if source.is_dir():
                shutil.copytree(source, destination, dirs_exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
        result[artifact_id] = str(destination)
    return result


def _artifact_records(artifacts: dict[str, str], action_id: str) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for artifact_id, value in artifacts.items():
        path = Path(value).resolve()
        record: dict[str, Any] = {
            "artifact_id": artifact_id,
            "path": str(path),
            "action_id": action_id,
            "valid": path.exists(),
        }
        if path.is_file():
            record["size_bytes"] = path.stat().st_size
            record["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif path.is_dir():
            record["size_bytes"] = sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
        records[artifact_id] = record
    return records


def _action_number(action_id: Any) -> int:
    match = re.fullmatch(r"action:(\d+)", str(action_id or ""))
    return int(match.group(1)) if match else 0


_SUCCEEDED = {"succeeded", "reconciled_succeeded"}


def _record_outputs(state: MissionState, outputs: dict[str, str], action_id: str) -> None:
    """Record new outputs; an output that replaces an earlier file under the same id (a revision) keeps the
    earlier file's record under `<id>@<earlier action>`, so it stays a known, tracked artifact."""
    for artifact_id, path in outputs.items():
        earlier = state.artifact_records.get(artifact_id)
        if earlier and earlier.get("path") and Path(earlier["path"]).resolve() != Path(path).resolve():
            state.artifact_records[f"{artifact_id}@{earlier.get('action_id') or 'earlier'}"] = {**earlier, "superseded": True}
    state.artifact_records.update(_artifact_records(outputs, action_id))


def _canonical_outputs(declared: Any, outputs: dict[str, str]) -> dict[str, str]:
    """Accept a declared output id with or without its `artifact:` prefix
    (`parsed-constraints` for `artifact:parsed-constraints`)."""
    result = dict(outputs)
    for name in declared:
        bare = name.split(":", 1)[-1]
        if name not in result and bare in result:
            result[name] = result.pop(bare)
    return result


def _file_digest(path: str) -> str | None:
    target = Path(path)
    return hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else None


def _untracked_artifacts(state: MissionState, artifact_dir: Path) -> list[str]:
    if not artifact_dir.is_dir():
        return []
    artifact_dir = artifact_dir.resolve()
    known = {Path(value).resolve() for value in state.artifacts.values()}
    known.update(Path(record["path"]).resolve() for record in state.artifact_records.values()
                 if isinstance(record, dict) and record.get("path"))
    # A recorded output folder inside the mission directory covers its files.
    known_folders = [path for path in known
                     if path.is_dir() and (path == artifact_dir or artifact_dir in path.parents)]
    return sorted(str(path) for path in (item.resolve() for item in artifact_dir.rglob("*"))
                  if path.is_file() and path not in known
                  and not any(folder in path.parents for folder in known_folders))


class AgentRuntime:
    def __init__(
        self, skills: dict[str, SkillSpec], store: StateStore,
        *, available_capabilities: set[str] | None = None,
        policies: list[ExecutionPolicySpec] | None = None,
        skill_knowledge: dict[str, dict[str, Any]] | None = None,
        workflow_references: list[dict[str, Any]] | None = None,
        suite_id: str | None = None,
    ):
        self.skills, self.store = skills, store
        self.capabilities = set(available_capabilities or [])
        self.policies = policies or []
        self.knowledge = skill_knowledge or {}
        self.workflows = workflow_references or []
        self.suite_id = suite_id

    def _feedback(self, event: str, skill_id: str | None, details: dict[str, Any]) -> None:
        self.store.feedback.append(event, self.store.mission_id, skill_id, details)

    def _load(self) -> MissionState:
        state = self.store.load()
        if state.mode != "agent":
            raise ValueError("Mission is not an Agent mission; create a new Agent mission")
        self.capabilities.update(state.available_capabilities)
        state.available_capabilities = sorted(self.capabilities)
        if self.suite_id:
            if state.suite_id and state.suite_id != self.suite_id:
                raise ValueError("Mission belongs to a different SkillSuite")
            if not state.suite_id:
                state.suite_id = self.suite_id
                self.store.save(state)
        return state

    def start(self, goal: str, *, constraints: list[str] | None = None,
              artifacts: dict[str, str] | None = None,
              start_skill: str | None = None, plan: list[str] | None = None,
              run_through: bool = False) -> MissionState:
        if self.store.state_path.exists():
            state = self._load()
            if goal and goal != state.goal:
                raise ValueError("Use a new mission ID for a different goal")
            return state
        if not goal.strip():
            raise ValueError("A mission goal is required")
        if start_skill and start_skill not in self.skills:
            raise ValueError(f"Unknown start Skill: {start_skill}")
        plan = [item.strip() for item in (plan or []) if item and item.strip()]
        unknown = [item for item in plan if item not in self.skills]
        if unknown:
            raise ValueError(f"Unknown Worker in --plan: {unknown}. Valid ids: {sorted(self.skills)}")
        state = MissionState(self.store.mission_id, status="awaiting_decision", mode="agent",
                             goal=goal, constraints=list(constraints or []), plan=plan, run_through=run_through,
                             available_capabilities=sorted(self.capabilities),
                             artifacts=_artifact_paths(artifacts or {}), start_skill=start_skill,
                             suite_id=self.suite_id)
        self.store.save(state)
        self.store.event("mission_created", {"goal": goal, "mode": "agent"})
        return state

    def _uncontracted(self, skill_id: str) -> bool:
        """An imported Worker without an instruction document cannot pass the read gate."""
        knowledge = self.knowledge.get(skill_id, {})
        return knowledge.get("requires_instruction") is True and not isinstance(knowledge.get("instruction_source"), dict)

    def _candidate_cards(self, state: MissionState) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        cards: list[tuple[int, dict[str, Any]]] = []
        excluded_skills: list[dict[str, str]] = []
        selectable: list[tuple[SkillSpec, dict[str, Any], set[str]]] = []
        for skill in self.skills.values():
            if self._uncontracted(skill.id):
                excluded_skills.append({"id": skill.id, "reason": "no instruction document (SKILL.md)"})
                continue
            knowledge = self.knowledge.get(skill.id, {})
            searchable = " ".join([
                skill.id, str(knowledge.get("name") or skill.id), str(knowledge.get("description") or ""),
                *map(str, skill.goal_types), *map(str, skill.triggers),
                *map(str, skill.required_capabilities), *map(str, skill.input_artifacts),
            ]).lower()
            selectable.append((skill, knowledge, search_terms(searchable)))
        goal_terms = search_terms(state.goal)
        if len(selectable) >= 3:
            # A term every Worker shares (for example "experiment" in a lab
            # library) cannot tell Workers apart, so it does not count as a match.
            goal_terms -= set.intersection(*(terms for _, _, terms in selectable))
        for skill, knowledge, searchable_terms in selectable:
            name = str(knowledge.get("name") or skill.id)
            description = str(knowledge.get("description") or "")
            score = sum(term in searchable_terms for term in goal_terms)
            card = {
                "id": skill.id,
                "name": name,
                "description": description,
                "suite_id": knowledge.get("suite_id"),
                "inputs": list(skill.input_artifacts),
                "required_capabilities": list(skill.required_capabilities),
                "side_effect_level": skill.side_effect_level,
                "missing_inputs": [artifact for artifact in skill.input_artifacts if artifact not in state.artifacts],
                "missing_capabilities": sorted(set(skill.required_capabilities) - self.capabilities),
                "match_score": score,
                "eligible": True,
            }
            if skill.optional_entrypoints or skill.optional_command:
                card["optional_script"] = {
                    "entrypoints": list(skill.optional_entrypoints),
                    "script_command": list(skill.optional_command),
                }
            cards.append((score, card))
        matched_cards = [
            item for item in cards
            if item[0] > 0
            or item[1]["id"] == state.start_skill
            or (item[1]["inputs"] and not item[1]["missing_inputs"])
        ]
        candidates = [card for _, card in sorted(matched_cards, key=lambda item: (-item[0], item[1]["id"]))[:5]]
        return candidates, excluded_skills

    def _step_executions(self, state: MissionState, skill_id: str) -> list[dict[str, Any]]:
        """Executions of one Worker in the current plan round (after the latest revision), oldest first."""
        return [state.skill_executions[key] for key in sorted(state.skill_executions, key=_action_number)
                if state.skill_executions[key].get("skill_id") == skill_id and _action_number(key) > state.plan_base]

    def _step_done(self, state: MissionState, skill_id: str) -> bool:
        return any(item.get("status") in _SUCCEEDED for item in self._step_executions(state, skill_id))

    def _artifact_dir(self, state: MissionState) -> Path:
        """Where the current round writes: artifacts/, or artifacts/rev<N>/ during a revision (earlier outputs stay)."""
        base = self.store.run_dir / "artifacts"
        return base / f"rev{len(state.revisions)}" if state.revisions else base

    def _open_revision(self, state: MissionState) -> dict[str, Any] | None:
        """The latest revision while it is still being worked on (not yet completed, dropped or replaced)."""
        if state.revisions and "applied" not in state.revisions[-1] and state.status not in {"completed", "cancelled"}:
            return state.revisions[-1]
        return None

    def revise(self, change: str, redo: list[str]) -> MissionState:
        """Reopen a finished mission for a change the user asked for and redo only the listed Workers.

        Results of the other Workers stay recorded and valid. The redone Workers write into
        artifacts/rev<N>/, so the earlier outputs are kept; their new outputs replace the artifact ids."""
        state = self._load()
        change = change.strip()
        if not change:
            raise ValueError('--revise needs the user\'s change, for example --revise "只能室温反应"')
        redo = list(dict.fromkeys(item.strip() for item in redo if item and item.strip()))
        if not redo:
            raise ValueError("--redo needs the Worker ids to run again, for example --redo constraint-parser,experiment-step-generator")
        unknown = [item for item in redo if item not in self.skills]
        if unknown:
            raise ValueError(f"Unknown Worker in --redo: {unknown}. Valid ids: {sorted(self.skills)}")
        finished = state.status == "completed" or (
            state.status == "awaiting_decision" and bool(state.plan)
            and all(self._step_done(state, step) for step in state.plan))
        unfinished = self._open_revision(state) if not finished and state.status == "awaiting_decision" else None
        if not finished and not unfinished:
            raise ValueError(f"Only a finished mission can be revised; this one is {state.status}. Finish or cancel the "
                             "current step first (see do_next).")
        if unfinished is not None:
            # A new --revise while the previous one is unfinished replaces it: back to the results before it.
            unfinished.update({"applied": False, "replaced_by": len(state.revisions) + 1})
            state.artifacts = dict(unfinished.get("artifacts_before") or state.artifacts)
        elif self._open_revision(state) is not None:
            state.revisions[-1]["applied"] = True  # all its steps were done: its results are the base now
        done_order: list[str] = []
        for key in sorted(state.skill_executions, key=_action_number):
            item = state.skill_executions[key]
            if item.get("status") in _SUCCEEDED and item.get("skill_id") and item["skill_id"] not in done_order:
                done_order.append(item["skill_id"])
        position = {skill_id: index for index, skill_id in enumerate(done_order)}
        redo = sorted(redo, key=lambda skill_id: (position.get(skill_id, len(position)), redo.index(skill_id)))
        kept = [skill_id for skill_id in done_order if skill_id not in redo]
        regenerated = {output for skill_id in redo for output in self.skills[skill_id].outputs}
        kept_changed = [skill_id for skill_id in kept
                        if skill_id in self.skills and set(self.skills[skill_id].input_artifacts) & regenerated]
        # A redone Worker whose input comes from a kept Worker gets the old file again: a change that lives in
        # that input (for example a condition of the instruction) needs its producer redone too.
        producers = {output: skill_id for skill_id in kept if skill_id in self.skills
                     for output in self.skills[skill_id].outputs}
        inputs_from_kept = {}
        for skill_id in redo:
            found = {artifact: producers[artifact] for artifact in self.skills[skill_id].input_artifacts
                     if artifact in producers}
            if found:
                inputs_from_kept[skill_id] = found
        number = len(state.revisions) + 1
        record = {"number": number, "change": change, "redo": redo, "kept": kept,
                  "kept_with_changed_inputs": kept_changed, "inputs_from_kept": inputs_from_kept,
                  "started_after": len(state.decisions), "previous_status": state.status,
                  "artifacts_before": dict(state.artifacts), "at": datetime.now(timezone.utc).isoformat()}
        if unfinished is not None:
            record["replaces"] = unfinished["number"]
        state.revisions.append(record)
        state.plan = redo
        state.plan_base = len(state.decisions)
        state.status, state.supervisor_status, state.block_reason = "awaiting_decision", "needs_action", None
        state.replan_required = False
        state.pending_action = state.pending_ticket = None
        state.observations.append({"action_id": f"revision:{number}", "status": "revision_requested",
                                   "summary": change, "redo": redo, "kept": kept})
        (self.store.run_dir / "artifacts" / f"rev{number}").mkdir(parents=True, exist_ok=True)
        self.store.save(state)
        self.store.event("mission_revised", record)
        return state

    def _previous_outputs(self, state: MissionState, skill_id: str) -> list[str]:
        """Output paths of this Worker's latest success before the current round."""
        for key in sorted(state.skill_executions, key=_action_number, reverse=True):
            item = state.skill_executions[key]
            if (item.get("skill_id") == skill_id and item.get("status") in _SUCCEEDED
                    and _action_number(key) <= state.plan_base):
                return [str(path) for path in (item.get("outputs") or {}).values()]
        return []

    def _plan_progress(self, state: MissionState) -> list[dict[str, Any]]:
        """Per plan step: done / failed / waiting / next / pending, from the recorded executions."""
        pending_skill = (state.pending_action or {}).get("skill_id")
        progress: list[dict[str, Any]] = []
        next_marked = False
        for skill_id in state.plan:
            executions = self._step_executions(state, skill_id)
            if self._step_done(state, skill_id):
                status = "done"
            elif pending_skill == skill_id and state.status in {"waiting_agent", "waiting_human"}:
                status = "waiting"
                next_marked = True
            elif executions and executions[-1].get("status") in {"failed", "timed_out", "reconciled_failed"}:
                status = "failed"
                next_marked = True
            elif not next_marked:
                status = "next"
                next_marked = True
            else:
                status = "pending"
            description = str(self.knowledge.get(skill_id, {}).get("description") or "")
            progress.append({"skill_id": skill_id, "status": status, "description": description[:60]})
        return progress

    def _cache_arg(self) -> str:
        cache = self.store.run_dir.parent.parent
        return cache.name if cache.name == "labontology_workspace_cache" else str(cache)

    @staticmethod
    def _answered_this_turn(state: MissionState) -> bool:
        """True when the user's message of this FounDryClaw turn already answered a question of this mission."""
        turn = os.environ.get("FOUNDRYCLAW_TURN_ID", "").strip()
        return bool(turn) and any(item.get("turn") == turn for item in state.observations
                                  if item.get("status") in {"human_answer", "human_approved", "rejected"})

    def _do_next(self, state: MissionState, candidates: list[dict[str, Any]],
                 retry_candidates: list[dict[str, Any]], progress: list[dict[str, Any]]) -> list[str]:
        """Exact next commands for the host Agent, filled in from the mission state."""
        lines = self._do_next_lines(state, candidates, retry_candidates, progress)
        if not self._answered_this_turn(state):
            return lines
        # One user message answers one question; a model that re-sends it with every command loops on refusals.
        if state.status == "waiting_human":
            return ["The user's message in this turn already answered an earlier question and is recorded. This new "
                    "question waits for the user's next message: your turn ends with your written reply. Do not run "
                    "resume (it would be refused) or start another step; reading the output files below is fine.",
                    *lines]
        if state.status in {"waiting_agent", "awaiting_decision", "running"}:
            return ["The user's message in this turn is already recorded: do not run `resume --answer` again in this "
                    "turn (it would be refused).", *lines]
        return lines

    def _do_next_lines(self, state: MissionState, candidates: list[dict[str, Any]],
                       retry_candidates: list[dict[str, Any]], progress: list[dict[str, Any]]) -> list[str]:
        script = "python .claude/skills/labontology/scripts/labontology.py"
        base = f"--cache-dir {self._cache_arg()} --mission-id {state.mission_id}"
        pending = state.pending_action or {}
        skill_text = ("The user's reply is the next message the user types. Text that begins with 'Base directory for "
                      "this skill' is the Skill document, not a reply: never pass it to resume.")
        if state.status == "cancelled":
            return ["Mission is cancelled. Tell the user and end the turn; a new goal gets a new mission (`run`)."]
        if state.status == "completed":
            lines = [
                "Mission is completed. Answer the user now from the recorded result: read the files in "
                "`mission.artifacts` you need (each at most once), present the key results as a short list or table "
                "(never paste raw JSON or a whole file), and end with one useful next step (for example whether to "
                "submit to the device). Do not run bootstrap or context again.",
                "If the user's message changes a condition of THIS task (temperature, amount, a material ...), do not "
                f"create a new mission: run {script} act {base} --revise \"<the user's change>\" --redo <ids of the "
                "Workers whose results depend on the change>. The --revise text is only the change itself (e.g. "
                "'反应温度改为 100 ℃'), not instructions for yourself. Only an unrelated new goal gets `run`.",
                "Nothing is running, so there is nothing to cancel: if the user wants to stop, say the task is already "
                "finished and its results stay. To undo a change, revise it back to the earlier value.",
            ]
            last = state.revisions[-1] if state.revisions else None
            if last and last.get("applied") is False:
                lines.insert(0, f"Revision {last['number']} (the user's change: {last['change']}) was NOT applied"
                             + (f": {last['dropped_reason']}" if last.get("dropped_reason") else "")
                             + ". Tell the user so in one sentence: the results are the ones from before that change.")
            return lines
        if state.status == "running":
            return [f"{script} reconcile {base} --outcome <not_started|succeeded|failed|unknown> --summary \"<evidence>\""]
        if state.status == "waiting_human":
            question = (state.pending_ticket or {}).get("question") or state.block_reason or ""
            approval = pending.get("kind") == "skill"
            flags = "--confirm or --reject" if approval else "(no extra flag)"
            if pending.get("step_gate"):
                files = ", ".join(str(path) for path in (pending.get("completed_outputs") or {}).values())
                return [
                    "Show the user the result of the step that just finished, then stop. Read these output files "
                    f"(each once) and present the key results, not just 'done': {files}",
                    "State in one sentence any limitation the step reported (for example that no literature was "
                    "available); the step is recorded as done, so do not tell the user to restart or redo it.",
                    f"Then relay this question and end the turn - do NOT start the next step yourself: {question}",
                    f"In the user's NEXT message, run once: {script} resume {base} --answer \"<the user's exact message>\" (no extra flag)",
                    skill_text,
                ]
            return [
                f"Relay this to the user and end the turn: {question}",
                f"In the user's NEXT message, run once: {script} resume {base} --answer \"<the user's exact message>\" {flags}",
                skill_text,
            ]
        if state.status == "waiting_agent":
            doc = (state.prepared_skill or {}).get("path") or "the prepared SKILL.md"
            steps = [f"Read {doc} and do the Worker's work (run its script if it declares one; write every output "
                     f"file into {self._artifact_dir(state)})."]
            revision = self._open_revision(state)
            if revision and pending.get("skill_id") in revision.get("redo", []):
                previous = self._previous_outputs(state, pending["skill_id"])
                from_kept = (revision.get("inputs_from_kept") or {}).get(pending["skill_id"]) or {}
                steps.append(
                    f"Revision {revision['number']}: the user changed: {revision['change']}. Run this Worker again "
                    "with that change in its inputs: a Worker that reads the user's instruction gets the original "
                    "instruction with the changed value rewritten in place (for example '…80 ℃ 反应 12 小时' becomes "
                    "'…100 ℃ 反应 12 小时'; only when a value cannot be replaced cleanly, append '；修改：<the change>'); "
                    "a Worker that reads an earlier step's file uses the file in `mission.artifacts`. Rerunning on "
                    "unchanged inputs repeats the old result."
                    + (f" Its previous output: {', '.join(previous)}." if previous else "")
                    + (f" Its input {', '.join(from_kept)} comes from kept {', '.join(dict.fromkeys(from_kept.values()))}"
                       ": if the change is in that input, this rerun cannot apply it - report it failed." if from_kept else ""))
                steps.append(
                    "Before resume, read the new output and check that the change is really in it: in the fields the "
                    "Worker records, or, for a value the Worker has no field for (e.g. a temperature in a parser that "
                    "only records materials), in its copy of the instruction such as `source_text` - that counts as "
                    "applied. Decide this once, here; after --complete the mission cannot be cancelled. If the change "
                    f"is not there, run {script} resume {base} --agent-failed --summary \"<what is still wrong>\" "
                    "instead of registering it. Never edit an earlier output, an input file or a Worker's own files "
                    "(SKILL.md, scripts, KB).")
            steps.append(f"{script} resume {base} --agent-completed --register-all --summary \"<what really happened>\"")
            steps.append(f"If it really failed: {script} resume {base} --agent-failed --summary \"<the real error text>\"")
            return steps
        # awaiting_decision
        if retry_candidates:
            item = retry_candidates[0]
            return [f"{script} act {base} --skill {item['skill_id']} --retry-of {item['action_id']}"]
        if state.plan:
            confirmed = (len(state.plan) < 2 or bool(state.revisions)
                         or any(item.get("status") == "human_answer" for item in state.action_history))
            if not confirmed:
                return [f"{script} act {base} --ask-plan   (asks the user to confirm the plan; then relay the question and end the turn)"]
            for item in progress:
                if item["status"] in {"next", "failed", "waiting"}:
                    ready = next((c for c in candidates if c["id"] == item["skill_id"]), None)
                    skill = self.skills.get(item["skill_id"])
                    missing = [a for a in (skill.input_artifacts if skill else []) if a not in state.artifacts]
                    earlier = {out for step in state.plan[:state.plan.index(item["skill_id"])]
                               for out in (self.skills[step].outputs if step in self.skills else {})}
                    external = [a for a in missing if a not in earlier]
                    if external:
                        note = (f"   (the mission does not hold input {external}; it cannot run yet. Start a new mission with "
                                f"`run --new-mission ... --input-artifact {external[0]}=<path of that file>` using exactly this id, "
                                "or ask the user for the file)")
                    elif missing:
                        note = f"   (waiting for input {missing}: run the previous plan step first)"
                    else:
                        note = ""
                    steps = [f"{script} act {base} --skill {item['skill_id']}{note}"]
                    revision = self._open_revision(state)
                    if revision and not any(self._step_done(state, step) for step in state.plan):
                        steps.append(
                            f"Revision {revision['number']} (the user changed: {revision['change']}): redo "
                            f"{', '.join(revision['redo'])}; keep {', '.join(revision['kept']) or 'nothing else'}."
                            + (f" Tell the user in one sentence why {', '.join(revision['kept_with_changed_inputs'])} "
                               "stay valid although an input is regenerated, or add them to --redo."
                               if revision.get("kept_with_changed_inputs") else ""))
                        for worker, inputs in (revision.get("inputs_from_kept") or {}).items():
                            makers = list(dict.fromkeys(inputs.values()))
                            steps.append(
                                f"{worker} reads {', '.join(f'{a} (made by {p}, kept)' for a, p in inputs.items())}. If "
                                "the change is in that input (for example a condition of the user's instruction, which "
                                f"{', '.join(makers)} turns into it), rerunning {worker} alone repeats the old result: "
                                f"run {script} act {base} --revise \"<the change>\" --redo "
                                f"{','.join(dict.fromkeys([*makers, *revision['redo']]))} instead (it replaces revision "
                                f"{revision['number']}).")
                    return steps
            return [f"{script} act {base} --complete   (all plan steps are done), then report the results to the user"]
        ready_ids = [c["id"] for c in candidates if not c["missing_inputs"] and not c["missing_capabilities"]]
        return [f"Choose one Worker from {ready_ids or [c['id'] for c in candidates]}, then run: {script} act {base} --skill <id>",
                f"If nothing fits or an input is missing: {script} act {base} --ask \"<one question for the user>\""]

    def context(self) -> dict[str, Any]:
        state = self._load()
        artifact_dir = self._artifact_dir(state)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        candidates, excluded_skills = self._candidate_cards(state)
        historical_experiences = self.store.experiences.search(
            state.goal, skill_ids=[card["id"] for card in candidates]
        )
        if not self.skills:
            coverage_diagnostic = {
                "status": "no_registered_worker",
                "execution_started": False,
                "registered_skill_count": 0,
                "candidate_count": 0,
                "fallback_available": True,
                "fallback_scope": "low_risk_read_only",
                "fallback_message": (
                    "如果这是低风险、只读分析，可以由 Agent 直接尝试，"
                    "结果会标记为 Agent 直接执行。是否继续？"
                ),
                "user_message": (
                    "当前没有找到可用的实验能力，任务还没有开始。"
                    "请先安装或初始化相关能力。"
                ),
            }
        elif not candidates:
            coverage_diagnostic = {
                "status": "no_matching_worker",
                "execution_started": False,
                "registered_skill_count": len(self.skills),
                "candidate_count": 0,
                "fallback_available": True,
                "fallback_scope": "low_risk_read_only",
                "fallback_message": (
                    "如果这是低风险、只读分析，可以由 Agent 直接尝试，"
                    "结果会标记为 Agent 直接执行。是否继续？"
                ),
                "user_message": (
                    "当前没有找到能完成这项任务的完整能力，所以还没有开始执行。"
                    "可能是相关 Skill 没有安装完整，或安装后没有被正确登记。"
                    "请检查相关 Skill 后重试。"
                ),
            }
        else:
            coverage_diagnostic = {
                "status": "candidate_found",
                "execution_started": False,
                "registered_skill_count": len(self.skills),
                "candidate_count": len(candidates),
                "user_message": "已经找到可用的实验能力，但任务还没有开始。",
            }
        retry_candidates = []
        for action_id, execution in state.skill_executions.items():
            skill = self.skills.get(execution.get("skill_id"))
            if (execution.get("status") in {"failed", "timed_out"}
                    and _action_number(action_id) > state.plan_base
                    and execution.get("retryable") is True
                    and skill is not None
                    and skill.side_effect_level == "read_only"
                    and execution.get("retry_count", 0) < skill.retry_limit):
                retry_candidates.append({
                    "action_id": action_id,
                    "skill_id": skill.id,
                    "failure_kind": execution.get("failure_kind"),
                    "retry_count": execution.get("retry_count", 0),
                })
        waiting_for_resume = state.status in {"waiting_agent", "waiting_human"}
        waiting_for_reconcile = state.status == "running"
        native_fallback_waiting = (
            state.status == "waiting_agent"
            and isinstance(state.pending_action, dict)
            and state.pending_action.get("execution_source") == "agent_native"
        )
        worker_cycle = {
            "entrypoint": "act",
            "after_act": "reconcile" if waiting_for_reconcile else ("resume" if waiting_for_resume else "context"),
            "requires_resume": waiting_for_resume,
            "requires_reconcile": waiting_for_reconcile,
            "resume_mode": (
                "agent_native" if native_fallback_waiting
                else "external_worker" if state.status == "waiting_agent"
                else "human_decision" if state.status == "waiting_human"
                else None
            ),
            "status": state.status,
        }
        if state.status in {"completed", "cancelled"}:
            next_step = f"Mission is {state.status}; report its recorded state and create a new mission for a new goal."
        elif state.status == "running":
            next_step = "Host Agent: reconcile the interrupted action before choosing another Worker."
        elif state.status == "waiting_agent":
            next_step = (
                "Host Agent: follow the prepared Worker document; optionally use its script accelerator, "
                "then call resume with the actual result (the resume output is already the new context; "
                "do not run context again)."
            )
        elif state.status == "waiting_human":
            next_step = ("Host Agent: if the user's latest message answers this question, call resume now with that exact "
                     "message (its output is already the new context); otherwise relay the pending question to the "
                     "user and end the turn.")
        elif state.replan_required:
            next_step = (
                "Host Agent: this output already is the current context, so do not run context again. Reassess the "
                "goal with the human answer and select one Worker from `skills`, Read its SKILL.md, run prepare-skill, "
                "write the decision file, then run act. If your previous Worker decision was paused because its "
                "assessment listed uncertainties, the user's reply does not run it: write that decision again with "
                "uncertainties [] and assessment.authorization set to the user's reply, then run act; "
                "for an explicitly approved low-risk read-only fallback, use agent_fallback; "
                "do not complete or compute outside a Worker or approved fallback."
            )
        else:
            next_step = ("Host Agent: this output already is the current context, so do not run context again. Choose the "
                     "next action: read the SKILL.md of one Worker from `skills`, run prepare-skill, write the decision "
                     "file, then run act; call resume only when the worker_cycle requires it.")
        plan_progress = self._plan_progress(state)
        do_next = self._do_next(state, candidates, retry_candidates, plan_progress)
        return {"mission": state.to_dict(), "skills": candidates, "candidate_count": len(candidates),
                "plan_progress": plan_progress, "do_next": do_next,
                "registered_skill_count": len(self.skills), "match_found": bool(candidates),
                "coverage_diagnostic": coverage_diagnostic,
                "excluded_skills": excluded_skills,
                "artifact_dir": str(artifact_dir),
                "supervisor_status": state.supervisor_status,
                "pending_ticket": state.pending_ticket,
                "prepared_skill": state.prepared_skill,
                "action_history_count": len(state.action_history),
                 "available_capabilities": sorted(self.capabilities),
                 "start_skill": state.start_skill,
                 "replan_required": state.replan_required,
                 "retry_candidates": retry_candidates,
                "workflow_references": self.workflows,
                "policies": [asdict(p) for p in self.policies],
                "worker_cycle": worker_cycle,
                "historical_experiences": historical_experiences,
                "next": next_step}

    def prepare_skill(self, skill_id: str) -> dict[str, Any]:
        """Read the selected Worker Skill and persist the exact document digest."""
        state = self._load()
        skill = self.skills.get(skill_id)
        if skill is None:
            raise ValueError(f"Unknown registered Skill: {skill_id}")
        source = self.knowledge.get(skill_id, {}).get("instruction_source")
        if not isinstance(source, dict) or not source.get("path"):
            raise ValueError(f"Skill has no instruction source: {skill_id}")
        path = Path(str(source["path"])).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"Skill document is unavailable: {path}")
        raw_content = path.read_bytes()
        actual_hash = hashlib.sha256(raw_content).hexdigest()
        recorded_hash = source.get("sha256")
        if recorded_hash and actual_hash != recorded_hash:
            raise ValueError("Skill document changed; refresh the cache and reassess the action")
        content = raw_content.decode("utf-8", errors="replace")
        prepared = {
            "skill_id": skill_id,
            "path": str(path),
            "sha256": actual_hash,
            "prepared_at": datetime.now(timezone.utc).isoformat(),
            "content": content,
        }
        state.prepared_skill = {key: value for key, value in prepared.items() if key != "content"}
        self.store.save(state)
        self.store.event("skill_prepared", {
            "skill": skill_id, "path": str(path), "sha256": prepared["sha256"]
        })
        self._feedback("skill_prepared", skill_id,
                       {"path": str(path), "sha256": prepared["sha256"]})
        return prepared

    def assert_skill_prepared(self, skill_id: str) -> None:
        state = self._load()
        skill = self.skills.get(skill_id)
        if skill is None:
            raise ValueError(f"Unknown registered Skill: {skill_id}")
        error = self._prepared_skill_error(state, skill)
        if error:
            raise ValueError(error)

    def decide(self, decision: dict[str, Any]) -> MissionState:
        if not isinstance(decision, dict):
            raise ValueError("Decision must be a JSON object")
        state = self._load()
        if state.status == "completed" and decision.get("kind") == "cancel":
            raise ValueError("The mission is already completed, so there is nothing to cancel: its results stay. Tell "
                             "the user once that the task is finished - do not retry. To undo a change, run act "
                             "--revise \"<back to the earlier value>\" --redo <Worker ids>.")
        if state.status == "completed":
            raise ValueError("The mission is already completed: there is nothing to run or complete. To change a result "
                             "run act --revise \"<the user's change>\" --redo <Worker ids>; otherwise answer the user "
                             "from mission.artifacts.")
        if state.status == "waiting_human":
            raise ValueError("The mission is waiting for the user's answer. Record it first: resume --answer "
                             "\"<the user's exact message>\"; then, if the user stopped the task, act --cancel.")
        if state.status == "waiting_agent":
            raise ValueError("A Worker action is pending: report it first with resume --agent-completed --register-all "
                             "or --agent-failed; then choose the next action.")
        if state.status != "awaiting_decision":
            raise ValueError(f"Cannot replace an action while mission is {state.status}")
        action = deepcopy(decision)
        if not isinstance(action.get("reason"), str) or not action["reason"].strip():
            raise ValueError("Decision requires a reason")
        kind = action.get("kind")
        if kind not in {"skill", "request_human", "agent_fallback", "complete", "cancel"}:
            raise ValueError("Decision kind must be skill, request_human, agent_fallback, complete or cancel")
        if kind == "complete" and state.replan_required:
            raise ValueError("Human answer received; replan in context and select a Worker before completing")
        revision = self._open_revision(state)
        if kind == "complete" and revision:
            missing = [step for step in state.plan if not self._step_done(state, step)]
            if missing:
                raise ValueError(
                    f"Revision {revision['number']} (the user's change: {revision['change']}) has not redone "
                    f"{', '.join(missing)} yet, so completing now would present the old results as changed. Run "
                    f"act --skill {missing[0]}. If the change cannot be applied (the Worker cannot take it or failed) "
                    "or the user drops it, run act --cancel --reason \"<why>\": that closes only revision "
                    f"{revision['number']} and keeps the results from before the change.")
        if kind == "skill":
            if action.get("skill_id") not in self.skills:
                raise ValueError(f"Unknown registered Skill: {action.get('skill_id')}")
            if self._uncontracted(action["skill_id"]):
                raise ValueError(f"Worker has no instruction document (SKILL.md) and cannot be selected: {action['skill_id']}")
            assessment = action.get("assessment", {})
            if not isinstance(assessment, dict) or assessment.get("impact") not in {"routine", "significant"}:
                raise ValueError("Agent assessment requires impact: routine or significant")
            if not isinstance(assessment.get("rationale"), str) or not assessment["rationale"].strip():
                raise ValueError("Agent assessment requires a rationale")
            for key in ("uncertainties", "authenticity_gaps"):
                if not isinstance(assessment.get(key), list) or not all(isinstance(x, str) for x in assessment[key]):
                    raise ValueError(f"Agent assessment requires {key} as a list of strings")
            if "authorization" in assessment and not isinstance(assessment["authorization"], str):
                raise ValueError("Existing authorization must cite the user's instruction")
            action["inputs"] = _artifact_paths(action.get("inputs", {}))
            action["arguments"] = self._decision_arguments(action, self.skills[action["skill_id"]])
            prepared_error = self._prepared_skill_error(state, self.skills[action["skill_id"]])
            if prepared_error:
                raise ValueError(prepared_error)
            if state.prepared_skill and state.prepared_skill.get("skill_id") == action["skill_id"]:
                action["prepared_skill"] = deepcopy(state.prepared_skill)
            instruction_error = self._instruction_error(action, self.skills[action["skill_id"]])
            if instruction_error:
                raise ValueError(instruction_error)
            action["skill_snapshot"] = self._skill_snapshot(self.skills[action["skill_id"]])
            retry_error = self._retry_error(state, action, self.skills[action["skill_id"]])
            if retry_error:
                raise ValueError(retry_error)
        if kind == "agent_fallback":
            fallback_error = self._agent_fallback_error(state, action)
            if fallback_error:
                raise ValueError(fallback_error)
        if kind == "request_human":
            if not str(action.get("question", "")).strip():
                raise ValueError("Human decision requires a question")
            # Only an answer to a question asked while no Worker matched can
            # approve the Agent fallback; the Runtime cannot judge the wording.
            action["fallback_offered"] = not self._candidate_cards(state)[0]
        action["id"] = f"action:{len(state.decisions) + 1}"
        action["action_id"] = action["id"]
        action["return_to"] = "labontology-skill"
        action["ticket_status"] = "issued"
        state.decisions.append(deepcopy(action))
        state.pending_action = action
        state.pending_ticket = action
        state.supervisor_status = "decision_pending"
        self.store.event("agent_decision", action)
        if kind == "cancel":
            if revision:
                # During a revision --cancel drops only that change: the results from before it stay.
                revision.update({"applied": False, "dropped_reason": action["reason"]})
                state.artifacts = dict(revision.get("artifacts_before") or state.artifacts)
                return self._observe(state, "revision_dropped", action["reason"], completed=True,
                                     revision=revision["number"])
            # The user stopped the task: close it without claiming a result.
            return self._observe(state, "cancelled", action["reason"], terminal_status="cancelled")
        if kind == "complete":
            # Only this round's folder: a file another round left behind is not an output of this one.
            untracked = _untracked_artifacts(state, self._artifact_dir(state))
            if untracked:
                state.untracked_external_calls.extend({"path": path, "action_id": action["id"]}
                                                       for path in untracked)
                return self._observe(state, "blocked",
                                     "Untracked external output must be returned through LabOntology",
                                     untracked_external_calls=untracked)
            if not any(
                execution.get("status") in {"succeeded", "reconciled_succeeded"}
                for execution in state.skill_executions.values()
                if isinstance(execution, dict)
            ):
                raise ValueError("Cannot complete without a successful Worker result")
            if revision:
                revision["applied"] = True
            return self._observe(state, "completed", action["reason"], completed=True)
        if kind == "request_human":
            return self._wait_human(state, action["question"])
        if kind == "agent_fallback":
            state.replan_required = False
            state.fallback_approval = None  # one approval allows one fallback
            return self._execute_agent_fallback(state)
        state.replan_required = False
        skill = self.skills[action["skill_id"]]
        prerequisite_error = self._prerequisites(state, action, skill)
        if prerequisite_error:
            self._record_prerequisite_feedback(skill, action, prerequisite_error)
            return self._observe(state, "blocked", prerequisite_error)
        assessment = action["assessment"]
        concerns = assessment["uncertainties"] + assessment["authenticity_gaps"]
        if assessment["impact"] == "significant" and not assessment.get("authorization", "").strip():
            concerns.append("Significant impact: " + assessment["rationale"])
        if any(p.requires_confirmation and skill.id in p.applies_to for p in self.policies):
            concerns.append("Explicit execution policy requires human confirmation")
        if concerns:
            return self._wait_human(state, "; ".join(concerns))
        return self._execute(state)

    def _agent_fallback_error(self, state: MissionState, action: dict[str, Any]) -> str | None:
        if not state.fallback_approval:
            return ("Agent fallback requires an explicit human approval first: the user's answer to a "
                    "request_human asked while no Worker matched; a rejection or other answer does not count")
        if action.get("side_effect_level") != "read_only":
            return "Agent fallback is limited to read-only work"
        assessment = action.get("assessment")
        if not isinstance(assessment, dict):
            return "Agent fallback requires an assessment"
        if assessment.get("impact") != "routine":
            return "Agent fallback is limited to routine, low-risk work"
        if not isinstance(assessment.get("rationale"), str) or not assessment["rationale"].strip():
            return "Agent fallback assessment requires a rationale"
        for key in ("uncertainties", "authenticity_gaps"):
            if not isinstance(assessment.get(key), list) or not all(isinstance(x, str) for x in assessment[key]):
                return f"Agent fallback assessment requires {key} as a list of strings"
        if not isinstance(assessment.get("authorization"), str) or not assessment["authorization"].strip():
            return "Agent fallback requires the user's explicit approval"
        return None

    def _skill_snapshot(self, skill: SkillSpec) -> dict[str, Any]:
        knowledge = self.knowledge.get(skill.id, {})
        return {"contract": asdict(skill), "suite_id": knowledge.get("suite_id"),
                "registry_file": knowledge.get("registry_file")}

    def _prerequisites(self, state: MissionState, action: dict, skill: SkillSpec) -> str | None:
        prepared_error = self._prepared_skill_error(state, skill)
        if prepared_error:
            return prepared_error
        instruction_error = self._instruction_error(action, skill)
        if instruction_error:
            return instruction_error
        if action.get("skill_snapshot") != self._skill_snapshot(skill):
            return "Selected Skill implementation or suite changed; reassess before execution"
        if any(p.blocked and skill.id in p.applies_to for p in self.policies):
            return "Explicit policy blocks this Skill"
        missing_caps = sorted(set(skill.required_capabilities) - self.capabilities)
        if missing_caps:
            return f"Required capability unavailable: {missing_caps}"
        artifacts = {**state.artifacts, **action.get("inputs", {})}
        missing = [a for a in skill.input_artifacts if a not in artifacts or not Path(artifacts[a]).exists()]
        if missing:
            return f"Required inputs missing: {missing}"
        return None

    def _decision_arguments(self, action: dict[str, Any], skill: SkillSpec) -> dict[str, Any]:
        arguments = action.get("arguments", {})
        if not isinstance(arguments, dict):
            raise ValueError("Decision arguments must be an object")
        bindings = skill.argument_bindings if isinstance(skill.argument_bindings, dict) else {}
        declared = bindings.get("parameters", {}) if isinstance(bindings.get("parameters", {}), dict) else {}
        unknown = sorted(set(arguments) - set(declared))
        if unknown:
            raise ValueError(f"Unknown declared argument(s) for {skill.id}: {unknown}")
        if not all(isinstance(value, (str, int, float, bool)) for value in arguments.values()):
            raise ValueError("Decision argument values must be strings, numbers, or booleans")
        return arguments

    def _prepared_skill_error(self, state: MissionState, skill: SkillSpec) -> str | None:
        """Require a fresh read for imported Worker Skills.

        Hand-built legacy skills without an instruction source keep their old
        behavior; imported worker Skills are always checked at the action
        boundary and again immediately before execution.
        """
        source = self.knowledge.get(skill.id, {}).get("instruction_source")
        if not isinstance(source, dict) or not source.get("path"):
            return None
        prepared = state.prepared_skill
        if not isinstance(prepared, dict) or prepared.get("skill_id") != skill.id:
            return "Worker Skill requires prepare_skill before execution"
        path = Path(str(source["path"])).expanduser().resolve()
        if not path.is_file():
            return f"Skill document is unavailable: {path}"
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        recorded_hash = source.get("sha256")
        if recorded_hash and actual_hash != recorded_hash:
            return "Skill document changed; refresh the cache and reassess the action"
        if prepared.get("path") != str(path) or prepared.get("sha256") != actual_hash:
            return "Prepared Skill document changed; refresh with prepare_skill"
        return None

    def _record_prerequisite_feedback(self, skill: SkillSpec, action: dict[str, Any],
                                      error: str) -> None:
        if error.startswith("Required capability unavailable:"):
            event = "missing_capability"
        elif error.startswith("Required inputs missing:"):
            event = "missing_precondition"
        else:
            return
        self._feedback(event, skill.id, {"action_id": action.get("id"), "error": error})

    def _instruction_error(self, action: dict[str, Any], skill: SkillSpec) -> str | None:
        source = self.knowledge.get(skill.id, {}).get("instruction_source")
        if not isinstance(source, dict) or not source.get("path") or not source.get("sha256"):
            return None
        path = Path(str(source["path"])).expanduser()
        if not path.is_file():
            return f"Skill document is unavailable: {path}"
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != source["sha256"]:
            return "Skill document changed; refresh the cache and reassess the action"
        reviewed = action.get("reviewed_instruction") or action.get("prepared_skill")
        if not isinstance(reviewed, dict):
            return "Skill decision requires a prepared Skill document"
        if str(reviewed.get("path")) != str(path.resolve()) or reviewed.get("sha256") != actual_hash:
            return "prepared Skill document does not match the current Skill document"
        return None

    def _retry_error(self, state: MissionState, action: dict[str, Any], skill: SkillSpec) -> str | None:
        retry_of = action.get("retry_of")
        if retry_of is None:
            return None
        if not isinstance(retry_of, str) or not retry_of:
            return "retry_of must name a prior action"
        prior = state.skill_executions.get(retry_of)
        if prior is None:
            return f"Retry target does not exist: {retry_of}"
        if prior.get("skill_id") != skill.id:
            return "Retry target belongs to a different Skill"
        if prior.get("status") not in {"failed", "timed_out"}:
            return "Retry target did not fail"
        if prior.get("retryable") is not True:
            return "Prior action is not retryable"
        if skill.side_effect_level != "read_only":
            return "Skill is not retryable because it is not read-only"
        retry_count = int(prior.get("retry_count", 0))
        if retry_count >= skill.retry_limit:
            return f"Retry limit reached for {skill.id}"
        action["retry_count"] = retry_count + 1
        return None

    def _wait_human(self, state: MissionState, question: str) -> MissionState:
        state.status, state.block_reason = "waiting_human", question
        state.supervisor_status = "waiting_human"
        self.store.save(state)
        self.store.event("human_decision_requested", {"action": state.pending_action["id"], "question": question})
        return state

    def _execute(self, state: MissionState) -> MissionState:
        action = state.pending_action
        skill = self.skills.get(action["skill_id"])
        if skill is None:
            return self._observe(state, "blocked", "Selected Skill is no longer registered; replan")
        error = self._prerequisites(state, action, skill)
        if error:
            self._record_prerequisite_feedback(skill, action, error)
            return self._observe(state, "blocked", error)
        state.artifacts.update(action.get("inputs", {}))
        # Every Worker is executed through the prepared document contract. A
        # script, when present, is merely an optional host-side accelerator.
        action["ticket_status"] = "waiting_external"
        state.status, state.block_reason = "waiting_agent", None
        state.supervisor_status = "waiting_external"
        state.skill_executions[action["id"]] = {
            "skill_id": skill.id,
            "status": "waiting_agent",
            "required_outputs": list(skill.outputs),
            "output_templates": dict(skill.outputs),
            "optional_script_available": bool(skill.optional_command or skill.optional_entrypoints),
        }
        self.store.save(state)
        self.store.event("agent_skill_waiting", {"action": action["id"], "skill": skill.id})
        return state

    def _execute_agent_fallback(self, state: MissionState) -> MissionState:
        action = state.pending_action
        action["execution_source"] = "agent_native"
        action["ticket_status"] = "waiting_external"
        state.status, state.block_reason = "waiting_agent", None
        state.supervisor_status = "waiting_external"
        state.skill_executions[action["id"]] = {
            "id": action["id"],
            "skill_id": None,
            "status": "waiting_agent",
            "execution_source": "agent_native",
            "required_outputs": [],
        }
        self.store.save(state)
        self.store.event("agent_fallback_waiting", {"action": action["id"]})
        return state

    def reconcile(self, outcome: str, summary: str, *, evidence: list[str] | None = None,
                  provided_artifacts: dict[str, str] | None = None) -> MissionState:
        """Resolve an interrupted process from external evidence without replaying it."""
        if outcome not in {"not_started", "succeeded", "failed", "unknown"}:
            raise ValueError("Reconciliation outcome must be not_started, succeeded, failed or unknown")
        if not summary.strip():
            raise ValueError("Reconciliation requires a summary")
        state = self._load()
        if state.status != "running" or not state.pending_action:
            raise ValueError("Only a running action can be reconciled")
        action = state.pending_action
        skill = self.skills.get(action.get("skill_id"))
        if skill is None:
            raise ValueError("Selected Skill is no longer registered; cannot reconcile its contract")
        snapshot = action.get("skill_snapshot")
        if snapshot is not None and snapshot != self._skill_snapshot(skill):
            raise ValueError("Selected Skill changed during interruption; cannot reconcile its contract")
        outputs = _materialize_artifacts(_artifact_paths(provided_artifacts or {}), self.store.run_dir / "artifacts")
        if outcome == "succeeded":
            missing = sorted(set(skill.outputs) - outputs.keys())
            if missing:
                raise ValueError(f"Required reconciled outputs missing: {missing}")
            state.artifacts.update(outputs)
            state.skill_executions[action["id"]] = {
                "id": action["id"], "skill_id": skill.id, "status": "reconciled_succeeded",
                "outputs": outputs, "summary": summary, "evidence": evidence or [],
            }
        elif outputs:
            raise ValueError("Only a succeeded reconciliation may provide output artifacts")
        details = {"outcome": outcome, "summary": summary, "evidence": evidence or [], "outputs": outputs}
        self.store.event("reconciliation", {"action": action["id"], **details})
        return self._observe(state, f"reconciled_{outcome}", summary, evidence=evidence or [], outputs=outputs)

    def resume(self, *, action_id: str = "", provided_artifacts: dict[str, str] | None = None,
               summary: str = "", evidence: list[str] | None = None, agent_completed: bool = False,
               agent_failed: bool = False,
               confirmed: bool = False, rejected: bool = False, answer: str = "") -> MissionState:
        state = self._load()
        if confirmed and rejected:
            raise ValueError("Cannot both approve and reject an action")
        if action_id:
            if state.status != "waiting_agent" or not state.pending_action:
                raise ValueError("No external Skill is waiting for a result")
            if state.pending_action.get("id") != action_id:
                raise ValueError(f"External action does not match pending action: {action_id}")
        if state.status not in {"waiting_human", "waiting_agent"}:
            if answer.strip() and self._answered_this_turn(state):
                raise ValueError(
                    f"Refused - the user's message in this turn is already recorded (mission status is {state.status}). "
                    "Do not run resume --answer again in this turn; follow `do_next` of the last output.")
            hint = {
                "awaiting_decision": (
                    "The previous answer or result is already recorded (see the last observation), so `resume` has "
                    "nothing to do. Do not call resume again. Choose one Worker from the last output's `skills`, "
                    "Read its SKILL.md, run prepare-skill, write the decision file, then run act."),
                "completed": ("The mission is completed; report the result to the user. If the user changes a "
                              "condition of this task, use `act --revise \"<change>\" --redo <Worker ids>` on this "
                              "mission instead of creating a new one."),
                "cancelled": "The mission is cancelled; tell the user.",
            }.get(state.status, "Read the current state with context once and decide the next command.")
            raise ValueError(f"Nothing is waiting for a resume: mission status is {state.status}. {hint}")
        if state.status == "waiting_human":
            if (confirmed or rejected) and not answer.strip():
                raise ValueError("Record the actual user reply when approving or rejecting an action")
            # One user message answers one question: FounDryClaw sets a new FOUNDRYCLAW_TURN_ID for every
            # user message. Without it (CLI, offline runs) there is no turn to compare and nothing changes.
            turn = os.environ.get("FOUNDRYCLAW_TURN_ID", "").strip()
            if (answer.strip() or confirmed or rejected) and self._answered_this_turn(state):
                question = (state.pending_ticket or {}).get("question") or state.block_reason or ""
                raise ValueError(
                    "Refused - the user has not answered this question yet: the user's message in this turn already "
                    "answered an earlier question. Do not run resume again in this turn. Write your reply now: show "
                    "the result of the step that just finished, ask the user this question, and end the turn"
                    + (f": {question}" if question else ".")
                    + " Resume with the user's next message.")
            if rejected:
                self._feedback("mission_resumed", state.pending_action.get("skill_id"),
                               {"action_id": state.pending_action["id"], "from_status": state.status})
                return self._observe(state, "rejected", answer or "User rejected the action", turn=turn or None)
            action = state.pending_action
            if action["kind"] == "request_human":
                if not answer.strip():
                    return state
                self._feedback("mission_resumed", action.get("skill_id"),
                               {"action_id": action["id"], "from_status": state.status})
                return self._observe(state, "human_answer", answer, turn=turn or None)
            assessment = action["assessment"]
            # Approval alone does not fill in missing facts. Return to reasoning
            # when the human supplies evidence, so the Agent reassesses the action.
            if assessment["uncertainties"] or assessment["authenticity_gaps"]:
                if not answer.strip():
                    return state
                self._feedback("mission_resumed", action.get("skill_id"),
                               {"action_id": action["id"], "from_status": state.status})
                return self._observe(state, "human_answer", answer, turn=turn or None)
            if not confirmed:
                if answer.strip():
                    raise ValueError(
                        "This pending Worker action asks for the user's approval: a plain --answer does not decide it. "
                        "Run resume again with --confirm --answer \"<the user's exact reply>\" to approve, or --reject "
                        "--answer \"<the user's exact reply>\" to decline.")
                return state
            self._feedback("mission_resumed", action.get("skill_id"),
                           {"action_id": action["id"], "from_status": state.status})
            state.observations.append({"action_id": action["id"], "status": "human_approved",
                                       "summary": answer or "User approved this action", "turn": turn or None})
            self.store.event("human_approved", {"action": action["id"], "answer": answer})
            return self._execute(state)
        if state.status != "waiting_agent":
            return state
        if agent_failed and (agent_completed or provided_artifacts):
            raise ValueError("Failed Agent execution cannot also report successful completion or outputs")
        if not (agent_completed or agent_failed or summary.strip() or provided_artifacts):
            if answer.strip() or confirmed or rejected:
                raise ValueError(
                    "Refused - the user's answer was already recorded; a Worker action is pending now, not a question. "
                    "Do the Worker's work (see `do_next` of `context`), then report it with "
                    "`resume --agent-completed --register-all --summary \"<what happened>\"`. "
                    "Do not send the user's answer again.")
            return state
        self._feedback("mission_resumed", state.pending_action.get("skill_id"),
                       {"action_id": state.pending_action["id"], "from_status": state.status})
        if state.pending_action.get("execution_source") == "agent_native":
            action = state.pending_action
            action_id = action["id"]
            if agent_failed:
                if not summary.strip():
                    raise ValueError("Failed Agent fallback requires an explanation")
                state.skill_executions[action_id] = {
                    "id": action_id,
                    "skill_id": None,
                    "status": "failed",
                    "execution_source": "agent_native",
                    "outputs": {},
                    "error": summary,
                    "evidence": evidence or [],
                    "failure_kind": "agent_native",
                    "retryable": False,
                }
                return self._observe(
                    state, "failed", summary, evidence=evidence or [],
                    execution_source="agent_native",
                )
            outputs = _materialize_artifacts(
                _artifact_paths(provided_artifacts or {}), self.store.run_dir / "artifacts"
            )
            state.artifacts.update(outputs)
            _record_outputs(state, outputs, action_id)
            state.skill_executions[action_id] = {
                "id": action_id,
                "skill_id": None,
                "status": "succeeded",
                "execution_source": "agent_native",
                "outputs": outputs,
                "summary": summary,
                "evidence": evidence or [],
            }
            return self._observe(
                state, "succeeded", summary or "Agent fallback completed without a textual result",
                outputs=outputs, evidence=evidence or [], execution_source="agent_native",
            )
        skill = self.skills.get(state.pending_action["skill_id"])
        if skill is None or state.pending_action.get("skill_snapshot") != self._skill_snapshot(skill):
            return self._observe(state, "blocked", "Selected Skill changed during Agent execution; reassess results")
        if agent_failed:
            if not summary.strip():
                raise ValueError("Failed Agent execution requires an explanation")
            state.skill_executions[state.pending_action["id"]] = {
                "id": state.pending_action["id"], "skill_id": skill.id, "status": "failed",
                "outputs": {}, "error": summary, "evidence": evidence or [],
                "failure_kind": "external_worker",
                "retryable": skill.side_effect_level == "read_only",
                "retry_count": 0,
            }
            return self._observe(state, "failed", summary, evidence=evidence or [])
        outputs = _materialize_artifacts(_artifact_paths(provided_artifacts or {}), self.store.run_dir / "artifacts")
        outputs = _canonical_outputs(skill.outputs, outputs)
        missing = sorted(set(skill.outputs) - outputs.keys())
        if missing:
            given = {Path(path).resolve() for path in outputs.values()}
            files = [f"{path} (given as {artifact_id})" for artifact_id, path in outputs.items()
                     if artifact_id not in skill.outputs]
            files += [path for path in _untracked_artifacts(state, self.store.run_dir / "artifacts")
                      if Path(path).resolve() not in given]
            raise ValueError(
                f"Required Agent outputs missing: {missing}. Files that could be it: "
                f"{files[:8] or 'none'}. Say which file is which output: resume --agent-completed "
                + " ".join(f"--provide-artifact {name}=<path of that file>" for name in missing)
                + ' --summary "<what happened>" (add --register-all to register the other files too). '
                "If the Worker did not produce it, report --agent-failed with the real reason.")
        revision = self._open_revision(state)
        if revision and skill.id in revision.get("redo", []):
            before = {digest for digest in map(_file_digest, self._previous_outputs(state, skill.id)) if digest}
            now = [_file_digest(outputs[name]) for name in skill.outputs if name in outputs]
            if before and now and all(digest in before for digest in now):
                raise ValueError(
                    f"The new output of {skill.id} is identical to its output before revision {revision['number']}, "
                    f"so the change ({revision['change']}) did not reach its inputs. Run it again with the change in "
                    "its inputs, or report resume --agent-failed --summary \"<why the change cannot be applied>\".")
        state.artifacts.update(outputs)
        _record_outputs(state, outputs, state.pending_action["id"])
        state.skill_executions[state.pending_action["id"]] = {
            "id": state.pending_action["id"], "skill_id": skill.id, "status": "succeeded",
            "outputs": outputs, "summary": summary, "evidence": evidence or []}
        state = self._observe(state, "succeeded", summary or "Agent Skill completed without a textual result",
                              outputs=outputs, evidence=evidence or [])
        return self._step_gate(state, skill.id, summary, outputs)

    def _step_gate(self, state: MissionState, skill_id: str, summary: str,
                   outputs: dict[str, str]) -> MissionState:
        """One plan step per turn: after a step succeeds with steps left, wait for the user before the next.

        The mission moves to waiting_human with a ticket, so the next Worker action is refused until the
        user has seen the result and answered (unless the user asked for --run-through)."""
        if state.run_through or skill_id not in state.plan:
            return state
        remaining = [item for item in state.plan if not self._step_done(state, item)]
        if not remaining:
            return state
        position = state.plan.index(skill_id) + 1
        question = (f"步骤 {position}/{len(state.plan)}（{skill_id}）已完成"
                    + (f"：{summary.strip()[:300]}" if summary.strip() else "")
                    + f"。下一步是 {remaining[0]}。是否继续？")
        action = {"kind": "request_human", "reason": "Plan step finished; the user reviews the result before the next step.",
                  "question": question, "fallback_offered": False, "step_gate": True,
                  "completed_skill": skill_id, "completed_outputs": dict(outputs),
                  "id": f"action:{len(state.decisions) + 1}", "return_to": "labontology-skill",
                  "ticket_status": "issued"}
        action["action_id"] = action["id"]
        state.decisions.append(deepcopy(action))
        state.pending_action = action
        state.pending_ticket = action
        state.supervisor_status = "decision_pending"
        self.store.event("agent_decision", action)
        return self._wait_human(state, question)

    def _observe(self, state: MissionState, status: str, summary: str,
                 *, completed: bool = False, terminal_status: str | None = None,
                 **details: Any) -> MissionState:
        observation = {"action_id": state.pending_action["id"], "status": status, "summary": summary, **details}
        state.observations.append(observation)
        ticket = state.pending_action
        if ticket:
            state.action_history.append({
                "action_id": ticket.get("id"),
                "skill_id": ticket.get("skill_id"),
                "return_to": ticket.get("return_to", "labontology-skill"),
                "status": status,
            })
            if status in {"failed", "reconciled_failed"}:
                self._feedback("skill_failed", ticket.get("skill_id"), {
                    "action_id": ticket.get("id"),
                    "status": status,
                    "summary": summary,
                    "failure_kind": details.get("failure_kind"),
                })
        state.fallback_approval = (
            {"action_id": ticket.get("id"), "answer": summary}
            if status == "human_answer" and ticket and ticket.get("kind") == "request_human"
            and ticket.get("fallback_offered") else None
        )
        state.pending_action = None
        state.pending_ticket = None
        if status in {"human_answer", "rejected"}:
            state.replan_required = True
        elif completed or terminal_status or status in {"succeeded", "failed", "blocked", "reconciled_failed"}:
            state.replan_required = False
        if terminal_status:
            state.status = state.supervisor_status = terminal_status
        else:
            state.status = "completed" if completed else "awaiting_decision"
            state.supervisor_status = "completed" if completed else "needs_action"
        state.block_reason = None
        self.store.save(state)
        self.store.event("observation", observation)
        if completed and not state.revisions:
            self.store.experiences.record_mission(state)
        return state
