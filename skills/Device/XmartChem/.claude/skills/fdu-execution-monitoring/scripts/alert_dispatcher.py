#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any, Dict, Optional

import requests

from monitoring_utils import MonitoringError


def push_chat_message(
    *,
    api_base: str,
    conversation_id: str,
    content: str,
    role: str = "assistant",
    timeout: int = 20,
    token: Optional[str] = None,
    tool_events: Optional[list[dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if not api_base:
        raise MonitoringError("sci_agent API base is required for chat push.")
    if not conversation_id:
        raise MonitoringError("conversation_id is required for chat push.")
    if not content.strip():
        raise MonitoringError("content is required for chat push.")

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload: Dict[str, Any] = {
        "conversationId": conversation_id,
        "role": role,
        "content": content,
    }
    if tool_events is not None:
        payload["toolEvents"] = tool_events

    response = requests.post(
        f"{api_base.rstrip('/')}/api/chat/push",
        json=payload,
        headers=headers,
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("success") is False:
        raise MonitoringError(f"sci_agent chat push failed: {data}")
    return data


def format_monitor_alert(result: Dict[str, Any]) -> str:
    final_status = result.get("final_status") or {}
    task_id = result.get("task_id")
    stop_reason = result.get("stop_reason")
    alerts = result.get("user_alerts") or []
    faults = result.get("faults_seen") or []
    alarms = result.get("alarms_seen") or []

    lines = [
        "FDU 设备任务监控提醒",
        "",
        f"- 任务 ID: {task_id}",
        f"- 当前状态: {final_status.get('label')} ({final_status.get('code')})",
        f"- 停止原因: {stop_reason}",
        f"- 故障数量: {len(faults)}",
        f"- 告警数量: {len(alarms)}",
    ]

    if alerts:
        lines.append("")
        lines.append("需要注意：")
        lines.extend(f"- {alert}" for alert in alerts)

    if faults:
        lines.append("")
        lines.append("故障摘要：")
        for item in faults[:5]:
            lines.append(f"- id={item.get('id')}, error_code={item.get('error_code')}, status={item.get('status')}")

    if alarms:
        lines.append("")
        lines.append("告警摘要：")
        for item in alarms[:5]:
            lines.append(f"- id={item.get('id')}, error_code={item.get('error_code')}, status={item.get('status')}")

    return "\n".join(lines)
