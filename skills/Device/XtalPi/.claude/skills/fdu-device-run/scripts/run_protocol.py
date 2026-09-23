#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict

import requests
from dotenv import load_dotenv

from device_api import DeviceAPIClient, DeviceRunError
from protocol_utils import (
    build_add_task_payload,
    load_protocol_from_sources,
    make_output_prefix,
    rewrite_unit_ids,
    summarize_layout,
    uniquify_task_name,
    write_json,
)

# 优先从.env文件加载配置，其次从环境变量加载
load_dotenv()  # 加载.env文件中的环境变量

BASE_URL = os.getenv("FDU_DEVICE_BASE_URL")
USERNAME = os.getenv("FDU_DEVICE_USERNAME")
PASSWORD = os.getenv("FDU_DEVICE_PASSWORD")
TIMEOUT = int(os.getenv("FDU_DEVICE_TIMEOUT"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Submit protocol JSON to device via AddTask. StartTask is disabled by default for safety."
    )
    parser.add_argument("--protocol-file", help="Path to protocol JSON file")
    parser.add_argument("--protocol-json", help="Inline protocol JSON string")
    parser.add_argument("--task-name", default="auto_generated_task", help="Base task name; a unique suffix is appended automatically")
    parser.add_argument("--base-url", default=BASE_URL, help="Device API base URL")
    parser.add_argument("--username", default=USERNAME, help="API username")
    parser.add_argument("--password", default=PASSWORD, help="API password")
    parser.add_argument("--timeout", type=int, default=TIMEOUT, help="HTTP timeout in seconds")
    parser.add_argument(
        "--keep-unit-ids",
        action="store_true",
        help="Keep original unit_id values. By default the script rewrites unit_id values to avoid duplication conflicts.",
    )
    parser.add_argument(
        "--enable-start",
        action="store_true",
        help="Actually call StartTask after AddTask. Default is disabled for on-site safety.",
    )
    parser.add_argument("--skip-curr-taskunit", type=int, default=1)
    parser.add_argument("--run-by-single-tube", type=int, default=0)
    parser.add_argument("--quick-cap", type=int, default=1)
    parser.add_argument("--use-tip-type", default="")
    return parser.parse_args()


def execute(args: argparse.Namespace) -> Dict[str, Any]:
    layout_list, protocol_source, structure_note = load_protocol_from_sources(
        protocol_json=args.protocol_json,
        protocol_file=args.protocol_file,
        allow_stdin=True,
    )

    final_task_name = uniquify_task_name(args.task_name)
    final_layout_list = layout_list if args.keep_unit_ids else rewrite_unit_ids(layout_list)

    client = DeviceAPIClient(
        base_url=args.base_url,
        username=args.username,
        password=args.password,
        timeout=args.timeout,
    )
    client.login()

    add_task_payload = build_add_task_payload(final_task_name, final_layout_list)
    add_task_result = client.add_task(add_task_payload)
    task_id = add_task_result.get("task_id")
    if task_id is None:
        raise DeviceRunError(f"AddTask succeeded but task_id is missing: {add_task_result}")

    result: Dict[str, Any] = {
        "protocol_source": protocol_source,
        "protocol_structure": structure_note,
        "protocol_structure_note": (
            "Detected single-step JSON object; auto-wrapped into protocol list with 1 step."
            if structure_note == "single_step_wrapped"
            else "Detected protocol JSON array."
        ),
        "task_name": final_task_name,
        "task_id": task_id,
        "layout_summary": summarize_layout(final_layout_list),
        "add_task_payload_preview": {
            "task_id": add_task_payload.get("task_id"),
            "task_name": add_task_payload.get("task_name"),
            "layout_count": len(add_task_payload.get("layout_list", [])),
        },
        "add_task_result": add_task_result,
        "start_task_enabled": bool(args.enable_start),
    }

    if args.enable_start:
        start_task_result = client.start_task(
            int(task_id),
            skip_curr_taskunit=args.skip_curr_taskunit,
            run_by_single_tube=args.run_by_single_tube,
            quick_cap=args.quick_cap,
            use_tip_type=args.use_tip_type,
        )
        result["start_task_result"] = start_task_result
    else:
        result["start_task_result"] = None
        result["start_task_note"] = (
            "StartTask was NOT called. This is intentional. "
            "Use --enable-start only when you are on-site and ready to run the device."
        )

    return result


def main() -> int:
    args = parse_args()
    try:
        result = execute(args)
        prefix = make_output_prefix("submit")
        output_file = prefix.with_suffix(".json")
        write_json(result, output_file)

        print("Connected to device and AddTask finished successfully.")
        print(f"Protocol source: {result['protocol_source']}")
        print(result["protocol_structure_note"])
        print(f"Task name: {result['task_name']}")
        print(f"Task ID: {result['task_id']}")
        print(f"Step count: {result['layout_summary']['step_count']}")
        print(f"Execution record saved to: {output_file}")
        if args.enable_start:
            print("StartTask was executed.")
        else:
            print("StartTask was skipped by default.")
        return 0

    except requests.HTTPError as e:
        print(f"HTTP request failed: {e}", file=sys.stderr)
        if e.response is not None:
            print("Response body:", file=sys.stderr)
            print(e.response.text, file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Execution failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
