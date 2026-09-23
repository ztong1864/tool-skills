#!/usr/bin/env python3
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
API_URL = "http://8.130.18.34:4002/api/order/order/order-progess-only-step"
STEP_LABELS = {3: "样品放置完成", 4: "试剂放置完成", 5: "耗材放置完成"}


def save_only_step(order_code, order_name, step, json_output=False, use_ssh=False,
                   ssh_host=SSH_HOST, ssh_user=SSH_USER,
                   ssh_password=SSH_PASSWORD, ssh_port=SSH_PORT,
                   ssh_timeout=SSH_TIMEOUT):
    body_json = json.dumps({
        "step": step,
        "orderCode": order_code,
        "orderName": order_name,
        "materialParameter": None,
    }, ensure_ascii=False)

    if use_ssh:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(hostname=ssh_host, username=ssh_user, password=ssh_password, port=ssh_port, timeout=ssh_timeout)
        except Exception as e:
            print(f"[ERROR] SSH 连接失败: {e}", file=sys.stderr)
            sys.exit(1)
        try:
            cmd = (f'curl -s -X PUT "{API_URL}" '
                   f'-H "Content-Type: application/json; charset=utf-8" '
                   f'--data-binary @-')
            stdin, stdout, stderr = client.exec_command(cmd)
            stdin.write(body_json)
            stdin.flush()
            stdin.channel.shutdown_write()
            raw = stdout.read().decode("utf-8", errors="replace").strip()
            err = stderr.read().decode("utf-8", errors="replace").strip()
        finally:
            client.close()
    else:
        result = subprocess.run(
            ["curl", "-s", "-X", "PUT", API_URL, "-H", "Content-Type: application/json; charset=utf-8", "--data-binary", "@-"],
            input=body_json,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        raw = result.stdout.strip()
        err = result.stderr.strip()

    if not raw:
        print(f"[ERROR] API 无响应。curl stderr: {err}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(raw)
    if data.get("code") != 1:
        print(f"[ERROR] API 返回失败: {data.get('message')}", file=sys.stderr)
        sys.exit(1)
    result = data.get("data", {})
    if json_output:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"[OK] 步骤已保存：{STEP_LABELS.get(step, f'step={step}')}")
        print(f"     orderCode   : {result.get('orderCode')}")
        print(f"     currentStep : {result.get('currentStep')}")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="入库后步骤保存")
    parser.add_argument("--order-code", required=True)
    parser.add_argument("--order-name", required=True)
    parser.add_argument("--step", required=True, type=int, choices=[3, 4, 5])
    parser.add_argument("--json-output", action="store_true")
    parser.add_argument("--use-ssh", action="store_true")
    parser.add_argument("--ssh-host", default=SSH_HOST)
    parser.add_argument("--ssh-user", default=SSH_USER)
    parser.add_argument("--ssh-password", default=SSH_PASSWORD)
    parser.add_argument("--ssh-port", type=int, default=SSH_PORT)
    parser.add_argument("--ssh-timeout", type=int, default=SSH_TIMEOUT)
    args = parser.parse_args()
    save_only_step(
        args.order_code,
        args.order_name,
        args.step,
        json_output=args.json_output,
        use_ssh=args.use_ssh,
        ssh_host=args.ssh_host,
        ssh_user=args.ssh_user,
        ssh_password=args.ssh_password,
        ssh_port=args.ssh_port,
        ssh_timeout=args.ssh_timeout,
    )
