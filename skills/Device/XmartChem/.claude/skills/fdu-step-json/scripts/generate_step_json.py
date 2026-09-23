#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from step_json_core import (
    KB_DIR,
    OUTPUT_DIR,
    StepJsonGenerationError,
    generate_step_json_from_text,
    summarize_unit_types,
    write_json,
)

TEST_PLAN_FILE = KB_DIR / "test_plan.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="根据实验方案生成单步 JSON。")
    parser.add_argument("--plan", type=str, default="", help="Markdown 或纯文本格式的实验方案")
    parser.add_argument("--plan-file", type=str, default="", help="实验方案文件路径")
    parser.add_argument("--test", action="store_true", help="运行 KB/test_plan.md 示例实验方案")
    return parser


def resolve_plan_text(plan_text: str, plan_file: str, use_test: bool) -> str:
    if use_test:
        return TEST_PLAN_FILE.read_text(encoding="utf-8").strip()
    if plan_file:
        return Path(plan_file).read_text(encoding="utf-8").strip()
    return plan_text.strip()


def build_run_timestamps() -> tuple[str, Path]:
    now = datetime.now().replace(microsecond=0)
    output_timestamp = now.strftime("%Y-%m-%d-%H-%M-%S")
    out_path = OUTPUT_DIR / f"generated_step_json_{now.strftime('%Y-%m-%d-%H-%M-%S')}.json"
    return output_timestamp, out_path


def main() -> int:
    args = build_parser().parse_args()
    plan_text = resolve_plan_text(args.plan, args.plan_file, args.test)

    if not plan_text:
        print("实验方案不能为空。请通过 --plan、--plan-file 或 --test 提供输入。", file=sys.stderr)
        return 1

    try:
        output_timestamp, out_path = build_run_timestamps()
        step_json, steps = generate_step_json_from_text(plan_text, timestamp=output_timestamp)
        write_json(step_json, out_path)

        print(f"单步 JSON 已生成：{out_path}")
        print(f"步骤总数：{len(steps)}")
        print(f"单元类型：{', '.join(summarize_unit_types(steps))}")
        return 0
    except StepJsonGenerationError as exc:
        print(f"生成失败：{exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"发生未预期错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
