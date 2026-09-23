#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[2]

EXAMPLE_PLAN_FILE = ROOT / "KB" / "example_plan.md"
OUTPUT_DIR = ROOT / "output"

MAX_LLM_ATTEMPTS = 3
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_REQUEST_TIMEOUT = 600
THINKING_MODE_MODELS = {"intern-s1-pro", "intern-s1", "intern-s1-mini"}
FORBIDDEN_TOKENS = {"layout_code", "chemical_id", "tray_QR_code", "QR_code"}
OPENAI_CLIENT: OpenAI | None = None


class ExperimentPlanError(Exception):
    pass


def log_status(message: str) -> None:
    print(message, flush=True)


def progress_label(done: int, total: int) -> str:
    return f"[{done}/{total}]"


def load_env() -> None:
    workspace_env = WORKSPACE / ".env"
    if workspace_env.exists():
        load_dotenv(workspace_env)


load_env()
LLM_REQUEST_TIMEOUT = int(os.getenv("LLM_REQUEST_TIMEOUT", str(LLM_REQUEST_TIMEOUT)))


def read_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text[1:] if text.startswith("\ufeff") else text


def write_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def normalize_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none"}:
        return ""
    return text


def normalize_amount(value: Any) -> str:
    text = normalize_value(value)
    return text.replace(" uL", " μL").replace(" ul", " μL")


def allocate_positions(count: int, tray: str = "T-3") -> list[str]:
    if count < 1:
        raise ExperimentPlanError("No experiments to allocate.")
    if count > 48:
        raise ExperimentPlanError("T-3 supports at most 48 tube positions.")

    if count <= 16:
        cols = 2
        rows = math.ceil(count / cols)
    else:
        best: tuple[int, int, int, int] | None = None
        for cols in range(1, 7):
            rows = math.ceil(count / cols)
            if rows > 8:
                continue
            candidate = (cols * rows - count, abs(rows - cols), cols, rows)
            if best is None or candidate < best:
                best = candidate
        if best is None:
            raise ExperimentPlanError("Could not allocate positions.")
        _, _, cols, rows = best

    start_col = (6 - cols) // 2
    start_row = math.ceil((8 - rows) / 2)
    positions: list[str] = []
    for col in range(start_col, start_col + cols):
        for row in range(start_row, start_row + rows):
            if len(positions) >= count:
                return positions
            positions.append(f"{tray}:{col * 8 + row}")
    return positions


def parse_reaction_duration_seconds(steps_text: str) -> tuple[int, int, int, int]:
    pre_stir_s = 1800 if re.search(r"30\s*分钟", steps_text) else 1800
    reaction_s = 86400 if re.search(r"24\s*h|24\s*小时", steps_text, re.IGNORECASE) else 86400
    mix_s = 300 if re.search(r"5\s*分钟", steps_text) else 300
    settle_s = 1200 if re.search(r"20\s*分钟", steps_text) else 1200
    return pre_stir_s, reaction_s, mix_s, settle_s


def call_llm(prompt: str, system_content: str = "你只输出干净的 Markdown，不要解释，不要代码围栏。") -> str:
    client = get_openai_client()
    model = require_llm_config(OPENAI_MODEL, "OPENAI_MODEL")
    extra_body = build_extra_body(model)
    try:
        request_kwargs: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        if extra_body is not None:
            request_kwargs["extra_body"] = extra_body
        response = client.chat.completions.create(**request_kwargs)
        content = response.choices[0].message.content or ""
        return content.strip()
    except Exception as exc:
        raise ExperimentPlanError(f"LLM request failed: {exc}") from exc


def get_openai_client() -> OpenAI:
    global OPENAI_CLIENT
    if OPENAI_CLIENT is not None:
        return OPENAI_CLIENT
    api_key = require_llm_config(OPENAI_API_KEY)
    base_url = require_llm_config(OPENAI_BASE_URL)
    require_llm_config(OPENAI_MODEL)
    OPENAI_CLIENT = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=LLM_REQUEST_TIMEOUT,
    )
    return OPENAI_CLIENT


def normalize_llm_markdown(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:markdown|md)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def validate_markdown(markdown: str, position: str) -> None:
    required_markers = [
        f"# 实验方案 {position}",
        "## 实验概述",
        "## 试剂作用与用量",
        "## 实验步骤",
        "## 反应位置与过滤信息",
        f"- 反应位：{position}",
    ]
    for marker in required_markers:
        if marker not in markdown:
            raise ExperimentPlanError(f"Generated plan missing marker: {marker}")
    for token in FORBIDDEN_TOKENS:
        if token in markdown:
            raise ExperimentPlanError(f"Generated plan contains forbidden token: {token}")
    if "# Experiment Plan" in markdown:
        raise ExperimentPlanError("Generated plan contains old English plan title.")
    if not re.search(r"(?m)^\d+\.\s+", markdown):
        raise ExperimentPlanError("Generated plan must contain numbered steps.")


def normalize_step_text(text: str) -> str:
    return re.sub(r"^\s*\d+\.\s*", "", text.strip()).rstrip("。；; ")


def build_row_payload(row: pd.Series) -> dict[str, str]:
    payload: dict[str, str] = {}
    for key, value in row.items():
        text = normalize_value(value)
        if text:
            payload[key] = text
    return payload


