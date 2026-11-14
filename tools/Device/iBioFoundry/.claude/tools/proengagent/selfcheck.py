#!/usr/bin/env python3
"""Load tool.py the way the backend does and exercise its handlers.

Run this with the backend's own venv after every edit and after deploying:
tool_backing_service._load_sdk_server() swallows a failed import silently, so a
broken file does not raise anywhere -- the tool just stops appearing, with no
clue why.

    python selfcheck.py              # structure + offline refusals only
    python selfcheck.py --live       # also call the service (needs PROENGAGENT_BASE_URL)

Exit status is 0 only when every check passed.
"""

import argparse
import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))
    if not condition:
        FAILURES.append(label)


def load_module(user_id: int | None = 1):
    """Exactly what _load_sdk_server does: spec_from_file_location + the user id."""
    spec = importlib.util.spec_from_file_location("_tool_backing_proengagent", HERE / "tool.py")
    module = importlib.util.module_from_spec(spec)
    module.FOUNDRYCLAW_USER_ID = user_id
    spec.loader.exec_module(module)
    return module


def text_of(answer: dict) -> str:
    return "".join(part.get("text", "") for part in answer.get("content", []))


def call(module, name: str, args: dict) -> dict:
    handler = {entry.name: entry.handler for entry in module.TOOLS}[name]
    answer = asyncio.run(handler(args))
    return {"error": bool(answer.get("is_error")), "text": text_of(answer)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Also call the service.")
    arguments = parser.parse_args()

    print("structure")
    module = load_module()
    server = module.SERVER
    tools = {entry.name: entry for entry in module.TOOLS}
    check("SERVER is an sdk server", isinstance(server, dict) and server.get("type") == "sdk")
    check("19 tools registered", len(tools) == 19, f"{len(tools)}: {', '.join(sorted(tools))}")
    check("catalog snapshot loaded", len(module._CATALOG) >= 100, f"{len(module._CATALOG)} tools")
    for required in ("ProtParam", "Pythia_Mut", "run_tool", "upload_file", "read_output", "list_tools"):
        check(f"{required} present", required in tools)
    oversized = [name for name, entry in tools.items() if len(entry.description) > 700]
    check("descriptions stay short", not oversized, ", ".join(oversized))

    print("\nguardrails (no service needed)")
    for blocked in ("multievolve_api", "esm_zeroshot"):
        answer = call(module, "run_tool", {"name": blocked, "inputs": {"sequence": "MKT"}})
        check(f"run_tool refuses {blocked}", answer["error"] and "esm-directed-evolution" in answer["text"])
    answer = call(module, "run_tool", {"name": "no_such_tool", "inputs": {}})
    check("run_tool rejects an unknown name", answer["error"] and "No tool named" in answer["text"])
    answer = call(module, "run_tool", {"name": "ProtParam", "inputs": "not a dict"})
    check("run_tool rejects non-object inputs", answer["error"] and "`inputs`" in answer["text"])
    answer = call(module, "list_tools", {"state": "not_deployed"})
    payload = json.loads(answer["text"])
    check("list_tools reports undeployed tools", payload.get("matched", 0) >= 5, f"{payload.get('matched')} found")

    saved = os.environ.pop("PROENGAGENT_BASE_URL", None)
    try:
        unset = load_module()
        unset._CONFIGURED_BASE_URL = ""
        answer = call(unset, "ProtParam", {"sequence": "MKTAYIAK"})
        check("missing address gives a readable error",
              answer["error"] and "PROENGAGENT_BASE_URL" in answer["text"] and "Traceback" not in answer["text"])
    finally:
        if saved is not None:
            os.environ["PROENGAGENT_BASE_URL"] = saved

    if not arguments.live:
        print("\n(skipping live calls; pass --live to include them)")
    else:
        print("\nlive calls")
        if not (module._CONFIGURED_BASE_URL or os.environ.get("PROENGAGENT_BASE_URL")):
            check("service address configured", False, "set PROENGAGENT_BASE_URL")
        else:
            sequence = "TTCCPSIVARSNFNVCRLPGTPEAICATYTGCIIIPGATCPGDYAN"
            answer = call(module, "sequence_length", {"sequence": sequence})
            check("sequence_length counts 46 residues", not answer["error"] and '"length": 46' in answer["text"])
            answer = call(module, "ProtParam", {"sequence": sequence})
            check("ProtParam returns properties", not answer["error"] and "Molecular weight" in answer["text"])
            answer = call(module, "get_pdb", {"pdb_id": "1CRN"})
            check("get_pdb fetches a structure", not answer["error"] and "1crn.pdb" in answer["text"])
            answer = call(module, "Pythia_Mut", {"pdb_file": "workspace/uploads/1crn.pdb", "mutation": "T1A"})
            check("Pythia_Mut scores a substitution", not answer["error"] and "ddg" in answer["text"])
            answer = call(module, "run_tool", {"name": "ddgun_predict",
                                               "inputs": {"wildtype_pdb": "workspace/uploads/1crn.pdb",
                                                          "mutation": "T1A"}})
            check("an undeployed tool is reported as such",
                  answer["error"] and "not deployed" in answer["text"].lower())
            answer = call(module, "run_tool", {"name": "freesasa_run",
                                               "inputs": {"pdb_file": "workspace/uploads/1crn.pdb"}})
            check("run_tool reaches a non-wrapped tool", not answer["error"] and "total_area" in answer["text"])

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed: {', '.join(FAILURES)}")
        sys.exit(1)
    print("all checks passed")


if __name__ == "__main__":
    main()
