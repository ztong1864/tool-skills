from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from ..fsutil import file_lock
from .agent_loop import AgentRuntime
from .models import SkillSpec
from .registry import Registry, _skill_from_data
from .state_store import StateStore


def load_skill_file(path: Path) -> SkillSpec:
    import yaml
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _skill_from_data(data, path.parent)


def _load_registry(args: argparse.Namespace) -> Registry:
    if getattr(args, "system_dir", None):
        return Registry.load_cache(Path(args.system_dir))
    return Registry.load(Path(args.registry))


def _select_suite(registry: Registry, suite_id: str | None):
    if suite_id:
        return registry.suite(suite_id)
    if len(registry.suites) != 1:
        raise ValueError("--suite is required when the registry contains multiple suites")
    return next(iter(registry.suites.values()))


def _parse_initial_artifacts(values: list[str]) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for value in values:
        artifact_id, separator, path = value.partition("=")
        if not separator or not artifact_id or not path:
            raise ValueError("--input-artifact must use ARTIFACT_ID=PATH")
        artifacts[artifact_id] = str(Path(path).expanduser().resolve())
    return artifacts


def _mission_store(args: argparse.Namespace) -> StateStore:
    root = Path(args.runs_dir) if args.runs_dir else (
        Path(args.system_dir) / "runs" if args.system_dir else Path("runs")
    )
    return StateStore(root, args.mission_id)


def build_agent_runtime(args: argparse.Namespace) -> AgentRuntime:
    registry = _load_registry(args)
    suites = [registry.suite(args.suite)] if args.suite else [registry.suites[key] for key in sorted(registry.suites)]
    skills, knowledge, workflows, policies = {}, {}, [], []
    for suite in suites:
        # Skill entities are global in the unified graph, so the same Skill may
        # belong to several suites; only a conflicting definition is ambiguous.
        duplicates = {skill_id for skill_id in set(skills).intersection(suite.skills)
                      if skills[skill_id] != suite.skills[skill_id]}
        if duplicates:
            raise ValueError(f"Ambiguous Skill IDs {sorted(duplicates)}; select --suite explicitly")
        for skill_id, spec in suite.skills.items():
            if skill_id not in skills:
                skills[skill_id] = spec
                knowledge[skill_id] = {**suite.skill_knowledge.get(skill_id, {}), "suite_id": suite.id}
        policies.extend(suite.policies)
        workflows.extend({
            "id": flow_id, "suite_id": suite.id, "file": str(path),
            "skills": [node.skill_id for node in suite.skill_flow(flow_id).nodes if node.skill_id],
            "role": "reference_only",
        } for flow_id, path in suite.flow_entries.items())
    return AgentRuntime(
        skills, _mission_store(args),
        available_capabilities=set(args.capability).union(*(suite.available_capabilities for suite in suites)), policies=policies,
        skill_knowledge=knowledge, workflow_references=workflows, suite_id=args.suite,
    )


