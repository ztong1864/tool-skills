#!/usr/bin/env python3
"""Upload a Momentum experiment script .txt file, queue a remote import job, and poll until it finishes."""

from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import sys
import time
from pathlib import Path


DEFAULT_HOST = "100.65.75.32"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "Admin"
DEFAULT_REMOTE_ROOT = r"D:\IB"
DEFAULT_REMOTE_SCRIPT_DIR = "process_scripts"
DEFAULT_IMPORTER_NAME = "import-process.ps1"
DEFAULT_JOB_QUERY_NAME = "get-import-process-job.ps1"


def require_paramiko():
    try:
        import paramiko  # type: ignore
    except ImportError:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "message": "Missing dependency: install paramiko in the active Python environment.",
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return None
    return paramiko


def ps_quote(value: str) -> str:
    return '"' + value.replace('"', r'\"') + '"'


def windows_to_sftp_path(path: str) -> str:
    return path.replace("\\", "/")


def join_windows_path(root: str, *parts: str) -> str:
    return str(Path(root, *parts))


def ensure_remote_dir(sftp, remote_dir: str) -> None:
    normalized = windows_to_sftp_path(remote_dir).rstrip("/")
    drive_match = re.match(r"^[A-Za-z]:", normalized)
    if drive_match:
        current = drive_match.group(0)
        rest = normalized[len(current) :].strip("/")
        parts = [p for p in rest.split("/") if p]
    else:
        current = "/" if normalized.startswith("/") else "."
        parts = [p for p in normalized.strip("/").split("/") if p]

    for part in parts:
        current = posixpath.join(current, part)
        try:
            sftp.stat(current)
        except OSError:
            sftp.mkdir(current)


def extract_json(text: str):
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def run_remote_command(ssh, command: str):
    stdin, stdout, stderr = ssh.exec_command(command)
    del stdin
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out, err


def build_queue_command(args, script_name: str) -> str:
    return " ".join(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            ps_quote(args.importer),
            "-ScriptName",
            ps_quote(script_name),
        ]
    )


