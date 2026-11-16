"""Fetch one completed-looking report through read-only SFTP over SSH."""
import argparse
from datetime import datetime, timezone
import fnmatch
import hashlib
import json
import math
import os
from pathlib import Path
import posixpath
import stat
import sys
import tempfile
import time


class ReportError(Exception):
    pass


def validate_config(config):
    if not isinstance(config, dict):
        raise ReportError("CONFIG: configuration must be a JSON object")
    for name in ("host", "username", "remote_dir"):
        value = config.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ReportError(f"CONFIG: fill in {name} before connecting")
        if any(c in value for c in "\x00\r\n"):
            raise ReportError(f"CONFIG: invalid control character in {name}")
    if not config["remote_dir"].startswith("/"):
        raise ReportError("CONFIG: remote_dir must be an absolute SFTP path beginning with /")
    port = config.get("port", 22)
    if type(port) is not int or not 1 <= port <= 65535:
        raise ReportError("CONFIG: port must be an integer from 1 to 65535")
    for field, default in (("timeout", 30), ("stable_seconds", 2)):
        value = config.get(field, default)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ReportError(f"CONFIG: {field} must be a positive finite number")
    patterns = config.get("patterns")
    if not isinstance(patterns, list) or not patterns or any(
        not isinstance(p, str) or not p or any(c in p for c in "/\\\x00\r\n") for p in patterns
    ):
        raise ReportError("CONFIG: patterns must be a nonempty list of filename globs")
    for field in ("key_filename", "known_hosts_file", "password_env", "password_file"):
        if config.get(field) is not None and (not isinstance(config[field], str) or not config[field].strip()):
            raise ReportError(f"CONFIG: {field} must be a nonempty string or null")
    if config.get("password_env") and config.get("password_file"):
        raise ReportError("CONFIG: choose either password_env or password_file")
    if "password" in config or "private_key" in config:
        raise ReportError("CONFIG: store credentials outside this JSON; use key_filename, password_env or password_file")


def utc(timestamp=None):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat() if timestamp is not None else datetime.now(timezone.utc).isoformat()


def fingerprint(info):
    return info.st_size, info.st_mtime, info.st_mode


def check_unchanged(sftp, path, before):
    current = sftp.lstat(path)
    if not stat.S_ISREG(current.st_mode) or fingerprint(current) != fingerprint(before):
        raise ReportError("REPORT_CHANGING: latest report is still changing; retry later")


def fetch_report(sftp, config, output_dir, sleep=time.sleep):
    validate_config(config)
    selected_at = utc()
    directory = config["remote_dir"].rstrip("/") or "/"
    candidates = [e for e in sftp.listdir_attr(directory)
                  if stat.S_ISREG(e.st_mode or 0)
                  and not e.filename.startswith(".")
                  and not any(c in e.filename for c in "/\\\x00\r\n")
                  and not e.filename.lower().endswith((".tmp", ".part", ".partial", ".lock", "~"))
                  and any(fnmatch.fnmatchcase(e.filename, p) for p in config["patterns"])]
    if not candidates:
        raise ReportError("NO_REPORT: no regular report files match the configured directory and patterns")
    newest_time = max(e.st_mtime for e in candidates)
    latest = [e for e in candidates if e.st_mtime == newest_time]
    if len(latest) != 1:
        raise ReportError("AMBIGUOUS_LATEST: equal modification times; narrow --pattern: "
                          + ", ".join(sorted(e.filename for e in latest)))
    selected = latest[0]
    if selected.st_size <= 0:
        raise ReportError("EMPTY_REPORT: latest matching report is empty; retry later")
    remote_path = posixpath.join(directory, selected.filename)
    check_unchanged(sftp, remote_path, selected)
    sleep(config.get("stable_seconds", 2))
    check_unchanged(sftp, remote_path, selected)

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    # A fresh directory prevents collisions and avoids trusting a remote filename as a local path.
    run_dir = Path(tempfile.mkdtemp(prefix="report_", dir=output_dir))
    extension = posixpath.splitext(selected.filename)[1].lower()
    if not extension or len(extension) > 12 or not extension[1:].isalnum():
        extension = ".bin"
    destination = run_dir / ("report" + extension)
    partial = run_dir / "download.part"
    manifest_path = run_dir / "fetch_result.json"
    digest = hashlib.sha256()
    downloaded = 0
    try:
        with sftp.open(remote_path, "rb") as source, partial.open("xb") as target:
            while True:
                block = source.read(1024 * 1024)
                if not block:
                    break
                target.write(block)
                digest.update(block)
                downloaded += len(block)
        check_unchanged(sftp, remote_path, selected)
        if downloaded != selected.st_size:
            raise ReportError("SIZE_MISMATCH: downloaded byte count differs from remote report size")
        partial.replace(destination)
        result = {
            "status": "downloaded", "host": config["host"], "port": config.get("port", 22),
            "remote_path": remote_path, "remote_filename": selected.filename,
            "remote_mtime_utc": utc(selected.st_mtime), "size_bytes": downloaded,
            "selected_at_utc": selected_at, "fetched_at_utc": utc(),
            "latest_basis": "maximum SFTP modification time among matching regular files at selection",
            "patterns": config["patterns"], "stable_seconds": config.get("stable_seconds", 2),
            "local_path": str(destination), "manifest_path": str(manifest_path),
            "sha256": digest.hexdigest(), "sha256_scope": "downloaded bytes; not a server-provided checksum",
            "verification": "remote size and mtime unchanged across stability window and transfer; byte count matches",
        }
        manifest_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return result
    except BaseException:
        # Only remove files created inside this fresh run directory.
        for path in (partial, destination, manifest_path):
            path.unlink(missing_ok=True)
        run_dir.rmdir()
        raise


