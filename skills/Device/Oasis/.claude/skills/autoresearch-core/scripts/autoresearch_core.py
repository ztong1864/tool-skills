#!/usr/bin/env python3
"""Model-agnostic AutoResearch loop driven by JSON and external commands."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RESULT_FIELDS = (
    "iteration",
    "candidate_id",
    "status",
    "kept",
    "metric",
    "best_metric_after",
    "started_at",
    "completed_at",
    "trial_dir",
    "error",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_json_output(output: str) -> dict[str, Any]:
    stripped = output.strip()
    if not stripped:
        raise ValueError("command produced no JSON output")
    try:
        payload = json.loads(stripped)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    for line in reversed(stripped.splitlines()):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError("could not find a JSON object in command output")


def nested_value(payload: dict[str, Any], dotted_key: str) -> Any:
    value: Any = payload
    for part in dotted_key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise ValueError(f"metric key not found in evaluator output: {dotted_key}")
        value = value[part]
    return value


def validate_command(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{field} must be a non-empty array of strings")
    return list(value)


def load_config(path: Path) -> dict[str, Any]:
    config = read_json(path)
    if not isinstance(config, dict):
        raise ValueError("config root must be a JSON object")
    required = ("name", "goal", "metric_key", "direction", "budget", "patience", "workspace", "baseline", "trial")
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError(f"missing config fields: {', '.join(missing)}")
    if config["direction"] not in {"higher", "lower"}:
        raise ValueError("direction must be higher or lower")
    if int(config["budget"]) <= 0 or int(config["patience"]) <= 0:
        raise ValueError("budget and patience must be positive")
    validate_command(config["baseline"].get("command"), "baseline.command")
    validate_command(config["trial"].get("command"), "trial.command")
    if "guard" in config:
        validate_command(config["guard"].get("command"), "guard.command")
    if "proposer" in config:
        validate_command(config["proposer"].get("command"), "proposer.command")
    return config


def resolve_workspace(config_path: Path, config: dict[str, Any]) -> Path:
    raw = Path(config["workspace"])
    return (raw if raw.is_absolute() else config_path.parent / raw).resolve()


def render_command(template: list[str], context: dict[str, str]) -> list[str]:
    try:
        return [item.format_map(context) for item in template]
    except KeyError as exc:
        raise ValueError(f"unknown command placeholder: {exc.args[0]}") from exc


def run_command(
    command: list[str],
    cwd: Path,
    timeout_seconds: int,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
        env=os.environ.copy(),
    )


def command_context(
    config_path: Path,
    workspace: Path,
    run_dir: Path,
    trial_dir: Path,
    proposal_path: Path | None,
) -> dict[str, str]:
    return {
        "python": sys.executable,
        "config": str(config_path.resolve()),
        "config_dir": str(config_path.parent.resolve()),
        "workspace": str(workspace),
        "run_dir": str(run_dir.resolve()),
        "trial_dir": str(trial_dir.resolve()),
        "proposal_path": "" if proposal_path is None else str(proposal_path.resolve()),
    }


def execute_json_command(
    template: list[str],
    context: dict[str, str],
    workspace: Path,
    timeout_seconds: int,
    input_payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], subprocess.CompletedProcess[str], list[str]]:
    command = render_command(template, context)
    input_text = None if input_payload is None else json.dumps(input_payload, ensure_ascii=False)
    completed = run_command(command, workspace, timeout_seconds, input_text=input_text)
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"command failed with exit code {completed.returncode}: {message[-2000:]}")
    payload = parse_json_output(completed.stdout)
    return payload, completed, command


def normalize_artifacts(payload: dict[str, Any], workspace: Path, trial_dir: Path) -> list[str]:
    artifacts = payload.get("artifacts", [])
    if artifacts is None:
        artifacts = []
    if not isinstance(artifacts, list) or not all(isinstance(item, str) for item in artifacts):
        raise ValueError("evaluator artifacts must be an array of paths")
    normalized = []
    for item in artifacts:
        path = Path(item)
        if not path.is_absolute():
            candidate = trial_dir / path
            path = candidate if candidate.exists() else workspace / path
        path = path.resolve()
        if not path.exists():
            raise ValueError(f"evaluator artifact does not exist: {path}")
        normalized.append(str(path))
    return normalized


def is_improvement(candidate: float, best: float, direction: str, tolerance: float) -> bool:
    if direction == "higher":
        return candidate > best + tolerance
    return candidate < best - tolerance


def append_result(run_dir: Path, record: dict[str, Any]) -> None:
    jsonl = run_dir / "results.jsonl"
    with jsonl.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    tsv = run_dir / "results.tsv"
    exists = tsv.exists()
    with tsv.open("a", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=RESULT_FIELDS, delimiter="\t")
        if not exists:
            writer.writeheader()
        writer.writerow({field: record.get(field, "") for field in RESULT_FIELDS})


def load_results(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "results.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def state_path(run_dir: Path) -> Path:
    return run_dir / "state.json"


def load_state(run_dir: Path) -> dict[str, Any]:
    path = state_path(run_dir)
    if not path.exists():
        raise ValueError(f"run is not initialized: {path}")
    return read_json(path)


def save_state(run_dir: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    write_json(state_path(run_dir), state)


def run_guard(config: dict[str, Any], context: dict[str, str], workspace: Path) -> dict[str, Any] | None:
    guard = config.get("guard")
    if not guard:
        return None
    timeout = int(guard.get("timeout_seconds", config.get("timeout_seconds", 3600)))
    payload, _, _ = execute_json_command(guard["command"], context, workspace, timeout)
    return payload


def init_run(config_path: Path, run_dir: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    run_dir = run_dir.resolve()
    if state_path(run_dir).exists():
        return load_state(run_dir)
    config = load_config(config_path)
    workspace = resolve_workspace(config_path, config)
    if not workspace.is_dir():
        raise ValueError(f"workspace does not exist: {workspace}")
    run_dir.mkdir(parents=True, exist_ok=True)
    baseline_dir = run_dir / "trials" / "000_baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    context = command_context(config_path, workspace, run_dir, baseline_dir, None)
    started = now_iso()
    run_guard(config, context, workspace)
    timeout = int(config["baseline"].get("timeout_seconds", config.get("timeout_seconds", 3600)))
    payload, completed, command = execute_json_command(config["baseline"]["command"], context, workspace, timeout)
    metric = float(nested_value(payload, config["metric_key"]))
    artifacts = normalize_artifacts(payload, workspace, baseline_dir)
    baseline = {
        "iteration": 0,
        "candidate_id": "baseline",
        "status": "ok",
        "kept": True,
        "metric": metric,
        "best_metric_after": metric,
        "proposal": {"candidate_id": "baseline", "type": "baseline"},
        "metrics": payload,
        "artifacts": artifacts,
        "trial_dir": str(baseline_dir),
        "command": command,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
        "started_at": started,
        "completed_at": now_iso(),
        "error": "",
    }
    state: dict[str, Any] = {
        "schema_version": 1,
        "name": config["name"],
        "goal": config["goal"],
        "status": "active",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "config_path": str(config_path),
        "config_sha256": sha256(config_path),
        "workspace": str(workspace),
        "metric_key": config["metric_key"],
        "direction": config["direction"],
        "budget": int(config["budget"]),
        "patience": int(config["patience"]),
        "tolerance": float(config.get("tolerance", 0.0)),
        "completed_trials": 0,
        "consecutive_non_improvements": 0,
        "baseline": baseline,
        "current_best": baseline,
    }
    write_json(run_dir / "config.snapshot.json", config)
    append_result(run_dir, baseline)
    save_state(run_dir, state)
    return state


def submit_trial(run_dir: Path, proposal: dict[str, Any]) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    state = load_state(run_dir)
    config_path = Path(state["config_path"])
    if sha256(config_path) != state["config_sha256"]:
        raise ValueError("config changed after initialization; start a new run")
    config = load_config(config_path)
    workspace = Path(state["workspace"])
    if state["status"] != "active":
        raise ValueError(f"run is not active: {state['status']}")
    if not isinstance(proposal, dict):
        raise ValueError("proposal must be a JSON object")
    candidate_id = proposal.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-" for char in candidate_id):
        raise ValueError("proposal.candidate_id must use letters, numbers, dot, underscore, or hyphen")
    evaluated = {row["candidate_id"] for row in load_results(run_dir)}
    if candidate_id in evaluated:
        raise ValueError(f"candidate_id already evaluated: {candidate_id}")
    iteration = int(state["completed_trials"]) + 1
    if iteration > int(state["budget"]):
        raise ValueError("trial budget is exhausted")
    trial_dir = run_dir / "trials" / f"{iteration:03d}_{candidate_id}"
    trial_dir.mkdir(parents=True, exist_ok=False)
    proposal_path = trial_dir / "proposal.json"
    write_json(proposal_path, proposal)
    context = command_context(config_path, workspace, run_dir, trial_dir, proposal_path)
    started = now_iso()
    record: dict[str, Any]
    try:
        run_guard(config, context, workspace)
        timeout = int(config["trial"].get("timeout_seconds", config.get("timeout_seconds", 3600)))
        payload, completed, command = execute_json_command(config["trial"]["command"], context, workspace, timeout)
        metric = float(nested_value(payload, state["metric_key"]))
        artifacts = normalize_artifacts(payload, workspace, trial_dir)
        run_guard(config, context, workspace)
        kept = is_improvement(metric, float(state["current_best"]["metric"]), state["direction"], float(state["tolerance"]))
        record = {
            "iteration": iteration,
            "candidate_id": candidate_id,
            "status": "ok",
            "kept": kept,
            "metric": metric,
            "best_metric_after": metric if kept else state["current_best"]["metric"],
            "proposal": proposal,
            "metrics": payload,
            "artifacts": artifacts,
            "trial_dir": str(trial_dir),
            "command": command,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
            "started_at": started,
            "completed_at": now_iso(),
            "error": "",
        }
    except Exception as exc:
        record = {
            "iteration": iteration,
            "candidate_id": candidate_id,
            "status": "failed",
            "kept": False,
            "metric": "",
            "best_metric_after": state["current_best"]["metric"],
            "proposal": proposal,
            "metrics": {},
            "artifacts": [],
            "trial_dir": str(trial_dir),
            "command": [],
            "stdout": "",
            "stderr": "",
            "started_at": started,
            "completed_at": now_iso(),
            "error": str(exc),
        }
    append_result(run_dir, record)
    state["completed_trials"] = iteration
    if record["kept"]:
        state["current_best"] = record
        state["consecutive_non_improvements"] = 0
    else:
        state["consecutive_non_improvements"] = int(state["consecutive_non_improvements"]) + 1
    if iteration >= int(state["budget"]):
        state["status"] = "completed_budget"
    elif int(state["consecutive_non_improvements"]) >= int(state["patience"]):
        state["status"] = "stopped_patience"
    save_state(run_dir, state)
    return record


def proposer_context(state: dict[str, Any], config: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "protocol_version": 1,
        "goal": state["goal"],
        "metric_key": state["metric_key"],
        "direction": state["direction"],
        "baseline_metric": state["baseline"]["metric"],
        "best_metric": state["current_best"]["metric"],
        "best_candidate_id": state["current_best"]["candidate_id"],
        "completed_trials": state["completed_trials"],
        "budget": state["budget"],
        "budget_remaining": int(state["budget"]) - int(state["completed_trials"]),
        "consecutive_non_improvements": state["consecutive_non_improvements"],
        "patience": state["patience"],
        "evaluated_candidate_ids": [row["candidate_id"] for row in results],
        "recent_results": [
            {
                "candidate_id": row["candidate_id"],
                "status": row["status"],
                "kept": row["kept"],
                "metric": row["metric"],
                "proposal": row.get("proposal", {}),
                "error": row.get("error", ""),
            }
            for row in results[-10:]
        ],
        "proposal_schema": config.get("proposal_schema", {}),
        "search_guidance": config.get("search_guidance", []),
    }


def run_loop(config_path: Path, run_dir: Path) -> dict[str, Any]:
    state = init_run(config_path, run_dir)
    config = load_config(Path(state["config_path"]))
    if "proposer" not in config:
        raise ValueError("config.proposer.command is required for loop mode; use submit for manual or external proposals")
    workspace = Path(state["workspace"])
    while state["status"] == "active":
        results = load_results(run_dir)
        context_payload = proposer_context(state, config, results)
        command_context_values = command_context(Path(state["config_path"]), workspace, run_dir, run_dir, None)
        timeout = int(config["proposer"].get("timeout_seconds", config.get("timeout_seconds", 3600)))
        proposal, _, _ = execute_json_command(
            config["proposer"]["command"],
            command_context_values,
            workspace,
            timeout,
            input_payload=context_payload,
        )
        if proposal.get("action") == "stop":
            state["status"] = "stopped_proposer"
            state["stop_reason"] = str(proposal.get("reason", "proposer requested stop"))
            save_state(run_dir, state)
            break
        record = submit_trial(run_dir, proposal)
        print(json.dumps({"event": "trial_completed", **{key: record.get(key) for key in ("iteration", "candidate_id", "status", "kept", "metric", "best_metric_after", "error")}}, ensure_ascii=False), flush=True)
        state = load_state(run_dir)
    return state


def copy_artifacts(artifacts: list[str], target: Path) -> list[str]:
    copied = []
    used = set()
    for raw in artifacts:
        source = Path(raw)
        name = source.name
        if name in used:
            name = f"{len(used):02d}_{name}"
        used.add(name)
        destination = target / name
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
        copied.append(name)
    return copied


def freeze_run(run_dir: Path, version: str) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    state = load_state(run_dir)
    if not version or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-" for char in version):
        raise ValueError("version contains unsupported characters")
    target = run_dir / "frozen" / version
    if target.exists():
        raise ValueError(f"version already exists: {target}")
    target.mkdir(parents=True)
    best = state["current_best"]
    raw_improvement = float(best["metric"]) - float(state["baseline"]["metric"])
    improvement = raw_improvement if state["direction"] == "higher" else -raw_improvement
    copied = copy_artifacts(best.get("artifacts", []), target)
    write_json(target / "strategy_config.json", best.get("proposal", {}))
    write_json(
        target / "metrics_summary.json",
        {
            "metric_key": state["metric_key"],
            "direction": state["direction"],
            "baseline_metric": state["baseline"]["metric"],
            "winner_metric": best["metric"],
            "improvement": improvement,
            "winner_metrics": best.get("metrics", {}),
        },
    )
    write_json(
        target / "provenance.json",
        {
            "version": version,
            "created_at": now_iso(),
            "run_dir": str(run_dir),
            "config_sha256": state["config_sha256"],
            "winner_candidate_id": best["candidate_id"],
            "winner_iteration": best["iteration"],
            "copied_artifacts": copied,
            "python": sys.version,
            "platform": platform.platform(),
        },
    )
    report = f"""# AutoResearch selection report

