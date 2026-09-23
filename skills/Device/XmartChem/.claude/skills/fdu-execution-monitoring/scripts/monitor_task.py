#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from alert_dispatcher import format_monitor_alert, push_chat_message
from device_monitor_api import DeviceMonitorAPIClient
from dotenv import load_dotenv
from monitoring_utils import (
    MonitoringError,
    build_observation,
    make_output_path,
    now_iso,
    observation_stop_reason,
    resolve_task_id,
    write_json,
)


def load_env() -> None:
    skill_root = Path(__file__).resolve().parents[1]
    agents_root = Path(__file__).resolve().parents[3]
    repo_root = Path(__file__).resolve().parents[4]
    for env_path in (skill_root / ".env", agents_root / ".env", repo_root / ".env"):
        if env_path.exists():
            load_dotenv(env_path)


load_env()

DEFAULT_MAX_DURATION_SECONDS = 48 * 60 * 60
DEFAULT_SCI_AGENT_API_BASE = "http://127.0.0.1:8000"


@dataclass(frozen=True)
class MonitorStartContext:
    task_id: int
    conversation_id: str


def env_timeout() -> int:
    try:
        return int(os.getenv("FDU_DEVICE_TIMEOUT", "20"))
    except ValueError:
        return 20


def build_client(args: argparse.Namespace) -> DeviceMonitorAPIClient:
    missing = [
        name
        for name, value in {
            "base_url": args.base_url,
            "username": args.username,
            "password": args.password,
        }.items()
        if not value
    ]
    if missing:
        raise MonitoringError(f"Missing API configuration: {', '.join(missing)}")
    return DeviceMonitorAPIClient(
        base_url=args.base_url,
        username=args.username,
        password=args.password,
        timeout=args.timeout,
    )


def collect_task_snapshot(client: Any, task_id: int) -> Dict[str, Any]:
    task_info = client.get_task_info(task_id)
    notice = client.get_notice(types=[0, 1, 2])
    return build_observation(task_id, task_info, notice)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Poll one FDU device task without controlling it.")
    parser.add_argument("--task-id", type=int, help="Device task id")
    parser.add_argument("--submit-result-file", help="Path to fdu-device-run submit_<timestamp>.json")
    parser.add_argument("--base-url", default=os.getenv("FDU_DEVICE_BASE_URL"), help="Device API base URL")
    parser.add_argument("--username", default=os.getenv("FDU_DEVICE_USERNAME"), help="API username")
    parser.add_argument("--password", default=os.getenv("FDU_DEVICE_PASSWORD"), help="API password")
    parser.add_argument("--timeout", type=int, default=env_timeout(), help="HTTP timeout in seconds")
    parser.add_argument("--poll-interval", type=float, default=10.0, help="Polling interval in seconds")
    parser.add_argument(
        "--max-duration",
        type=float,
        default=DEFAULT_MAX_DURATION_SECONDS,
        help="Maximum monitoring duration in seconds. Use 0 to run until task terminal/fault/alarm.",
    )
    parser.add_argument(
        "--sci-agent-api-base",
        default=DEFAULT_SCI_AGENT_API_BASE,
        help=f"sci_agent backend API base for pushed alerts. Default: {DEFAULT_SCI_AGENT_API_BASE}",
    )
    parser.add_argument(
        "--conversation-id",
        required=True,
        help="sci_agent conversationId to receive pushed alerts. The Agent must resolve it before starting this script.",
    )
    parser.add_argument(
        "--push-token",
        default=os.getenv("SCI_AGENT_PUSH_TOKEN"),
        help="Optional bearer token for sci_agent /api/chat/push.",
    )
    parser.add_argument("--push-timeout", type=int, default=20, help="sci_agent push HTTP timeout in seconds")
    parser.add_argument("--output", help="Output JSON path. Defaults to output/task_monitor_<timestamp>.json")
    return parser.parse_args(argv)


def timeline_entry(observation: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "observed_at": observation.get("observed_at"),
        "status": observation.get("status"),
        "progress": observation.get("progress"),
        "fault_count": len(observation.get("faults", [])),
        "alarm_count": len(observation.get("alarms", [])),
        "notice_count": len(observation.get("notices", [])),
        "user_alerts": observation.get("user_alerts", []),
    }


def resolve_start_context(args: argparse.Namespace) -> MonitorStartContext:
    task_id = resolve_task_id(task_id=args.task_id, submit_result_file=args.submit_result_file)
    conversation_id = str(getattr(args, "conversation_id", "") or "").strip()
    if not conversation_id:
        raise MonitoringError("conversation_id is required. The Agent must resolve it before starting monitor_task.py.")
    return MonitorStartContext(task_id=task_id, conversation_id=conversation_id)


