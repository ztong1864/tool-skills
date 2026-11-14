#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"

STEP_SKILL_ROOT = ROOT.parent / "fdu-step-json"
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
    parser.add_argument("--output", type=str, default="",
                        help="总 step JSON 的输出路径（写进 mission 的 artifacts 目录）；默认 output/generated_multi_step_json_<timestamp>.json")
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


STEP_JSON_TIMEOUT_SECONDS = 180


def call_fdu_step_json(plan_file: Path) -> Dict[str, Any]:
    """Run fdu-step-json for one plan into a private temporary file: picking the newest file in fdu-step-json's
    shared output/ could take another user's run, and that folder may not be writable."""
    if not STEP_SCRIPT_PATH.exists():
        raise MultiStepGenerationError(f"未找到 fdu-step-json 脚本：{STEP_SCRIPT_PATH}")
    with tempfile.TemporaryDirectory(prefix="fdu_step_json_") as work_dir:
        return _run_fdu_step_json(plan_file, Path(work_dir) / "step_json.json")


def _run_fdu_step_json(plan_file: Path, output: Path) -> Dict[str, Any]:
    cmd = [sys.executable, str(STEP_SCRIPT_PATH), "--plan-file", str(plan_file), "--output", str(output)]

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

    if not output.exists():
        raise MultiStepGenerationError("fdu-step-json 未生成任何输出文件。")
    return read_json(output)


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


class AnchorSlot:
    """One row shared by the groups' anchor steps (stirring, filtering) in the merged table."""

    def __init__(self, kind: str, step: Dict[str, Any]) -> None:
        self.kind = kind
        self.step = step


