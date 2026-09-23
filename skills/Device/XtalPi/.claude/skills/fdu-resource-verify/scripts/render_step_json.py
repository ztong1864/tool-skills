#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_step_json(step_json_path: Path) -> Dict[str, Any]:
    if not step_json_path.exists():
        raise FileNotFoundError(f"步骤JSON文件不存在: {step_json_path}")
    return load_json(step_json_path)


def load_resource_info() -> List[Dict[str, Any]]:
    resource_path = ROOT / "KB" / "resource_info.json"
    if not resource_path.exists():
        raise FileNotFoundError(f"资源信息文件不存在: {resource_path}")
    data = load_json(resource_path)
    if not isinstance(data, list):
        raise ValueError("resource_info.json 必须是数组。")
    return data


def normalize_substance_name(name: str) -> str:
    return str(name).strip().lower()


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


def pick_resource_for_step(
    step: Dict[str, Any],
    resource_list: List[Dict[str, Any]],
    resource_index: Dict[str, List[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    unit_type = str(step.get("unit_type", "")).strip()
    skill_input = step.get("skill_input") or {}
    if not isinstance(skill_input, dict):
        return None

    if unit_type == "exp_filtering_samples":
        layout_code = str(skill_input.get("source_layout_code", "")).strip()
        if not layout_code:
            return None
        resource = find_resource_by_layout_code(layout_code, resource_list)
        return resource if resource and is_resource_available(resource) else None

    if unit_type == "exp_high_filtering_samples":
        substance = str(skill_input.get("substance", "")).strip()
        if not substance:
            return None
        matches = filter_available_resources(find_resources_by_substance(substance, resource_index))
        return matches[0] if matches else None

    if unit_type in {"exp_add_solid", "exp_pipetting"}:
        substance = str(skill_input.get("substance", "")).strip()
        if not substance:
            return None
        matches = filter_available_resources(find_resources_by_substance(substance, resource_index))
        return matches[0] if matches else None

    return None


def attach_resource_info_from_details(
    step_json: Dict[str, Any],
    verification_details: List[Dict[str, Any]],
) -> Dict[str, Any]:
    enriched = dict(step_json)
    result_by_step_index = {
        result.get("step_index"): result.get("resource_info")
        for result in verification_details
        if isinstance(result, dict)
    }

    steps = enriched.get("steps", [])
    if isinstance(steps, list):
        enriched_steps: List[Any] = []
        for step in steps:
            if not isinstance(step, dict):
                enriched_steps.append(step)
                continue

            updated_step = dict(step)
            updated_step["resource_info"] = result_by_step_index.get(updated_step.get("step_index"))
            enriched_steps.append(updated_step)
        enriched["steps"] = enriched_steps

    return enriched


def attach_resource_info_direct(
    step_json: Dict[str, Any],
    resource_list: List[Dict[str, Any]],
) -> Dict[str, Any]:
    resource_index = build_resource_index(resource_list)
    enriched = dict(step_json)

    steps = enriched.get("steps", [])
    if isinstance(steps, list):
        enriched_steps: List[Any] = []
        for step in steps:
            if not isinstance(step, dict):
                enriched_steps.append(step)
                continue

            updated_step = dict(step)
            updated_step["resource_info"] = pick_resource_for_step(step, resource_list, resource_index)
            enriched_steps.append(updated_step)
        enriched["steps"] = enriched_steps

    return enriched


def save_enriched_step_json(step_json: Dict[str, Any], output_path: Path) -> None:
    output_path.write_text(
        json.dumps(step_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"增强后的 step JSON 已保存到: {output_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="渲染带 resource_info 的 step JSON。")
    parser.add_argument("step_json_path", help="原始 step JSON 文件路径")
    parser.add_argument(
        "verification_result_path",
        nargs="?",
        default="",
        help="verification_result JSON 文件路径；不提供时进入直接回填模式",
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        help="直接回填资源信息，不读取 verification_result",
    )
    parser.add_argument(
        "--output-path",
        default="",
        help="输出路径。默认写入 output/verified_step_json_<timestamp>.json",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    step_json_path = Path(args.step_json_path)
    verification_result_path = Path(args.verification_result_path) if args.verification_result_path else None
    output_path = (
        Path(args.output_path)
        if args.output_path
        else OUTPUT_DIR / f"verified_step_json_{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.json"
    )

    try:
        step_json = load_step_json(step_json_path)

        if args.direct or verification_result_path is None:
            resource_list = load_resource_info()
            enriched_step_json = attach_resource_info_direct(step_json, resource_list)
            print("直接回填模式: 已使用当前 resource_info.json 回填资源信息。")
        else:
            verification_result = load_json(verification_result_path)
            details = verification_result.get("details", [])
            if not isinstance(details, list):
                raise ValueError("verification_result.details 必须是数组。")
            enriched_step_json = attach_resource_info_from_details(step_json, details)
            print("校验回填模式: 已根据 verification_result 回填资源信息。")

        save_enriched_step_json(enriched_step_json, output_path)
        return 0
    except FileNotFoundError as exc:
        print(f"错误: {exc}")
        return 1
    except Exception as exc:
        print(f"未知错误: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
