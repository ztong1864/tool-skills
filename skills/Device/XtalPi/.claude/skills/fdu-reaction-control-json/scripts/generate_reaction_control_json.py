#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import re
import secrets
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Union

ROOT = Path(__file__).resolve().parents[1]
KB_DIR = ROOT / "KB"
OUT_DIR = ROOT / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)
MAX_RESOURCE_AGE_HOURS = 24

TARGET_DEFAULTS = {
    "layout_code": "T-3:0",
    "ori_layout_code": None,
    "layout_code_ref": "T-3:A1",
    "substance": "",
    "resource_type": "TTR2T",
    "tray_QR_code": "TTR2T_01",
    "QR_code": "",
    "unit_column": 0,
    "unit_row": 0,
    "unit_type": "exp_magnetic_stirrer",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_json_or_string(value: str) -> Any:
    path = Path(value)
    if path.exists() and path.is_file():
        return load_json(path)
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def load_step_unit(value: str) -> Dict[str, Any]:
    data = load_json_or_string(value)
    if data is None:
        raise ValueError("输入必须是 step_unit JSON 对象或 JSON 文件路径；不再支持旧式 instruction 字符串。")
    if not isinstance(data, dict):
        raise ValueError("Step unit JSON 必须是一个对象")
    if "skill_input" in data and isinstance(data["skill_input"], dict):
        return data
    if any(k in data for k in ("target_layout_code", "layout_code", "temperature", "reaction_duration", "rotation_speed", "is_wait", "still_tem")):
        return {"skill_input": data}
    raise ValueError("输入必须是 step_unit JSON 对象或包含 skill_input 的 JSON")


def make_unit_id() -> str:
    return f"unit-{secrets.token_hex(6)}"


def parse_duration(text: str) -> int:
    hour_match = re.search(r"(\d+(?:\.\d+)?)\s*(小时|h|hr|hour|hours)", text, re.IGNORECASE)
    min_match = re.search(r"(\d+(?:\.\d+)?)\s*(分钟|min|mins|minute|minutes)", text, re.IGNORECASE)
    sec_match = re.search(r"(\d+(?:\.\d+)?)\s*(秒|sec|secs|second|seconds)", text, re.IGNORECASE)
    if hour_match:
        return int(float(hour_match.group(1)) * 3600)
    if min_match:
        return int(float(min_match.group(1)) * 60)
    if sec_match:
        return int(float(sec_match.group(1)))
    return 1800


def parse_temperature(text: str) -> Union[str, int, float]:
    if re.search(r"室温|\brt\b", text, re.IGNORECASE):
        return "rt"
    m = re.search(r"(\d+(?:\.\d+)?)\s*(°C|℃|C|度)", text, re.IGNORECASE)
    if not m:
        return "rt"
    value = float(m.group(1))
    return int(value) if value.is_integer() else value


def parse_still_temperature(text: str, default: Union[str, int, float]) -> Union[str, int, float]:
    if re.search(r"静置.*室温|室温静置", text, re.IGNORECASE):
        return "rt"
    m = re.search(r"静置[^\d]*(\d+(?:\.\d+)?)\s*(°C|℃|C|度)", text, re.IGNORECASE)
    if not m:
        return default
    value = float(m.group(1))
    return int(value) if value.is_integer() else value


def parse_rpm(text: str) -> int:
    m = re.search(r"(\d+)\s*rpm", text, re.IGNORECASE)
    return int(m.group(1)) if m else 800


def parse_is_wait(text: str) -> bool:
    if re.search(r"不等待|无需等待|后台继续|continue without wait", text, re.IGNORECASE):
        return False
    return True


def build_target(target_layout_code: str) -> Dict[str, Any]:
    target = dict(TARGET_DEFAULTS)
    target["layout_code"] = target_layout_code
    return target


def build_action(slot: Dict[str, Any]) -> Dict[str, Any]:
    target = build_target(slot["target_layout_code"])

    # 对于短时间的搅拌操作（reaction_duration <= 300秒），设置 is_wait 为 false
    is_wait = slot["is_wait"]
    if slot["reaction_duration"] <= 300:
        is_wait = False

    return {
        "layout_code": target["layout_code"],
        "substance": target["substance"],
        "resource_type": target["resource_type"],
        "tray_QR_code": target["tray_QR_code"],
        "QR_code": target["QR_code"],
        "unit_column": target["unit_column"],
        "unit_row": target["unit_row"],
        "unit_type": target["unit_type"],
        "unit_id": make_unit_id(),
        "process_json": {
            "temperature": slot["temperature"],
            "reaction_duration": slot["reaction_duration"],
            "is_wait": is_wait,
            "rotation_speed": slot["rotation_speed"],
            "still_tem": slot["still_tem"],
            "custom": {
                "step": {
                    "rotation_speed": 50,
                    "temperature": 1
                },
                "unit": ""
            },
        },
    }


def save_output(action: Dict[str, Any]) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUT_DIR / f"generated_reaction_control_{ts}.json"
    path.write_text(json.dumps(action, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("step_unit", help="step_unit JSON 对象或 JSON 文件路径")
    args = parser.parse_args()

    parsed = load_step_unit(args.step_unit)
    slot = parsed["skill_input"]
    if "target_layout_code" not in slot and "layout_code" in slot:
        slot["target_layout_code"] = slot["layout_code"]
    action = build_action(slot)
    out = save_output(action)
    print(f"saved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
