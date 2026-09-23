#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[2]
AGENTS_ROOT = ROOT.parents[1]
KB_DIR = ROOT / "KB"
OUTPUT_DIR = ROOT / "output"

DEFAULT_CONSTRAINTS = WORKSPACE / ".claude" / "skills" / "constraint-parser" / "output" / "parsed_constraints_2026-04-27-13-31-19.json"
DEFAULT_REFERENCE_DIR = WORKSPACE / "experiment_plans"
ATA_STEP_FILE = KB_DIR / "ata_step.md"
REFERENCE_PLAN_FILE = KB_DIR / "reference_experiment_plan.md"


class StepGenerationError(Exception):
    pass


def load_env() -> None:
    env_path = AGENTS_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)


load_env()

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def read_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text[1:] if text.startswith("\ufeff") else text


def read_json(path: Path) -> Any:
    return json.loads(read_text(path))


def write_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_reference_markdown(reference_dir: Path, max_files: int = 3) -> str:
    chunks: list[str] = []
    if REFERENCE_PLAN_FILE.exists():
        chunks.append(read_text(REFERENCE_PLAN_FILE).strip())

    if reference_dir.exists():
        for path in sorted(reference_dir.glob("*.md"))[:max_files]:
            text = read_text(path).strip()
            if text and text not in chunks:
                chunks.append(f"<!-- {path.name} -->\n{text}")

    return "\n\n---\n\n".join(chunks)


def normalize_model_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except Exception as exc:
        raise StepGenerationError(f"LLM detection output is not valid JSON: {exc}; output={cleaned[:500]}") from exc
    if not isinstance(data, dict):
        raise StepGenerationError("LLM detection output must be a JSON object.")
    return data


def build_detection_prompt(source_text: str) -> str:
    return f"""
请判断用户输入的实验指令属于哪一种反应类型。

只输出 JSON，不要输出 Markdown 或解释。

输出格式：
{{
  "reaction_type": "ATA" | "unknown",
  "confidence": 0.0,
  "reason": "一句中文理由"
}}

判断规则：
- 如果文本出现 ATA、炔丙基化、苯乙炔/醛底物组合、金属盐/手性胺优化体系等明显 ATA 线索，输出 "ATA"。
- 如果无法判断，输出 "unknown"。

用户输入：
{source_text}
""".strip()


def build_steps_prompt(source_text: str, ata_steps: str, reference_text: str) -> str:
    return f"""
你是自动化化学实验步骤编写助手。

输入已被判定为 ATA 反应。
请根据用户原始实验指令和 ATA 步骤模板，输出可执行的实验步骤。

严格要求：
1. 只输出编号步骤列表，不要输出标题、实验概述、试剂作用与用量、过滤信息或其他章节。
2. 直接参考 `ATA 步骤模板` 的步骤顺序和表达方式。
3. 根据 `source_text` 替换或保留试剂/底物/用量信息。
4. 如果用户只给出类别，如“金属盐”“手性胺”“溶剂”，步骤中也保留类别，不要编造具体名称。
5. 不输出反应位、过滤位、layout_code、chemical_id、QR_code、托盘信息。
6. 保留 ATA 模板中的流程条件：室温 500 rpm 预搅拌 30 分钟；70℃ 500 rpm 反应 24 h；加入 0.2 mL 联苯内标溶液和 0.6 mL 乙腈；室温搅拌 5 分钟、静置 20 分钟；移取 0.02 mL 上层清液，用 0.8 mL 乙腈稀释。
7. 步骤编号应连续，每步只表达一个主要操作。
8. 不写长篇解释。

## source_text
{source_text}

## ATA 步骤模板
{ata_steps}

## 参考实验方案 Markdown
{reference_text}

请只输出最终编号步骤列表。
""".strip()


def require_llm_config(value: str | None, label: str) -> str:
    if not value:
        raise StepGenerationError(f"{label} is not set.")
    return value


def sanitize_markdown(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:markdown|md)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def validate_markdown(text: str) -> None:
    if not re.search(r"^\s*1[.、]", text, flags=re.MULTILINE):
        raise StepGenerationError("Generated steps must start with a numbered step list.")
    forbidden_sections = ["# 实验步骤方案", "## 实验概述", "## 实验步骤", "## 试剂作用与用量", "## 反应位置与过滤信息"]
    for marker in forbidden_sections:
        if marker in text:
            raise StepGenerationError(f"Generated output must not contain section heading: {marker}")
    if any(token in text for token in ["layout_code", "chemical_id", "QR_code", "tray_QR_code"]):
        raise StepGenerationError("Generated Markdown contains forbidden device binding fields.")


def call_llm(prompt: str, system_content: str = "你只输出干净内容，不输出解释。") -> str:
    api_key = require_llm_config(OPENAI_API_KEY, "OPENAI_API_KEY")
    base_url = require_llm_config(OPENAI_BASE_URL, "OPENAI_BASE_URL")
    model = require_llm_config(OPENAI_MODEL, "OPENAI_MODEL")

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": system_content,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.2,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=120)
    if response.status_code != 200:
        raise StepGenerationError(f"LLM request failed: HTTP {response.status_code}; body={response.text[:1000]}")
    data = response.json()
    try:
        return data["choices"][0]["message"]["content"] or ""
    except Exception as exc:
        raise StepGenerationError(f"Invalid LLM response format: {exc}; raw={data}") from exc


def detect_reaction_type(source_text: str) -> dict[str, Any]:
    raw = call_llm(build_detection_prompt(source_text), system_content="你只输出 JSON，不输出解释。")
    data = normalize_model_json(raw)
    reaction_type = str(data.get("reaction_type", "")).strip().upper()
    if reaction_type not in {"ATA", "UNKNOWN"}:
        data["reaction_type"] = "unknown"
    return data


def generate_steps(constraints_path: Path, reference_dir: Path) -> str:
    constraints = read_json(constraints_path)
    source_text = constraints.get("source_text")
    if not source_text:
        raise StepGenerationError("Constraint JSON does not contain source_text.")
    detection = detect_reaction_type(source_text)
    if str(detection.get("reaction_type", "")).upper() != "ATA":
        reason = detection.get("reason") or "输入未被识别为 ATA 反应。"
        raise StepGenerationError(f"Unsupported reaction type: {detection.get('reaction_type')}; {reason}")
    ata_steps = read_text(ATA_STEP_FILE)
    reference_text = load_reference_markdown(reference_dir)
    markdown = sanitize_markdown(call_llm(build_steps_prompt(source_text, ata_steps, reference_text), system_content="你只输出编号实验步骤列表，不输出标题或解释。"))
    validate_markdown(markdown)
    return markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Markdown experiment steps using LLM.")
    parser.add_argument("--constraints", default=str(DEFAULT_CONSTRAINTS), help="constraint-parser JSON path.")
    parser.add_argument("--reference-dir", default=str(DEFAULT_REFERENCE_DIR), help="Directory containing reference experiment .md files.")
    parser.add_argument("--output", default="", help="Output Markdown path.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        markdown = generate_steps(Path(args.constraints), Path(args.reference_dir))
        out_path = Path(args.output) if args.output else OUTPUT_DIR / f"generated_experiment_steps_{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.md"
        write_text(markdown + "\n", out_path)
        print(f"Experiment steps generated: {out_path}")
        return 0
    except Exception as exc:
        print(f"Generation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
