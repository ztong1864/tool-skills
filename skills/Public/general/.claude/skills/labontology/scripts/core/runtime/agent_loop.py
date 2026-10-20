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

from .flows import flow_plan, flow_revision_plan
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

# FounDryClaw sets a new turn id for every user message and passes the message itself, so the Runtime can take the
# user's reply to a question from the turn instead of the model sending it with `resume --answer` (models re-sent it
# with every later command and looped on the refusals). Outside FounDryClaw neither is set.
TURN_ENV = "FOUNDRYCLAW_TURN_ID"
USER_MESSAGE_ENV = "FOUNDRYCLAW_USER_MESSAGE"
# A Skill's work takes at least one model call between act and resume; a resume sooner than this came in the same
# batch of tool calls as its act (see _resumed_in_same_batch). 3 s let a batch of 20 calls through: its second
# resume came 4 s after the act. Real gaps were 15 s and more. Tests that drive act and resume back to back set 0.
MIN_WORK_SECONDS_ENV = "LABONTOLOGY_MIN_WORK_SECONDS"
DEFAULT_MIN_WORK_SECONDS = 8.0
# A review Skill's verdict line (fdu-risk-review: "verdict: pass | needs_human_review | block").
_VERDICT = re.compile(r"\bverdict\s*[:：]\s*(pass|needs_human_review|block)\b", re.IGNORECASE)
# The question is still the user's to answer: LabOntology refusals carrying this text end the FounDryClaw turn.
UNANSWERED = "the user has not answered this question yet"


def _documentation_search_text(documentation: Any) -> str:
    """Build a bounded search view of a Skill document without placing it in context."""
    if not isinstance(documentation, dict):
        return ""
    parts: list[str] = []
    for key in (
        "input_hints", "output_hints", "execution_order_hints",
        "precondition_hints", "constraint_hints", "related_skill_refs",
    ):
        values = documentation.get(key, [])
        if isinstance(values, list):
            parts.extend(str(value) for value in values[:40])
    sections = documentation.get("sections", [])
    if isinstance(sections, list):
        for section in sections[:20]:
            if not isinstance(section, dict):
                continue
            parts.append(str(section.get("heading") or ""))
            parts.append(str(section.get("text") or "")[:800])
    return " ".join(parts)


def _current_turn() -> str:
    return os.environ.get(TURN_ENV, "").strip()


