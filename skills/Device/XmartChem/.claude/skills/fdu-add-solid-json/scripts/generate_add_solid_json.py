#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

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
    "unit_type": "exp_add_solid",
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
    if any(k in data for k in ("target_layout_code", "layout_code", "add_weight", "substance", "unit", "resource_info")):
        return {"skill_input": data}
    raise ValueError("输入必须是 step_unit JSON 对象或包含 skill_input 的 JSON")


def make_unit_id() -> str:
    return f"unit-{secrets.token_hex(6)}"


def to_mg(value: float, unit: str) -> float:
    return value * 1000.0 if unit.lower() == "g" else value


def calculate_offset(add_weight: float, unit: str) -> float:
    """Calculate offset based on weight and unit."""
    weight_mg = to_mg(add_weight, unit)
    if weight_mg >= 20.0:
        return 2.1
    elif weight_mg >= 1.0:
        return 0.05
    elif weight_mg >= 0.5:
        return 0.08
    else:
        return 0.0125


def build_target(target_layout_code: str) -> Dict[str, Any]:
    target = dict(TARGET_DEFAULTS)
    target["layout_code"] = target_layout_code
    return target


def build_action(slot: Dict[str, Any], source: Dict[str, Any] | None = None) -> Dict[str, Any]:
    target = build_target(slot.get("target_layout_code") or slot.get("layout_code", TARGET_DEFAULTS["layout_code"]))
    src_layout = None
    source_resource_type = None
    source_substance = None
    if source:
        src_layout = source.get("source_layout_code") or source.get("layout_code")
        source_resource_type = source.get("resource_type")
        source_substance = source.get("substance")

    add_weight = to_mg(slot["add_weight"], slot["unit"])
    offset = calculate_offset(slot["add_weight"], slot["unit"])
    step_offset = offset / 4.0

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
            "src_layout_code": src_layout,
            "resource_type": source_resource_type,
            "substance": source_substance,
            "add_weight": add_weight,
            "offset": offset,
            "custom": {
                "unit": "mg",
                "unitOptions": ["mg", "g"],
                "step": {"offset": step_offset},
            },
        },
    }


def save_output(action: Dict[str, Any]) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUT_DIR / f"generated_add_solid_{ts}.json"
    path.write_text(json.dumps(action, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("step_unit", help="step_unit JSON 对象或 JSON 文件路径")
    args = parser.parse_args()

    parsed = load_step_unit(args.step_unit)
    slot = parsed["skill_input"]
    source = parsed.get("resource_info")
    if "target_layout_code" not in slot and "layout_code" in slot:
        slot["target_layout_code"] = slot["layout_code"]
    action = build_action(slot, source)
    out = save_output(action)
    print(f"saved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
