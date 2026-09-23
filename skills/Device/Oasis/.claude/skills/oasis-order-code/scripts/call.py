#!/usr/bin/env python3
"""
Oasis 绿洲实验平台 - 获取新实验编号
API: GET http://8.130.18.34:4002/api/order/order/order-code

用法：
    python call.py
    python call.py --only-data
    python call.py --json-output
    python call.py --use-ssh
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
SSH_TIMEOUT = 100
API_URL = "http://8.130.18.34:4002/api/order/order/order-code"


def get_order_code(only_data=False, json_output=False, use_ssh=False,
                   ssh_host=SSH_HOST, ssh_user=SSH_USER,
                   ssh_password=SSH_PASSWORD, ssh_port=SSH_PORT,
                   ssh_timeout=SSH_TIMEOUT):
    if use_ssh:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=ssh_host,
                username=ssh_user,
                password=ssh_password,
                port=ssh_port,
                timeout=ssh_timeout,
            )
        except Exception as e:
            print(f"[ERROR] SSH 连接失败: {e}", file=sys.stderr)
            sys.exit(1)

        cmd = f'curl -s "{API_URL}"'
        try:
            _, stdout, stderr = client.exec_command(cmd)
            raw = stdout.read().decode("utf-8", errors="replace").strip()
            err = stderr.read().decode("utf-8", errors="replace").strip()
        finally:
            client.close()
    else:
        try:
            result = subprocess.run(
                ["curl", "-s", API_URL],
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
        print(f"[ERROR] JSON 解析失败: {e}\n原始响应: {raw}", file=sys.stderr)
        sys.exit(1)

    if data.get("code") != 1:
        print(f"[ERROR] API 返回失败: {data.get('message')}", file=sys.stderr)
        sys.exit(1)

    order_code = data["data"]
    if only_data:
        print(order_code)
    elif json_output:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"[OK] 实验编号: {order_code}")

    return order_code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="获取绿洲平台新实验编号")
    parser.add_argument("--only-data", action="store_true", help="只输出 orderCode 字符串")
    parser.add_argument("--json-output", action="store_true", help="输出完整 JSON 响应")
    parser.add_argument("--use-ssh", action="store_true", help="显式改为通过 SSH 在远端执行 curl")
    parser.add_argument("--ssh-host", default=SSH_HOST, help="SSH host/IP")
    parser.add_argument("--ssh-user", default=SSH_USER, help="SSH username")
    parser.add_argument("--ssh-password", default=SSH_PASSWORD, help="SSH password")
    parser.add_argument("--ssh-port", type=int, default=SSH_PORT, help="SSH port")
    parser.add_argument("--ssh-timeout", type=int, default=SSH_TIMEOUT, help="SSH timeout seconds")
    args = parser.parse_args()

    get_order_code(
        only_data=args.only_data,
        json_output=args.json_output,
        use_ssh=args.use_ssh,
        ssh_host=args.ssh_host,
        ssh_user=args.ssh_user,
        ssh_password=args.ssh_password,
        ssh_port=args.ssh_port,
        ssh_timeout=args.ssh_timeout,
    )