def _mission_command(args: argparse.Namespace, store: StateStore) -> None:
    """Load, change, and save one mission; the caller holds its lock."""
    existing = store.load() if store.state_path.exists() else None
    if existing and existing.suite_id:
        if args.suite and args.suite != existing.suite_id:
            raise ValueError("Mission belongs to a different SkillSuite")
        args.suite = existing.suite_id
    runtime = build_agent_runtime(args)
    if args.command == "run":
        runtime.start(args.goal, constraints=args.constraint,
                      artifacts=_parse_initial_artifacts(args.input_artifact),
                      start_skill=args.start_skill,
                      plan=[item for item in (args.plan or "").split(",") if item.strip()],
                      run_through=bool(args.run_through))
    elif args.command == "act":
        decision = json.loads(Path(args.decision_file).read_text(encoding="utf-8-sig"))
        runtime.decide(decision)
    elif args.command == "prepare-skill":
        runtime.prepare_skill(args.skill_id)
    elif args.command == "resume":
        if args.action_id:
            runtime.resume(
                action_id=args.action_id,
                summary=args.summary,
                provided_artifacts=_parse_initial_artifacts(args.provide_artifact),
                evidence=args.evidence,
                agent_completed=not args.agent_failed,
                agent_failed=args.agent_failed,
            )
        else:
            runtime.resume(provided_artifacts=_parse_initial_artifacts(args.provide_artifact),
                           summary=args.summary, evidence=args.evidence,
                           agent_completed=args.agent_completed, confirmed=args.confirm,
                           agent_failed=args.agent_failed,
                           rejected=args.reject, answer=args.answer)
    elif args.command == "revise":
        runtime.revise(args.change, [item for item in (args.redo or "").split(",") if item.strip()])
    elif args.command == "reconcile":
        runtime.reconcile(args.outcome, args.summary, evidence=args.evidence,
                          provided_artifacts=_parse_initial_artifacts(args.provide_artifact))
    print(json.dumps(runtime.context(), ensure_ascii=True, indent=2))


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agent-directed LabOntology missions")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "resume", "context", "act", "prepare-skill", "reconcile", "revise"):
        command = subparsers.add_parser(name)
        registry_source = command.add_mutually_exclusive_group(required=True)
        registry_source.add_argument("--registry")
        registry_source.add_argument("--system-dir")
        command.add_argument("--suite")
        command.add_argument("--runs-dir")
        command.add_argument(
            "--input-artifact",
            action="append",
            default=[],
            metavar="ARTIFACT_ID=PATH",
            help="Seed an external mission input artifact; may be repeated.",
        )
        command.add_argument(
            "--provide-artifact",
            action="append",
            default=[],
            metavar="ARTIFACT_ID=PATH",
            help="Provide outputs from an Agent Skill when resuming; may be repeated.",
        )
        command.add_argument("--mission-id", required=True)
        command.add_argument("--capability", action="append", default=[])
        if name == "run":
            command.add_argument("--goal", default="", help="Mission goal for default Agent mode")
            command.add_argument("--constraint", action="append", default=[])
            command.add_argument("--start-skill", help="Preferred first Skill; Agent may replan")
            command.add_argument("--plan", default="", help="Comma-separated Worker ids for a multi-step goal, in order")
            command.add_argument("--run-through", action="store_true", help="Do not pause for the user after each plan step")
        if name == "act":
            command.add_argument("--decision-file", required=True, help="One host-Agent decision as JSON")
        if name == "prepare-skill":
            command.add_argument("--skill-id", required=True, help="Worker Skill to read before acting")
        if name == "resume":
            command.add_argument("--action-id", default="", help="External Agent action being reported")
            command.add_argument("--confirm", action="store_true")
            command.add_argument("--reject", action="store_true")
            command.add_argument("--answer", default="", help="Actual user reply to a pending human decision")
            command.add_argument("--summary", default="", help="Agent Skill result; no artifact required")
            command.add_argument("--evidence", action="append", default=[])
            command.add_argument("--agent-completed", action="store_true")
            command.add_argument("--agent-failed", action="store_true")
        if name == "revise":
            command.add_argument("--change", required=True, help="The user's change to the finished task")
            command.add_argument("--redo", default="", help="Comma-separated Worker ids to run again")
        if name == "reconcile":
            command.add_argument("--outcome", required=True,
                                 choices=("not_started", "succeeded", "failed", "unknown"))
            command.add_argument("--summary", required=True)
            command.add_argument("--evidence", action="append", default=[])
    status = subparsers.add_parser("status")
    status_source = status.add_mutually_exclusive_group()
    status_source.add_argument("--runs-dir")
    status_source.add_argument("--cache-dir")
    status.add_argument("--mission-id", required=True)
    args = parser.parse_args(argv)
    if args.command == "status":
        runs_dir = Path(args.runs_dir) if args.runs_dir else (
            Path(args.cache_dir) / "runs" if args.cache_dir else Path("runs")
        )
        store = StateStore(runs_dir, args.mission_id)
        if not store.state_path.is_file():
            raise ValueError(f"Unknown mission: {args.mission_id}")
        state = store.load()
    else:
        store = _mission_store(args)
        if args.command != "run" and not store.state_path.is_file():
            raise ValueError(f"Unknown mission: {args.mission_id}")
        with file_lock(store.lock_path):
            _mission_command(args, store)
        return 0
    print(json.dumps(state.to_dict(), ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
