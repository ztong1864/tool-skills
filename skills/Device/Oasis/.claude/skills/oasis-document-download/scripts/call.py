#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import paramiko

SSH_HOST = "100.126.125.28"
SSH_USER = "HT"
SSH_PASSWORD = "1"
SSH_PORT = 22
SSH_TIMEOUT = 10
BASE_URL = "http://8.130.18.34:4003"
DEFAULT_OUTPUT_DIR = "outputs/oasis-document-download"


def build_list_url(folder_path=""):
    if folder_path:
        return f"{BASE_URL}/list/{quote(folder_path.replace(chr(92), '/').strip('/'), safe='/')}"
    return f"{BASE_URL}/list"


def build_download_url(file_path):
    normalized = file_path.replace(chr(92), "/").strip("/")
    return f"{BASE_URL}/download/{quote(normalized, safe='/')}"


def build_health_url():
    return f"{BASE_URL}/"


def normalize_download_target(target):
    normalized = target.replace(chr(92), "/").strip()
    if normalized.startswith(BASE_URL):
        normalized = normalized[len(BASE_URL):]
    if normalized.startswith("/download/"):
        normalized = normalized[len("/download/"):]
    elif normalized.startswith("download/"):
        normalized = normalized[len("download/"):]
    return normalized.strip("/")


