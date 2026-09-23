#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parents[4] / ".env"
if env_path.exists():
    load_dotenv(env_path)

ROOT = Path(__file__).resolve().parents[1]
KB_DIR = ROOT / "KB"
OUTPUT_DIR = ROOT / "output"

UNIT_SKILL_MAP_FILE = KB_DIR / "unit_skill_map.json"

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MAX_GENERATION_ATTEMPTS = 3
THINKING_MODE_MODELS = {"intern-s1-pro", "intern-s1", "intern-s1-mini"}

MASS_UNITS = {"mg", "g"}
VOLUME_UNITS = {"uL", "μL", "µL", "mL", "L"}
SUBSTANCE_UNIT_TYPES = {"exp_add_solid", "exp_pipetting"}
UNIT_ALIASES = {
    "μL": "uL",
    "µL": "uL",
    "ul": "uL",
    "UL": "uL",
    "ml": "mL",
    "l": "L",
}
REQUIRED_STEP_FIELDS = {
    "step_index",
    "unit_type",
    "downstream_skill",
    "instruction",
    "skill_input",
}
SKILL_INPUT_FIELDS = {
    "exp_add_solid": {"layout_code", "unit_column", "unit_row", "substance", "add_weight", "unit"},
    "exp_pipetting": {"layout_code", "unit_column", "unit_row", "substance", "add_volume", "unit"},
    "exp_magnetic_stirrer": {
        "layout_code",
        "unit_column",
        "unit_row",
        "temperature",
        "reaction_duration",
        "rotation_speed",
        "is_wait",
        "still_tem",
    },
    "exp_filtering_samples": {"layout_code", "unit_column", "unit_row", "add_volume", "unit", "dst_pos"},
    "exp_high_filtering_samples": {"layout_code", "unit_column", "unit_row", "add_volume", "substance", "dilute_volume", "unit", "dst_pos"},
}


class StepJsonGenerationError(Exception):
    pass


