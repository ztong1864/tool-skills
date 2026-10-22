#!/usr/bin/env python3
"""Amino-acid probabilities at masked positions of a protein, from the ESM service.

The ESM-2 model is held by the ESM service, a separate process that keeps the checkpoint in memory
(like TRACE Lab: base address in ESM_SERVICE_BASE_URL, by default http://127.0.0.1:8789). This script
prepares the request, posts it and prints the answer, so it needs nothing but the standard library and
no model file of its own. Nothing is sent to an online service and no key is needed.

The printed JSON is the same as before, with one field added by the service: elapsed_s.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "http://127.0.0.1:8789"
GENBANK_SUFFIXES = {".gb", ".gbk", ".genbank", ".gbff"}
MAX_RECORD_BYTES = 2 * 1024 * 1024  # the service refuses a larger record
MAX_TOP = 20  # there are 20 standard amino acids


def fail(message: str) -> None:
    raise SystemExit(f"esm_mask_probabilities: {message}")


# --- input -------------------------------------------------------------------------------------------------

def service_url(args: argparse.Namespace) -> str:
    """--base-url, else the address the backend passes to the chat, else the local default."""
    return (args.base_url or os.environ.get("ESM_SERVICE_BASE_URL") or DEFAULT_BASE_URL).strip().rstrip("/")


def read_record_file(path_text: str) -> str:
    """The text of a FASTA or GenBank file. The service parses it; this side only reads it."""
    path = Path(path_text)
    if not path.is_file():
        fail(f"no such file: {path}")
    if path.stat().st_size > MAX_RECORD_BYTES:
        fail(f"{path.name} is larger than 2 MB; pass a file with the records of interest only")
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gb18030"):  # Notepad and Excel on a Chinese Windows save GBK
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    fail(f"{path.name} is neither UTF-8 nor GB18030 text")


def parse_positions(raw: str) -> list[int]:
    try:
        return [int(item) for item in raw.replace(";", ",").split(",") if item.strip()]
    except ValueError:
        fail(f"--positions must be 1-based residue numbers such as 45,120, got {raw!r}")


def request_body(args: argparse.Namespace) -> dict[str, Any]:
    """The request for /api/mask-probabilities. Every rule about the sequence itself is the service's."""
    body: dict[str, Any] = {}
    if args.fasta:
        if args.sequence:
            fail("give --sequence or --fasta, not both")
        body["record_text"] = read_record_file(args.fasta)
        suffix = Path(args.fasta).suffix.lower()
        body["record_format"] = "genbank" if suffix in GENBANK_SUFFIXES else "fasta"
        if args.record:
            body["record"] = args.record
    elif args.sequence:
        body["sequence"] = args.sequence.strip()
    else:
        fail("give --sequence (with <mask>, or a wild type with --positions) or --fasta")
    if args.positions:
        body["positions"] = parse_positions(args.positions)
    if args.model:
        body["model"] = args.model
    for name in ("translate", "independent", "standard_only", "renormalize_selected"):
        if getattr(args, name):
            body[name] = True
    if args.tokens:
        body["tokens"] = args.tokens
    body["top"] = args.top
    return body


# --- the service -------------------------------------------------------------------------------------------

def describe_error(exc: urllib.error.HTTPError) -> str:
    """The service's own sentence for a refused request, so the reason reaches the user unchanged."""
    try:
        payload = json.loads(exc.read().decode("utf-8"))
    except (ValueError, OSError):
        return f"the ESM service answered HTTP {exc.code}"
    if isinstance(payload, dict) and isinstance(payload.get("error"), str):
        return payload["error"]
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(detail, list) and detail:  # the API's own body validation
        first = detail[0] if isinstance(detail[0], dict) else {}
        where = ".".join(str(part) for part in first.get("loc", []) if part != "body")
        message = str(first.get("msg", "invalid value"))
        return f"{where}: {message}" if where else message
    if isinstance(detail, str):
        return detail
    return f"the ESM service answered HTTP {exc.code}: {json.dumps(payload, ensure_ascii=False)[:500]}"


