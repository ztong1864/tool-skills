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
BASE_URL = "http://8.130.18.34:4002/api/storage/location/empty-locations-by-type"
TYPE_LABELS = {0: "耗材", 1: "样品", 2: "试剂"}


def get_empty_locations(workflow_id, commonly_order_id, material_type_mode,
                        loc_count=1, material_type_id="", only_data=False,
                        json_output=False, use_ssh=False, ssh_host=SSH_HOST,
                        ssh_user=SSH_USER, ssh_password=SSH_PASSWORD,
                        ssh_port=SSH_PORT, ssh_timeout=SSH_TIMEOUT):
    url = (f"{BASE_URL}?materialTypeMode={material_type_mode}"
           f"&locCount={loc_count}"
           f"&workflowId={workflow_id}"
           f"&commonlyOrderId={commonly_order_id}"
           f"&materialTypeId={material_type_id}")

    if use_ssh:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(hostname=ssh_host, username=ssh_user,
                           password=ssh_password, port=ssh_port, timeout=ssh_timeout)
        except Exception as e:
            print(f"[ERROR] SSH 连接失败: {e}", file=sys.stderr)
            sys.exit(1)
        try:
            _, stdout, stderr = client.exec_command(f'curl -s "{url}"')
            raw = stdout.read().decode("utf-8", errors="replace").strip()
            err = stderr.read().decode("utf-8", errors="replace").strip()
        finally:
            client.close()
    else:
        result = subprocess.run(["curl", "-s", url], capture_output=True, text=True, encoding="utf-8")
        raw = result.stdout.strip()
        err = result.stderr.strip()

    if not raw:
        print(f"[ERROR] API 无响应。curl stderr: {err}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(raw)
    if data.get("code") != 1:
        print(f"[ERROR] API 返回失败: {data.get('message')}", file=sys.stderr)
        sys.exit(1)

    if only_data:
        print(json.dumps(data["data"], ensure_ascii=False, indent=2))
    elif json_output:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        label = TYPE_LABELS.get(material_type_mode, str(material_type_mode))
        items = data["data"]
        print(f"[OK] {label} 库位分配结果（共 {len(items)} 种物料）：\n")
        for item in items:
            print(f"  物料类型: {item.get('materialTypeName')}  (materialTypeId: {item.get('materialTypeId')})")
            for loc in item.get("locations", []):
                print(f"    库位: {loc.get('code')}  locationId: {loc.get('id')}")
            print()
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="获取绿洲空闲库位")
    parser.add_argument("--workflow-id", required=True)
    parser.add_argument("--order-id", required=True)
    parser.add_argument("--type", required=True, type=int, choices=[0, 1, 2])
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--material-type-id", default="")
    parser.add_argument("--only-data", action="store_true")
    parser.add_argument("--json-output", action="store_true")
    parser.add_argument("--use-ssh", action="store_true")
    parser.add_argument("--ssh-host", default=SSH_HOST)
    parser.add_argument("--ssh-user", default=SSH_USER)
    parser.add_argument("--ssh-password", default=SSH_PASSWORD)
    parser.add_argument("--ssh-port", type=int, default=SSH_PORT)
    parser.add_argument("--ssh-timeout", type=int, default=SSH_TIMEOUT)
    args = parser.parse_args()
    get_empty_locations(
        workflow_id=args.workflow_id,
        commonly_order_id=args.order_id,
        material_type_mode=args.type,
        loc_count=args.count,
        material_type_id=args.material_type_id,
        only_data=args.only_data,
        json_output=args.json_output,
        use_ssh=args.use_ssh,
        ssh_host=args.ssh_host,
        ssh_user=args.ssh_user,
        ssh_password=args.ssh_password,
        ssh_port=args.ssh_port,
        ssh_timeout=args.ssh_timeout,
    )