def read_text(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    # 处理 UTF-8 BOM
    if content.startswith("\ufeff"):
        content = content[1:]
    return content


def read_json(path: Path) -> Any:
    return json.loads(read_text(path))


def write_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_inputs() -> tuple[str, Dict[str, Any], Dict[str, str]]:
    unit_skill_map = read_json(UNIT_SKILL_MAP_FILE)
    example_json = read_json(KB_DIR / "example_step_json.json")

    if not isinstance(unit_skill_map, dict) or not unit_skill_map:
        raise StepJsonGenerationError("unit_skill_map.json must be a non-empty JSON object.")
    
    if not isinstance(example_json, dict) or "steps" not in example_json:
        raise StepJsonGenerationError("example_step_json.json must be a valid JSON object with a steps array.")

    return build_compact_schema_text(unit_skill_map), example_json, unit_skill_map


def build_compact_schema_text(unit_skill_map: Dict[str, str]) -> str:
    skill_input_summary = {
        unit_type: sorted(fields)
        for unit_type, fields in SKILL_INPUT_FIELDS.items()
    }
    summary = {
        "top_level_required": ["timestamp", "steps"],
        "step_required": sorted(REQUIRED_STEP_FIELDS),
        "allowed_unit_type_to_skill": unit_skill_map,
        "skill_input_fields": skill_input_summary,
        "mass_units": sorted(MASS_UNITS),
        "volume_units": sorted(VOLUME_UNITS),
    }
    return json.dumps(summary, ensure_ascii=False, indent=2)





def build_prompt(
    plan_text: str,
    schema_text: str,
    example_json: Dict[str, Any],
    unit_skill_map: Dict[str, str],
    previous_error: str = "",
) -> str:
    retry_note = ""
    if previous_error:
        retry_note = f"""
请把输入的实验方案转换成逐步原子操作 JSON，必须生成JSON。

## 严格规则

### 基本格式要求
1. 只能输出 JSON，不要输出 Markdown，不要输出解释。
2. 顶层必须是包含 `timestamp` 和 `steps` 的对象。
3. 每个 step 只能表示一个原子操作。
4. 每个 step 必须包含 `step_index`、`unit_type`、`downstream_skill`、`instruction`、`skill_input`。
5. `instruction` 必须是一条适合人工复核的中文单句。
6. `skill_input` 必须是结构化载荷，字段必须与该 `unit_type` 对应的下游原子 skill 输入 schema 完全一致。
7. 不要输出无关的运行时或设备绑定字段，例如 `chemical_id`、`tray_QR_code`、`QR_code`。

### 默认值和字段规范
8. `instruction` 使用统一的复核句式，例如"向 <位置> 加入 ..."或"从 <位置> 取 ... 过滤"，不要直接照抄过长的流程原句。
9. 必须从实验方案中提取正确的位置信息（如"T-3:11"），并将其作为`layout_code`使用，不要使用任何默认值或假设的位置。
10. 化学物名称必须直接沿用实验方案中的专业名称，不要使用额外别名映射，不要擅自改写成简称、俗称或其他同义表达；`instruction` 与 `skill_input` 中的名称必须保持一致。

### 过滤和高过滤步骤的特殊规则
10. 必须稳定区分"过滤"和"高滤"：
   - 只有实验方案明确出现"高滤""高过滤""稀释""稀释取样"等表述时，才能使用 `exp_high_filtering_samples` / `fdu-high-filter-json`。
   - 普通"过滤""过滤取样""过滤样品"默认使用 `exp_filtering_samples` / `fdu-filter-json`，除非文本明确写出"高滤"或"稀释"。
   - 不允许把"高滤"错误映射成普通过滤，也不允许把普通过滤错误映射成高滤。
   - 如果同一方案同时出现"过滤"和"高滤"，必须拆成两个不同步骤，并分别使用各自的 `unit_type`。
11. 对过滤类步骤，`instruction` 文案必须与 `unit_type` 一致：
   - `exp_filtering_samples` 使用"过滤"
   - `exp_high_filtering_samples` 使用"高滤"
   - 不要混写成"高滤过滤"或省略"高"字。
12. 对于高过滤步骤，substance字段必须使用实验方案中指定的稀释剂名称（如"乙腈"），而不是"反应液"。

## 输入内容

### 实验方案
{plan_text}

### Schema
{schema_text}

### `unit_type` 到下游 skill 的映射
{json.dumps(unit_skill_map, ensure_ascii=False, indent=2)}

### 示例输出
{json.dumps(example_json, ensure_ascii=False, indent=2)}

### 错误修正（如果有）
{retry_note}
""".strip()

    return f"""
你是一个自动化化学实验流程规划器。
请把输入的实验方案转换成逐步原子操作 JSON。

## 严格规则

### 基本格式要求
1. 只能输出 JSON，不要输出 Markdown，不要输出解释。
2. 顶层必须是包含 `timestamp` 和 `steps` 的对象。
3. 每个 step 只能表示一个原子操作。
4. 每个 step 必须包含 `step_index`、`unit_type`、`downstream_skill`、`instruction`、`skill_input`。
5. `instruction` 必须是一条适合人工复核的中文单句。
6. `skill_input` 必须是结构化载荷，字段必须与该 `unit_type` 对应的下游原子 skill 输入 schema 完全一致。
7. 不要输出无关的运行时或设备绑定字段，例如 `chemical_id`、`tray_QR_code`、`QR_code`。

### 默认值和字段规范
8. `instruction` 使用统一的复核句式，例如"向 <位置> 加入 ..."或"从 <位置> 取 ... 过滤"，不要直接照抄过长的流程原句。
9. 必须从实验方案中提取正确的位置信息（如"T-3:11"），并将其作为`layout_code`使用，不要使用任何默认值或假设的位置。
10. 化学物名称必须直接沿用实验方案中的名称，不要使用额外别名映射，不要擅自改写成简称、俗称或其他同义表达，不要擅自更改字符；`instruction` 与 `skill_input` 中的名称必须保持一致。

### 过滤和高过滤步骤的特殊规则
11. 必须稳定区分"过滤"和"高滤"：
    - 只有实验方案明确出现"高滤""高过滤""稀释""稀释取样"等表述时，才能使用 `exp_high_filtering_samples` / `fdu-high-filter-json`。
    - 普通"过滤""过滤取样""过滤样品"默认使用 `exp_filtering_samples` / `fdu-filter-json`，除非文本明确写出"高滤"或"稀释"。
    - 不允许把"高滤"错误映射成普通过滤，也不允许把普通过滤错误映射成高滤。
    - 如果同一方案同时出现"过滤"和"高滤"，必须拆成两个不同步骤，并分别使用各自的 `unit_type`。
12. 对过滤类步骤，`instruction` 文案必须与 `unit_type` 一致：
    - `exp_filtering_samples` 使用"过滤"
    - `exp_high_filtering_samples` 使用"高滤"
    - 不要混写成"高滤过滤"或省略"高"字。
13. 对于高过滤步骤，substance字段必须使用实验方案中指定的稀释剂名称（如"乙腈"），而不是"反应液"。

## 输入内容

### 实验方案
{plan_text}

### Schema
{schema_text}

### `unit_type` 到下游 skill 的映射
{json.dumps(unit_skill_map, ensure_ascii=False, indent=2)}

### 示例输出
{json.dumps(example_json, ensure_ascii=False, indent=2)}

### 错误修正（如果有）
{retry_note}
""".strip()


def build_extra_body(model: str) -> Dict[str, Any] | None:
    if model in THINKING_MODE_MODELS:
        return {"thinking_mode": False}
    return None


def call_llm(prompt: str) -> str:
    if not OPENAI_API_KEY:
        raise StepJsonGenerationError("OPENAI_API_KEY is not set.")
    if not OPENAI_BASE_URL:
        raise StepJsonGenerationError("OPENAI_BASE_URL is not set.")
    if not OPENAI_MODEL:
        raise StepJsonGenerationError("OPENAI_MODEL is not set.")

    url = f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    extra_body = build_extra_body(OPENAI_MODEL)
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": "你只能生成合法 JSON。不要输出 Markdown，不要输出说明。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    if extra_body is not None:
        payload["extra_body"] = extra_body

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=120)

        # 添加详细的错误日志
        if response.status_code != 200:
            print(f"API 请求失败: {response.status_code}")
            print(f"响应头: {response.headers}")
            print(f"响应内容: {response.text}")
            print(f"请求 URL: {url}")
            print(f"请求模型: {OPENAI_MODEL}")
            print(f"提示长度: {len(prompt)} 字符")

        response.raise_for_status()
        data = response.json()

        try:
            return (data["choices"][0]["message"]["content"] or "").strip()
        except Exception as exc:
            raise StepJsonGenerationError(f"Invalid LLM response format: {exc}; raw={data}")
    except requests.exceptions.RequestException as exc:
        print(f"请求异常: {exc}")
        if hasattr(exc, 'response') and exc.response is not None:
            print(f"错误响应: {exc.response.text}")
        raise