def call(url: str, path: str, body: dict[str, Any] | None, timeout: float) -> Any:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        f"{url}{path}",
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST" if data else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        fail(describe_error(exc))
    except urllib.error.URLError as exc:
        fail(f"cannot reach the ESM service at {url}: {exc.reason}. It runs as a separate service on the "
             "server (start_esm_service.cmd); an administrator can start or check it")
    except TimeoutError:
        fail(f"the ESM service at {url} did not answer within {timeout:.0f} s. A large model on a busy CPU "
             "can take longer: raise --timeout, or ask an administrator to check the service")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Amino-acid probabilities at masked protein positions from "
                                                 "the ESM service (no online service, no key).")
    parser.add_argument("--sequence", help="Protein sequence with one or more <mask>, or a wild type with --positions.")
    parser.add_argument("--fasta", help="FASTA or GenBank file (.gb/.gbk) holding the sequence instead of --sequence.")
    parser.add_argument("--record", help="Record id in --fasta (default: the first record).")
    parser.add_argument("--translate", action="store_true", help="The input is DNA/RNA coding sequence: translate it first.")
    parser.add_argument("--positions", help="1-based residues of the wild type to mask, e.g. 45,120.")
    parser.add_argument("--model", help="Installed ESM-2 model such as esm2-150m (default: the service's, esm2-35m).")
    parser.add_argument("--independent", action="store_true",
                        help="With --positions: predict each position with only that one masked (the others keep "
                             "the wild type). Default: all positions masked together in one pass.")
    parser.add_argument("--tokens", help="Comma-separated output tokens (default: 20 amino acids plus ESM's special tokens).")
    parser.add_argument("--standard-only", action="store_true", help="Output only the 20 standard amino acids.")
    parser.add_argument("--renormalize-selected", action="store_true", help="Renormalize over the output tokens so they sum to 1.")
    parser.add_argument("--top", type=int, default=5,
                        help=f"How many best standard amino acids to list per position, 0-{MAX_TOP} (default: 5).")
    parser.add_argument("--output-json", help="Also write the JSON to this file.")
    parser.add_argument("--base-url", help=f"The ESM service to call (default: ESM_SERVICE_BASE_URL, else {DEFAULT_BASE_URL}).")
    parser.add_argument("--timeout", type=float, default=300.0, help="Seconds to wait for the service (default: 300).")
    parser.add_argument("--health", action="store_true", help="Print the service's health instead: is it up, which model is loaded.")
    parser.add_argument("--list-models", action="store_true", help="Print which models the service knows and which are installed.")
    # Flags of the version that loaded the model in this environment. Kept so an old command explains what
    # changed instead of failing with argparse's "unrecognized arguments".
    parser.add_argument("--models-dir", help=argparse.SUPPRESS)
    parser.add_argument("--mock", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.models_dir:
        fail("--models-dir is gone: the model files belong to the ESM service now. --list-models says what it "
             "has, --base-url points at another service")
    if args.mock:
        fail("--mock is gone: made-up numbers are a mode of the service itself (ESM_SERVICE_MOCK), which only "
             "an administrator can turn on. --health says whether the service is in that mode")
    url = service_url(args)
    if args.health or args.list_models:
        path = "/api/health" if args.health else "/api/models"
        print(json.dumps(call(url, path, None, args.timeout), indent=2, ensure_ascii=False))
        return 0
    if not 0 <= args.top <= MAX_TOP:
        fail(f"--top must be between 0 and {MAX_TOP}: there are only {MAX_TOP} standard amino acids")
    answer = call(url, "/api/mask-probabilities", request_body(args), args.timeout)
    text = json.dumps(answer, indent=2, ensure_ascii=False)
    if args.output_json:
        Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_json).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
