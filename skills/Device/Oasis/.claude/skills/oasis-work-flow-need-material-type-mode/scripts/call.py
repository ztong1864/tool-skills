#!/usr/bin/env python3
"""
Oasis 绿洲实验平台 - 获取工作流所需物料类型
API: GET http://8.130.18.34:4002/api/storage/location/work-flow-need-material-type-mode/{subWorkflowId}
"""

import argparse
import json
import subprocess
import sys

import paramiko

SSH_HOST = "100.126.125.28"
SSH_USER = "HT"
SSH_PASSWORD = "1"
SSH_PORT = 22
SSH_TIMEOUT = 10
BASE_URL = "http://8.130.18.34:4002/api/storage/location/work-flow-need-material-type-mode/{sub_workflow_id}"


def get_material_type_mode(sub_workflow_id, only_data=False, json_output=False, use_ssh=False,
                           ssh_host=SSH_HOST, ssh_user=SSH_USER,
                           ssh_password=SSH_PASSWORD, ssh_port=SSH_PORT,
                           ssh_timeout=SSH_TIMEOUT):
    url = BASE_URL.format(sub_workflow_id=sub_workflow_id)

    if use_ssh:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(hostname=ssh_host, username=ssh_user,
                           password=ssh_password, port=ssh_port, timeout=ssh_timeout)
        except Exception as e:
            print(f"[ERROR] SSH 连接失败: {e}", file=sys.stderr)
            sys.exit(1)

        cmd = f'curl -s "{url}"'
        try:
            _, stdout, stderr = client.exec_command(cmd)
            raw = stdout.read().decode("utf-8", errors="replace").strip()
            err = stderr.read().decode("utf-8", errors="replace").strip()
        finally:
            client.close()
    else:
        try:
            result = subprocess.run(
                ["curl", "-s", url],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            raw = result.stdout.strip()
            err = result.stderr.strip()
        except Exception as e:
            print(f"[ERROR] 直接访问 API 失败: {e}", file=sys.stderr)
            sys.exit(1)

    if not raw:
        print(f"[ERROR] API 无响应。curl stderr: {err}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON 解析失败: {e}\n原始响应: {raw[:200]}", file=sys.stderr)
        sys.exit(1)

    if data.get("code") != 1:
        print(f"[ERROR] API 返回失败: {data.get('message')}", file=sys.stderr)
        sys.exit(1)

    mode = data["data"]
    if only_data:
        print(mode)
    elif json_output:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        labels = ["样品", "试剂", "耗材"]
        needed = [labels[i] for i, c in enumerate(mode) if c == "1"]
        not_needed = [labels[i] for i, c in enumerate(mode) if c == "0"]
        print(f"[OK] 物料需求: {mode}")
        print(f"     需要  : {', '.join(needed) if needed else '无'}")
        print(f"     不需要: {', '.join(not_needed) if not_needed else '无'}")

    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="获取绿洲工作流所需物料类型")
    parser.add_argument("--id", required=True, metavar="SUB_WORKFLOW_ID", help="子工作流 ID")
    parser.add_argument("--only-data", action="store_true", help="只输出 3 位模式字符串，如 101")
    parser.add_argument("--json-output", action="store_true", help="输出完整 JSON 响应")
    parser.add_argument("--use-ssh", action="store_true", help="显式改为通过 SSH 在远端执行 curl")
    parser.add_argument("--ssh-host", default=SSH_HOST, help="SSH host/IP")
    parser.add_argument("--ssh-user", default=SSH_USER, help="SSH username")
    parser.add_argument("--ssh-password", default=SSH_PASSWORD, help="SSH password")
    parser.add_argument("--ssh-port", type=int, default=SSH_PORT, help="SSH port")
    parser.add_argument("--ssh-timeout", type=int, default=SSH_TIMEOUT, help="SSH timeout seconds")
    args = parser.parse_args()
    get_material_type_mode(
        args.id,
        only_data=args.only_data,
        json_output=args.json_output,
        use_ssh=args.use_ssh,
        ssh_host=args.ssh_host,
        ssh_user=args.ssh_user,
        ssh_password=args.ssh_password,
        ssh_port=args.ssh_port,
        ssh_timeout=args.ssh_timeout,
    )
