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
API_URL = "http://8.130.18.34:4002/api/order/order/order-progess"


def save_order_progess(order_code, order_name, workflow_id, workflow_name,
                       parameters, step_material_records="{}", commonly_order_id=None,
                       current_step=2, concurrency_stamp="", json_output=False,
                       use_ssh=False, ssh_host=SSH_HOST, ssh_user=SSH_USER,
                       ssh_password=SSH_PASSWORD, ssh_port=SSH_PORT,
                       ssh_timeout=SSH_TIMEOUT):
    body_json = json.dumps({
        "commonlyOrderId": commonly_order_id,
        "concurrencyStamp": concurrency_stamp,
        "currentStep": current_step,
        "orderCode": order_code,
        "orderName": order_name,
        "parameters": parameters,
        "stepMaterialRecords": step_material_records,
        "workflowId": workflow_id,
        "workflowName": workflow_name,
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
        print("[OK] 实验步骤已保存！")
        print(f"     orderCode       : {result.get('orderCode')}")
        print(f"     commonlyOrderId : {result.get('id')}")
        print(f"     currentStep     : {result.get('currentStep')}")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="保存绿洲实验步骤")
    parser.add_argument("--order-code", required=True)
    parser.add_argument("--order-name", required=True)
    parser.add_argument("--workflow-id", required=True)
    parser.add_argument("--workflow-name", required=True)
    parser.add_argument("--parameters", default="{}")
    parser.add_argument("--parameters-file")
    parser.add_argument("--step-material-records", default="{}")
    parser.add_argument("--commonly-order-id", default=None)
    parser.add_argument("--step", type=int, default=2)
    parser.add_argument("--concurrency-stamp", default="")
    parser.add_argument("--json-output", action="store_true")
    parser.add_argument("--use-ssh", action="store_true")
    parser.add_argument("--ssh-host", default=SSH_HOST)
    parser.add_argument("--ssh-user", default=SSH_USER)
    parser.add_argument("--ssh-password", default=SSH_PASSWORD)
    parser.add_argument("--ssh-port", type=int, default=SSH_PORT)
    parser.add_argument("--ssh-timeout", type=int, default=SSH_TIMEOUT)
    args = parser.parse_args()

    parameters = args.parameters
    if args.parameters_file:
        with open(args.parameters_file, encoding="utf-8") as f:
            parameters = json.dumps(json.load(f), ensure_ascii=False)

    save_order_progess(
        order_code=args.order_code,
        order_name=args.order_name,
        workflow_id=args.workflow_id,
        workflow_name=args.workflow_name,
        parameters=parameters,
        step_material_records=args.step_material_records,
        commonly_order_id=args.commonly_order_id,
        current_step=args.step,
        concurrency_stamp=args.concurrency_stamp,
        json_output=args.json_output,
        use_ssh=args.use_ssh,
        ssh_host=args.ssh_host,
        ssh_user=args.ssh_user,
        ssh_password=args.ssh_password,
        ssh_port=args.ssh_port,
        ssh_timeout=args.ssh_timeout,
    )
