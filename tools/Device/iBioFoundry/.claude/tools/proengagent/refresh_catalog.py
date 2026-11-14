#!/usr/bin/env python3
"""Refresh catalog.json from a live ProEngAgent service.

Run this after the service is upgraded (new tools, renamed inputs, something
newly deployed). It is deliberately a separate script, not something tool.py
does on import: tool.py is re-executed for every chat session, so fetching the
catalog there would add a network round trip per session and would make the
whole tool vanish whenever the service is unreachable.

    python refresh_catalog.py                      # catalog only
    python refresh_catalog.py --probe              # also re-check what is deployed
    python refresh_catalog.py --base-url http://host:7861

`--probe` matters because the service's catalog has no "is this actually
usable" field. An undeployed tool answers HTTP 200 with
{"success": true, "output": {"success": false, "deployed": false, "error": ...}},
so the only way to know is to call it. The probe calls every fast/medium
single-input tool once with a 46-residue test sequence (or a test PDB) and
records the verdict as `probe` on each catalog entry; slow tools, multi-input
tools and the ESM scoring tools are left as `unknown`.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CATALOG = Path(__file__).resolve().parent / "catalog.json"
PROBE_SEQUENCE = "TTCCPSIVARSNFNVCRLPGTPEAICATYTGCIIIPGATCPGDYAN"  # crambin (1CRN), 46 aa
PROBE_PDB_ID = "1CRN"
# Scoring tools that belong to the esm-directed-evolution skill's workflow; never probed
# or wrapped here (see tool.py's ESM_WORKFLOW_TOOLS).
ESM_WORKFLOW_TOOLS = {"multievolve_api", "multi_evolve_api", "esm_zeroshot"}
KEEP_FIELDS = (
    "name", "description", "inputs", "outputs", "requirements",
    "speed", "accuracy", "reliability", "implements", "has_wrapper",
)


def base_url(argument: str | None) -> str:
    url = (argument or os.environ.get("PROENGAGENT_BASE_URL") or "").strip().rstrip("/")
    if not url:
        sys.exit("No service address: pass --base-url or set PROENGAGENT_BASE_URL.")
    return url


def fetch_catalog(base: str, timeout: float) -> list[dict]:
    with urllib.request.urlopen(f"{base}/api/general/tools", timeout=timeout) as response:
        data = json.load(response)
    tools = data if isinstance(data, list) else data.get("tools", data)
    if isinstance(tools, dict):
        tools = list(tools.values())
    if not isinstance(tools, list) or not tools:
        sys.exit(f"{base}/api/general/tools did not return a tool list.")
    return tools


def call(base: str, name: str, inputs: dict, timeout: float) -> dict:
    body = json.dumps({"inputs": inputs}).encode()
    request = urllib.request.Request(
        f"{base}/api/general/tool/{name}", data=body, headers={"Content-Type": "application/json"}
    )
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            answer = json.load(response)
    except urllib.error.HTTPError as exc:
        return {"_state": "http_error", "_detail": f"HTTP {exc.code}", "_s": round(time.time() - started, 1)}
    except Exception as exc:  # noqa: BLE001 - a probe never raises
        return {"_state": "unreachable", "_detail": f"{type(exc).__name__}", "_s": round(time.time() - started, 1)}
    answer["_s"] = round(time.time() - started, 1)
    return answer


def verdict(answer: dict) -> tuple[str, str]:
    """Collapse one tool answer into (state, detail). See tool.py's _verdict() for the
    same logic applied at call time -- the envelope's own `success` is true even for a
    tool that reports failure inside `output`, so both layers have to be read."""
    if answer.get("_state"):
        return answer["_state"], answer.get("_detail", "")
    if answer.get("success") is False:
        return "error", str(answer.get("error"))[:300]
    output = answer.get("output")
    if isinstance(output, dict):
        if output.get("deployed") is False:
            return "not_deployed", str(output.get("error"))[:300]
        if output.get("success") is False:
            return "failed", str(output.get("error"))[:300]
    if output is None:
        return "empty", "the service answered success with no output"
    return "ok", ""


def probe(base: str, tools: list[dict], timeout: float) -> dict[str, dict]:
    """One call per fast/medium single-input tool. Nothing here mutates the service
    beyond the files its own tools write into their workspace."""
    pdb_path = None
    answer = call(base, "get_pdb", {"pdb_id": PROBE_PDB_ID}, timeout)
    if verdict(answer)[0] == "ok":
        pdb_path = f"workspace/uploads/{PROBE_PDB_ID.lower()}.pdb"
    else:
        print(f"  (get_pdb failed, skipping pdb_file tools: {verdict(answer)[1][:120]})")

    results: dict[str, dict] = {}
    checked = datetime.now(timezone.utc).date().isoformat()
    for entry in tools:
        name = entry["name"]
        keys = tuple(sorted((entry.get("inputs") or {}).keys()))
        if name in ESM_WORKFLOW_TOOLS or entry.get("speed") in ("slow", "very_slow"):
            continue
        if keys == ("sequence",):
            inputs = {"sequence": PROBE_SEQUENCE}
        elif keys == ("pdb_file",) and pdb_path:
            inputs = {"pdb_file": pdb_path}
        else:
            continue
        answer = call(base, name, inputs, timeout)
        state, detail = verdict(answer)
        results[name] = {"state": state, "checked": checked}
        if detail:
            results[name]["detail"] = detail
        print(f"  {state:14s} {answer.get('_s'):>6}s  {name}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", help="Service address (default: PROENGAGENT_BASE_URL).")
    parser.add_argument("--probe", action="store_true", help="Also re-check which tools are deployed.")
    parser.add_argument("--timeout", type=float, default=90.0, help="Per-request timeout in seconds.")
    arguments = parser.parse_args()

    base = base_url(arguments.base_url)
    print(f"Fetching {base}/api/general/tools ...")
    tools = fetch_catalog(base, arguments.timeout)
    print(f"  {len(tools)} tools")

    previous: dict[str, dict] = {}
    if CATALOG.exists():
        try:
            for entry in json.loads(CATALOG.read_text(encoding="utf-8")).get("tools", []):
                if entry.get("probe"):
                    previous[entry["name"]] = entry["probe"]
        except (OSError, ValueError):
            pass

    probed = probe(base, tools, arguments.timeout) if arguments.probe else {}
    if arguments.probe:
        counts: dict[str, int] = {}
        for value in probed.values():
            counts[value["state"]] = counts.get(value["state"], 0) + 1
        print("  probe summary:", counts)

    entries = []
    for tool in sorted(tools, key=lambda item: item["name"].lower()):
        entry = {field: tool[field] for field in KEEP_FIELDS if field in tool}
        state = probed.get(tool["name"]) or previous.get(tool["name"])
        if state:
            entry["probe"] = state
        entries.append(entry)

    payload = {
        "version": 1,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": f"{base}/api/general/tools",
        "n_tools": len(entries),
        "note": "Snapshot read by tool.py. `probe` is this repo's own call-it-and-see verdict, "
                "not a field the service publishes; absent means never probed.",
        "tools": entries,
    }
    CATALOG.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote {CATALOG} ({CATALOG.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
