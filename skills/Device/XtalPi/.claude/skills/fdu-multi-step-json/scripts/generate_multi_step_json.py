#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

STEP_SKILL_ROOT = ROOT.parent / "fdu-step-json"
STEP_OUTPUT_DIR = STEP_SKILL_ROOT / "output"
STEP_SCRIPT_PATH = STEP_SKILL_ROOT / "scripts" / "generate_step_json.py"


class MultiStepGenerationError(Exception):
    pass


def log_status(message: str) -> None:
    print(message, flush=True)


def progress_label(done: int, total: int) -> str:
    return f"[{done}/{total}]"


def write_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="将多个实验方案合并为一个多方案 step JSON。")
    parser.add_argument("--plan-files", nargs="+", required=True, help="多个 .md 实验方案文件路径")
    parser.add_argument(
        "--target-layout-codes",
        nargs="*",
        default=[],
        help="与 plan-files 一一对应的目标反应位",
    )
    parser.add_argument("--task-name", type=str, default="", help="输出中的 task_name")
    return parser


def replace_layout_fields(skill_input: Dict[str, Any], target_layout_code: str) -> Dict[str, Any]:
    updated = dict(skill_input)
    if "target_layout_code" in updated:
        updated["target_layout_code"] = target_layout_code
    if "source_layout_code" in updated:
        updated["source_layout_code"] = target_layout_code
    return updated


def remap_step(step: Dict[str, Any], target_layout_code: str) -> Dict[str, Any]:
    updated = deepcopy(step)
    skill_input = updated.get("skill_input")
    if not isinstance(skill_input, dict):
        raise MultiStepGenerationError("step.skill_input 必须是对象。")

    updated["skill_input"] = replace_layout_fields(skill_input, target_layout_code)
    updated["instruction"] = str(updated.get("instruction", "")).replace("T-3:0", target_layout_code)
    return updated


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def list_step_outputs() -> set[Path]:
    return set(STEP_OUTPUT_DIR.glob("generated_step_json_*.json"))


STEP_JSON_TIMEOUT_SECONDS = 180