def build_prompt(
    position: str,
    tray: str,
    row_payload: dict[str, str],
    steps_text: str,
    example_plan_text: str,
) -> str:
    pre_stir_s, reaction_s, mix_s, settle_s = parse_reaction_duration_seconds(steps_text)
    filter_index = position.split(":", 1)[1]
    return f"""
你要生成一篇中文 Markdown 实验方案，必须严格参考示例的四段结构和写法。

输出要求：
1. 只输出 Markdown 本文，不要解释，不要代码围栏，不要附加前后缀。
2. 顶层标题必须是 `# 实验方案 {position}`。
3. 必须且只能包含四个章节：
   - `## 实验概述`
   - `## 试剂作用与用量`
   - `## 实验步骤`
   - `## 反应位置与过滤信息`
4. `## 试剂作用与用量` 用项目符号列表。
5. `## 实验步骤` 用连续编号列表，并尽量与步骤参考文件的流程一致。
6. 明确写出反应位 `{position}` 和过滤位 `W3-5:{filter_index}`。
7. 不要出现 `layout_code`、`chemical_id`、`tray_QR_code`、`QR_code`。
8. 如果某个试剂在输入里是 `none` 或为空，就不要写入该试剂条目。
9. 所有用量必须保持输入中的数值和单位，不要擅自改写。
10. 文中要自然地把步骤中的 `{pre_stir_s} s`、`{reaction_s} s`、`{mix_s} s`、`{settle_s} s` 反映出来。

### 示例模板
{example_plan_text}

### 步骤参考
{steps_text}

### 本次实验数据
{json.dumps(row_payload, ensure_ascii=False, indent=2)}

### 写作目标
请根据本次实验数据，写出一份与示例同风格的完整实验方案。输出要适合直接保存为 `.md` 文件。
""".strip()


def require_llm_config(value: str | None, label: str) -> str:
    if not value:
        raise ExperimentPlanError(f"{label} is not set.")
    return value


def build_extra_body(model: str) -> dict[str, Any] | None:
    if model in THINKING_MODE_MODELS:
        return {"thinking_mode": False}
    return None


def generate_one_plan(
    index: int,
    row: pd.Series,
    position: str,
    tray: str,
    steps_text: str,
    example_plan_text: str,
) -> tuple[int, str]:
    row_payload = build_row_payload(row)
    last_error = ""

    for attempt in range(1, MAX_LLM_ATTEMPTS + 1):
        log_status(f"request {position}")
        prompt = build_prompt(position, tray, row_payload, steps_text, example_plan_text)
        if last_error:
            prompt += f"\n\n### 上一次错误\n{last_error}"

        markdown = normalize_llm_markdown(call_llm(prompt))
        try:
            validate_markdown(markdown, position)
            return index, markdown
        except ExperimentPlanError as exc:
            last_error = f"Attempt {attempt}: {exc}"
            if attempt < MAX_LLM_ATTEMPTS:
                log_status(f"retry request {position}: {exc}")

    raise ExperimentPlanError(f"Failed to generate valid plan after {MAX_LLM_ATTEMPTS} attempts for {position}. {last_error}")


def render_plans(
    steps_file: Path,
    amounts_csv: Path,
    output_dir: Path,
    tray: str = "T-3",
) -> list[Path]:
    if not steps_file.exists():
        raise ExperimentPlanError(f"Missing steps file: {steps_file}")
    if not amounts_csv.exists():
        raise ExperimentPlanError(f"Missing amounts CSV: {amounts_csv}")
    if not EXAMPLE_PLAN_FILE.exists():
        raise ExperimentPlanError(f"Missing example plan file: {EXAMPLE_PLAN_FILE}")

    steps_text = read_text(steps_file)
    example_plan_text = read_text(EXAMPLE_PLAN_FILE)
    df = pd.read_csv(amounts_csv)
    if df.empty:
        raise ExperimentPlanError("Amounts CSV contains no experiments.")

    positions = allocate_positions(len(df), tray=tray)
    output_dir.mkdir(parents=True, exist_ok=True)
    written_paths: list[Path] = []
    log_status(f"Generating {len(df)} plans")

    for idx, (row, position) in enumerate(zip(df.to_dict(orient="records"), positions), start=1):
        idx, markdown = generate_one_plan(
            idx,
            pd.Series(row),
            position,
            tray,
            steps_text,
            example_plan_text,
        )
        path = output_dir / f"experiment_plan_{tray}_{position.split(':', 1)[1]}.md"
        write_text(markdown, path)
        log_status(f"{progress_label(idx, len(df))} wrote {path.name}")
        written_paths.append(path)

    return written_paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Markdown experiment plans with LLM.")
    parser.add_argument("--steps-file", required=True, help="Generated experiment steps Markdown file.")
    parser.add_argument("--amounts-csv", required=True, help="Recommendation CSV with amount columns.")
    parser.add_argument("--output-dir", default="", help="Output directory. Defaults to output/experiment_plan_<timestamp>.")
    parser.add_argument("--tray", default="T-3", help="Reaction tray prefix, default T-3.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir) if args.output_dir else OUTPUT_DIR / f"experiment_plan_{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}"

    try:
        log_status(f"Output dir: {output_dir}")
        log_status(f"Steps file: {Path(args.steps_file)}")
        log_status(f"Amounts CSV: {Path(args.amounts_csv)}")
        paths = render_plans(
            Path(args.steps_file),
            Path(args.amounts_csv),
            output_dir,
            tray=args.tray,
        )
        positions = [path.stem.rsplit("_", 1)[-1] for path in paths]
        log_status(f"{progress_label(len(paths), len(paths))} Experiment plans generated: {output_dir}")
        log_status(f"Count: {len(paths)}")
        log_status("Positions: " + ", ".join(positions))
        return 0
    except Exception as exc:
        print(f"Generation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
