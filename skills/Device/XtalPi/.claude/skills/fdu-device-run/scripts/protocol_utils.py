#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import re
import secrets
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from device_api import DeviceRunError

DEFAULT_PROTOCOL_PATH = (
    Path.home() / ".claude" / "skills" / "fdu-add-solid-json" / "output" / "generated_protocol.json"
)
SKILL_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = SKILL_ROOT / "output"
DEFAULT_TASK_NAME = "auto_generated_task"

REQUIRED_STEP_FIELDS = [
    "layout_code",
    "resource_type",
    "unit_column",
    "unit_row",
    "unit_type",
    "process_json",
]

OPTIONAL_STEP_FIELDS = [
    "unit_id",
    "substance",
    "QR_code",
]


def ensure_output_dir() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


def make_output_prefix(prefix: str = "submit") -> Path:
    ts = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    return ensure_output_dir() / f"{prefix}_{ts}"


def write_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def normalize_protocol_structure(data: Any) -> tuple[list[dict], str]:
    """
    支持两种输入：
    1. 单个 step JSON 对象 -> 自动包装成 list
    2. step JSON 数组 -> 直接使用

    返回：
        layout_list, structure_note
    """
    if isinstance(data, dict):
        return [data], "single_step_wrapped"

    if isinstance(data, list):
        if not data:
            raise DeviceRunError("Protocol JSON is empty.")
        if not all(isinstance(x, dict) for x in data):
            raise DeviceRunError("Protocol JSON array must contain JSON objects only.")
        return data, "list"

    raise DeviceRunError("Protocol JSON must be a JSON object or a JSON array.")


def parse_protocol_text(text: str) -> tuple[list[dict], str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise DeviceRunError(f"Protocol JSON parse failed: {e}") from e

    layout_list, structure_note = normalize_protocol_structure(data)
    validate_protocol_json(layout_list)
    return layout_list, structure_note


def load_protocol_from_sources(
    *,
    protocol_json: Optional[str],
    protocol_file: Optional[str],
    allow_stdin: bool = True,
) -> tuple[list[dict], str, str]:
    """
    读取优先级：
    1. --protocol-json
    2. --protocol-file
    3. stdin
    4. 默认路径 fallback

    返回：
        layout_list, protocol_source, structure_note
    """
    if protocol_json and protocol_json.strip():
        text = strip_code_fence(protocol_json)
        layout_list, structure_note = parse_protocol_text(text)
        return layout_list, "inline_json", structure_note

    if protocol_file and protocol_file.strip():
        path = Path(protocol_file).expanduser()
        if not path.exists():
            raise DeviceRunError(f"Protocol file not found: {path}")
        layout_list, structure_note = parse_protocol_text(path.read_text(encoding="utf-8"))
        return layout_list, str(path), structure_note

    if allow_stdin and not sys.stdin.isatty():
        stdin_text = sys.stdin.read().strip()
        if stdin_text:
            layout_list, structure_note = parse_protocol_text(strip_code_fence(stdin_text))
            return layout_list, "stdin", structure_note

    if DEFAULT_PROTOCOL_PATH.exists():
        layout_list, structure_note = parse_protocol_text(DEFAULT_PROTOCOL_PATH.read_text(encoding="utf-8"))
        return layout_list, str(DEFAULT_PROTOCOL_PATH), structure_note

    raise DeviceRunError(
        "No protocol input found. Please pass --protocol-json or --protocol-file, pipe JSON via stdin, "
        f"or make sure the default file exists: {DEFAULT_PROTOCOL_PATH}"
    )


def validate_protocol_json(layout_list: Any) -> None:
    if not isinstance(layout_list, list):
        raise DeviceRunError("Protocol JSON must be normalized to a list before validation.")

    if not layout_list:
        raise DeviceRunError("Protocol JSON is empty.")

    seen_unit_ids: set[str] = set()

    for i, step in enumerate(layout_list):
        if not isinstance(step, dict):
            raise DeviceRunError(f"Protocol step {i} is not an object.")

        for field in REQUIRED_STEP_FIELDS:
            if field not in step:
                raise DeviceRunError(f"Protocol step {i} missing required field: {field}")

        # unit_id 验证：如果存在才验证
        unit_id = step.get("unit_id")
        if unit_id is not None:
            unit_id = str(unit_id)
            if not unit_id.startswith("unit-"):
                raise DeviceRunError(f"Protocol step {i} has invalid unit_id, must start with 'unit-': {unit_id}")
            if unit_id in seen_unit_ids:
                raise DeviceRunError(f"Duplicate unit_id found in protocol: {unit_id}")
            seen_unit_ids.add(unit_id)

        if not isinstance(step.get("process_json"), dict):
            raise DeviceRunError(f"Protocol step {i} field process_json must be an object.")


def uniquify_task_name(task_name: Optional[str]) -> str:
    base = (task_name or DEFAULT_TASK_NAME).strip()
    if not base:
        base = DEFAULT_TASK_NAME
    suffix = datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{secrets.token_hex(2)}"
    return f"{base}_{suffix}"


def rewrite_unit_ids(layout_list: list[dict], suffix: Optional[str] = None) -> list[dict]:
    """
    重新生成 unit_id，避免复用旧 JSON 时和历史任务冲突。
    API 要求 unit_id 唯一，且必须以 unit- 开头。
    如果步骤没有 unit_id 字段，则跳过。
    """
    suffix = suffix or (datetime.now().strftime("%Y%m%d%H%M%S") + secrets.token_hex(3))
    new_layout = deepcopy(layout_list)
    for idx, step in enumerate(new_layout):
        # 只有当步骤有 unit_id 字段时才重新生成
        if "unit_id" in step:
            step["unit_id"] = f"unit-{suffix}-{idx:03d}"
    return new_layout


def build_add_task_payload(task_name: str, layout_list: list[dict]) -> Dict[str, Any]:
    return {
        "task_id": 0,
        "task_name": task_name,
        "layout_list": layout_list,
        "task_template_id_list": [],
        "is_audit_log": False,
        "is_copy": False,
    }


def summarize_layout(layout_list: Iterable[dict]) -> Dict[str, Any]:
    layout_list = list(layout_list)
    return {
        "step_count": len(layout_list),
        "unit_types": [str(x.get("unit_type", "")) for x in layout_list],
        "layout_codes": [str(x.get("layout_code", "")) for x in layout_list],
    }
