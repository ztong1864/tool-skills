"""Mission plans from a device's declared experiment flow (experiment_flows.yaml, see references/experiment-flows.md).

A flow lists Skills in order. A step may name a review Skill that checks its result right after it, a question
the user answers before the flow goes on (`pause`), and a named stop point (`stop`). A plan is the flow up to one
stop: each step's Skill, then its review; a step with a pause pauses after its last plan entry."""
from __future__ import annotations

from typing import Any


def _review_label(skill_id: str) -> str:
    return f"审查 {skill_id} 的结果"


def _plan_entries(steps: list[dict[str, Any]]) -> dict[str, Any]:
    plan: list[str] = []
    labels: list[str] = []
    pauses: list[int] = []
    questions: dict[str, str] = {}
    for step in steps:
        plan.append(step["skill"])
        labels.append("")
        if step.get("review"):
            plan.append(step["review"])
            labels.append(_review_label(step["skill"]))
        if step.get("pause"):
            pauses.append(len(plan) - 1)
            questions[str(len(plan) - 1)] = step["pause"]
    final_question = questions.get(str(len(plan) - 1))
    # The last entry ends the plan; its question is asked when the plan is done (see do_next), not as a pause.
    pauses = [position for position in pauses if position < len(plan) - 1]
    return {"plan": plan, "labels": labels, "pauses": pauses,
            "questions": {key: value for key, value in questions.items() if int(key) in pauses},
            "final_question": final_question}


def flow_plan(flow: dict[str, Any], until: str | None, skills: set[str]) -> dict[str, Any]:
    """The plan for `run --flow <id> --until <stop>`; a ValueError names what is wrong and the valid choices."""
    missing = sorted(set(flow.get("missing_skills") or []) | {
        skill_id for step in flow.get("steps") or [] for skill_id in (step.get("skill"), step.get("review"))
        if skill_id and skill_id not in skills})
    if missing:
        raise ValueError(f"Experiment flow {flow['id']} names Skills this library does not have: {missing}. "
                         "Fix experiment_flows.yaml of its ontology Skill, or plan without --flow.")
    steps = [step for step in flow.get("steps") or [] if step.get("skill")]
    stops = dict(flow.get("stops") or {})
    stop = (until or "").strip() or flow.get("default_stop") or None
    if stop is not None and stop not in stops:
        raise ValueError(f"Experiment flow {flow['id']} has no stop {stop!r}; its stops are "
                         + "; ".join(f"{name} ({text})" if text else name for name, text in stops.items()))
    end = next((index for index, step in enumerate(steps) if stop and step.get("stop") == stop), len(steps) - 1)
    chosen = [step for step in steps[:end + 1] if not step.get("optional")]
    if not chosen:
        raise ValueError(f"Experiment flow {flow['id']} has no steps up to {stop!r}")
    following = next((step for step in steps[end + 1:] if not step.get("optional")), None)
    return {**_plan_entries(chosen),
            "flow": {"id": flow["id"], "name": flow.get("name") or flow["id"], "until": stop,
                     "ontology_skill": flow.get("ontology_skill"),
                     "next": ({"skill": following["skill"], "stop": following.get("stop")} if following else None)}}


def flow_revision_plan(flow: dict[str, Any], until: str | None, redo: list[str]) -> dict[str, Any] | None:
    """The plan of a revision (act --revise ... --redo ...) on a flow mission: the redone steps in flow order, each
    with its review and pause, so a changed result is reviewed again before the user confirms it. None when no
    redone Skill is a step of the flow (the plain --redo list is used then)."""
    steps = [step for step in flow.get("steps") or [] if step.get("skill")]
    end = next((index for index, step in enumerate(steps) if until and step.get("stop") == until), len(steps) - 1)
    chosen = [step for step in steps[:end + 1] if step["skill"] in set(redo) and not step.get("optional")]
    if not chosen:
        return None
    return _plan_entries(chosen)
