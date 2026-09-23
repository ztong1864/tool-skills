#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import re
import secrets
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

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
    "unit_type": "exp_filtering_samples",
}

DST_DEFAULT = {"resource_type": "TTS2TCP_V2", "tray_QR_code": "TTS2TCP_V2_01"}


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
    if any(k in data for k in ("source_layout_code", "layout_code", "add_volume", "dst_pos", "unit")):
        return {"skill_input": data}
    raise ValueError("输入必须是 step_unit JSON 对象或包含 skill_input 的 JSON")


def load_dst_map() -> Dict[str, str]:
    path = KB_DIR / "filter_dst_map.json"
    if path.exists():
        data = load_json(path)
        if isinstance(data, dict):
            return data
    return {}


def make_unit_id() -> str:
    return f"unit-{secrets.token_hex(6)}"


def to_ml(value: float, unit: str) -> float:
    unit = unit.lower()
    if unit == "μl" or unit == "ul":
        return value / 1000.0
    if unit == "ml":
        return value
    if unit == "l":
        return value * 1000.0
    raise ValueError(f"不支持的体积单位: {unit}")


def infer_dst(source_layout_code: str, dst_map: Dict[str, str]) -> str:
    if source_layout_code in dst_map:
        return dst_map[source_layout_code]
    m = re.search(r"T-\d+:(\d+)$", source_layout_code)
    idx = int(m.group(1)) if m else 0
    return f"W3-5:{idx}"


def validate_dst(dst_pos: str, resources: List[Dict[str, Any]]) -> None:
    for r in resources:
        if r.get("layout_code") != dst_pos:
            continue
        if r.get("resource_type") != DST_DEFAULT["resource_type"]:
            continue
        if r.get("tray_QR_code") != DST_DEFAULT["tray_QR_code"]:
            continue
        return
    raise ValueError(f"过滤目标位不存在或不匹配：{dst_pos}")


def build_target(source_layout_code: str) -> Dict[str, Any]:
    target = dict(TARGET_DEFAULTS)
    target["layout_code"] = source_layout_code
    return target


def build_action(slot: Dict[str, Any], dst_pos: str) -> Dict[str, Any]:
    target = build_target(slot["source_layout_code"])
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
            "add_volume": to_ml(slot["add_volume"], slot["unit"]),
            "offset": 0.0,
            "custom": {
                "unit": "mL",
                "unitOptions": ["μL", "mL", "L"],
                "step": {"add_volume": 0.1},
            },
            "dilute_volume": 0.0,
            "quick_cap": 1,
            "use_tip_type": "",
            "dst": {"pos": dst_pos, **DST_DEFAULT},
        },
    }


def save_output(action: Dict[str, Any]) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUT_DIR / f"generated_filter_{ts}.json"
    path.write_text(json.dumps(action, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("step_unit", help="step_unit JSON 对象或 JSON 文件路径")
    args = parser.parse_args()

    parsed = load_step_unit(args.step_unit)
    dst_map = load_dst_map()
    slot = parsed["skill_input"]
    if "source_layout_code" not in slot and "layout_code" in slot:
        slot["source_layout_code"] = slot["layout_code"]
    dst_pos = slot.get("dst_pos") or infer_dst(slot["source_layout_code"], dst_map)
    action = build_action(slot, dst_pos)
    out = save_output(action)
    print(f"saved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
