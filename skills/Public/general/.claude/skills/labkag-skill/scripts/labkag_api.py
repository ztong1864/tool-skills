from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests

DEFAULT_BASE_URL = os.environ.get("LABKAG_BASE_URL", "http://127.0.0.1:8001").rstrip("/")


def _request_json(method: str, url: str, *, json_payload=None, files=None, timeout=60):
    response = requests.request(
        method,
        url,
        json=json_payload,
        files=files,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def _load_json_file(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def cmd_health(args: argparse.Namespace) -> int:
    return _print_json_response("GET", f"{args.base_url}/health")


def cmd_upload(args: argparse.Namespace) -> int:
    with Path(args.file).open("rb") as file_handle:
        return _print_file_upload_response(
            f"{args.base_url}/v1/papers/upload",
            file_handle,
            Path(args.file).name,
            args.timeout,
        )


def cmd_extract(args: argparse.Namespace) -> int:
    payload = {
        "file_id": args.file_id,
        "project_id": args.project_id,
        "extract_level": args.extract_level,
        "return_chunks": args.return_chunks,
    }
    return _print_json_response("POST", f"{args.base_url}/v1/papers/extract", json_payload=payload)


def cmd_ingest(args: argparse.Namespace) -> int:
    payload = {
        "project_id": args.project_id,
        "paper_extraction": _load_json_file(args.paper_extraction),
        "confirm": args.confirm,
    }
    return _print_json_response("POST", f"{args.base_url}/v1/papers/ingest", json_payload=payload)


def cmd_query(args: argparse.Namespace) -> int:
    payload = {
        "question": args.question,
        "project_id": args.project_id,
        "paper_id": args.paper_id,
        "top_k": args.top_k,
    }
    return _print_json_response(
        "POST",
        f"{args.base_url}/v1/literature/query",
        json_payload=payload,
    )


def cmd_search(args: argparse.Namespace) -> int:
    payload = {
        "query": args.query,
        "project_id": args.project_id,
        "paper_id": args.paper_id,
        "top_k": args.top_k,
    }
    return _print_json_response(
        "POST",
        f"{args.base_url}/v1/evidence/search",
        json_payload=payload,
    )


def cmd_knowledge(args: argparse.Namespace) -> int:
    url = f"{args.base_url}/v1/papers/{args.paper_id}/knowledge"
    params = {"project_id": args.project_id, "include_evidence": args.include_evidence}
    return _print_json_response("GET", url, params=params, timeout=args.timeout)


def _print_json_response(
    method: str,
    url: str,
    *,
    json_payload=None,
    params=None,
    timeout: int = 60,
) -> int:
    try:
        response = requests.request(
            method,
            url,
            json=json_payload,
            params=params,
            timeout=timeout,
        )
        if response.status_code >= 400:
            _print_error(response)
            return 1
        print(json.dumps(response.json(), ensure_ascii=False, indent=2))
        return 0
    except requests.RequestException as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def _print_file_upload_response(url: str, file_handle, filename: str, timeout: int) -> int:
    try:
        response = requests.post(
            url,
            files={"file": (filename, file_handle, "application/pdf")},
            timeout=timeout,
        )
        if response.status_code >= 400:
            _print_error(response)
            return 1
        print(json.dumps(response.json(), ensure_ascii=False, indent=2))
        return 0
    except requests.RequestException as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def _print_error(response: requests.Response) -> None:
    try:
        body = response.json()
    except ValueError:
        print(response.text, file=sys.stderr)
        return
    print(json.dumps(body, ensure_ascii=False, indent=2), file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Call the LabKAG API.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout", type=int, default=60)

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("health").set_defaults(func=cmd_health)

    upload = subparsers.add_parser("upload")
    upload.add_argument("--file", required=True)
    upload.set_defaults(func=cmd_upload)

    extract = subparsers.add_parser("extract")
    extract.add_argument("--file-id", required=True)
    extract.add_argument("--project-id")
    extract.add_argument("--extract-level", default="basic", choices=["basic", "detailed"])
    extract.add_argument("--return-chunks", action="store_true")
    extract.set_defaults(func=cmd_extract)

    ingest = subparsers.add_parser("ingest")
    ingest.add_argument("--project-id")
    ingest.add_argument("--paper-extraction", required=True)
    ingest.add_argument("--confirm", action="store_true")
    ingest.set_defaults(func=cmd_ingest)

    query = subparsers.add_parser("query")
    query.add_argument("--question", required=True)
    query.add_argument("--project-id")
    query.add_argument("--paper-id")
    query.add_argument("--top-k", type=int, default=5)
    query.set_defaults(func=cmd_query)

    search = subparsers.add_parser("search")
    search.add_argument("--query", required=True)
    search.add_argument("--project-id")
    search.add_argument("--paper-id")
    search.add_argument("--top-k", type=int, default=10)
    search.set_defaults(func=cmd_search)

    knowledge = subparsers.add_parser("knowledge")
    knowledge.add_argument("--paper-id", required=True)
    knowledge.add_argument("--project-id")
    knowledge.add_argument(
        "--include-evidence",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    knowledge.set_defaults(func=cmd_knowledge)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.base_url = args.base_url.rstrip("/")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