def build_query_command(args, job_id: str) -> str:
    return " ".join(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            ps_quote(args.job_query),
            "-JobId",
            ps_quote(job_id),
        ]
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script_file", help="Local .txt experiment script path to upload and import.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--username", default=DEFAULT_USERNAME)
    parser.add_argument("--password", default=os.environ.get("MOMENTUM_IMPORT_PASSWORD", DEFAULT_PASSWORD))
    parser.add_argument(
        "--remote-root",
        default=DEFAULT_REMOTE_ROOT,
        help="Remote root directory that contains process_scripts/, import-process.ps1, and get-import-process-job.ps1.",
    )
    parser.add_argument("--script-root", help="Remote experiment script directory. Defaults to <remote-root>\\process_scripts.")
    parser.add_argument("--importer", help="Remote import script path. Defaults to <remote-root>\\import-process.ps1.")
    parser.add_argument("--job-query", help="Remote job query script path. Defaults to <remote-root>\\get-import-process-job.ps1.")
    parser.add_argument("--remote-name", help="Remote file name. Defaults to the local basename.")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--poll-seconds", type=float, default=2.5)
    parser.add_argument("--connect-timeout", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    local_path = Path(args.script_file)
    if not local_path.is_file():
        print(json.dumps({"status": "failed", "message": f"Local experiment script not found: {local_path}"}, ensure_ascii=False, indent=2))
        return 2
    if local_path.suffix.lower() != ".txt":
        print(json.dumps({"status": "failed", "message": f"Expected a .txt file: {local_path}"}, ensure_ascii=False, indent=2))
        return 2

    script_name = args.remote_name or local_path.name
    if Path(script_name).name != script_name or not script_name.lower().endswith(".txt"):
        print(json.dumps({"status": "failed", "message": "--remote-name must be a .txt file name, not a path."}, ensure_ascii=False, indent=2))
        return 2

    remote_root = args.remote_root
    args.script_root = args.script_root or join_windows_path(remote_root, DEFAULT_REMOTE_SCRIPT_DIR)
    args.importer = args.importer or join_windows_path(remote_root, DEFAULT_IMPORTER_NAME)
    args.job_query = args.job_query or join_windows_path(remote_root, DEFAULT_JOB_QUERY_NAME)

    remote_dir = args.script_root
    remote_path = windows_to_sftp_path(posixpath.join(windows_to_sftp_path(remote_dir).rstrip("/"), script_name))
    queue_command = build_queue_command(args, script_name)

    if args.dry_run:
        print(
            json.dumps(
                {
                    "status": "dry-run",
                    "host": args.host,
                    "localPath": str(local_path),
                    "remoteRoot": remote_root,
                    "remoteScriptRoot": args.script_root,
                    "importer": args.importer,
                    "jobQuery": args.job_query,
                    "remotePath": remote_path,
                    "queueCommand": queue_command,
                    "jobQueryCommandTemplate": build_query_command(args, "<jobId>"),
                    "pollSeconds": args.poll_seconds,
                    "timeoutSeconds": args.timeout_seconds,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    paramiko = require_paramiko()
    if paramiko is None:
        return 2

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(
            hostname=args.host,
            username=args.username,
            password=args.password,
            timeout=args.connect_timeout,
            banner_timeout=args.connect_timeout,
            auth_timeout=args.connect_timeout,
        )
        sftp = ssh.open_sftp()
        try:
            ensure_remote_dir(sftp, remote_dir)
            sftp.put(str(local_path), remote_path)
        finally:
            sftp.close()

        queue_exit_code, queue_stdout, queue_stderr = run_remote_command(ssh, queue_command)
        queue_payload = extract_json(queue_stdout)
        if queue_exit_code != 0 or not isinstance(queue_payload, dict):
            print(
                json.dumps(
                    {
                        "status": "failed",
                        "host": args.host,
                        "uploaded": True,
                        "localPath": str(local_path),
                        "remotePath": remote_path,
                        "queueExitCode": queue_exit_code,
                        "queueResult": queue_payload,
                        "stderr": queue_stderr.strip() or None,
                        "stdout": queue_stdout.strip() or None,
                        "message": "Failed to queue import job.",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 1

        job_id = queue_payload.get("jobId")
        queue_status = queue_payload.get("status")
        if queue_status != "queued" or not job_id:
            print(
                json.dumps(
                    {
                        "status": "failed",
                        "host": args.host,
                        "uploaded": True,
                        "localPath": str(local_path),
                        "remotePath": remote_path,
                        "queueExitCode": queue_exit_code,
                        "queueResult": queue_payload,
                        "stderr": queue_stderr.strip() or None,
                        "message": "Queue request did not return a queued jobId.",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 1

        deadline = time.monotonic() + args.timeout_seconds
        polls: list[dict[str, object]] = []

        while True:
            if time.monotonic() > deadline:
                print(
                    json.dumps(
                        {
                            "status": "timeout",
                            "host": args.host,
                            "uploaded": True,
                            "localPath": str(local_path),
                            "remotePath": remote_path,
                            "queueResult": queue_payload,
                            "jobId": job_id,
                            "lastPoll": polls[-1] if polls else None,
                            "message": "Timed out waiting for import job to finish.",
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 1

            query_command = build_query_command(args, str(job_id))
            query_exit_code, query_stdout, query_stderr = run_remote_command(ssh, query_command)
            query_payload = extract_json(query_stdout)
            poll_snapshot = {
                "queryExitCode": query_exit_code,
                "result": query_payload,
            }
            if query_stderr.strip():
                poll_snapshot["stderr"] = query_stderr.strip()
            polls.append(poll_snapshot)

            if query_exit_code != 0 or not isinstance(query_payload, dict):
                print(
                    json.dumps(
                        {
                            "status": "failed",
                            "host": args.host,
                            "uploaded": True,
                            "localPath": str(local_path),
                            "remotePath": remote_path,
                            "queueResult": queue_payload,
                            "jobId": job_id,
                            "lastPoll": poll_snapshot,
                            "message": "Failed to query import job state.",
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 1

            status = query_payload.get("status")
            exit_code = query_payload.get("exitCode")
            if status == "completed" and exit_code == 0:
                print(
                    json.dumps(
                        {
                            "status": "completed",
                            "host": args.host,
                            "uploaded": True,
                            "localPath": str(local_path),
                            "remotePath": remote_path,
                            "queueResult": queue_payload,
                            "jobId": job_id,
                            "jobResult": query_payload,
                            "pollCount": len(polls),
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 0

            if status == "failed":
                print(
                    json.dumps(
                        {
                            "status": "failed",
                            "host": args.host,
                            "uploaded": True,
                            "localPath": str(local_path),
                            "remotePath": remote_path,
                            "queueResult": queue_payload,
                            "jobId": job_id,
                            "jobResult": query_payload,
                            "pollCount": len(polls),
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 1

            if status not in {"queued", "processing"}:
                print(
                    json.dumps(
                        {
                            "status": "failed",
                            "host": args.host,
                            "uploaded": True,
                            "localPath": str(local_path),
                            "remotePath": remote_path,
                            "queueResult": queue_payload,
                            "jobId": job_id,
                            "jobResult": query_payload,
                            "pollCount": len(polls),
                            "message": f"Unexpected job status: {status}",
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 1

            time.sleep(args.poll_seconds)
    except Exception as exc:
        print(json.dumps({"status": "failed", "message": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