def normalize_model_output(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        if len(parts) >= 3:
            cleaned = parts[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
    return cleaned.strip()


def parse_step_json(text: str) -> Dict[str, Any]:
    try:
        data = json.loads(normalize_model_output(text))
    except Exception as exc:
        raise StepJsonGenerationError(f"Model output is not valid JSON: {exc}")

    if not isinstance(data, dict):
        raise StepJsonGenerationError("Top level output must be a JSON object.")

    return data


def current_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d-%H-%M-%S")


def format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{float(value):g}"


def clean_instruction_text(text: str) -> str:
    cleaned = re.sub(r"^\s*\d+\.\s*", "", text.strip())
    return cleaned.rstrip("。；;，, ")


def extract_canonical_substance_map(plan_text: str) -> Dict[str, str]:
    alias_map: Dict[str, str] = {}
    for raw_line in plan_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or not line.startswith("-"):
            continue
        if "：" not in line and ":" not in line:
            continue

        payload = re.split(r"[：:]", line[1:].strip(), maxsplit=1)
        if len(payload) != 2:
            continue

        raw_value = payload[1].strip()
        if not raw_value:
            continue

        # 保留完整的物质名称，不移除括号内的内容
        value_without_notes = re.sub(r"（反应后加入）", "", raw_value)
        value_without_notes = re.sub(r"\([^)]*after reaction[^)]*\)", "", value_without_notes, flags=re.IGNORECASE)
        value_without_notes = value_without_notes.replace("，", " ")
        value_without_notes = re.sub(r"\s+", " ", value_without_notes).strip(" ，,。")

        canonical = raw_value.strip()
        if not canonical:
            continue

        aliases = {
            raw_value.strip(),
            value_without_notes,
            canonical,
        }

        short_name = re.split(r"\s+\d", canonical, maxsplit=1)[0].strip(" ，,")
        if short_name:
            aliases.add(short_name)

        for alias in aliases:
            normalized_alias = clean_instruction_text(alias)
            if normalized_alias:
                alias_map[normalized_alias.lower()] = canonical

    return alias_map


def normalize_substance_name(name: Any, canonical_map: Dict[str, str]) -> str:
    """Normalize a substance name using only names derived from the plan text.
    
    Args:
        name: The substance name to normalize.
        canonical_map: Map of canonical names extracted from plan text.
    
    Returns:
        The normalized substance name.
    """
    text = clean_instruction_text(str(name))
    if not text:
        return text

    direct = canonical_map.get(text.lower())
    if direct:
        return direct

    return text


def format_volume_instruction(value: Any, unit: Any) -> str:
    return f"{format_number(float(value))} {unit}"


def format_temperature_instruction(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{format_number(float(value))}C"
    text = str(value).strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered == "rt":
        return "rt"
    if text.endswith("C"):
        return text
    return text


def format_duration_instruction(seconds: Any) -> str:
    return f"{int(seconds)} 秒"


def get_layout_code(skill_input: Dict[str, Any]) -> str:
    layout_code = skill_input.get("layout_code") or skill_input.get("target_layout_code") or skill_input.get("source_layout_code")
    if not layout_code:
        raise StepJsonGenerationError("layout_code is required in skill_input")
    return str(layout_code).strip()


def parse_unit_column(layout_code: str) -> int:
    match = re.search(r":(\d+)$", layout_code)
    if not match:
        raise StepJsonGenerationError(f"layout_code must end with :<column>, got {layout_code!r}")
    return int(match.group(1))


def build_instruction_from_step(step: Dict[str, Any], canonical_map: Dict[str, str]) -> str:
    unit_type = str(step.get("unit_type", "")).strip()
    skill_input = step.get("skill_input") or {}
    layout_code = get_layout_code(skill_input)

    if unit_type == "exp_add_solid":
        substance = normalize_substance_name(skill_input["substance"], canonical_map)
        standardized_substance = standardize_substance_name(substance)
        return clean_instruction_text(
            f"向 {layout_code} 加入 {format_number(float(skill_input['add_weight']))} {skill_input['unit']} {standardized_substance}"
        )

    if unit_type == "exp_pipetting":
        volume_text = format_volume_instruction(skill_input["add_volume"], skill_input["unit"])
        substance = normalize_substance_name(skill_input["substance"], canonical_map)
        standardized_substance = standardize_substance_name(substance)
        return clean_instruction_text(f"向 {layout_code} 加入 {volume_text} {standardized_substance}")

    if unit_type == "exp_magnetic_stirrer":
        temperature_text = format_temperature_instruction(skill_input["temperature"])
        duration_text = format_duration_instruction(skill_input["reaction_duration"])
        return clean_instruction_text(
            f"{layout_code} 在 {temperature_text} 下搅拌 {duration_text}，{skill_input['rotation_speed']} rpm"
        )

    if unit_type == "exp_filtering_samples":
        volume_text = format_volume_instruction(skill_input["add_volume"], skill_input["unit"])
        dst_pos = skill_input.get("dst_pos")
        if dst_pos:
            return clean_instruction_text(f"从 {layout_code} 取 {volume_text} 过滤到 {dst_pos}")
        return clean_instruction_text(f"从 {layout_code} 取 {volume_text} 过滤")

    if unit_type == "exp_high_filtering_samples":
        volume_text = format_volume_instruction(skill_input["add_volume"], skill_input["unit"])
        dst_pos = skill_input.get("dst_pos")
        substance = skill_input.get("substance", "")
        dilute_volume = skill_input.get("dilute_volume")

        if dst_pos and substance and dilute_volume:
            dilute_text = format_volume_instruction(dilute_volume, skill_input["unit"])
            return clean_instruction_text(f"从 {layout_code} 取 {volume_text} 到 {dst_pos} 用 {dilute_text} {substance} 稀释")
        elif dst_pos:
            return clean_instruction_text(f"从 {layout_code} 取 {volume_text} 高滤到 {dst_pos}")
        return clean_instruction_text(f"从 {layout_code} 取 {volume_text} 高滤")

    return clean_instruction_text(str(step.get("instruction", "")))


def normalize_instructions(step_json: Dict[str, Any], plan_text: str) -> Dict[str, Any]:
    normalized = dict(step_json)
    steps = normalized.get("steps")
    if not isinstance(steps, list):
        return normalized

    canonical_map = extract_canonical_substance_map(plan_text)
    normalized_steps: List[Dict[str, Any]] = []

    for step in steps:
        if not isinstance(step, dict):
            normalized_steps.append(step)
            continue

        normalized_step = dict(step)
        skill_input = normalized_step.get("skill_input")
        if isinstance(skill_input, dict):
            if "substance" in skill_input:
                normalized_skill_input = dict(skill_input)
                # 标准化物质名称，先规范化再标准化
                normalized_skill_input["substance"] = standardize_substance_name(
                    normalize_substance_name(skill_input.get("substance", ""), canonical_map)
                )
                normalized_step["skill_input"] = normalized_skill_input
        normalized_step["instruction"] = build_instruction_from_step(normalized_step, canonical_map)
        normalized_steps.append(normalized_step)

    normalized["steps"] = normalized_steps
    return normalized


def normalize_step_json(data: Dict[str, Any], timestamp: str | None = None) -> Dict[str, Any]:
    normalized = dict(data)
    normalized.pop("format", None)
    normalized.pop("version", None)
    normalized["timestamp"] = timestamp or current_timestamp()
    steps = normalized.get("steps")
    if isinstance(steps, list):
        normalized_steps: List[Dict[str, Any]] = []
        for step in steps:
            if isinstance(step, dict):
                cleaned_step = dict(step)
                cleaned_step.pop("requirement", None)
                normalized_steps.append(cleaned_step)
            else:
                normalized_steps.append(step)
        normalized["steps"] = normalized_steps
    return normalized


def normalize_unit_text(unit: Any) -> Any:
    """标准化单位文本，使用别名映射"""
    if unit is None:
        return unit
    text = str(unit).strip()
    return UNIT_ALIASES.get(text, text)


def standardize_substance_name(name: str) -> str:
    return name.strip()


def reorder_skill_input_fields(skill_input: Dict[str, Any]) -> Dict[str, Any]:

    # 字段排序优先级
    field_priority = [
        "layout_code", "unit_column", "unit_row", "substance",
        "add_weight", "add_volume", "temperature", "reaction_duration",
        "rotation_speed", "is_wait", "still_tem", "dilute_volume",
        "unit", "dst_pos"
    ]

    reordered = {}

    # 按优先级顺序添加字段
    for field in field_priority:
        if field in skill_input:
            reordered[field] = skill_input[field]

    # 添加剩余字段（不在优先级列表中的）
    for key, value in skill_input.items():
        if key not in reordered:
            reordered[key] = value

    return reordered


def repair_step_json(data: Dict[str, Any], unit_skill_map: Dict[str, str], timestamp: str | None = None) -> Dict[str, Any]:
    """修复和标准化步骤JSON数据"""
    repaired = normalize_step_json(data, timestamp=timestamp)
    steps = repaired.get("steps")
    if not isinstance(steps, list):
        return repaired

    repaired_steps: List[Any] = []
    layout_row_counters: Dict[str, int] = {}

    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            repaired_steps.append(step)
            continue

        fixed_step = dict(step)
        fixed_step["step_index"] = index

        unit_type = str(fixed_step.get("unit_type", "")).strip()
        if unit_type in unit_skill_map:
            fixed_step["downstream_skill"] = unit_skill_map[unit_type]

        skill_input = fixed_step.get("skill_input")
        if isinstance(skill_input, dict):
            fixed_skill_input = dict(skill_input)
            layout_code = get_layout_code(fixed_skill_input)
            unit_column = parse_unit_column(layout_code)
            unit_row = layout_row_counters.get(layout_code, 0)
            layout_row_counters[layout_code] = unit_row + 1

            # 清理冗余的布局代码字段
            fixed_skill_input.pop("target_layout_code", None)
            fixed_skill_input.pop("source_layout_code", None)
            fixed_skill_input["layout_code"] = layout_code
            fixed_skill_input["unit_column"] = unit_column
            fixed_skill_input["unit_row"] = unit_row

            # 根据单位类型过滤和排序字段
            if unit_type in SKILL_INPUT_FIELDS:
                expected_fields = SKILL_INPUT_FIELDS[unit_type]
                fixed_skill_input = {key: fixed_skill_input[key] for key in expected_fields if key in fixed_skill_input}
                fixed_skill_input = reorder_skill_input_fields(fixed_skill_input)

            # 标准化单位
            if "unit" in fixed_skill_input:
                fixed_skill_input["unit"] = normalize_unit_text(fixed_skill_input["unit"])

            fixed_step["skill_input"] = fixed_skill_input

        repaired_steps.append(fixed_step)

    repaired["steps"] = repaired_steps
    return repaired


def summarize_unit_types(steps: List[Dict[str, Any]]) -> List[str]:
    seen = set()
    ordered_types: List[str] = []
    for step in steps:
        unit_type = str(step.get("unit_type", "")).strip()
        if unit_type and unit_type not in seen:
            seen.add(unit_type)
            ordered_types.append(unit_type)
    return ordered_types


def require_non_empty_string(value: Any, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise StepJsonGenerationError(f"{label} must not be empty.")
    return text


def require_number(value: Any, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise StepJsonGenerationError(f"{label} must be numeric.")
    return float(value)


def require_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise StepJsonGenerationError(f"{label} must be an integer.")
    return value


def require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise StepJsonGenerationError(f"{label} must be boolean.")
    return value


def require_unit(value: Any, allowed_units: set[str], label: str) -> str:
    unit = require_non_empty_string(value, label)
    if unit not in allowed_units:
        choices = ", ".join(sorted(allowed_units))
        raise StepJsonGenerationError(f"{label} must be one of {choices}.")
    return unit


def require_temperature_like(value: Any, label: str) -> Any:
    if isinstance(value, bool):
        raise StepJsonGenerationError(f"{label} must be a string or number.")
    if isinstance(value, (int, float)):
        return value
    return require_non_empty_string(value, label)


def validate_layout_fields(skill_input: Dict[str, Any], step_number: int) -> str:
    layout_code = require_non_empty_string(skill_input["layout_code"], f"Step {step_number} layout_code")
    expected_unit_column = parse_unit_column(layout_code)
    unit_column = require_int(skill_input["unit_column"], f"Step {step_number} unit_column")
    unit_row = require_int(skill_input["unit_row"], f"Step {step_number} unit_row")
    if unit_column != expected_unit_column:
        raise StepJsonGenerationError(
            f"Step {step_number} unit_column mismatch for {layout_code}: {unit_column} != {expected_unit_column}"
        )
    if unit_row < 0:
        raise StepJsonGenerationError(f"Step {step_number} unit_row must be >= 0.")
    return layout_code


def validate_skill_input_fields(unit_type: str, skill_input: Dict[str, Any], step_number: int) -> None:
    expected_fields = SKILL_INPUT_FIELDS[unit_type]
    actual_fields = set(skill_input)
    if actual_fields != expected_fields:
        raise StepJsonGenerationError(
            f"Step {step_number} skill_input fields mismatch for {unit_type}: {sorted(actual_fields)} != {sorted(expected_fields)}"
        )


def validate_add_solid_input(skill_input: Dict[str, Any], step_number: int) -> None:
    """验证添加固体输入"""
    validate_layout_fields(skill_input, step_number)
    require_non_empty_string(skill_input["substance"], f"Step {step_number} substance")
    require_number(skill_input["add_weight"], f"Step {step_number} add_weight")
    require_unit(skill_input["unit"], MASS_UNITS, f"Step {step_number} unit")


def validate_pipetting_input(skill_input: Dict[str, Any], step_number: int) -> None:
    """验证移液输入"""
    validate_layout_fields(skill_input, step_number)
    require_non_empty_string(skill_input["substance"], f"Step {step_number} substance")
    require_number(skill_input["add_volume"], f"Step {step_number} add_volume")
    require_unit(skill_input["unit"], VOLUME_UNITS, f"Step {step_number} unit")


def validate_filtering_input(skill_input: Dict[str, Any], step_number: int, unit_type: str = "exp_filtering_samples") -> None:
    """验证过滤输入"""
    validate_layout_fields(skill_input, step_number)
    require_number(skill_input["add_volume"], f"Step {step_number} add_volume")
    require_unit(skill_input["unit"], VOLUME_UNITS, f"Step {step_number} unit")

    # 对于高滤步骤，额外验证substance和dilute_volume字段
    if unit_type == "exp_high_filtering_samples":
        require_non_empty_string(skill_input["substance"], f"Step {step_number} substance")
        require_number(skill_input["dilute_volume"], f"Step {step_number} dilute_volume")

    # 验证目标位置（如果存在）
    dst_pos = skill_input.get("dst_pos")
    if dst_pos is not None:
        require_non_empty_string(dst_pos, f"Step {step_number} dst_pos")


def validate_stirrer_input(skill_input: Dict[str, Any], step_number: int) -> None:
    """验证搅拌输入"""
    validate_layout_fields(skill_input, step_number)
    require_temperature_like(skill_input["temperature"], f"Step {step_number} temperature")
    require_int(skill_input["reaction_duration"], f"Step {step_number} reaction_duration")
    require_int(skill_input["rotation_speed"], f"Step {step_number} rotation_speed")
    require_bool(skill_input["is_wait"], f"Step {step_number} is_wait")
    require_temperature_like(skill_input["still_tem"], f"Step {step_number} still_tem")


SKILL_INPUT_VALIDATORS = {
    "exp_add_solid": validate_add_solid_input,
    "exp_pipetting": validate_pipetting_input,
    "exp_magnetic_stirrer": validate_stirrer_input,
    "exp_filtering_samples": validate_filtering_input,
    "exp_high_filtering_samples": validate_filtering_input,
}


def validate_skill_input(unit_type: str, skill_input: Dict[str, Any], step_number: int) -> None:
    validate_skill_input_fields(unit_type, skill_input, step_number)
    validator = SKILL_INPUT_VALIDATORS[unit_type]
    # 对于过滤类步骤，传递unit_type参数
    if unit_type in ("exp_filtering_samples", "exp_high_filtering_samples"):
        validator(skill_input, step_number, unit_type)
    else:
        validator(skill_input, step_number)


def _update_layout_row_counters(layout_row_counters: Dict[str, int], layout_code: str, unit_row: int) -> None:
    """更新布局行计数器，确保unit_row按顺序递增"""
    expected_unit_row = layout_row_counters.get(layout_code, 0)
    if unit_row != expected_unit_row:
        raise StepJsonGenerationError(
            f"unit_row mismatch for {layout_code}: {unit_row} != {expected_unit_row}"
        )
    layout_row_counters[layout_code] = expected_unit_row + 1


def validate_step_json(data: Dict[str, Any], unit_skill_map: Dict[str, str]) -> List[Dict[str, Any]]:
    require_non_empty_string(data.get("timestamp"), "Top level timestamp")

    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        raise StepJsonGenerationError("Top level steps must be a non-empty array.")

    layout_row_counters: Dict[str, int] = {}

    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise StepJsonGenerationError(f"Step {index} must be an object.")

        missing = REQUIRED_STEP_FIELDS - set(step)
        if missing:
            raise StepJsonGenerationError(f"Step {index} is missing required fields: {', '.join(sorted(missing))}")

        step_index = require_int(step["step_index"], f"Step {index} step_index")
        unit_type = require_non_empty_string(step["unit_type"], f"Step {index} unit_type")
        downstream_skill = require_non_empty_string(step["downstream_skill"], f"Step {index} downstream_skill")
        require_non_empty_string(step["instruction"], f"Step {index} instruction")
        skill_input = step["skill_input"]

        if step_index != index:
            raise StepJsonGenerationError(f"Step {index} step_index must increase as 1..N.")
        if unit_type not in unit_skill_map:
            raise StepJsonGenerationError(f"Step {index} uses unsupported unit_type: {unit_type}")
        if downstream_skill != unit_skill_map[unit_type]:
            raise StepJsonGenerationError(
                f"Step {index} downstream_skill mismatch for {unit_type}: {downstream_skill} != {unit_skill_map[unit_type]}"
            )
        if not isinstance(skill_input, dict):
            raise StepJsonGenerationError(f"Step {index} skill_input must be an object.")

        validate_skill_input(unit_type, skill_input, index)
        _update_layout_row_counters(layout_row_counters, skill_input["layout_code"], skill_input["unit_row"])

    return steps


def generate_step_json_from_text(plan_text: str, timestamp: str | None = None) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    schema_text, example_json, unit_skill_map = load_inputs()
    last_error = ""

    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        prompt = build_prompt(
            plan_text,
            schema_text,
            example_json,
            unit_skill_map,
            previous_error=last_error,
        )
        llm_output = call_llm(prompt)

        try:
            step_json = repair_step_json(parse_step_json(llm_output), unit_skill_map, timestamp=timestamp)
            step_json = normalize_instructions(step_json, plan_text)
            steps = validate_step_json(step_json, unit_skill_map)
            return step_json, steps
        except StepJsonGenerationError as exc:
            last_error = f"Attempt {attempt}: {exc}"
    
    # If we get here, all attempts failed
    raise StepJsonGenerationError(f"Failed to generate valid step JSON after {MAX_GENERATION_ATTEMPTS} attempts. Last error: {last_error}")

