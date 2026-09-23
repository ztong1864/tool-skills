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
BASE_URL = "http://8.130.18.34:4002/api/storage/location/pre-distribute-sample/{associate_id}"


def collect_material_name_map(obj, mapping=None):
    if mapping is None:
        mapping = {}
    if isinstance(obj, dict):
        material_id = obj.get("holdMId") or obj.get("materialId")
        material_name = obj.get("holdMName") or obj.get("materialName") or obj.get("name")
        if material_id and material_name:
            mapping[str(material_id)] = str(material_name)
        for value in obj.values():
            collect_material_name_map(value, mapping)
    elif isinstance(obj, list):
        for item in obj:
            collect_material_name_map(item, mapping)
    return mapping


def get_pre_distributed_sample(associate_id, only_data=False, json_output=False,
                               material_name_map_only=False, use_ssh=False,
                               ssh_host=SSH_HOST, ssh_user=SSH_USER,
                               ssh_password=SSH_PASSWORD, ssh_port=SSH_PORT,
                               ssh_timeout=SSH_TIMEOUT):
    url = BASE_URL.format(associate_id=associate_id)
    if use_ssh:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(hostname=ssh_host, username=ssh_user, password=ssh_password, port=ssh_port, timeout=ssh_timeout)
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
    if isinstance(data, dict) and "code" in data and "data" in data:
        if data.get("code") != 1:
            print(f"[ERROR] API 返回失败: {data.get('message')}", file=sys.stderr)
            sys.exit(1)
        result = data.get("data")
        full_output = data
    else:
        result = data
        full_output = data

    material_name_map = collect_material_name_map(result)
    if material_name_map_only:
        print(json.dumps(material_name_map, ensure_ascii=False, indent=2))
    elif only_data:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif json_output:
        print(json.dumps(full_output, ensure_ascii=False, indent=2))
    else:
        if not isinstance(result, dict):
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return full_output
        print("[OK] 已获取预分样结果")
        print(f"     associateId  : {associate_id}")
        print(f"     locationId   : {result.get('id')}")
        print(f"     locationCode : {result.get('code')}")
        print(f"     sampleId     : {result.get('holdMId')}")
        print(f"     sampleName   : {result.get('holdMName')}")
        print(f"     sampleCode   : {result.get('holdMCode')}")
        print(f"     sampleType   : {result.get('holdMTypeName')}")
        if material_name_map:
            print("     materialMap  :")
            print(json.dumps(material_name_map, ensure_ascii=False, indent=2))
    return full_output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="获取 Oasis 已分配样品")
    parser.add_argument("--associate-id", required=True)
    parser.add_argument("--only-data", action="store_true")
    parser.add_argument("--json-output", action="store_true")
    parser.add_argument("--material-name-map", action="store_true")
    parser.add_argument("--use-ssh", action="store_true")
    parser.add_argument("--ssh-host", default=SSH_HOST)
    parser.add_argument("--ssh-user", default=SSH_USER)
    parser.add_argument("--ssh-password", default=SSH_PASSWORD)
    parser.add_argument("--ssh-port", type=int, default=SSH_PORT)
    parser.add_argument("--ssh-timeout", type=int, default=SSH_TIMEOUT)
    args = parser.parse_args()
    get_pre_distributed_sample(
        associate_id=args.associate_id,
        only_data=args.only_data,
        json_output=args.json_output,
        material_name_map_only=args.material_name_map,
        use_ssh=args.use_ssh,
        ssh_host=args.ssh_host,
        ssh_user=args.ssh_user,
        ssh_password=args.ssh_password,
        ssh_port=args.ssh_port,
        ssh_timeout=args.ssh_timeout,
    )
