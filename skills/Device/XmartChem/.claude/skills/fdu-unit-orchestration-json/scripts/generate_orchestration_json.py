#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from orchestration_core import (
    generate_orchestration_json,
    OrchestrationError,
)


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser."""
    parser = argparse.ArgumentParser(
        description="根据 fdu-step-json 的输出生成设备执行协议 JSON。"
    )
    parser.add_argument(
        "--step-json",
        type=str,
        required=True,
        help="fdu-step-json 生成的步骤 JSON 文件路径"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="输出文件路径（可选，默认为 output/generated_protocol_YYYY-MM-DD-HH-MM-SS.json）"
    )
    return parser


def main() -> int:
    """Main entry point."""
    args = build_parser().parse_args()

    # Validate step JSON path
    step_json_path = Path(args.step_json)
    if not step_json_path.exists():
        print(f"错误：步骤 JSON 文件不存在：{step_json_path}", file=sys.stderr)
        return 1

    # Determine output path
    output_path = None
    if args.output:
        output_path = Path(args.output)

    try:
        # Generate orchestration JSON
        protocol, out_path = generate_orchestration_json(step_json_path, output_path)

        # Print summary
        print(f"执行协议已生成：{out_path}")
        print(f"步骤总数：{len(protocol)}")

        # Print unit types
        unit_types = set(step.get("unit_type") for step in protocol if "unit_type" in step)
        if unit_types:
            print(f"单元类型：{', '.join(sorted(unit_types))}")

        return 0
    except OrchestrationError as exc:
        print(f"编排失败：{exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"发生未预期错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