def execute(
    args: argparse.Namespace,
    *,
    client: Optional[Any] = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    clock_fn: Callable[[], float] = time.monotonic,
    alert_sender: Optional[Callable[..., Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    start_context = resolve_start_context(args)
    args.conversation_id = start_context.conversation_id

    client = client or build_client(args)
    client.login()

    started_at = now_iso()
    start_time = clock_fn()
    timeline: List[Dict[str, Any]] = []
    observations: List[Dict[str, Any]] = []
    max_duration = max(float(args.max_duration), 0.0)
    unlimited = max_duration == 0.0
    stop_reason = "stopped_without_reason"

    while True:
        observation = collect_task_snapshot(client, start_context.task_id)
        observations.append(observation)
        timeline.append(timeline_entry(observation))

        reason = observation_stop_reason(observation)
        if reason:
            stop_reason = reason
            break

        elapsed = clock_fn() - start_time
        if not unlimited and elapsed >= max_duration:
            stop_reason = "max_duration_reached"
            break

        sleep_for = args.poll_interval if unlimited else min(args.poll_interval, max(max_duration - elapsed, 0))
        if sleep_for <= 0:
            stop_reason = "poll_interval_non_positive"
            break
        sleep_fn(sleep_for)

    final_observation = observations[-1] if observations else None
    result = {
        "task_id": start_context.task_id,
        "conversation_id": start_context.conversation_id,
        "started_at": started_at,
        "ended_at": now_iso(),
        "stop_reason": stop_reason,
        "final_status": final_observation.get("status") if final_observation else None,
        "timeline": timeline,
        "notices_seen": [n for o in observations for n in o.get("notices", [])],
        "faults_seen": [n for o in observations for n in o.get("faults", [])],
        "alarms_seen": [n for o in observations for n in o.get("alarms", [])],
        "user_alerts": final_observation.get("user_alerts", []) if final_observation else [],
        "observations": observations,
        "alert_push": None,
    }
    maybe_push_alert(args, result, alert_sender=alert_sender)
    return result


def should_push_alert(result: Dict[str, Any]) -> bool:
    stop_reason = str(result.get("stop_reason") or "")
    if stop_reason in {"fault_detected", "alarm_detected"}:
        return True
    final_label = (result.get("final_status") or {}).get("label")
    return final_label in {"FAILED", "USER_TERMINATED", "EMERGENCY_STOP"}


def maybe_push_alert(
    args: argparse.Namespace,
    result: Dict[str, Any],
    *,
    alert_sender: Optional[Callable[..., Dict[str, Any]]] = None,
) -> None:
    if not should_push_alert(result):
        return

    conversation_id = str(result.get("conversation_id") or getattr(args, "conversation_id", "") or "").strip()
    if not conversation_id:
        result["alert_push"] = {
            "attempted": False,
            "reason": "conversation_id_not_provided",
        }
        return

    api_base = getattr(args, "sci_agent_api_base", None) or DEFAULT_SCI_AGENT_API_BASE

    sender = alert_sender or push_chat_message
    content = format_monitor_alert(result)
    try:
        response = sender(
            api_base=api_base,
            conversation_id=conversation_id,
            content=content,
            role="assistant",
            timeout=getattr(args, "push_timeout", 20),
            token=getattr(args, "push_token", None),
        )
        result["alert_push"] = {
            "attempted": True,
            "success": True,
            "conversation_id": conversation_id,
            "response": response,
        }
    except Exception as exc:
        result["alert_push"] = {
            "attempted": True,
            "success": False,
            "conversation_id": conversation_id,
            "error": str(exc),
        }


def main() -> int:
    args = parse_args()
    try:
        result = execute(args)
        output_path = Path(args.output).expanduser() if args.output else make_output_path("task_monitor")
        write_json(result, output_path)

        final = result.get("final_status") or {}
        print(f"Task ID: {result['task_id']}")
        print(f"Final status: {final.get('label')} ({final.get('code')})")
        print(f"Stop reason: {result['stop_reason']}")
        print(f"Faults seen: {len(result['faults_seen'])}")
        print(f"Alarms seen: {len(result['alarms_seen'])}")
        for alert in result["user_alerts"]:
            print(f"Alert: {alert}")
        print(f"Monitoring record saved to: {output_path}")
        return 0
    except Exception as e:
        print(f"Monitoring failed: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