def run_json_request(url, use_ssh=False,
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

        try:
            _, stdout, stderr = client.exec_command(f'curl -s "{url}"')
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
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON 解析失败: {e}\n原始响应: {raw[:500]}", file=sys.stderr)
        sys.exit(1)


def resolve_output_path(file_path, output=None, output_dir=DEFAULT_OUTPUT_DIR):
    if output:
        return Path(output)
    relative_parts = [part for part in file_path.replace(chr(92), "/").split("/") if part]
    return Path(output_dir).joinpath(*relative_parts)


def check_service(json_output=False, use_ssh=False,
                  ssh_host=SSH_HOST, ssh_user=SSH_USER,
                  ssh_password=SSH_PASSWORD, ssh_port=SSH_PORT,
                  ssh_timeout=SSH_TIMEOUT):
    data = run_json_request(
        build_health_url(),
        use_ssh=use_ssh,
        ssh_host=ssh_host,
        ssh_user=ssh_user,
        ssh_password=ssh_password,
        ssh_port=ssh_port,
        ssh_timeout=ssh_timeout,
    )

    if json_output:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print("[OK] 远程文档服务可用")
        print(f"     message  : {data.get('message')}")
        print(f"     list     : {data.get('list')}")
        print(f"     download : {data.get('download')}")
    return data


def list_documents(folder_path="", only_data=False, json_output=False,
                   use_ssh=False, ssh_host=SSH_HOST, ssh_user=SSH_USER,
                   ssh_password=SSH_PASSWORD, ssh_port=SSH_PORT,
                   ssh_timeout=SSH_TIMEOUT):
    data = run_json_request(
        build_list_url(folder_path),
        use_ssh=use_ssh,
        ssh_host=ssh_host,
        ssh_user=ssh_user,
        ssh_password=ssh_password,
        ssh_port=ssh_port,
        ssh_timeout=ssh_timeout,
    )

    items = data.get("items", [])
    if only_data:
        print(json.dumps(items, ensure_ascii=False, indent=2))
    elif json_output:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print("[OK] 已获取目录内容")
        print(f"     currentPath : {data.get('current_path')}")
        print(f"     baseDir     : {data.get('base_dir')}")
        print(f"     itemCount   : {len(items)}")
        for item in items:
            item_type = item.get("type")
            name = item.get("name")
            path = item.get("path")
            print(f"     - [{item_type}] {name} -> {path}")
    return data


def collect_file_paths(folder_path="", recursive=False,
                       use_ssh=False, ssh_host=SSH_HOST, ssh_user=SSH_USER,
                       ssh_password=SSH_PASSWORD, ssh_port=SSH_PORT,
                       ssh_timeout=SSH_TIMEOUT):
    data = run_json_request(
        build_list_url(folder_path),
        use_ssh=use_ssh,
        ssh_host=ssh_host,
        ssh_user=ssh_user,
        ssh_password=ssh_password,
        ssh_port=ssh_port,
        ssh_timeout=ssh_timeout,
    )

    file_paths = []
    for item in data.get("items", []):
        item_type = item.get("type")
        item_path = item.get("path")
        if item_type == "file" and item_path:
            file_paths.append(item_path)
        elif recursive and item_type == "folder" and item_path:
            file_paths.extend(
                collect_file_paths(
                    folder_path=item_path,
                    recursive=True,
                    use_ssh=use_ssh,
                    ssh_host=ssh_host,
                    ssh_user=ssh_user,
                    ssh_password=ssh_password,
                    ssh_port=ssh_port,
                    ssh_timeout=ssh_timeout,
                )
            )
    return file_paths


def download_document(file_path, output=None, output_dir=DEFAULT_OUTPUT_DIR,
                      overwrite=False, use_ssh=False,
                      ssh_host=SSH_HOST, ssh_user=SSH_USER,
                      ssh_password=SSH_PASSWORD, ssh_port=SSH_PORT,
                      ssh_timeout=SSH_TIMEOUT):
    file_path = normalize_download_target(file_path)
    output_path = resolve_output_path(file_path, output=output, output_dir=output_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not overwrite:
        print(f"[ERROR] 输出文件已存在: {output_path}。如需覆盖请追加 --overwrite", file=sys.stderr)
        sys.exit(1)

    url = build_download_url(file_path)
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

        try:
            _, stdout, stderr = client.exec_command(f'curl -sL "{url}"')
            content = stdout.read()
            err = stderr.read().decode("utf-8", errors="replace").strip()
        finally:
            client.close()
    else:
        try:
            result = subprocess.run(
                ["curl", "-sL", url],
                capture_output=True,
            )
            content = result.stdout
            err = result.stderr.decode("utf-8", errors="replace").strip()
        except Exception as e:
            print(f"[ERROR] 直接访问 API 失败: {e}", file=sys.stderr)
            sys.exit(1)

    if not content:
        print(f"[ERROR] 下载结果为空。curl stderr: {err}", file=sys.stderr)
        sys.exit(1)

    if content.startswith(b"{") and b'"detail":"Not Found"' in content[:300]:
        print(f"[ERROR] 目标文件不存在: {file_path}", file=sys.stderr)
        sys.exit(1)

    if content.startswith(b"{") and b'"detail":"Forbidden"' in content[:300]:
        print(f"[ERROR] 路径非法或无权访问: {file_path}", file=sys.stderr)
        sys.exit(1)

    output_path.write_bytes(content)
    print("[OK] 文件下载完成")
    print(f"     remotePath : {file_path}")
    print(f"     savedTo    : {output_path}")
    print(f"     bytes      : {output_path.stat().st_size}")
    return output_path


def download_multiple_documents(file_paths, output_dir=DEFAULT_OUTPUT_DIR,
                                overwrite=False, json_output=False,
                                use_ssh=False, ssh_host=SSH_HOST, ssh_user=SSH_USER,
                                ssh_password=SSH_PASSWORD, ssh_port=SSH_PORT,
                                ssh_timeout=SSH_TIMEOUT):
    saved_files = []
    for file_path in file_paths:
        saved_path = download_document(
            file_path=file_path,
            output=None,
            output_dir=output_dir,
            overwrite=overwrite,
            use_ssh=use_ssh,
            ssh_host=ssh_host,
            ssh_user=ssh_user,
            ssh_password=ssh_password,
            ssh_port=ssh_port,
            ssh_timeout=ssh_timeout,
        )
        saved_files.append(
            {
                "remote_path": file_path,
                "saved_to": str(saved_path),
                "bytes": saved_path.stat().st_size,
            }
        )

    if json_output:
        print(json.dumps(saved_files, ensure_ascii=False, indent=2))
    else:
        print("[OK] Multiple files downloaded.")
        print(f"     fileCount  : {len(saved_files)}")
        print(f"     outputDir  : {output_dir}")
    return saved_files


def download_folder(folder_path="", output_dir=DEFAULT_OUTPUT_DIR,
                    overwrite=False, recursive=False, json_output=False,
                    use_ssh=False, ssh_host=SSH_HOST, ssh_user=SSH_USER,
                    ssh_password=SSH_PASSWORD, ssh_port=SSH_PORT,
                    ssh_timeout=SSH_TIMEOUT):
    file_paths = collect_file_paths(
        folder_path=folder_path,
        recursive=recursive,
        use_ssh=use_ssh,
        ssh_host=ssh_host,
        ssh_user=ssh_user,
        ssh_password=ssh_password,
        ssh_port=ssh_port,
        ssh_timeout=ssh_timeout,
    )

    if not file_paths:
        print("[ERROR] 目标目录下没有可下载文件", file=sys.stderr)
        sys.exit(1)

    saved_files = []
    for file_path in file_paths:
        saved_path = download_document(
            file_path=file_path,
            output=None,
            output_dir=output_dir,
            overwrite=overwrite,
            use_ssh=use_ssh,
            ssh_host=ssh_host,
            ssh_user=ssh_user,
            ssh_password=ssh_password,
            ssh_port=ssh_port,
            ssh_timeout=ssh_timeout,
        )
        saved_files.append(
            {
                "remote_path": file_path,
                "saved_to": str(saved_path),
                "bytes": saved_path.stat().st_size,
            }
        )

    if json_output:
        print(json.dumps(saved_files, ensure_ascii=False, indent=2))
    else:
        print("[OK] 批量下载完成")
        print(f"     folderPath : {folder_path or '.'}")
        print(f"     fileCount  : {len(saved_files)}")
        print(f"     recursive  : {'true' if recursive else 'false'}")
        print(f"     outputDir  : {output_dir}")
    return saved_files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="查询远程目录并下载文档到本地")
    parser.add_argument("--check-service", action="store_true", help="检查远程文档服务是否可用")
    parser.add_argument("--folder-path", default="", help="要查询的相对目录路径；不传时查询根目录")
    parser.add_argument("--download-path", help="要下载的相对文件路径")
    parser.add_argument("--download-paths", nargs="+", help="要批量下载的多个相对文件路径；可以来自不同目录")
    parser.add_argument("--download-urls", nargs="+", help="要批量下载的多个 download_url；每个元素可以直接使用 list 返回的 download_url")
    parser.add_argument("--download-folder", action="store_true", help="批量下载目标目录下的文件")
    parser.add_argument("--recursive", action="store_true", help="批量下载目录时递归包含子目录")
    parser.add_argument("--output", help="下载文件的本地输出路径")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="未传 --output 时的本地输出目录")
    parser.add_argument("--overwrite", action="store_true", help="允许覆盖已存在的本地文件")
    parser.add_argument("--only-data", action="store_true", help="只输出 list 的 items 数组")
    parser.add_argument("--json-output", action="store_true", help="输出完整 JSON")
    parser.add_argument("--use-ssh", action="store_true", help="显式改为通过 SSH 在远端执行 curl")
    parser.add_argument("--ssh-host", default=SSH_HOST, help="SSH host/IP")
    parser.add_argument("--ssh-user", default=SSH_USER, help="SSH username")
    parser.add_argument("--ssh-password", default=SSH_PASSWORD, help="SSH password")
    parser.add_argument("--ssh-port", type=int, default=SSH_PORT, help="SSH port")
    parser.add_argument("--ssh-timeout", type=int, default=SSH_TIMEOUT, help="SSH timeout seconds")
    args = parser.parse_args()

    active_download_modes = sum(
        [
            1 if args.download_path else 0,
            1 if args.download_paths else 0,
            1 if args.download_urls else 0,
            1 if args.download_folder else 0,
        ]
    )
    if active_download_modes > 1:
        print("[ERROR] --download-path、--download-paths、--download-urls 和 --download-folder 不能同时使用", file=sys.stderr)
        sys.exit(1)

    if args.download_path:
        download_document(
            file_path=args.download_path,
            output=args.output,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
            use_ssh=args.use_ssh,
            ssh_host=args.ssh_host,
            ssh_user=args.ssh_user,
            ssh_password=args.ssh_password,
            ssh_port=args.ssh_port,
            ssh_timeout=args.ssh_timeout,
        )
    elif args.download_paths:
        if args.output:
            print("[ERROR] --download-paths 场景下不能同时使用 --output；请改用 --output-dir", file=sys.stderr)
            sys.exit(1)
        download_multiple_documents(
            file_paths=args.download_paths,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
            json_output=args.json_output,
            use_ssh=args.use_ssh,
            ssh_host=args.ssh_host,
            ssh_user=args.ssh_user,
            ssh_password=args.ssh_password,
            ssh_port=args.ssh_port,
            ssh_timeout=args.ssh_timeout,
        )
    elif args.download_urls:
        if args.output:
            print("[ERROR] --download-urls 场景下不能同时使用 --output；请改用 --output-dir", file=sys.stderr)
            sys.exit(1)
        download_multiple_documents(
            file_paths=args.download_urls,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
            json_output=args.json_output,
            use_ssh=args.use_ssh,
            ssh_host=args.ssh_host,
            ssh_user=args.ssh_user,
            ssh_password=args.ssh_password,
            ssh_port=args.ssh_port,
            ssh_timeout=args.ssh_timeout,
        )
    elif args.download_folder:
        download_folder(
            folder_path=args.folder_path,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
            recursive=args.recursive,
            json_output=args.json_output,
            use_ssh=args.use_ssh,
            ssh_host=args.ssh_host,
            ssh_user=args.ssh_user,
            ssh_password=args.ssh_password,
            ssh_port=args.ssh_port,
            ssh_timeout=args.ssh_timeout,
        )
    elif args.check_service:
        check_service(
            json_output=args.json_output,
            use_ssh=args.use_ssh,
            ssh_host=args.ssh_host,
            ssh_user=args.ssh_user,
            ssh_password=args.ssh_password,
            ssh_port=args.ssh_port,
            ssh_timeout=args.ssh_timeout,
        )
    else:
        list_documents(
            folder_path=args.folder_path,
            only_data=args.only_data,
            json_output=args.json_output,
            use_ssh=args.use_ssh,
            ssh_host=args.ssh_host,
            ssh_user=args.ssh_user,
            ssh_password=args.ssh_password,
            ssh_port=args.ssh_port,
            ssh_timeout=args.ssh_timeout,
        )
