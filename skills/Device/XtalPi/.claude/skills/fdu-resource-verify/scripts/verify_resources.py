#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MAX_RESOURCE_AGE_HOURS = 24
SUPPORTED_DOWNSTREAM_SKILLS = {
    "fdu-add-liquid-json",
    "fdu-add-solid-json",
    "fdu-high-filter-json",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_resource_info() -> List[Dict[str, Any]]:
    resource_path = ROOT / "KB" / "resource_info.json"
    if not resource_path.exists():
        raise FileNotFoundError(f"资源信息文件不存在: {resource_path}")
    return load_json(resource_path)


def normalize_substance_name(name: str) -> str:
    return name.strip().lower()


def build_resource_index(resource_list: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    index: Dict[str, List[Dict[str, Any]]] = {}
    for resource in resource_list:
        substance = normalize_substance_name(resource.get("substance", ""))
        if substance:
            index.setdefault(substance, []).append(resource)
    return index


def find_resources_by_substance(
    substance: str,
    resource_index: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    normalized = normalize_substance_name(substance)
    if normalized in resource_index:
        return resource_index[normalized]

    matches: List[Dict[str, Any]] = []
    for key, resources in resource_index.items():
        if normalized in key or key in normalized:
            matches.extend(resources)
    return matches


def find_resource_by_layout_code(
    layout_code: str,
    resource_list: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    for resource in resource_list:
        if resource.get("layout_code") == layout_code:
            return resource
    return None


def is_resource_available(resource: Dict[str, Any]) -> bool:
    return resource.get("status", 0) == 0


def filter_available_resources(resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [resource for resource in resources if is_resource_available(resource)]


def format_resource_info(resource: Dict[str, Any]) -> str:
    parts = [
        f"layout_code: {resource.get('layout_code', 'N/A')}",
        f"resource_type: {resource.get('resource_type', 'N/A')}",
    ]
    if resource.get("available_volume") is not None:
        parts.append(f"available_volume: {resource['available_volume']} mL")
    if resource.get("available_weight") is not None:
        parts.append(f"available_weight: {resource['available_weight']} mg")
    return ", ".join(parts)


def infer_weight_unit(resource: Dict[str, Any], default: str = "mg") -> str:
    unit = (resource.get("unit") or "").strip().lower()
    if unit in {"mg", "g"}:
        return unit
    return default


def infer_volume_unit(resource: Dict[str, Any], default: str = "mL") -> str:
    unit = (resource.get("unit") or "").strip()
    normalized = unit.lower()
    if normalized in {"ul", "μl", "ml", "l"}:
        if normalized == "ul":
            return "uL"
        if normalized == "μl":
            return "μL"
        if normalized == "ml":
            return "mL"
        return "L"
    return default


def to_mg(value: float, unit: str) -> float:
    unit = unit.lower()
    if unit == "g":
        return value * 1000.0
    if unit == "mg":
        return value
    raise ValueError(f"不支持的重量单位: {unit}")


def to_ml(value: float, unit: str) -> float:
    unit = unit.lower()
    if unit in {"μl", "ul"}:
        return value / 1000.0
    if unit == "ml":
        return value
    if unit == "l":
        return value * 1000.0
    raise ValueError(f"不支持的体积单位: {unit}")


def validate_weight(
    requested_weight: float,
    requested_unit: str,
    available_weight: float,
    available_unit: str,
) -> tuple[bool, str]:
    try:
        req_mg = to_mg(requested_weight, requested_unit)
        avail_mg = to_mg(available_weight, available_unit)
        if req_mg > avail_mg:
            return False, f"重量不足：请求 {req_mg} mg，可用 {avail_mg} mg"
        return True, f"重量验证通过：请求 {req_mg} mg，可用 {avail_mg} mg"
    except ValueError as exc:
        return False, f"重量验证失败：{exc}"


def validate_volume(
    requested_volume: float,
    requested_unit: str,
    available_volume: float,
    available_unit: str,
) -> tuple[bool, str]:
    try:
        req_ml = to_ml(requested_volume, requested_unit)
        avail_ml = to_ml(available_volume, available_unit)
        if req_ml > avail_ml:
            return False, f"体积不足：请求 {req_ml} mL，可用 {avail_ml} mL"
        return True, f"体积验证通过：请求 {req_ml} mL，可用 {avail_ml} mL"
    except ValueError as exc:
        return False, f"体积验证失败：{exc}"


def get_latest_snapshot_path() -> Path | None:
    candidates = sorted(ROOT.joinpath("KB").glob("resource_info_*.json"))
    filtered = [path for path in candidates if path.name != "resource_info.json"]
    return filtered[-1] if filtered else None


def is_resource_info_stale(path: Path) -> bool:
    age_hours = (time.time() - path.stat().st_mtime) / 3600
    return age_hours > MAX_RESOURCE_AGE_HOURS


def refresh_resource_info() -> None:
    script_path = ROOT / "scripts" / "fetch_resource_info.py"
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        error_text = (result.stderr or result.stdout).strip()
        raise RuntimeError(
            "刷新资源信息失败，请检查 fetch_resource_info.py 或设备接口状态。"
            + (f"\n{error_text}" if error_text else "")
        )


def extract_resources_from_snapshot(snapshot_path: Path) -> List[Dict[str, Any]]:
    data = load_json(snapshot_path)
    if isinstance(data, dict) and isinstance(data.get("resources"), list):
        resources = data["resources"]
    elif isinstance(data, list):
        resources = data
    else:
        raise RuntimeError(f"资源快照格式不正确: {snapshot_path}")

    resource_info_path = ROOT / "KB" / "resource_info.json"
    resource_info_path.write_text(
        json.dumps(resources, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return resources


def ensure_resource_info() -> List[Dict[str, Any]]:
    resource_info_path = ROOT / "KB" / "resource_info.json"
    snapshot_path = get_latest_snapshot_path()
    needs_refresh = not resource_info_path.exists() or snapshot_path is None or is_resource_info_stale(snapshot_path)

    if needs_refresh:
        try:
            refresh_resource_info()
        except Exception as exc:
            snapshot_path = get_latest_snapshot_path()
            if snapshot_path is not None and snapshot_path.exists():
                print(f"警告: 无法刷新资源信息 ({exc})，使用本地快照 {snapshot_path.name}", flush=True)
                return extract_resources_from_snapshot(snapshot_path)
            if resource_info_path.exists():
                print(f"警告: 无法刷新资源信息 ({exc})，使用本地 resource_info.json", flush=True)
                return load_resource_info()
            raise

    if not resource_info_path.exists():
        raise FileNotFoundError(f"未找到资源信息文件: {resource_info_path}")
    return load_resource_info()


def load_step_json(step_json_path: Path) -> Dict[str, Any]:
    if not step_json_path.exists():
        raise FileNotFoundError(f"步骤JSON文件不存在: {step_json_path}")
    return load_json(step_json_path)


def extract_substances(step_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    substances: List[Dict[str, Any]] = []
    steps = step_json.get("steps", [])

    for step in steps:
        step_index = step.get("step_index", 0)
        unit_type = step.get("unit_type", "")
        downstream_skill = step.get("downstream_skill", "")
        instruction = step.get("instruction", "")
        skill_input = step.get("skill_input", {})
        substance = skill_input.get("substance", "")

        if downstream_skill not in SUPPORTED_DOWNSTREAM_SKILLS:
            continue

        if substance:
            substances.append(
                {
                    "step_index": step_index,
                    "unit_type": unit_type,
                    "downstream_skill": downstream_skill,
                    "instruction": instruction,
                    "substance": substance,
                    "skill_input": skill_input,
                }
            )

    return substances


def verify_substance(
    substance_info: Dict[str, Any],
    resource_list: List[Dict[str, Any]],
    resource_index: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    unit_type = substance_info.get("unit_type", "")
    skill_input = substance_info.get("skill_input", {})
    substance = substance_info["substance"]

    if unit_type == "exp_filtering_samples":
        source_layout_code = skill_input.get("source_layout_code", "")
        source_resource = find_resource_by_layout_code(source_layout_code, resource_list)
        matches = [source_resource] if source_resource else []
    elif unit_type == "exp_high_filtering_samples":
        matches = find_resources_by_substance(substance, resource_index)
    else:
        matches = find_resources_by_substance(substance, resource_index)

    available = filter_available_resources(matches)
    selected_resource = available[0] if available else None

    result = {
        **substance_info,
        "matches_count": len(matches),
        "available_count": len(available),
        "available_resources": available,
        "resource_info": selected_resource,
        "is_valid": len(available) > 0,
        "validation_message": "",
        "quantity_validation": None,
    }

    if available:
        resource = available[0]
        unit_type = substance_info.get("unit_type", "")
        skill_input = substance_info.get("skill_input", {})

        if unit_type == "exp_add_solid":
            requested_weight = skill_input.get("add_weight", 0)
            requested_unit = skill_input.get("unit", "mg")
            available_weight = resource.get("available_weight", 0)
            available_unit = infer_weight_unit(resource, default="mg")

            is_valid, message = validate_weight(
                requested_weight,
                requested_unit,
                available_weight,
                available_unit,
            )
            result["quantity_validation"] = {
                "type": "weight",
                "requested": {"value": requested_weight, "unit": requested_unit},
                "available": {"value": available_weight, "unit": available_unit},
                "is_valid": is_valid,
                "message": message,
            }
            result["is_valid"] = is_valid
            result["validation_message"] = message

        elif unit_type == "exp_pipetting":
            requested_volume = skill_input.get("add_volume", 0)
            requested_unit = skill_input.get("unit", "mL")
            available_volume = resource.get("available_volume", 0)
            available_unit = infer_volume_unit(resource, default="mL")

            is_valid, message = validate_volume(
                requested_volume,
                requested_unit,
                available_volume,
                available_unit,
            )
            result["quantity_validation"] = {
                "type": "volume",
                "requested": {"value": requested_volume, "unit": requested_unit},
                "available": {"value": available_volume, "unit": available_unit},
                "is_valid": is_valid,
                "message": message,
            }
            result["is_valid"] = is_valid
            result["validation_message"] = message

        elif unit_type == "exp_filtering_samples":
            requested_volume = skill_input.get("add_volume", 0)
            requested_unit = skill_input.get("unit", "mL")
            available_volume = resource.get("available_volume", 0)
            available_unit = infer_volume_unit(resource, default="mL")
            source_layout_code = skill_input.get("source_layout_code", "")

            is_valid, message = validate_volume(
                requested_volume,
                requested_unit,
                available_volume,
                available_unit,
            )
            result["quantity_validation"] = {
                "type": "volume",
                "requested": {"value": requested_volume, "unit": requested_unit},
                "available": {"value": available_volume, "unit": available_unit},
                "is_valid": is_valid,
                "message": message,
            }
            result["is_valid"] = is_valid
            result["validation_message"] = (
                f"{message} (source_layout_code={source_layout_code})"
                if source_layout_code
                else message
            )

        elif unit_type == "exp_high_filtering_samples":
            layout_code = skill_input.get("layout_code", "")
            substance = skill_input.get("substance", "")
            dilute_volume = skill_input.get("dilute_volume", 0)
            dilute_unit = skill_input.get("unit", "mL")

            if substance:
                dilute_matches = find_resources_by_substance(substance, resource_index)
                dilute_available = filter_available_resources(dilute_matches)

                if dilute_available:
                    dilute_resource = dilute_available[0]
                    available_volume = dilute_resource.get("available_volume", 0)
                    available_unit = infer_volume_unit(dilute_resource, default="mL")

                    is_valid, message = validate_volume(
                        dilute_volume,
                        dilute_unit,
                        available_volume,
                        available_unit,
                    )
                    result["quantity_validation"] = {
                        "type": "volume",
                        "requested": {"value": dilute_volume, "unit": dilute_unit},
                        "available": {"value": available_volume, "unit": available_unit},
                        "is_valid": is_valid,
                        "message": message,
                    }
                    result["is_valid"] = is_valid
                    result["validation_message"] = (
                        f"{message} (dilute_substance={substance}, layout_code={layout_code})"
                    )
                    result["resource_info"] = dilute_resource
                else:
                    result["is_valid"] = False
                    result["validation_message"] = f"稀释剂 {substance} 不可用 (layout_code={layout_code})"
            else:
                result["is_valid"] = False
                result["validation_message"] = "高滤步骤缺少稀释剂信息"

    return result


def verify_step_json(
    step_json: Dict[str, Any],
    resource_list: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    resource_index = build_resource_index(resource_list)
    substances = extract_substances(step_json)
    return [verify_substance(sub, resource_list, resource_index) for sub in substances]


def print_verification_result(results: List[Dict[str, Any]]) -> None:
    print("=" * 80)
    print("资源验证结果")
    print("=" * 80)
    print()

    total = len(results)
    valid = sum(1 for r in results if r.get("is_valid", False))
    invalid = total - valid

    print(f"总步骤数: {total}")
    print(f"验证通过: {valid}")
    print(f"验证失败: {invalid}")
    print()

    print("=" * 80)
    print("详细验证信息")
    print("=" * 80)
    print()

    for result in results:
        step_index = result["step_index"]
        unit_type = result["unit_type"]
        instruction = result["instruction"]
        substance = result["substance"] or result.get("skill_input", {}).get("source_layout_code", "")
        matches_count = result["matches_count"]
        available_count = result["available_count"]
        available_resources = result["available_resources"]
        quantity_validation = result.get("quantity_validation")

        print(f"步骤 {step_index} [{unit_type}]")
        print(f"指令: {instruction}")
        print(f"物质: {substance}")

        if available_count == 0:
            print(f"状态: ✗ 资源不可用 (找到 {matches_count} 个匹配, {available_count} 个可用)")
            print("  提示: 请检查资源名称或补充相关资源")
        elif quantity_validation:
            requested = quantity_validation.get("requested", {})
            available = quantity_validation.get("available", {})
            qv_message = quantity_validation.get("message", "")
            qv_is_valid = quantity_validation.get("is_valid", False)

            if qv_is_valid:
                print(f"状态: ✓ {qv_message}")
            else:
                print(f"状态: ✗ {qv_message}")

            print(f"  请求: {requested['value']} {requested['unit']}")
            print(f"  可用: {available['value']} {available['unit']}")

            if available_resources:
                print("匹配的资源:")
                for resource in available_resources:
                    print(f"  - {format_resource_info(resource)}")
        else:
            print(f"状态: ✓ 资源可用 (找到 {matches_count} 个匹配, {available_count} 个可用)")
            if available_resources:
                print("匹配的资源:")
                for resource in available_resources:
                    print(f"  - {format_resource_info(resource)}")

        print()

    print("=" * 80)
    print("验证完成")
    print("=" * 80)


def save_verification_result(results: List[Dict[str, Any]], output_path: Path) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    save_data = {
        "timestamp": timestamp,
        "summary": {
            "total_steps": len(results),
            "valid": sum(1 for r in results if r.get("is_valid", False)),
            "invalid": sum(1 for r in results if not r.get("is_valid", True)),
        },
        "details": [
            {
                "step_index": r["step_index"],
                "unit_type": r["unit_type"],
                "instruction": r["instruction"],
                "substance": r["substance"],
                "matches_count": r["matches_count"],
                "available_count": r["available_count"],
                "is_valid": r.get("is_valid", False),
                "validation_message": r.get("validation_message", ""),
                "quantity_validation": r.get("quantity_validation"),
                "resource_info": r.get("resource_info"),
                "available_resources": r.get("available_resources", []),
            }
            for r in results
        ],
    }

    output_path.write_text(
        json.dumps(save_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"验证结果已保存到: {output_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="校验 step JSON 对应资源是否可用。")
    parser.add_argument("step_json_path", help="fdu-step-json 生成的 step JSON 文件路径")
    parser.add_argument(
        "--output-path",
        default="",
        help="验证结果输出路径。默认写入 output/verification_result_<timestamp>.json",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    step_json_path = Path(args.step_json_path)
    output_path = (
        Path(args.output_path)
        if args.output_path
        else OUTPUT_DIR / f"verification_result_{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.json"
    )

    try:
        step_json = load_step_json(step_json_path)
        resource_list = ensure_resource_info()
        results = verify_step_json(step_json, resource_list)
        invalid_count = sum(1 for result in results if not result.get("is_valid", False))

        print_verification_result(results)
        save_verification_result(results, output_path)
        if invalid_count > 0:
            print("提醒: 存在资源缺失或数量不足，请先补充资源后再进入回填或后续编排。")
        return 0
    except FileNotFoundError as exc:
        print(f"错误: {exc}")
        return 1
    except Exception as exc:
        print(f"未知错误: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