def _unanswered_error(question: str) -> ValueError:
    return ValueError(
        f"Refused - {UNANSWERED}: it was asked in this turn, or the user's message in this turn already answered an "
        "earlier question. Do not start the next step or send an answer in this turn. Write your reply now: show the "
        "result of the step that just finished, ask the user this question, and end the turn"
        + (f": {question}" if question else ".") + " Continue with the user's next message.")


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
        experiment_flows: dict[str, dict[str, Any]] | None = None,
    ):
        self.skills, self.store = skills, store
        self.capabilities = set(available_capabilities or [])
        self.policies = policies or []
        self.knowledge = skill_knowledge or {}
        self.workflows = workflow_references or []
        self.suite_id = suite_id
        self.experiment_flows = experiment_flows or {}
        self.notice: str | None = None  # a resume that changed nothing says so in the next output

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
              run_through: bool = False, flow: str = "", until: str = "") -> MissionState:
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
        flow_id = flow.strip().removeprefix("flow:")
        built: dict[str, Any] = {}
        if flow_id:
            if plan:
                raise ValueError("Use either --flow or --plan, not both: --flow builds the plan from the flow")
            declared = self.experiment_flows.get(flow_id)
            if declared is None:
                known = "; ".join(f"{key} ({item.get('name')})" for key, item in sorted(self.experiment_flows.items()))
                raise ValueError(f"Unknown experiment flow: {flow_id}. "
                                 + (f"Declared flows: {known}" if known else "This library declares no experiment flow."))
            built = flow_plan(declared, until, set(self.skills))
            plan = built["plan"]
        elif until.strip():
            raise ValueError("--until is a stop point of --flow; it needs --flow")
        unknown = [item for item in plan if item not in self.skills]
        if unknown:
            raise ValueError(f"Unknown Skill id in --plan: {unknown}. Valid ids: {sorted(self.skills)}")
        if len(plan) > 1 and not flow_id:
            # A model planned flow steps itself ("先解析约束，再推荐，然后换算投料量，最后生成编号实验步骤") and
            # the recommendations went on unreviewed, THF at 70 ℃ included: the flow's reviews come with its steps.
            # A single Skill asked for alone stays a one-step plan.
            for declared in self.experiment_flows.values():
                steps = {step.get("skill") for step in declared.get("steps") or []}
                chosen = flow_revision_plan(declared, None, plan) if set(plan) <= steps else None
                if chosen:
                    plan = chosen["plan"]
                    built = {"pauses": chosen["pauses"], "labels": chosen["labels"],
                             "questions": chosen["questions"]}
                    self.notice = (f"These Skills are steps of the experiment flow {declared.get('name') or declared['id']} "
                                   f"({declared['id']}): the plan runs them in the flow's order with the review after "
                                   "each step that has one, and pauses only where the flow pauses (see plan_progress).")
                    break
        state = MissionState(self.store.mission_id, status="awaiting_decision", mode="agent",
                             goal=goal, constraints=list(constraints or []), plan=plan, run_through=run_through,
                             available_capabilities=sorted(self.capabilities),
                             artifacts=_artifact_paths(artifacts or {}), start_skill=start_skill,
                             suite_id=self.suite_id)
        if built:
            if built.get("flow"):
                state.flow = {**built["flow"], "final_question": built["final_question"]}
            state.plan_pauses = built["pauses"]
            state.plan_labels = built["labels"]
            state.plan_questions = built["questions"]
        self.store.save(state)
        self.store.event("mission_created", {"goal": goal, "mode": "agent"})
        return state

    def _uncontracted(self, skill_id: str) -> bool:
        """An imported Skill without an instruction document cannot pass the read gate."""
        knowledge = self.knowledge.get(skill_id, {})
        return knowledge.get("requires_instruction") is True and not isinstance(knowledge.get("instruction_source"), dict)

    def _candidate_cards(self, state: MissionState) -> tuple[list[dict[str, Any]], list[dict[str, str]], bool]:
        """(candidate cards, Skills left out, whether the goal's words matched any Skill).

        When no Skill matches the goal's words, every selectable Skill is offered for review by its document
        instead: words prove nothing either way (a Skill described in another language than the goal), and five
        of them picked by id would just be the first five in alphabetical order."""
        cards: list[tuple[int, dict[str, Any]]] = []
        excluded_skills: list[dict[str, str]] = []
        selectable: list[tuple[SkillSpec, dict[str, Any], set[str], set[str]]] = []
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
            selectable.append((skill, knowledge, search_terms(searchable),
                               search_terms(_documentation_search_text(knowledge.get("documentation")).lower())))
        goal_terms = search_terms(state.goal)
        if len(selectable) >= 3:
            # A term every Skill shares (for example "experiment" in a lab
            # library) cannot tell Skills apart, so it does not count as a match.
            goal_terms -= set.intersection(*(terms | doc_terms for _, _, terms, doc_terms in selectable))
        goal_text = str(state.goal or "").lower()
        for skill, knowledge, searchable_terms, doc_terms in selectable:
            name = str(knowledge.get("name") or skill.id)
            description = str(knowledge.get("description") or "")
            # The name, description and declared contract count twice as much as a word in the document's text.
            score = sum(2 if term in searchable_terms else 1 if term in doc_terms else 0 for term in goal_terms)
            # A Skill the goal names (its id or SKILL.md name) is always offered, first: word overlap missed
            # one whose description is in another language than the goal.
            if any(len(label) >= 3 and label.lower() in goal_text for label in {skill.id, name}):
                score += 100
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
        if matched_cards:
            candidates = [card for _, card in sorted(matched_cards, key=lambda item: (-item[0], item[1]["id"]))[:5]]
            return candidates, excluded_skills, True
        review = sorted((card for _, card in cards), key=lambda card: card["id"])
        for card in review:
            card["selection_note"] = "关键词未直接命中，必须读取完整 Skill 文档确认是否适用。"
            card["document"] = (self.knowledge.get(card["id"], {}).get("instruction_source") or {}).get("path")
        return review, excluded_skills, False

    def _step_executions(self, state: MissionState, skill_id: str) -> list[dict[str, Any]]:
        """Executions of one Skill in the current plan round (after the latest revision), oldest first."""
        return [state.skill_executions[key] for key in sorted(state.skill_executions, key=_action_number)
                if state.skill_executions[key].get("skill_id") == skill_id and _action_number(key) > state.plan_base]

    def _step_done(self, state: MissionState, skill_id: str) -> bool:
        return any(item.get("status") in _SUCCEEDED for item in self._step_executions(state, skill_id))

    def _plan_slots(self, state: MissionState) -> dict[int, dict[str, Any]]:
        """Plan position (0-based) -> the successful execution of this round that did it.

        Each success fills the earliest open position of its Skill. A Skill the plan lists more than once (a
        review after several steps of a flow) fills a later position only when every position before it is
        filled, so reviewing one result twice does not tick off the review of a later one. For a plan without
        repeated Skills this is the same as "the Skill succeeded in this round"."""
        repeated = {skill_id for skill_id in state.plan if state.plan.count(skill_id) > 1}
        # A position reopened by a redo (see _redo_steps) takes only an action issued after the redo.
        floors = {int(key): value for key, value in (state.plan_floors or {}).items()}
        slots: dict[int, dict[str, Any]] = {}
        for key in sorted(state.skill_executions, key=_action_number):
            item = state.skill_executions[key]
            if _action_number(key) <= state.plan_base or item.get("status") not in _SUCCEEDED:
                continue
            skill_id = item.get("skill_id")
            position = next((index for index, step in enumerate(state.plan)
                             if step == skill_id and index not in slots
                             and _action_number(key) > floors.get(index, 0)), None)
            if position is None or (skill_id in repeated and any(index not in slots for index in range(position))):
                continue
            slots[position] = item
        return slots

    def _open_positions(self, state: MissionState) -> list[int]:
        slots = self._plan_slots(state)
        return [index for index in range(len(state.plan)) if index not in slots]

    def _open_review_index(self, state: MissionState, skill_id: str) -> int | None:
        """The plan position this Skill works on (its earliest open one) when that position is a flow review."""
        position = next((index for index in self._open_positions(state) if state.plan[index] == skill_id), None)
        if position and position < len(state.plan_labels) and state.plan_labels[position]:
            return position
        return None

    def _review_redo(self, state: MissionState, position: int) -> str | None:
        """The reviewed Skill to run again when the review at this open plan position did not pass and that Skill
        has not run since: the next step is that Skill with the user's change, then the review."""
        if not position or position >= len(state.plan_labels) or not state.plan_labels[position]:
            return None
        runs = self._step_executions(state, state.plan[position])
        if not runs or runs[-1].get("status") != "failed":
            return None
        failed = _action_number(runs[-1].get("id"))
        reviewed = state.plan[position - 1]
        redone = any(item.get("status") in _SUCCEEDED and _action_number(item.get("id")) > failed
                     for item in self._step_executions(state, reviewed))
        return None if redone else reviewed

    def _skill_open(self, state: MissionState, skill_id: str) -> bool:
        """The Skill still has work in this round: an open plan position, or (outside the plan) no success yet."""
        if skill_id in state.plan:
            return any(state.plan[index] == skill_id for index in self._open_positions(state))
        return not self._step_done(state, skill_id)

    def _artifact_dir(self, state: MissionState) -> Path:
        """Where the current round writes: artifacts/, or artifacts/rev<N>/ during a revision (earlier outputs stay)."""
        base = self.store.run_dir / "artifacts"
        return base / f"rev{len(state.revisions)}" if state.revisions else base

    def _new_name_note(self, state: MissionState) -> str:
        """For a Skill run again in the same round: the same file name over the earlier output was neither new nor
        registrable, and a model made its own artifacts/rev1/ folder instead, which register-all does not read."""
        return (f"Write its new output into {self._artifact_dir(state)} under a new file name (for example add _v2 "
                "before the extension; do not create a rev folder), so --register-all registers it and the new file "
                "replaces the earlier one.")

    def _open_revision(self, state: MissionState) -> dict[str, Any] | None:
        """The latest revision while it is still being worked on (not yet completed, dropped or replaced)."""
        if state.revisions and "applied" not in state.revisions[-1] and state.status not in {"completed", "cancelled"}:
            return state.revisions[-1]
        return None

    def revise(self, change: str, redo: list[str]) -> MissionState:
        """Reopen a finished mission for a change the user asked for and redo only the listed Skills.

        Results of the other Skills stay recorded and valid. The redone Skills write into
        artifacts/rev<N>/, so the earlier outputs are kept; their new outputs replace the artifact ids."""
        state = self._load()
        change = change.strip()
        if not change:
            raise ValueError('--revise needs the user\'s change, for example --revise "只能室温反应"')
        redo = list(dict.fromkeys(item.strip() for item in redo if item and item.strip()))
        if not redo:
            raise ValueError("--redo needs the Skill ids to run again, for example --redo constraint-parser,experiment-step-generator")
        unknown = [item for item in redo if item not in self.skills]
        if unknown:
            raise ValueError(f"Unknown Skill id in --redo: {unknown}. Valid ids: {sorted(self.skills)}")
        finished = state.status == "completed" or (
            state.status == "awaiting_decision" and bool(state.plan) and not self._open_positions(state))
        unfinished = self._open_revision(state) if not finished and state.status == "awaiting_decision" else None
        if not finished and not unfinished:
            if state.status in {"awaiting_decision", "waiting_human"} and state.plan:
                # The plan is not finished yet (for example the user asks at a pause to redo the step that just
                # finished): redo it here. Refusing this told the user an administrator had to fix the mission.
                return self._redo_steps(state, change, redo)
            pending = state.pending_action or {}
            if state.status == "waiting_agent":
                raise ValueError(f"{pending.get('skill_id') or 'A Skill'} ({pending.get('id')}) is still waiting for its "
                                 "result: report it first (resume --agent-completed --register-all, or --agent-failed), "
                                 "then run this --revise again.")
            if state.status in {"awaiting_decision", "waiting_human"}:
                raise ValueError("This mission has no plan, so nothing is done in an order to go back to: run act --skill "
                                 "<id> again with the user's change.")
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
        # A redone Skill whose input comes from a kept Skill gets the old file again: a change that lives in
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
        # A mission planned from an experiment flow redoes the listed steps in flow order, each with its review
        # and pause, so a changed result is reviewed again before the user confirms it. A redone Skill that is
        # not a step of the flow makes it the plain --redo list (a pause after every step).
        declared = self.experiment_flows.get((state.flow or {}).get("id") or "")
        revision_plan = flow_revision_plan(declared, state.flow.get("until"), redo) if declared else None
        if revision_plan is not None and not set(redo) <= set(revision_plan["plan"]):
            revision_plan = None
        if revision_plan is not None:
            state.plan, state.plan_pauses = revision_plan["plan"], revision_plan["pauses"]
            state.plan_labels, state.plan_questions = revision_plan["labels"], revision_plan["questions"]
        else:
            state.plan, state.plan_pauses, state.plan_labels, state.plan_questions = redo, None, [], {}
        if state.flow:
            # A revision ends like any revision (act --complete and report), not at the flow's stop question.
            state.flow = {**state.flow, "final_question": None, "next": None}
        state.plan_base = len(state.decisions)
        state.plan_floors = {}  # a new round: positions reopened in the earlier one do not apply
        state.status, state.supervisor_status, state.block_reason = "awaiting_decision", "needs_action", None
        state.replan_required = False
        state.pending_action = state.pending_ticket = None
        state.observations.append({"action_id": f"revision:{number}", "status": "revision_requested",
                                   "summary": change, "redo": redo, "kept": kept})
        (self.store.run_dir / "artifacts" / f"rev{number}").mkdir(parents=True, exist_ok=True)
        self.store.save(state)
        self.store.event("mission_revised", record)
        return state

    def _redo_steps(self, state: MissionState, change: str, redo: list[str]) -> MissionState:
        """act --revise on a plan that is not finished: go back to the earliest listed step that is done.

        That step and every later step already done open again in this mission (a flow review comes with the step
        it reviews, since it follows it), and the plan goes on from there with its pauses; the earlier results stay
        recorded until the new ones replace them. At a pause the user's message is the change and is recorded."""
        slots = self._plan_slots(state)
        starts = []
        for skill_id in redo:
            done = [index for index in slots if state.plan[index] == skill_id]
            if not done:
                where = (f"it is a later step of the plan and runs in its turn" if skill_id in state.plan
                         else f"it is not a step of this plan ({', '.join(dict.fromkeys(state.plan))})")
                raise ValueError(f"{skill_id} has not run in this mission yet: {where}. --redo takes steps that are "
                                 "done.")
            position = max(done)
            if position < len(state.plan_labels) and state.plan_labels[position]:
                raise ValueError(f"{skill_id} at step {position + 1} is a review ({state.plan_labels[position]}): it "
                                 f"runs again with the step it reviews. Put {state.plan[position - 1]} in --redo.")
            starts.append(position)
        if state.status == "waiting_human":
            # Only after --redo is valid: recording ends the pause, and a refused redo left the mission no longer
            # waiting. Refused for an approval and in the turn that asked.
            state = self._record_turn_reply(state)
        start = min(starts)
        reopened = sorted(index for index in slots if index >= start)
        floor = len(state.decisions)
        state.plan_floors = {**(state.plan_floors or {}), **{str(index): floor for index in reopened}}
        number = sum(1 for item in state.observations if item.get("status") == "redo_requested") + 1
        steps = list(dict.fromkeys(state.plan[index] for index in reopened))
        state.observations.append({"action_id": f"redo:{number}", "status": "redo_requested", "summary": change,
                                   "redo": steps, "positions": reopened, "floor": floor,
                                   "at": datetime.now(timezone.utc).isoformat()})
        state.status, state.supervisor_status, state.block_reason = "awaiting_decision", "needs_action", None
        state.replan_required = False
        state.pending_action = state.pending_ticket = None
        self.store.save(state)
        self.store.event("mission_redo", {"number": number, "change": change, "positions": reopened})
        return state

    def _open_redo(self, state: MissionState) -> dict[str, Any] | None:
        """The latest redo (_redo_steps) while one of its reopened positions is still open."""
        record = next((item for item in reversed(state.observations) if item.get("status") == "redo_requested"), None)
        if record is None or int(record.get("floor") or 0) < state.plan_base:
            return None  # none, or one from before a revision started a new round
        slots = self._plan_slots(state)
        return record if any(index not in slots for index in record.get("positions") or []) else None

    def _previous_outputs(self, state: MissionState, skill_id: str) -> list[str]:
        """Output paths of this Skill's latest success before the current round."""
        for key in sorted(state.skill_executions, key=_action_number, reverse=True):
            item = state.skill_executions[key]
            if (item.get("skill_id") == skill_id and item.get("status") in _SUCCEEDED
                    and _action_number(key) <= state.plan_base):
                return [str(path) for path in (item.get("outputs") or {}).values()]
        return []

    def _plan_progress(self, state: MissionState) -> list[dict[str, Any]]:
        """Per plan step: done / failed / waiting / next / pending, from the recorded executions."""
        pending_skill = (state.pending_action or {}).get("skill_id")
        slots = self._plan_slots(state)
        progress: list[dict[str, Any]] = []
        next_marked = False
        for position, skill_id in enumerate(state.plan):
            executions = self._step_executions(state, skill_id)
            # Only the earliest open position of a Skill (one listed more than once) can be the one it works on.
            first_open = position == next((index for index, step in enumerate(state.plan)
                                           if step == skill_id and index not in slots), None)
            if position in slots:
                status = "done"
            elif first_open and pending_skill == skill_id and state.status in {"waiting_agent", "waiting_human"}:
                status = "waiting"
                next_marked = True
            elif (first_open and executions
                  and executions[-1].get("status") in {"failed", "timed_out", "reconciled_failed"}):
                status = "failed"
                next_marked = True
            elif not next_marked:
                status = "next"
                next_marked = True
            else:
                status = "pending"
            description = str(self.knowledge.get(skill_id, {}).get("description") or "")
            entry: dict[str, Any] = {"skill_id": skill_id, "status": status, "description": description[:60]}
            if position < len(state.plan_labels) and state.plan_labels[position]:
                entry["label"] = state.plan_labels[position]
            if state.plan_pauses is not None and position in state.plan_pauses and not state.run_through:
                entry["pause"] = state.plan_questions.get(str(position)) or True
            skill = self.skills.get(skill_id)
            if skill is not None and skill.side_effect_level != "read_only":
                entry["side_effect_level"] = skill.side_effect_level
            progress.append(entry)
        return progress

    def _cache_arg(self) -> str:
        cache = self.store.run_dir.parent.parent
        return cache.name if cache.name == "labontology_workspace_cache" else str(cache)

    @staticmethod
    def _answered_this_turn(state: MissionState) -> bool:
        """True when the user's message of this FounDryClaw turn already answered a question of this mission."""
        turn = _current_turn()
        return bool(turn) and any(item.get("turn") == turn for item in state.observations
                                  if item.get("status") in {"human_answer", "human_approved", "rejected"})

    @staticmethod
    def _is_approval(action: dict[str, Any] | None) -> bool:
        """A Skill action paused for the user's approval (policy or significant impact), not a question: it needs
        an explicit resume --confirm or --reject. One paused for uncertainties is a question."""
        if not isinstance(action, dict) or action.get("kind") != "skill":
            return False
        assessment = action.get("assessment") or {}
        return not (assessment.get("uncertainties") or assessment.get("authenticity_gaps"))

    def _reply_pending(self, state: MissionState) -> bool:
        """The open question was asked in an earlier turn and this turn has not answered anything yet: the user's
        message of this turn is the reply, and the next act records it."""
        turn = _current_turn()
        return (state.status == "waiting_human" and bool(turn) and not self._is_approval(state.pending_action)
                and (state.pending_action or {}).get("asked_turn") != turn and not self._answered_this_turn(state))

    def _record_turn_reply(self, state: MissionState) -> MissionState:
        """Record the user's message of this turn as the answer to the open question, before the act it led to.

        Refused while the question is still the user's to answer (asked in this turn, or this turn's message
        already answered an earlier one), for an approval (resume --confirm / --reject), and outside FounDryClaw,
        where no turn says which message is the reply (resume --answer records it there)."""
        pending = state.pending_action or {}
        question = (state.pending_ticket or {}).get("question") or state.block_reason or ""
        if self._is_approval(pending):
            raise ValueError(
                f"{pending.get('skill_id')} waits for the user's approval. In the user's reply, run resume --confirm "
                "--answer \"<the user's exact reply>\" to approve or resume --reject --answer \"<the user's exact "
                "reply>\" to decline; another act cannot decide it. If the user has not replied yet, relay this and "
                f"end the turn: {question}")
        turn = _current_turn()
        if not turn:
            raise ValueError("The mission is waiting for the user's answer. Record it first: resume --answer "
                             "\"<the user's exact message>\"; then run this act again.")
        if not self._reply_pending(state):
            raise _unanswered_error(question)
        reply = os.environ.get(USER_MESSAGE_ENV, "").strip() or "（用户在这一轮的消息中回复了这个问题，原文见对话）"
        self._feedback("mission_resumed", pending.get("skill_id"), {"action_id": pending.get("id"),
                                                                    "from_status": state.status})
        state = self._observe(state, "human_answer", reply[:4000], turn=turn, recorded_from="turn")
        # The act that follows is the decision taken with this reply in view.
        state.replan_required = False
        return state

    def _do_next(self, state: MissionState, candidates: list[dict[str, Any]],
                 retry_candidates: list[dict[str, Any]], progress: list[dict[str, Any]]) -> list[str]:
        """Exact next commands for the host Agent, filled in from the mission state."""
        lines = self._do_next_lines(state, candidates, retry_candidates, progress)
        if self._answered_this_turn(state):
            # One user message answers one question; a model that re-sends it with every command loops.
            if state.status == "waiting_human":
                lines = ["The user's message in this turn already answered an earlier question and is recorded. This "
                         "new question waits for the user's next message: your turn ends with your written reply. Do "
                         "not start the next step in this turn (act would be refused); reading the output files below "
                         "is fine.", *lines]
            elif state.status in {"waiting_agent", "awaiting_decision", "running"}:
                lines = ["The user's message in this turn is already recorded as the answer: do not send it again.",
                         *lines]
        last = state.observations[-1] if state.observations else {}
        if state.status == "awaiting_decision" and last.get("status") == "rejected":
            # Without this the plan's next step was the declined action itself, offered again.
            declined = next((item.get("skill_id") for item in reversed(state.decisions)
                             if item.get("id") == last.get("action_id")), None) or "the action"
            script = "python .claude/skills/labontology/scripts/labontology.py"
            base = f"--cache-dir {self._cache_arg()} --mission-id {state.mission_id}"
            # --complete needs a Skill result; with none (a device action declined at once) the task is cancelled.
            finish = (f"{script} act {base} --complete" if any(
                item.get("status") in _SUCCEEDED for item in state.skill_executions.values())
                else f"{script} act {base} --cancel --reason \"the user declined {declined}\"")
            lines = [f"The user declined {declined}: do not run it again unless the user asks for it. To finish here, "
                     f"run {finish} and tell the user what was done and that {declined} did not run.", *lines]
        return lines

    def _next_act(self, state: MissionState, progress: list[dict[str, Any]], base: str, script: str) -> str | None:
        """The act that continues the plan once the user has replied (plan confirmation or a step pause)."""
        item = next((entry for entry in progress if entry["status"] in {"next", "failed"}), None)
        if not item:
            return None
        redo = self._review_redo(state, progress.index(item))
        if redo:
            return self._redo_act(item, redo, base, script)
        return (f"{script} act {base} --skill {item['skill_id']}"
                + (f"   (this step: {item['label']})" if item.get("label") else ""))

    @staticmethod
    def _redo_act(item: dict[str, Any], redo: str, base: str, script: str) -> str:
        # An answer that only confirmed a fact ("每种各 0.05 当量", "确认适用于密闭体系") reran the calculator twice
        # for the same table: such a reply goes to the review, not to the reviewed Skill.
        return (f"{script} act {base} --skill {redo}   ({item['label']} did not pass. If the user's reply changes "
                f"what {redo} works from (drop or replace conditions, other values), run {redo} again with that change, "
                f"then the review. If the reply only answers the review's question (confirms a fact, chooses an option) "
                f"and {redo}'s result stays as it is, run the review again with the answer instead: {script} act {base} "
                f"--skill {item['skill_id']}. Without a reply from the user, do neither.)")

    def _do_next_lines(self, state: MissionState, candidates: list[dict[str, Any]],
                       retry_candidates: list[dict[str, Any]], progress: list[dict[str, Any]]) -> list[str]:
        script = "python .claude/skills/labontology/scripts/labontology.py"
        base = f"--cache-dir {self._cache_arg()} --mission-id {state.mission_id}"
        pending = state.pending_action or {}
        # Only where the model types the reply itself (--answer). Worded as a note on that command: a model read the
        # earlier "Text that begins with 'Base directory for this skill' is the Skill document, not a reply" as a
        # remark on the conversation and told the user "这条消息是 LabOntology 的说明文本…".
        skill_text = ("About --answer (a note for you; do not repeat it to the user): it is the user's own words from "
                      "their next message, never the text that begins with 'Base directory for this skill' (the Skill "
                      "document).")
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
                "Skills whose results depend on the change>. The --revise text is only the change itself (e.g. "
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
            if self._is_approval(pending):
                return [
                    f"{pending.get('skill_id')} needs the user's approval. Relay this to the user and end the turn: "
                    f"{question}",
                    f"In the user's NEXT message: {script} resume {base} --confirm --answer \"<the user's exact reply>\" "
                    f"to approve, or {script} resume {base} --reject --answer \"<the user's exact reply>\" to decline.",
                    skill_text,
                ]
            following = self._next_act(state, progress, base, script)
            after = (following or f"{script} act {base} --skill <the Skill the reply calls for>   (or --ask, "
                     "--complete ...)")
            if not _current_turn():
                # Outside FounDryClaw no turn says which message is the reply: it is recorded explicitly.
                reply = [f"In the user's NEXT message, run once: {script} resume {base} --answer \"<the user's exact "
                         "message>\"", f"Then: {after}", skill_text]
            elif self._reply_pending(state):
                return [
                    f"The user's message in this turn replies to the question: {question}",
                    f"If it confirms or chooses how to go on, run: {after}. LabOntology records the message as the "
                    "answer when the act runs; do not run resume. A choice in it (for example only some rows) is "
                    "passed to that Skill as its document allows.",
                    f"If it asks to redo a step that is already done (for example the one that just finished, with a "
                    f"change): {script} act {base} --revise \"<the user's change>\" --redo <that step's Skill id>; the "
                    "plan goes back to that step in this mission.",
                    f"If the user stops the task: {script} act {base} --cancel. If the message is about something else, "
                    "answer it and leave the mission waiting.",
                ]
            else:
                # No --answer to type here: LabOntology takes the reply from the user's next turn.
                reply = [f"In the user's NEXT message, run the next command directly: {after}. LabOntology records "
                         "that message as the answer; no resume is needed. If the user stops the task: "
                         f"{script} act {base} --cancel."]
            if pending.get("step_gate"):
                files = ", ".join(str(path) for path in (pending.get("completed_outputs") or {}).values())
                return [
                    "Show the user the result of the step that just finished, then stop. Read these output files "
                    f"(each once) and present the key results, not just 'done': {files}",
                    "State in one sentence any limitation the step reported (for example that no literature was "
                    "available); the step is recorded as done, so do not tell the user to restart or redo it.",
                    f"Then relay this question and end the turn - do NOT start the next step yourself: {question}",
                    *reply,
                ]
            return [f"Relay this to the user and end the turn: {question}", *reply]
        if state.status == "waiting_agent":
            doc = (state.prepared_skill or {}).get("path") or "the prepared SKILL.md"
            steps = [f"Read {doc} and do the Skill's work (run its script if it declares one; write every output "
                     f"file into {self._artifact_dir(state)}). If the user asked for an output at a path of their own "
                     "(for example `--output outputs/result.csv`), also copy that file there; the copy in the folder "
                     "above is the one resume registers. Run resume only after the work has finished and its output "
                     "is written: never in the same batch of tool calls as the Skill's script or the files it reads."]
            running = self.skills.get(pending.get("skill_id") or "")
            folder_outputs = [name for name, template in (running.outputs.items() if running else [])
                              if not Path(str(template or "")).suffix]
            if folder_outputs:
                steps.append(f"{', '.join(folder_outputs)} {'is' if len(folder_outputs) == 1 else 'are'} declared without "
                             "a file type: when the Skill writes it as a folder (an --output-dir), make that folder a "
                             f"new subfolder of {self._artifact_dir(state)}; --register-all registers the folder.")
            position = next((index for index, item in enumerate(progress) if item["status"] == "waiting"), None)
            if position is not None and progress[position].get("label"):
                reviewed = self._plan_slots(state).get(position - 1) or {}
                files = ", ".join(str(path) for path in (reviewed.get("outputs") or {}).values())
                steps.append(
                    f"This step is a review of the experiment flow: {progress[position]['label']}"
                    + (f" ({files})" if files else "") + ". Give the verdict and the findings in --summary. A verdict "
                    "that blocks the experiment is reported with --agent-failed, the findings and what must change "
                    "(the Runtime then asks the user; after the reply the reviewed Skill runs again with the change, "
                    "then this review); a verdict that needs a person's judgement goes into the summary, so the user "
                    "sees it when asked to confirm.")
                runs = self._step_executions(state, progress[position]["skill_id"])
                answer = (self._review_reply(state, progress[position - 1]["skill_id"])
                          if len(runs) > 1 and runs[-2].get("status") == "failed" else "")
                if answer:
                    steps.append(f"The previous review of this result did not pass and the user answered: {answer[:300]}. "
                                 "Take that answer into account in this verdict; do not ask the user the same question "
                                 "again.")
            redo_of = next((item for index, item in enumerate(progress)
                            if self._review_redo(state, index) == pending.get("skill_id")), None)
            if redo_of is not None:
                runs = self._step_executions(state, redo_of["skill_id"])
                findings = str((runs[-1] if runs else {}).get("error") or "")[:300]
                reply = self._review_reply(state, pending.get("skill_id"))
                steps.append(
                    f"{redo_of['label']} did not pass" + (f": {findings}" if findings else "") + ". "
                    + (f"The user replied: {reply[:300]}. " if reply else "")
                    + f"Run {pending.get('skill_id')} again with that change in its inputs (a Skill that reads the "
                    "user's instruction gets it with the change written in; a choice such as dropping some rows goes "
                    "in as the Skill's document allows). Never edit its earlier output. "
                    + self._new_name_note(state)
                    + f" After resume, the review runs again (act --skill {redo_of['skill_id']}).")
            redo_record = self._open_redo(state)
            if redo_record and pending.get("skill_id") in redo_record.get("redo", []):
                steps.append(
                    f"The user asked to redo this step: {redo_record['summary']}. Run {pending.get('skill_id')} again "
                    "with that change in its inputs (a Skill that reads the user's instruction gets it with the change "
                    "written in; a choice such as which rows to keep goes in as the Skill's document allows, for "
                    "example --rows numbers of the table it reads). Never edit its earlier output. "
                    + self._new_name_note(state)
                    + " An output identical to the earlier one is refused: then the change did not reach its inputs.")
            revision = self._open_revision(state)
            if revision and pending.get("skill_id") in revision.get("redo", []):
                previous = self._previous_outputs(state, pending["skill_id"])
                from_kept = (revision.get("inputs_from_kept") or {}).get(pending["skill_id"]) or {}
                steps.append(
                    f"Revision {revision['number']}: the user changed: {revision['change']}. Run this Skill again "
                    "with that change in its inputs: a Skill that reads the user's instruction gets the original "
                    "instruction with the changed value rewritten in place (for example '…80 ℃ 反应 12 小时' becomes "
                    "'…100 ℃ 反应 12 小时'; only when a value cannot be replaced cleanly, append '；修改：<the change>'); "
                    "a Skill that reads an earlier step's file uses the file in `mission.artifacts`. Rerunning on "
                    "unchanged inputs repeats the old result."
                    + (f" Its previous output: {', '.join(previous)}." if previous else "")
                    + (f" Its input {', '.join(from_kept)} comes from kept {', '.join(dict.fromkeys(from_kept.values()))}"
                       ": if the change is in that input, this rerun cannot apply it - report it failed." if from_kept else ""))
                steps.append(
                    "Before resume, read the new output and check that the change is really in it: in the fields the "
                    "Skill records, or, for a value the Skill has no field for (e.g. a temperature in a parser that "
                    "only records materials), in its copy of the instruction such as `source_text` - that counts as "
                    "applied. Decide this once, here; after --complete the mission cannot be cancelled. If the change "
                    f"is not there, run {script} resume {base} --agent-failed --summary \"<what is still wrong>\" "
                    "instead of registering it. Never edit an earlier output, an input file or a Skill's own files "
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
            for position, item in enumerate(progress):
                if item["status"] in {"next", "failed", "waiting"}:
                    redo = self._review_redo(state, position)
                    if redo:
                        # Also a mission whose review failed before it asked the user: the change may not be known.
                        return [self._redo_act(item, redo, base, script),
                                "If the user has not said what to change yet, ask first: "
                                f"{script} act {base} --ask \"<what to change>\", then end the turn."]
                    ready = next((c for c in candidates if c["id"] == item["skill_id"]), None)
                    skill = self.skills.get(item["skill_id"])
                    waived = self._flow_waived_inputs(state, skill) if skill else set()
                    missing = [a for a in (skill.input_artifacts if skill else [])
                               if a not in state.artifacts and a not in waived]
                    earlier = {out for step in state.plan[:position]
                               for out in (self.skills[step].outputs if step in self.skills else {})}
                    external = [a for a in missing if a not in earlier]
                    if external:
                        note = ("   (the mission does not hold input " + str(external) + ": add "
                                + " ".join(f"--input {a}=<path of that file>" for a in external) + " to this act; a "
                                "file the user uploaded counts, otherwise ask the user for the file)")
                    elif missing:
                        note = f"   (waiting for input {missing}: run the previous plan step first)"
                    else:
                        note = ""
                    steps = [f"{script} act {base} --skill {item['skill_id']}{note}"
                             + (f"   (this step: {item['label']})" if item.get("label") else "")]
                    redo_record = self._open_redo(state)
                    if redo_record and position in (redo_record.get("positions") or []):
                        steps.append(
                            f"The user asked to redo: {redo_record['summary']}. From this step on, "
                            f"{', '.join(redo_record['redo'])} run again in plan order (each with its review and "
                            "pause); the earlier results stay recorded until the new ones replace them.")
                    revision = self._open_revision(state)
                    if revision and not self._plan_slots(state):
                        steps.append(
                            f"Revision {revision['number']} (the user changed: {revision['change']}): redo "
                            f"{', '.join(revision['redo'])}; keep {', '.join(revision['kept']) or 'nothing else'}."
                            + (f" Tell the user in one sentence why {', '.join(revision['kept_with_changed_inputs'])} "
                               "stay valid although an input is regenerated, or add them to --redo."
                               if revision.get("kept_with_changed_inputs") else ""))
                        for skill_id, inputs in (revision.get("inputs_from_kept") or {}).items():
                            makers = list(dict.fromkeys(inputs.values()))
                            steps.append(
                                f"{skill_id} reads {', '.join(f'{a} (made by {p}, kept)' for a, p in inputs.items())}. If "
                                "the change is in that input (for example a condition of the user's instruction, which "
                                f"{', '.join(makers)} turns into it), rerunning {skill_id} alone repeats the old result: "
                                f"run {script} act {base} --revise \"<the change>\" --redo "
                                f"{','.join(dict.fromkeys([*makers, *revision['redo']]))} instead (it replaces revision "
                                f"{revision['number']}).")
                    return steps
            flow = state.flow or {}
            if flow.get("final_question") or flow.get("next"):
                # The plan ends at the flow's stop point; the flow's checkpoint there is the user's decision.
                following = dict(flow.get("next") or {})
                following.setdefault("skill", following.get("worker"))  # missions planned before the rename
                lines = [f"All plan steps of the experiment flow {flow.get('name') or flow.get('id')} up to "
                         f"{flow.get('until') or 'its end'} are done. Show the results"
                         + (f" and ask the user: {flow['final_question']}" if flow.get("final_question") else "")
                         + ". End the turn there."]
                if following.get("skill"):
                    lines.append(f"Only if the user then asks to go on: {script} act {base} --skill {following['skill']}"
                                 + ("   (a device action: the Runtime asks for the user's confirmation first)"
                                    if self.skills.get(following["skill"]) is not None
                                    and self.skills[following["skill"]].side_effect_level != "read_only" else ""))
                lines.append(f"When the user is finished (for example '结束吧' or '先不创建设备任务'): {script} act {base} "
                             "--complete, which keeps the results; not --cancel (refused once the plan is done).")
                return lines
            return [f"{script} act {base} --complete   (all plan steps are done), then report the results to the user"]
        # A Skill that lacks an input stays on the list (after the ready ones, unless the goal names it), with how
        # to give that input: listing only the ready ones hid the Skill the user asked for when its input was a
        # file uploaded after the mission started, and the model kept retrying resume.
        usable = [c for c in candidates if not c["missing_capabilities"]] or candidates
        usable = sorted(usable, key=lambda c: (c["match_score"] < 100, bool(c["missing_inputs"])))
        steps = []
        # Without a plan nothing says when the goal is met: after a Skill succeeded the model was only offered
        # more Skills, and it ended the turn without --complete (the mission stayed open).
        done = list(dict.fromkeys(
            item.get("skill_id") for _, item in sorted(state.skill_executions.items(), key=lambda kv: _action_number(kv[0]))
            if item.get("status") in _SUCCEEDED))
        if done:
            steps.append(f"{', '.join(done)} finished. If that meets the user's goal: {script} act {base} --complete, "
                         "then report the results to the user. Only if the goal needs another step:")
        if candidates and "selection_note" in candidates[0]:
            # candidate_review: no Skill matched the goal's words, so every registered Skill is listed.
            return steps + [
                "No Skill matched the words of the goal, so `skills` lists every registered Skill with its "
                "description and `document`. Read the SKILL.md of the ones whose description could fit (each once) "
                "and decide from the document; do not tell the user the ability is missing before reading them.",
                f"When one covers the goal: {script} act {base} --skill <id>",
                "If none does: tell the user the task has not started and why (coverage_diagnostic.user_message). For "
                f"routine read-only work you may ask {script} act {base} --ask \"<may the Agent do it directly?>\"; "
                "only after the user agrees, submit an agent_fallback decision (see references/runtime-protocol.md)."]
        steps.append(f"Choose one Skill from {[c['id'] for c in usable]}, then run: {script} act {base} --skill <id>")
        needs: dict[tuple[str, ...], list[str]] = {}
        for card in usable:
            if card["missing_inputs"]:
                needs.setdefault(tuple(card["missing_inputs"]), []).append(card["id"])
        for missing, needing in needs.items():
            makers = [skill_id for skill_id, skill in self.skills.items()
                      if skill_id not in needing and any(a in skill.outputs for a in missing)][:2]
            steps.append(
                f"{', '.join(needing)} {'needs' if len(needing) == 1 else 'need'} {list(missing)}, which the mission "
                "does not hold: add " + " ".join(f"--input {a}=<path of that file>" for a in missing) + " to its act. "
                "A file the user uploaded counts (its path is in the message's attachment list)"
                + (f"; without one, run {' or '.join(makers)} first, which makes it" if makers else "") + ".")
        return steps + [
            f"These are only the closest word matches: any registered Skill can be chosen the same way, for example "
            f"one the user asked for by name (`{script} inspect --cache-dir {self._cache_arg()} --skills` "
            "lists them). Do not ask the user whether to use a Skill they already asked for.",
            f"If nothing fits or an input is missing: {script} act {base} --ask \"<one question for the user>\""]

    def context(self) -> dict[str, Any]:
        state = self._load()
        artifact_dir = self._artifact_dir(state)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        candidates, excluded_skills, matched = self._candidate_cards(state)
        historical_experiences = self.store.experiences.search(
            state.goal, skill_ids=[card["id"] for card in candidates] if matched else []
        )
        fallback = {
            "fallback_available": True,
            "fallback_scope": "low_risk_read_only",
            "fallback_message": (
                "如果这是低风险、只读分析，可以由 Agent 直接尝试，"
                "结果会标记为 Agent 直接执行。是否继续？"
            ),
        }
        if not candidates:
            coverage_diagnostic = {
                "status": "no_registered_skill",
                "execution_started": False,
                "registered_skill_count": len(self.skills),
                "candidate_count": 0,
                **fallback,
                "user_message": (
                    "当前没有找到可用的实验能力，任务还没有开始。"
                    "请先安装或初始化相关能力。"
                ),
            }
        elif not matched:
            coverage_diagnostic = {
                "status": "candidate_review",
                "execution_started": False,
                "registered_skill_count": len(self.skills),
                "candidate_count": len(candidates),
                **fallback,
                "user_message": (
                    "当前已登记实验能力，但任务关键词没有直接匹配，任务还没有开始。"
                    "请先读取候选 Skill 的完整说明确认是否适用，确认后再开始执行。"
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
            # Only the Skill's latest run in this round, and only while its step is not done: a failed run that
            # was then retried successfully stayed a candidate, and do_next (which puts retries before the plan's
            # next step) had the Skill run again after its step was done.
            if (execution.get("status") in {"failed", "timed_out"}
                    and _action_number(action_id) > state.plan_base
                    and execution.get("retryable") is True
                    and skill is not None
                    and skill.side_effect_level == "read_only"
                    and execution.get("retry_count", 0) < skill.retry_limit
                    and self._step_executions(state, skill.id)[-1] is execution
                    and self._skill_open(state, skill.id)
                    # A failed flow review is not retried on the same result (missions from before reviews were
                    # marked review_not_passed): the reviewed Skill runs again first.
                    and not self._review_redo(state, self._open_review_index(state, skill.id) or 0)):
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
        execution_cycle = {
            "entrypoint": "act",
            "after_act": "reconcile" if waiting_for_reconcile else ("resume" if waiting_for_resume else "context"),
            "requires_resume": waiting_for_resume,
            "requires_reconcile": waiting_for_reconcile,
            "resume_mode": (
                "agent_native" if native_fallback_waiting
                else "external_skill" if state.status == "waiting_agent"
                else "human_decision" if state.status == "waiting_human"
                else None
            ),
            "status": state.status,
        }
        if state.status in {"completed", "cancelled"}:
            next_step = f"Mission is {state.status}; report its recorded state and create a new mission for a new goal."
        elif state.status == "running":
            next_step = "Host Agent: reconcile the interrupted action before choosing another Skill."
        elif state.status == "waiting_agent":
            next_step = (
                "Host Agent: follow the prepared Skill document; optionally use its script accelerator, "
                "then call resume with the actual result (the resume output is already the new context; "
                "do not run context again)."
            )
        elif state.status == "waiting_human":
            next_step = ("Host Agent: follow do_next. A question is answered by the user's next message (the next act "
                         "records it); an approval needs resume --confirm or --reject with the user's reply.")
        elif state.replan_required:
            next_step = (
                "Host Agent: this output already is the current context, so do not run context again. Reassess the "
                "goal with the human answer and select one Skill from `skills`, Read its SKILL.md, run prepare-skill, "
                "write the decision file, then run act. If your previous Skill decision was paused because its "
                "assessment listed uncertainties, the user's reply does not run it: write that decision again with "
                "uncertainties [] and assessment.authorization set to the user's reply, then run act; "
                "for an explicitly approved low-risk read-only fallback, use agent_fallback; "
                "do not complete or compute outside a Skill or approved fallback."
            )
        else:
            next_step = ("Host Agent: this output already is the current context, so do not run context again. Choose the "
                     "next action: read the SKILL.md of one Skill from `skills`, run prepare-skill, write the decision "
                     "file, then run act; call resume only when the execution_cycle requires it.")
        plan_progress = self._plan_progress(state)
        do_next = self._do_next(state, candidates, retry_candidates, plan_progress)
        notice = {"notice": self.notice} if self.notice else {}
        return {**notice, "mission": state.to_dict(), "skills": candidates, "candidate_count": len(candidates),
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
                "execution_cycle": execution_cycle,
                "historical_experiences": historical_experiences,
                "next": next_step}

    def prepare_skill(self, skill_id: str) -> dict[str, Any]:
        """Read the selected Skill and persist the exact document digest."""
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
                             "--revise \"<back to the earlier value>\" --redo <Skill ids>.")
        if state.status == "completed":
            raise ValueError("The mission is already completed: there is nothing to run or complete. To change a result "
                             "run act --revise \"<the user's change>\" --redo <Skill ids>; otherwise answer the user "
                             "from mission.artifacts.")
        if state.status == "waiting_human":
            state = self._record_turn_reply(state)
        if state.status == "waiting_agent":
            pending = state.pending_action or {}
            pending_skill = pending.get("skill_id") or "The Agent fallback"
            if (decision.get("kind") == "skill" and decision.get("skill_id") == pending.get("skill_id")
                    and not decision.get("retry_of")):
                # The same act again: refusing it made a model send it four more times (it never saw that the
                # Skill was already issued). Say so and give the current context.
                self.notice = (f"{pending_skill} is already issued ({pending.get('id')}) and waits for its work, so "
                               "this act changed nothing. Do not run act again: do what `do_next` below says (read "
                               "its SKILL.md, write its outputs into artifact_dir), then report it with resume.")
                return state
            raise ValueError(f"{pending_skill} ({pending.get('id')}) is still waiting for its result: do its work and "
                             "report it first with resume --agent-completed --register-all (or --agent-failed if it "
                             "really failed); then choose the next action.")
        if state.status != "awaiting_decision":
            raise ValueError(f"Cannot replace an action while mission is {state.status}")
        action = deepcopy(decision)
        if not isinstance(action.get("reason"), str) or not action["reason"].strip():
            raise ValueError("Decision requires a reason: put a non-empty \"reason\" field in the decision file, or pass "
                             "act --decision-file <file> --reason \"<why>\"")
        kind = action.get("kind")
        if kind not in {"skill", "request_human", "agent_fallback", "complete", "cancel"}:
            raise ValueError("Decision kind must be skill, request_human, agent_fallback, complete or cancel")
        if kind == "complete" and state.replan_required:
            raise ValueError("Human answer received; replan in context and select a Skill before completing")
        revision = self._open_revision(state)
        if kind == "cancel" and not revision and state.plan and not self._open_positions(state):
            # "先不创建设备任务，结束吧" at the flow's stop cancelled two missions whose plan was done.
            raise ValueError("All plan steps of this mission are done, so there is nothing to cancel: end it with act "
                             "--complete (the results stay) and tell the user what was produced. --cancel stops a task "
                             "before its steps are done.")
        if kind == "complete" and revision:
            missing = list(dict.fromkeys(state.plan[index] for index in self._open_positions(state)))
            if missing:
                raise ValueError(
                    f"Revision {revision['number']} (the user's change: {revision['change']}) has not redone "
                    f"{', '.join(missing)} yet, so completing now would present the old results as changed. Run "
                    f"act --skill {missing[0]}. If the change cannot be applied (the Skill cannot take it or failed) "
                    "or the user drops it, run act --cancel --reason \"<why>\": that closes only revision "
                    f"{revision['number']} and keeps the results from before the change.")
        if kind == "skill":
            if action.get("skill_id") not in self.skills:
                raise ValueError(f"Unknown registered Skill: {action.get('skill_id')}")
            if self._uncontracted(action["skill_id"]):
                raise ValueError(f"Skill has no instruction document (SKILL.md) and cannot be selected: {action['skill_id']}")
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
            # Which answers can approve the Agent fallback. The Runtime cannot judge the wording, so it rules out the
            # questions that are clearly about something else: a plan confirmation or a step pause (the mission has a
            # plan; with no word match, a plan confirmation used to count) and, once a Skill matched the goal, any
            # question after a Skill action was issued. Word matching alone was no sign: loose matches ("帮我",
            # "规划" in a PCR request matching MOF Skills) made the fallback impossible.
            action["fallback_offered"] = not state.plan and (
                not self._candidate_cards(state)[2]
                or not any(item.get("kind") == "skill" for item in state.decisions))
        action["id"] = f"action:{len(state.decisions) + 1}"
        action["action_id"] = action["id"]
        action["return_to"] = "labontology-skill"
        action["ticket_status"] = "issued"
        # resume --register-all looks for this action's files written into a mistyped mission folder after this.
        action["issued_at"] = datetime.now(timezone.utc).isoformat()
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
                raise ValueError("Cannot complete without a successful Skill result")
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
            concerns.append("影响较大：" + assessment["rationale"])
        if any(p.requires_confirmation and skill.id in p.applies_to for p in self.policies):
            # The user reads this question: name the action (it said only "Explicit execution policy requires
            # human confirmation").
            concerns.append(self._approval_question(skill))
        if concerns:
            return self._wait_human(state, "；".join(concerns))
        return self._execute(state)

    def _approval_question(self, skill: SkillSpec) -> str:
        """The question for a Skill whose manifest requires the user's confirmation, naming what it does."""
        description = " ".join(str(self.knowledge.get(skill.id, {}).get("description") or "").split())
        if len(description) > 120:
            cut = max(description.rfind("；", 0, 120), description.rfind("。", 0, 120))
            description = description[:cut + 1] if cut > 0 else description[:120] + "…"
        kind = "设备动作" if skill.side_effect_level != "read_only" else "需要你确认的动作"
        return (f"即将执行 {skill.id}" + (f"（{description.rstrip('。；')}）" if description else "")
                + f"。这是{kind}，需要你明确确认后才会执行。是否确认执行？")

    def _agent_fallback_error(self, state: MissionState, action: dict[str, Any]) -> str | None:
        if not state.fallback_approval:
            return ("Agent fallback requires an explicit human approval first: the user's answer to an act --ask "
                    "question asked before any Skill action of this mission (not a plan confirmation or a step pause); "
                    "a rejection or other answer does not count")
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
        waived = self._flow_waived_inputs(state, skill)
        missing = [a for a in skill.input_artifacts
                   if a not in waived and (a not in artifacts or not Path(artifacts[a]).exists())]
        if missing:
            return f"Required inputs missing: {missing}"
        return None

    def _flow_waived_inputs(self, state: MissionState, skill: SkillSpec) -> set[str]:
        """Inputs that do not block a step of an experiment-flow plan: ones only Skills outside the plan make.

        Inputs are partly inferred from the Skills a SKILL.md mentions (fdu-multi-step-json "calls fdu-step-json
        internally", so it seemed to need fdu-step-json's outputs). The device's declared flow says which steps
        feed which, so such an input never blocks the flow; an input no Skill makes (a user's file) still does."""
        if not state.flow or skill.id not in state.plan:
            return set()
        planned = set(state.plan)
        waived = set()
        for artifact in skill.input_artifacts:
            makers = {skill_id for skill_id, spec in self.skills.items() if artifact in spec.outputs}
            if makers and not makers & planned:
                waived.add(artifact)
        return waived

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
        """Require a fresh read for imported Skills.

        Hand-built legacy skills without an instruction source keep their old
        behavior; imported Skills are always checked at the action
        boundary and again immediately before execution.
        """
        source = self.knowledge.get(skill.id, {}).get("instruction_source")
        if not isinstance(source, dict) or not source.get("path"):
            return None
        prepared = state.prepared_skill
        if not isinstance(prepared, dict) or prepared.get("skill_id") != skill.id:
            return "Skill requires prepare_skill before execution"
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
        # A question asked in this turn is answered by a later message (see _record_turn_reply).
        state.pending_action["asked_turn"] = _current_turn() or None
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
        # Every Skill is executed through the prepared document contract. A
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
        only_answer = bool(answer.strip()) and not (agent_completed or agent_failed or summary.strip()
                                                    or provided_artifacts or confirmed or rejected)
        if only_answer and state.status not in {"waiting_human", "running"}:
            # Nothing waits for an answer. Refusing made models send it again and again; say so and go on.
            already = self._answered_this_turn(state)
            self.notice = (
                ("The user's message in this turn is already recorded as the answer" if already else
                 f"Nothing waits for an answer (mission status is {state.status}), so this changed nothing")
                + ". Do not send it again: do what `do_next` below says"
                + (" (a Skill action is pending: do its work, then report it)." if state.status == "waiting_agent"
                   else "."))
            return state
        if state.status not in {"waiting_human", "waiting_agent"}:
            hint = {
                "awaiting_decision": (
                    "The previous answer or result is already recorded (see the last observation), so `resume` has "
                    "nothing to do. Do not call resume again. Choose one Skill from the last output's `skills`, "
                    "Read its SKILL.md, run prepare-skill, write the decision file, then run act."),
                "completed": ("The mission is completed; report the result to the user. If the user changes a "
                              "condition of this task, use `act --revise \"<change>\" --redo <Skill ids>` on this "
                              "mission instead of creating a new one."),
                "cancelled": "The mission is cancelled; tell the user.",
            }.get(state.status, "Read the current state with context once and decide the next command.")
            raise ValueError(f"Nothing is waiting for a resume: mission status is {state.status}. {hint}")
        if state.status == "waiting_human":
            if (confirmed or rejected) and not answer.strip():
                raise ValueError("Record the actual user reply when approving or rejecting an action")
            # One user message answers one question, and only one asked before it: FounDryClaw sets a new turn id
            # for every user message. Without it (CLI, offline runs) there is no turn to compare and nothing changes.
            turn = _current_turn()
            if (answer.strip() or confirmed or rejected) and turn and (
                    self._answered_this_turn(state) or (state.pending_action or {}).get("asked_turn") == turn):
                raise _unanswered_error((state.pending_ticket or {}).get("question") or state.block_reason or "")
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
                        "This pending Skill action asks for the user's approval: a plain --answer does not decide it. "
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
            if confirmed or rejected:
                self.notice = ("Nothing waits for an approval: a Skill action is already running. Do its work, then "
                               "report it (see `do_next`).")
            return state
        too_soon = self._resumed_in_same_batch(state.pending_action)
        if too_soon:
            raise ValueError(too_soon)
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
        review_error = self._review_report_error(state, skill, summary, provided_artifacts or {})
        if review_error:
            raise ValueError(review_error)
        if agent_failed:
            if not summary.strip():
                raise ValueError("Failed Agent execution requires an explanation")
            # A review step of an experiment flow that fails means the reviewed result did not pass: retrying the
            # review on the same result blocks again, so the user decides the change (see _review_not_passed).
            review = self._open_review_index(state, skill.id)
            state.skill_executions[state.pending_action["id"]] = {
                "id": state.pending_action["id"], "skill_id": skill.id, "status": "failed",
                "outputs": {}, "error": summary, "evidence": evidence or [],
                "failure_kind": "review_not_passed" if review is not None else "external_skill",
                "retryable": review is None and skill.side_effect_level == "read_only",
                # A failed retry keeps its count (set from the retried action), so retry_limit ends a chain of retries.
                "retry_count": int(state.pending_action.get("retry_count") or 0),
            }
            state = self._observe(state, "failed", summary, evidence=evidence or [])
            return self._review_not_passed(state, review, summary) if review is not None else state
        outputs = _materialize_artifacts(_artifact_paths(provided_artifacts or {}), self.store.run_dir / "artifacts")
        outputs = _canonical_outputs(skill.outputs, outputs)
        missing = sorted(set(skill.outputs) - outputs.keys())
        if missing:
            given = {Path(path).resolve() for path in outputs.values()}
            files = [f"{path} (given as {artifact_id})" for artifact_id, path in outputs.items()
                     if artifact_id not in skill.outputs]
            files += [path for path in _untracked_artifacts(state, self.store.run_dir / "artifacts")
                      if Path(path).resolve() not in given]
            folders = [name for name in missing if not Path(str(skill.outputs.get(name, ""))).suffix]
            raise ValueError(
                f"Required Agent outputs missing: {missing}. Files that could be it: "
                f"{files[:8] or 'none'}."
                + (f" {', '.join(folders)} may be a folder (the declared output has no file type): give the folder "
                   "the Skill wrote it as." if folders else "")
                + " Say which file is which output: resume --agent-completed "
                + " ".join(f"--provide-artifact {name}=<path of that {'file or folder' if name in folders else 'file'}>"
                           for name in missing)
                + ' --summary "<what happened>" (add --register-all to register the other files too). '
                "If the Skill did not produce it, report --agent-failed with the real reason.")
        redo_record = self._open_redo(state)
        if redo_record and skill.id in redo_record.get("redo", []):
            floor = int(redo_record.get("floor") or 0)
            before = {digest for key, item in state.skill_executions.items()
                      if item.get("skill_id") == skill.id and item.get("status") in _SUCCEEDED
                      and state.plan_base < _action_number(key) <= floor
                      for digest in map(_file_digest, (item.get("outputs") or {}).values()) if digest}
            now = [_file_digest(outputs[name]) for name in skill.outputs if name in outputs]
            if before and now and all(digest in before for digest in now):
                raise ValueError(
                    f"The new output of {skill.id} is identical to its output before the redo, so the user's change "
                    f"({redo_record['summary']}) did not reach its inputs. Run it again with the change in its inputs, "
                    "or report resume --agent-failed --summary \"<why the change cannot be applied>\".")
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

        The mission moves to waiting_human with a ticket, so the next Skill action is refused until the
        user has seen the result and answered (unless the user asked for --run-through)."""
        if state.run_through or skill_id not in state.plan:
            return state
        slots = self._plan_slots(state)
        done = state.skill_executions.get((state.observations[-1] if state.observations else {}).get("action_id"))
        # The position this run filled; a run that filled none (a repeat of a step already done) does not pause.
        position = next((index for index, item in slots.items() if done is not None and item is done), None)
        remaining = [index for index in range(len(state.plan)) if index not in slots]
        if position is None or not remaining:
            return state
        if state.plan_pauses is not None and position not in state.plan_pauses:
            return state  # an experiment flow pauses only where it asks the user (see core/runtime/flows.py)
        label = state.plan_labels[position] if position < len(state.plan_labels) else ""
        # The summary often repeats the step name ("constraint-parser 已完成：…"), which the question already says.
        brief = re.sub(rf"^\s*{re.escape(skill_id)}\s*(?:已完成|完成)?\s*[：:，,]\s*", "", summary.strip())
        brief = brief[:300].rstrip("。．.；;，,：: ")  # the sentence goes on with "。下一步是…"
        flow_question = state.plan_questions.get(str(position), "").strip().rstrip("。？?")
        question = (f"步骤 {position + 1}/{len(state.plan)}（{skill_id}" + (f"：{label}" if label else "") + "）已完成"
                    + (f"：{brief}" if brief else "")
                    + f"。下一步是 {state.plan[remaining[0]]}。"
                    + (f"{flow_question}？" if flow_question else "是否继续？"))
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

    def _review_not_passed(self, state: MissionState, position: int, summary: str) -> MissionState:
        """A flow review did not pass: wait for the user's change. The reply leads to the reviewed Skill run again
        with the change and then the review (see _review_redo); before, do_next offered to retry the review on the
        same result and the user's reply was not recorded."""
        reviewed = state.plan[position - 1]
        label = state.plan_labels[position] if position < len(state.plan_labels) else f"审查 {reviewed} 的结果"
        brief = summary.strip()[:400].rstrip("。．.；;，,：: ")
        question = (f"{label}未通过：{brief}。请告诉我怎么修改（例如去掉或替换有问题的条件），或回答审查提出的问题："
                    f"需要修改时我会按你的修改重新运行 {reviewed} 再审查，只是回答问题时我会带着你的回答重新审查；"
                    "也可以停止这次任务。")
        action = {"kind": "request_human", "reason": "The review of a flow step did not pass; the user decides the change.",
                  "question": question, "fallback_offered": False, "review_failed": True,
                  "reviewed_skill": reviewed, "id": f"action:{len(state.decisions) + 1}",
                  "return_to": "labontology-skill", "ticket_status": "issued"}
        action["action_id"] = action["id"]
        state.decisions.append(deepcopy(action))
        state.pending_action = action
        state.pending_ticket = action
        state.supervisor_status = "decision_pending"
        self.store.event("agent_decision", action)
        return self._wait_human(state, question)

    @staticmethod
    def _resumed_in_same_batch(action: dict[str, Any] | None) -> str | None:
        """A resume a few seconds after its act came in the same batch of tool calls, so the work could not have
        been done: a model wrote three review verdicts this way before the files they review existed."""
        try:
            issued = datetime.fromisoformat(str((action or {}).get("issued_at") or ""))
        except ValueError:
            return None  # issued before actions were timestamped
        elapsed = (datetime.now(timezone.utc) - issued).total_seconds()
        try:
            minimum = float(os.environ.get(MIN_WORK_SECONDS_ENV, "") or DEFAULT_MIN_WORK_SECONDS)
        except ValueError:
            minimum = DEFAULT_MIN_WORK_SECONDS
        if not 0 <= elapsed < minimum:
            return None
        return (f"{(action or {}).get('skill_id') or 'The action'} ({(action or {}).get('id')}) was issued {elapsed:.1f} s "
                "ago: this resume came in the same batch of tool calls as its act, before the work could be done. Do "
                "the Skill's work first (for a review: read the files it reviews, then write the verdict), then run "
                "resume on its own, after the work.")

    def _review_report_error(self, state: MissionState, skill: SkillSpec, summary: str,
                             provided: dict[str, str]) -> str | None:
        """A flow review reports its verdict, not the reviewed step's files or summary: a model registered a review
        with the recommender's CSV and summary, so the review was never done."""
        position = self._open_review_index(state, skill.id)
        if position is None:
            reviewers = {step.get("review") for flow in self.experiment_flows.values()
                         for step in flow.get("steps") or [] if step.get("review")}
            if skill.id not in reviewers and _VERDICT.search(summary or ""):
                # A batch registered the review's verdict as the recommender's result (its own resume refused).
                return (f"This --summary is a review verdict, but the pending action is {skill.id} "
                        f"({(state.pending_action or {}).get('id')}), not a review. Report {skill.id}'s own result; "
                        "the review is the next step, issued with its own act after this one is registered.")
            return None
        label = state.plan_labels[position]
        foreign = []
        for artifact_id in provided:
            record = state.artifact_records.get(artifact_id) or {}
            producer = (state.skill_executions.get(str(record.get("action_id"))) or {}).get("skill_id")
            declared_elsewhere = artifact_id not in skill.outputs and any(
                artifact_id in other.outputs for other_id, other in self.skills.items() if other_id != skill.id)
            if declared_elsewhere or (artifact_id in state.artifacts and producer != skill.id):
                foreign.append(artifact_id)
        if foreign:
            return (f"{skill.id} at step {position + 1} is a review ({label}): {', '.join(foreign)} "
                    f"{'is a result' if len(foreign) == 1 else 'are results'} of earlier steps, not of this review. "
                    "Report the review with resume --agent-completed --summary \"<verdict and findings>\" (or "
                    "--agent-failed), without --provide-artifact for the files it reviewed.")
        reviewed = self._plan_slots(state).get(position - 1) or {}
        if summary.strip() and summary.strip() == str(reviewed.get("summary") or "").strip():
            return (f"This --summary is the summary of {state.plan[position - 1]}, the step under review ({label}). "
                    "Read the files it reviews, then give this review's own verdict and findings.")
        return None

    @staticmethod
    def _review_reply(state: MissionState, skill_id: str | None) -> str:
        """The user's reply to the latest "review did not pass" question about this reviewed Skill."""
        ticket = next((item for item in reversed(state.decisions)
                       if item.get("review_failed") and item.get("reviewed_skill") == skill_id), None)
        if ticket is None:
            return ""
        answer = next((item for item in reversed(state.observations)
                       if item.get("action_id") == ticket.get("id") and item.get("status") == "human_answer"), None)
        return str((answer or {}).get("summary") or "")

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
        if status == "human_answer":
            state.replan_required = True
        elif completed or terminal_status or status in {"succeeded", "failed", "blocked", "reconciled_failed", "rejected"}:
            # A rejection is the user's decision not to run that action: finishing the task afterwards is a valid
            # next step (declining the device task at the end of an experiment flow left --complete refused).
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