def call_fdu_step_json(plan_file: Path) -> Dict[str, Any]:
    if not STEP_SCRIPT_PATH.exists():
        raise MultiStepGenerationError(f"未找到 fdu-step-json 脚本：{STEP_SCRIPT_PATH}")

    before = list_step_outputs()
    cmd = [sys.executable, str(STEP_SCRIPT_PATH), "--plan-file", str(plan_file)]

    try:
        subprocess.run(
            cmd,
            check=True,
            cwd=str(STEP_SKILL_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=STEP_JSON_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise MultiStepGenerationError(
            f"调用 fdu-step-json 超时 ({STEP_JSON_TIMEOUT_SECONDS}s)：{exc}"
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else ""
        stdout = exc.stdout.strip() if exc.stdout else ""
        message = stderr or stdout or str(exc)
        raise MultiStepGenerationError(
            f"调用 fdu-step-json 失败：{message}"
        ) from exc
    except KeyboardInterrupt:
        raise MultiStepGenerationError("调用 fdu-step-json 时收到键盘中断。请重试或检查上游命令是否已停止。")

    after = list_step_outputs()
    created = sorted(after - before, key=lambda p: p.stat().st_mtime)
    if created:
        return read_json(created[-1])

    candidates = sorted(after, key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise MultiStepGenerationError("fdu-step-json 未生成任何输出文件。")
    return read_json(candidates[0])


def get_unit_type(step: Dict[str, Any]) -> str:
    unit_type = str(step.get("unit_type", "")).strip()
    if not unit_type:
        raise MultiStepGenerationError("step.unit_type 不能为空。")
    return unit_type


def parse_unit_column(layout_code: str) -> int:
    match = re.search(r":(\d+)$", str(layout_code).strip())
    return int(match.group(1)) if match else 0


def get_step_layout_code(step: Dict[str, Any]) -> str:
    skill_input = step.get("skill_input")
    if not isinstance(skill_input, dict):
        raise MultiStepGenerationError("step.skill_input 必须是对象。")

    layout_code = str(skill_input.get("layout_code", "")).strip()
    if not layout_code:
        raise MultiStepGenerationError("step.skill_input.layout_code 不能为空。")
    return layout_code


def get_step_unit_column(step: Dict[str, Any]) -> int:
    skill_input = step.get("skill_input")
    if not isinstance(skill_input, dict):
        raise MultiStepGenerationError("step.skill_input 必须是对象。")

    unit_column = skill_input.get("unit_column")
    if isinstance(unit_column, int):
        return unit_column
    if isinstance(unit_column, str) and unit_column.strip().isdigit():
        return int(unit_column.strip())
    return parse_unit_column(get_step_layout_code(step))


def normalize_anchor_type(unit_type: str) -> Optional[str]:
    if unit_type == "exp_magnetic_stirrer":
        return "stirrer"
    if unit_type in {"exp_filtering_samples", "exp_high_filtering_samples"}:
        return "filtering"
    return None


def build_anchor_positions(step_group: Sequence[Dict[str, Any]]) -> List[int]:
    if not step_group:
        return []

    positions = [0]
    for idx, step in enumerate(step_group[1:], start=1):
        if normalize_anchor_type(get_unit_type(step)) is not None:
            positions.append(idx)

    last_idx = len(step_group) - 1
    if positions[-1] != last_idx:
        positions.append(last_idx)

    return positions


def build_anchor_signature(step_group: Sequence[Dict[str, Any]], anchor_positions: Sequence[int]) -> List[str]:
    if not step_group or not anchor_positions:
        return []

    signature = ["first"]
    last_idx = len(step_group) - 1
    for position in anchor_positions[1:]:
        if position == last_idx:
            signature.append(normalize_anchor_type(get_unit_type(step_group[position])) or "last")
            continue

        anchor_type = normalize_anchor_type(get_unit_type(step_group[position]))
        if anchor_type is None:
            raise MultiStepGenerationError("对齐锚点类型不受支持。")
        signature.append(anchor_type)

    return signature


def validate_anchor_signatures(
    step_groups: Sequence[Sequence[Dict[str, Any]]],
    anchor_positions_list: Sequence[Sequence[int]],
) -> None:
    expected_signature: Optional[List[str]] = None

    for group_idx, (step_group, anchor_positions) in enumerate(
        zip(step_groups, anchor_positions_list),
        start=1,
    ):
        current_signature = build_anchor_signature(step_group, anchor_positions)
        if expected_signature is None:
            expected_signature = current_signature
            continue

        if current_signature != expected_signature:
            layout_code = get_step_layout_code(step_group[0]) if step_group else f"group-{group_idx}"
            raise MultiStepGenerationError(
                "各列实验的对齐锚点序列不一致："
                f"{layout_code} -> {current_signature}，期望 {expected_signature}"
            )


def distribute_rows_evenly(start_row: int, end_row: int, step_count: int) -> List[int]:
    available_rows = list(range(start_row + 1, end_row))
    slot_count = len(available_rows)

    if step_count == 0:
        return []
    if step_count > slot_count:
        raise MultiStepGenerationError("无法在目标表格中安排所有步骤。")
    if step_count == slot_count:
        return available_rows
    if step_count == 1:
        return [available_rows[-1]]

    chosen_indices: List[int] = []
    last_index = slot_count - 1
    for idx in range(step_count):
        raw_index = round(idx * last_index / (step_count - 1))
        min_index = 0 if not chosen_indices else chosen_indices[-1] + 1
        max_index = slot_count - (step_count - idx)
        chosen_indices.append(min(max(raw_index, min_index), max_index))

    return [available_rows[idx] for idx in chosen_indices]


def align_step_group_rows(
    step_group: Sequence[Dict[str, Any]],
    anchor_positions: Sequence[int],
    anchor_rows: Sequence[int],
) -> List[Tuple[int, Dict[str, Any]]]:
    aligned_steps: List[Tuple[int, Dict[str, Any]]] = []

    for anchor_idx, step_idx in enumerate(anchor_positions):
        aligned_steps.append((anchor_rows[anchor_idx], deepcopy(step_group[step_idx])))

    for segment_idx in range(len(anchor_positions) - 1):
        start_step_idx = anchor_positions[segment_idx]
        end_step_idx = anchor_positions[segment_idx + 1]
        interior_steps = step_group[start_step_idx + 1 : end_step_idx]
        interior_rows = distribute_rows_evenly(
            anchor_rows[segment_idx],
            anchor_rows[segment_idx + 1],
            len(interior_steps),
        )
        aligned_steps.extend(
            (unit_row, deepcopy(step))
            for unit_row, step in zip(interior_rows, interior_steps)
        )

    return aligned_steps


def combine_steps(step_groups: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if not step_groups:
        return []

    sorted_groups = sorted(
        step_groups,
        key=lambda group: (
            get_step_unit_column(group[0]),
            get_step_layout_code(group[0]),
        ),
    )
    anchor_positions_list = [build_anchor_positions(group) for group in sorted_groups]
    validate_anchor_signatures(sorted_groups, anchor_positions_list)

    segment_max_lengths: List[int] = []
    for segment_idx in range(len(anchor_positions_list[0]) - 1):
        segment_max_lengths.append(
            max(
                anchor_positions[segment_idx + 1] - anchor_positions[segment_idx] - 1
                for anchor_positions in anchor_positions_list
            )
        )

    anchor_rows = [0]
    for segment_max_length in segment_max_lengths:
        anchor_rows.append(anchor_rows[-1] + segment_max_length + 1)

    combined_with_positions: List[Tuple[int, int, Dict[str, Any]]] = []
    for step_group, anchor_positions in zip(sorted_groups, anchor_positions_list):
        aligned_steps = align_step_group_rows(step_group, anchor_positions, anchor_rows)
        for unit_row, step in aligned_steps:
            skill_input = step.get("skill_input")
            if not isinstance(skill_input, dict):
                raise MultiStepGenerationError("step.skill_input 必须是对象。")
            skill_input["unit_row"] = unit_row
            combined_with_positions.append((unit_row, get_step_unit_column(step), step))

    combined_with_positions.sort(key=lambda item: (item[0], item[1]))

    combined: List[Dict[str, Any]] = []
    for step_index, (_, _, step) in enumerate(combined_with_positions, start=1):
        step["step_index"] = step_index
        combined.append(step)

    return combined


def generate_multi_step_json_from_files(
    plan_files: List[str], target_layout_codes: List[str], task_name: str
) -> Dict[str, Any]:
    if not plan_files:
        raise MultiStepGenerationError("必须提供至少一个 plan file。")

    if target_layout_codes and len(target_layout_codes) != len(plan_files):
        raise MultiStepGenerationError("target_layout_codes 的数量必须与 plan_files 一致。")

    step_groups: List[List[Dict[str, Any]]] = []
    log_status(f"Generating {len(plan_files)} multi-step JSONs")

    for index, plan_file in enumerate(plan_files, start=1):
        path = Path(plan_file).resolve()
        if not path.exists():
            raise MultiStepGenerationError(f"plans[{index}] 文件不存在：{path}")

        if not path.read_text(encoding="utf-8").strip():
            raise MultiStepGenerationError(f"plans[{index}] 实验方案为空：{path}")

        step_json = call_fdu_step_json(path)
        steps = step_json.get("steps")
        if not isinstance(steps, list) or not steps:
            raise MultiStepGenerationError(f"fdu-step-json 返回结果缺少有效 steps：{path}")

        log_status(f"{progress_label(index, len(plan_files))} fdu-step-json completed: {path.name} ({len(steps)} steps)")

        if target_layout_codes:
            target_layout_code = target_layout_codes[index - 1]
            remapped_steps = [remap_step(step, target_layout_code) for step in steps]
        else:
            remapped_steps = [deepcopy(step) for step in steps]

        step_groups.append(remapped_steps)

    result: Dict[str, Any] = {
        "timestamp": datetime.now().strftime("%Y-%m-%d-%H-%M-%S"),
        "steps": combine_steps(step_groups),
    }

    if task_name.strip():
        result["task_name"] = task_name.strip()

    return result


def main() -> int:
    args = build_parser().parse_args()

    try:
        result = generate_multi_step_json_from_files(
            args.plan_files,
            args.target_layout_codes,
            args.task_name,
        )
        out_path = OUTPUT_DIR / f"generated_multi_step_json_{result['timestamp']}.json"
        write_json(result, out_path)
        log_status(f"{progress_label(len(args.plan_files), len(args.plan_files))} Multi-step JSON generated: {out_path}")
        log_status(f"步骤总数：{len(result['steps'])}")
        return 0
    except MultiStepGenerationError as exc:
        print(f"生成失败：{exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"发生未预期错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