def _number(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _stirrer_settings(step: Dict[str, Any]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    skill_input = step.get("skill_input") if isinstance(step.get("skill_input"), dict) else {}
    return (_number(skill_input.get("temperature")), _number(skill_input.get("reaction_duration")),
            _number(skill_input.get("rotation_speed")))


def _match_score(slot: AnchorSlot, kind: str, step: Dict[str, Any]) -> Optional[int]:
    """How well a group's anchor step fits a row; None when it cannot share it. Stirring steps that agree in
    temperature, duration and speed fit best, so a group missing one of them lines the others up with their match."""
    if slot.kind != kind:
        return None
    if kind != "stirrer":
        return 1
    score = 1
    for weight, mine, theirs in zip((1, 2, 1), _stirrer_settings(slot.step), _stirrer_settings(step)):
        if mine is not None and theirs is not None and abs(mine - theirs) < 1e-6:
            score += weight
    return score


def _align_to_slots(slots: List[AnchorSlot], anchors: List[Tuple[int, str]],
                    step_group: Sequence[Dict[str, Any]]) -> Tuple[List[AnchorSlot], List[AnchorSlot]]:
    """Line a group's anchors up with the rows so far, keeping both orders (the first step stays on the first row).
    Returns the rows with the group's unmatched anchors added and the row of each of the group's anchors."""
    rest_slots, rest_anchors = slots[1:], anchors[1:]
    rows, cols = len(rest_slots), len(rest_anchors)
    best = [[0] * (cols + 1) for _ in range(rows + 1)]
    for i in range(1, rows + 1):
        for j in range(1, cols + 1):
            value = max(best[i - 1][j], best[i][j - 1])
            score = _match_score(rest_slots[i - 1], rest_anchors[j - 1][1], step_group[rest_anchors[j - 1][0]])
            if score is not None:
                value = max(value, best[i - 1][j - 1] + score)
            best[i][j] = value

    pairs: List[Tuple[Optional[AnchorSlot], Optional[Tuple[int, str]]]] = []
    i, j = rows, cols
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            score = _match_score(rest_slots[i - 1], rest_anchors[j - 1][1], step_group[rest_anchors[j - 1][0]])
            if score is not None and best[i][j] == best[i - 1][j - 1] + score:
                pairs.append((rest_slots[i - 1], rest_anchors[j - 1]))
                i, j = i - 1, j - 1
                continue
        if i > 0 and (j == 0 or best[i][j] == best[i - 1][j]):
            pairs.append((rest_slots[i - 1], None))
            i -= 1
        else:
            pairs.append((None, rest_anchors[j - 1]))
            j -= 1
    pairs.reverse()

    merged = [slots[0]]
    mapping = [slots[0]]
    for slot, anchor in pairs:
        if slot is None:
            slot = AnchorSlot(anchor[1], step_group[anchor[0]])
        merged.append(slot)
        if anchor is not None:
            mapping.append(slot)
    return merged, mapping


def describe_slot(slot: AnchorSlot) -> str:
    if slot.kind == "stirrer":
        temperature, duration, speed = _stirrer_settings(slot.step)
        parts = [f"{value:g} {unit}" for value, unit in ((temperature, "℃"), (duration, "s"), (speed, "rpm"))
                 if value is not None]
        return "反应控制" + (f"（{'、'.join(parts)}）" if parts else "")
    return {"filtering": "过滤", "last": "最后一步"}.get(slot.kind, slot.kind)


def plan_anchor_slots(
    step_groups: Sequence[Sequence[Dict[str, Any]]],
    anchor_positions_list: Sequence[Sequence[int]],
) -> Tuple[List[AnchorSlot], List[List[AnchorSlot]]]:
    """The shared rows of the anchor steps and, per group, the row of each of its anchors.

    Groups with the same anchor sequence are lined up position by position. A recommendation does not always have
    every step (no molecular sieve, a cooling step written as its own stirring step in one plan and not in another),
    so differing sequences are lined up by order and stirring settings instead of failing; a group without one of
    the rows leaves it empty on its reaction position."""
    anchors_list = [list(zip(positions, build_anchor_signature(group, positions)))
                    for group, positions in zip(step_groups, anchor_positions_list)]
    signatures = [[kind for _, kind in anchors] for anchors in anchors_list]
    if all(signature == signatures[0] for signature in signatures):
        slots = [AnchorSlot(kind, step_groups[0][position]) for position, kind in anchors_list[0]]
        return slots, [list(slots) for _ in step_groups]

    reference = max(range(len(step_groups)), key=lambda index: (len(anchors_list[index]), -index))
    slots = [AnchorSlot(kind, step_groups[reference][position]) for position, kind in anchors_list[reference]]
    mappings: List[List[AnchorSlot]] = [[] for _ in step_groups]
    mappings[reference] = list(slots)
    for index, (group, anchors) in enumerate(zip(step_groups, anchors_list)):
        if index != reference:
            slots, mappings[index] = _align_to_slots(slots, anchors, group)
    return slots, mappings


def report_missing_anchors(
    step_groups: Sequence[Sequence[Dict[str, Any]]],
    slots: Sequence[AnchorSlot],
    mappings: Sequence[Sequence[AnchorSlot]],
) -> None:
    notes = []
    for group, mapping in zip(step_groups, mappings):
        present = {id(slot) for slot in mapping}
        missing = [describe_slot(slot) for slot in slots if id(slot) not in present]
        if missing:
            notes.append(f"{get_step_layout_code(group[0])} 没有 {'、'.join(missing)}")
    if notes:
        log_status("提示：各组的反应控制/过滤步骤不完全相同，已按顺序和反应控制条件对齐，缺少的步骤在该反应位留空："
                   + "；".join(notes) + "。")


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


def split_across_rows(count: int, expected: Sequence[int], capacity: Sequence[int]) -> List[int]:
    """How many of a group's in-between steps go into each stretch between two rows it skips: in proportion to
    what the other groups do there (no cooling step: its additions after the reaction go after the others' cooling
    row, not onto it), within the room each stretch has."""
    weights = list(expected) if sum(expected) else list(capacity)
    total = sum(weights) or 1
    raw = [count * weight / total for weight in weights]
    quota = [int(value) for value in raw]
    for index in sorted(range(len(raw)), key=lambda i: (quota[i] - raw[i], -i))[:count - sum(quota)]:
        quota[index] += 1
    overflow = 0
    for index in range(len(quota)):
        quota[index] += overflow
        overflow = max(0, quota[index] - capacity[index])
        quota[index] -= overflow
    for index in reversed(range(len(quota))):
        take = min(capacity[index] - quota[index], overflow)
        quota[index] += take
        overflow -= take
    return quota


def place_group_steps(
    step_group: Sequence[Dict[str, Any]],
    anchor_positions: Sequence[int],
    anchor_slots: Sequence[int],
    slot_rows: Sequence[int],
    expected: Sequence[int],
) -> List[Tuple[int, Dict[str, Any]]]:
    """(row, step) for one group: its anchors on their slots' rows, the steps between them spread over the rows in
    between (a slot the group does not have stays empty for it)."""
    aligned_steps: List[Tuple[int, Dict[str, Any]]] = []
    for step_idx, slot in zip(anchor_positions, anchor_slots):
        aligned_steps.append((slot_rows[slot], deepcopy(step_group[step_idx])))

    for segment_idx in range(len(anchor_positions) - 1):
        interior_steps = step_group[anchor_positions[segment_idx] + 1: anchor_positions[segment_idx + 1]]
        start, end = anchor_slots[segment_idx], anchor_slots[segment_idx + 1]
        stretches = list(range(start, end))
        quota = split_across_rows(len(interior_steps), [expected[slot] for slot in stretches],
                                  [slot_rows[slot + 1] - slot_rows[slot] - 1 for slot in stretches])
        cursor = 0
        for slot, count in zip(stretches, quota):
            rows = distribute_rows_evenly(slot_rows[slot], slot_rows[slot + 1], count)
            aligned_steps.extend((row, deepcopy(step)) for row, step in zip(rows, interior_steps[cursor: cursor + count]))
            cursor += count

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
    slots, mappings = plan_anchor_slots(sorted_groups, anchor_positions_list)
    report_missing_anchors(sorted_groups, slots, mappings)

    # Each slot's row leaves room for every group's steps between two of its anchors. A group that skips slots in
    # between leaves their rows empty, so its steps need that many more rows. expected[i]: how many steps the groups
    # that go straight from slot i to slot i + 1 have there, used to place a skipping group's steps.
    slot_index = {id(slot): index for index, slot in enumerate(slots)}
    anchor_slots_list = [[slot_index[id(slot)] for slot in mapping] for mapping in mappings]
    slot_rows = [0] * len(slots)
    expected = [0] * len(slots)
    needs: Dict[int, List[Tuple[int, int]]] = {}
    for anchor_positions, anchor_slots in zip(anchor_positions_list, anchor_slots_list):
        for segment_idx in range(len(anchor_positions) - 1):
            start, end = anchor_slots[segment_idx], anchor_slots[segment_idx + 1]
            interior = anchor_positions[segment_idx + 1] - anchor_positions[segment_idx] - 1
            needs.setdefault(end, []).append((start, interior + end - start - 1))
            if end == start + 1:
                expected[start] = max(expected[start], interior)
    for index in range(1, len(slots)):
        slot_rows[index] = max([slot_rows[index - 1] + 1]
                               + [slot_rows[start] + interior + 1 for start, interior in needs.get(index, [])])

    combined_with_positions: List[Tuple[int, int, Dict[str, Any]]] = []
    for step_group, anchor_positions, anchor_slots in zip(sorted_groups, anchor_positions_list, anchor_slots_list):
        aligned_steps = place_group_steps(step_group, anchor_positions, anchor_slots, slot_rows, expected)
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
        out_path = (Path(args.output) if args.output
                    else OUTPUT_DIR / f"generated_multi_step_json_{result['timestamp']}.json")
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