- Version: `{version}`
- Goal: {state['goal']}
- Status: `{state['status']}`
- Metric: `{state['metric_key']}` ({state['direction']})
- Baseline: `{state['baseline']['metric']}`
- Winner: `{best['metric']}`
- Candidate: `{best['candidate_id']}`
- Completed trials: `{state['completed_trials']}`
- Copied artifacts: `{', '.join(copied) if copied else 'none'}`

The core selects the best measured candidate. Domain-specific stability or locked-test gates must be applied by the evaluator or a downstream acceptance step.
"""
    (target / "selection_report.md").write_text(report, encoding="utf-8")
    return {"status": "frozen", "version": version, "output_dir": str(target), "candidate_id": best["candidate_id"], "metric": best["metric"], "artifacts": copied}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate-config")
    validate.add_argument("--config", type=Path, required=True)
    init = sub.add_parser("init")
    init.add_argument("--config", type=Path, required=True)
    init.add_argument("--run-dir", type=Path, required=True)
    submit = sub.add_parser("submit")
    submit.add_argument("--run-dir", type=Path, required=True)
    submit.add_argument("--proposal", type=Path, required=True)
    loop = sub.add_parser("loop")
    loop.add_argument("--config", type=Path, required=True)
    loop.add_argument("--run-dir", type=Path, required=True)
    status = sub.add_parser("status")
    status.add_argument("--run-dir", type=Path, required=True)
    freeze = sub.add_parser("freeze")
    freeze.add_argument("--run-dir", type=Path, required=True)
    freeze.add_argument("--version", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "validate-config":
            config = load_config(args.config.resolve())
            result = {"valid": True, "name": config["name"], "metric_key": config["metric_key"], "direction": config["direction"]}
        elif args.command == "init":
            result = init_run(args.config, args.run_dir)
        elif args.command == "submit":
            proposal = read_json(args.proposal.resolve())
            result = submit_trial(args.run_dir, proposal)
        elif args.command == "loop":
            result = run_loop(args.config, args.run_dir)
        elif args.command == "status":
            result = load_state(args.run_dir.resolve())
        else:
            result = freeze_run(args.run_dir, args.version)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