def connect(config, *, config_dir=None):
    try:
        import paramiko
    except ImportError as exc:
        raise ReportError("DEPENDENCY: install scripts/requirements.txt in the current Python environment") from exc
    password_env = config.get("password_env")
    password = os.environ.get(password_env) if password_env else None
    if password_env and not password:
        raise ReportError(f"AUTH: environment variable {password_env} is unset or empty")
    password_file = config.get("password_file")
    if password_file:
        path = Path(password_file).expanduser()
        if not path.is_absolute():
            if config_dir is None:
                raise ReportError("AUTH: relative password file requires the configuration directory")
            path = Path(config_dir) / path
        try:
            password = path.read_text(encoding="utf-8-sig").rstrip("\r\n")
        except (OSError, UnicodeError) as exc:
            raise ReportError("AUTH: cannot read the configured password file") from exc
        if not password or "\n" in password or "\r" in password:
            raise ReportError("AUTH: the password file must contain one nonempty line")
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    known_hosts = Path(config.get("known_hosts_file") or "~/.ssh/known_hosts").expanduser()
    if known_hosts.is_file():
        client.load_host_keys(str(known_hosts))
    elif config.get("known_hosts_file"):
        raise ReportError("CONFIG: known_hosts_file does not exist")
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    key = config.get("key_filename")
    timeout = config.get("timeout", 30)
    try:
        client.connect(hostname=config["host"], port=config.get("port", 22), username=config["username"],
                       key_filename=str(Path(key).expanduser()) if key else None, password=password,
                       allow_agent=not password_file, look_for_keys=not password_file,
                       timeout=timeout, banner_timeout=timeout, auth_timeout=timeout, channel_timeout=timeout)
        return client
    except BaseException:
        client.close()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path, help="UTF-8 JSON connection and report settings")
    parser.add_argument("--output-dir", type=Path, help="local directory to receive a new report subdirectory")
    parser.add_argument("--pattern", action="append", help="filename glob; repeat for alternatives; overrides config patterns")
    parser.add_argument("--check-config", action="store_true", help="validate settings without making a network connection")
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding="utf-8-sig"))
        if args.pattern:
            if not isinstance(config, dict):
                raise ReportError("CONFIG: configuration must be a JSON object")
            config["patterns"] = args.pattern
        validate_config(config)
        if args.check_config:
            print(json.dumps({"status": "config_valid", "connected": False}))
            return 0
        if args.output_dir is None:
            raise ReportError("CONFIG: --output-dir is required when fetching a report")
        with connect(config, config_dir=args.config.resolve().parent) as client, client.open_sftp() as sftp:
            sftp.get_channel().settimeout(config.get("timeout", 30))
            result = fetch_report(sftp, config, args.output_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error_type": type(exc).__name__, "message": str(exc)},
                         ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
