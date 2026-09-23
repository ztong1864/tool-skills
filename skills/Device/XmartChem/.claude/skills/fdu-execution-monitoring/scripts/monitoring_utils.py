#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


SKILL_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = SKILL_ROOT / "output"

TASK_STATUS = {
    0: "UNSTARTED",
    1: "RUNNING",
    2: "COMPLETED",
    3: "PAUSED",
    4: "FAILED",
    5: "USER_TERMINATED",
    6: "PAUSING",
    7: "USER_TERMINATING",
    8: "EMERGENCY_STOP",
}

TERMINAL_STATUSES = {"COMPLETED", "FAILED", "USER_TERMINATED", "EMERGENCY_STOP"}
ATTENTION_STATUSES = {"FAILED", "PAUSED", "USER_TERMINATED", "EMERGENCY_STOP"}

NOTICE_TYPES = {
    0: "notice",
    1: "fault",
    2: "alarm",
}


class MonitoringError(Exception):
    """Raised when task observation or monitoring cannot continue."""


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_output_dir() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


def make_output_path(prefix: str) -> Path:
    ts = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    return ensure_output_dir() / f"{prefix}_{ts}.json"


def write_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: str | Path) -> Any:
    p = Path(path).expanduser()
    if not p.exists():
        raise MonitoringError(f"JSON file not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def resolve_task_id(*, task_id: Optional[int], submit_result_file: Optional[str]) -> int:
    if task_id is not None:
        return int(task_id)
    if not submit_result_file:
        raise MonitoringError("Please provide --task-id or --submit-result-file.")
    data = read_json(submit_result_file)
    if not isinstance(data, dict):
        raise MonitoringError("Submit result JSON must be an object.")
    raw_task_id = data.get("task_id")
    if raw_task_id is None:
        add_task_result = data.get("add_task_result")
        if isinstance(add_task_result, dict):
            raw_task_id = add_task_result.get("task_id")
    if raw_task_id is None:
        raise MonitoringError(f"Submit result does not contain task_id: {submit_result_file}")
    return int(raw_task_id)


def unwrap_task_info(raw: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(raw.get("result"), dict):
        return raw["result"]
    return raw


def unwrap_notice_list(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(raw.get("list"), list):
        return [x for x in raw["list"] if isinstance(x, dict)]
    result = raw.get("result")
    if isinstance(result, dict) and isinstance(result.get("list"), list):
        return [x for x in result["list"] if isinstance(x, dict)]
    return []


def status_label(status: Any) -> str:
    try:
        return TASK_STATUS[int(status)]
    except (TypeError, ValueError, KeyError):
        return "UNKNOWN"


def notice_type_label(value: Any) -> str:
    try:
        return NOTICE_TYPES[int(value)]
    except (TypeError, ValueError, KeyError):
        return "unknown"


def task_progress(task_info: Dict[str, Any]) -> Dict[str, Any]:
    tube_sums = task_info.get("tube_sums")
    tube_finish = task_info.get("tube_finish")
    ratio = None
    try:
        if tube_sums is not None and float(tube_sums) > 0 and tube_finish is not None:
            ratio = float(tube_finish) / float(tube_sums)
    except (TypeError, ValueError, ZeroDivisionError):
        ratio = None
    return {
        "tube_sums": tube_sums,
        "tube_finish": tube_finish,
        "ratio": ratio,
    }


def split_notices(notices: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped = {"notices": [], "faults": [], "alarms": [], "unknown": []}
    for notice in notices:
        label = notice_type_label(notice.get("type"))
        if label == "notice":
            grouped["notices"].append(notice)
        elif label == "fault":
            grouped["faults"].append(notice)
        elif label == "alarm":
            grouped["alarms"].append(notice)
        else:
            grouped["unknown"].append(notice)
    return grouped


def build_user_alerts(status: str, faults: List[Dict[str, Any]], alarms: List[Dict[str, Any]]) -> List[str]:
    alerts: List[str] = []
    if status == "COMPLETED":
        alerts.append("任务已完成。")
    elif status == "FAILED":
        alerts.append("任务失败，需要人工查看设备任务详情和通知。")
    elif status == "PAUSED":
        alerts.append("任务处于暂停状态，需要人工确认现场情况。")
    elif status == "USER_TERMINATED":
        alerts.append("任务已被用户终止。")
    elif status == "EMERGENCY_STOP":
        alerts.append("任务处于紧急停止状态，需要现场人工确认。")

    if faults:
        alerts.append(f"发现 {len(faults)} 条故障通知，需要人工查看。")
    if alarms:
        alerts.append(f"发现 {len(alarms)} 条告警通知，需要人工查看。")
    if not alerts:
        alerts.append("未发现终态、故障或告警。")
    return alerts


def build_observation(task_id: int, task_info_raw: Dict[str, Any], notice_raw: Dict[str, Any]) -> Dict[str, Any]:
    task_info = unwrap_task_info(task_info_raw)
    raw_status = task_info.get("status")
    label = status_label(raw_status)
    grouped = split_notices(unwrap_notice_list(notice_raw))
    progress = task_progress(task_info)

    return {
        "observed_at": now_iso(),
        "task_id": task_id,
        "task_name": task_info.get("task_name") or task_info.get("name"),
        "status": {
            "code": raw_status,
            "label": label,
            "terminal": label in TERMINAL_STATUSES,
            "requires_attention": label in ATTENTION_STATUSES,
        },
        "timestamps": {
            "task_begin_time": task_info.get("task_begin_time"),
            "task_end_time": task_info.get("task_end_time"),
            "created_at": task_info.get("created_at"),
            "updated_at": task_info.get("updated_at"),
        },
        "progress": progress,
        "notices": grouped["notices"],
        "faults": grouped["faults"],
        "alarms": grouped["alarms"],
        "unknown_notices": grouped["unknown"],
        "user_alerts": build_user_alerts(label, grouped["faults"], grouped["alarms"]),
        "raw": {
            "task_info": task_info_raw,
            "notice": notice_raw,
        },
    }


def observation_stop_reason(observation: Dict[str, Any]) -> Optional[str]:
    if observation.get("faults"):
        return "fault_detected"
    if observation.get("alarms"):
        return "alarm_detected"
    status = observation.get("status", {}).get("label")
    if status in TERMINAL_STATUSES:
        return f"terminal_status:{status}"
    return None
