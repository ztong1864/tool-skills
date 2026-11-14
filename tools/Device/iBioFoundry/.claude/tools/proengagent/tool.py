"""In-process (SDK) tool: ProEngAgent protein-engineering service.

Converts the `proengagent-api` skill (skills/Device/iBioFoundry/.claude/skills/proengagent-api,
a 25 KB SKILL.md that existed only on the server) into a sdk_python tool -- see
tool_backing_service.py's module docstring for the backing schema, and trace_collab.py
for the same move done for TRACE Lab. The skill's whole content was "here are the tools,
here is how to POST", which is what a tool is for: the model now gets named tools with
parameter schemas instead of prose it has to read and then hand-write HTTP calls from.

The service is a plain FastAPI REST app (`POST /api/general/tool/{name}` with
`{"inputs": {...}}`), not an MCP server, which is why this is sdk_python and not an
mcp_http backing. Its address comes from PROENGAGENT_BASE_URL (api/.env), read at call
time rather than import time so a missing setting gives a readable error instead of
silently dropping the whole tool.

Two tiers, 19 tools:

* 14 typed wrappers for the tools this device actually uses, with the real input field
  names (the catalog sometimes advertises internal ones -- `inputs` for parse_pdf_document
  says `pdf_file`, mapped internally to `pdf_path`), each verified by calling it.
* 5 utilities -- list_tools / describe_tool / run_tool / upload_file / read_output --
  that reach the other ~95 catalog tools without hardcoding them.

Three things the service does that every handler here has to cope with:

1. `success` in the envelope is about the HTTP call, not the work. An undeployed tool
   answers HTTP 200 with {"success": true, "output": {"success": false, "deployed":
   false, "error": "..."}} -- ddgun_predict and imutant2_predict do exactly this. Both
   layers are read (_verdict), and a tool that reports its own failure is surfaced as an
   error, never as a result.
2. `output` is sometimes a JSON object and sometimes prose ("Successfully fetched ...,
   saved in workspace/uploads/1crn.pdb"). Both are passed through as they come.
3. File arguments are paths on the service's own machine, not local ones: get_pdb,
   esm_fold and upload_file produce such paths, and the structure tools consume them.
   Results come back as `downloads` entries that read_output fetches.

`catalog.json` is a snapshot refreshed by refresh_catalog.py, not fetched here: this file
is re-executed for every chat session, so a fetch would cost a round trip per session and
would make the tool disappear whenever the service is down. Its `probe` field is this
repo's own call-it-and-see verdict -- the service publishes no such status, and the old
skill's hand-written "Stub" list was wrong in both directions (proteinmpnn_api works;
protein_sol_predict, stride_assign, seqvec_embed and five others do not).

Note for deployment: tool_backing_service re-executes this file for every new chat session
and silently drops the whole tool if the import fails -- import it once with the app's venv
after any edit.
"""

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from claude_agent_sdk import create_sdk_mcp_server, tool

try:  # the backend's own setting; absent when this file is imported outside the app (self-checks)
    from app.core.config import PROENGAGENT_BASE_URL as _CONFIGURED_BASE_URL
except Exception:  # noqa: BLE001
    _CONFIGURED_BASE_URL = ""

# Set by tool_backing_service before this file runs (one module instance per chat session):
# whose chat this is. Needed to put downloaded results into that user's own workspace.
FOUNDRYCLAW_USER_ID = globals().get("FOUNDRYCLAW_USER_ID")

_HERE = Path(__file__).resolve().parent
_CATALOG_PATH = _HERE / "catalog.json"
_FULL_LIMIT = 12000  # chars of JSON kept inline before the compact view takes over
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
_SPEED_TIMEOUTS = {"fast": 90.0, "medium": 300.0, "slow": 600.0, "very_slow": 900.0}
_MAX_TIMEOUT = 900.0

# Scoring tools owned by the esm-directed-evolution skill. Refused here on purpose: that
# skill's workflow (round structure, the pauses where the user picks candidates, the reply
# format, the derived probabilities) is the point of it, and a bare tool call is a way
# around all of it. This is the one hard refusal in this file -- everything else the
# service exposes can be called, and a tool that is broken or undeployed says so itself.
ESM_WORKFLOW_TOOLS = {"multievolve_api", "multi_evolve_api", "esm_zeroshot"}
_ESM_REFUSAL = (
    "{name} is the scoring engine of the esm-directed-evolution skill, so it is not called directly from "
    "here: use that skill, which runs the same ESM-2 scan and then follows its own workflow (positions, "
    "candidate shortlist, the pauses where the user decides, the required reply format). For a stability "
    "check on named substitutions use Pythia_Mut instead."
)


def _load_catalog() -> tuple[dict[str, dict], dict[str, Any]]:
    try:
        payload = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, {}
    tools = payload.get("tools") or []
    meta = {key: payload.get(key) for key in ("fetched_at", "source", "n_tools")}
    return {entry["name"]: entry for entry in tools if entry.get("name")}, meta


_CATALOG, _CATALOG_META = _load_catalog()


# --- Service calls ---------------------------------------------------------------------------------
def _base_url() -> str:
    url = (_CONFIGURED_BASE_URL or os.environ.get("PROENGAGENT_BASE_URL") or "").strip().rstrip("/")
    if not url:
        raise ValueError(
            "The ProEngAgent address is not configured: set PROENGAGENT_BASE_URL in api/.env and restart the "
            "backend. Nothing in this tool has a default address."
        )
    return url


def _timeout_for(name: str, given: Any = None) -> float:
    if isinstance(given, (int, float)) and given > 0:
        return min(float(given), _MAX_TIMEOUT)
    speed = (_CATALOG.get(name) or {}).get("speed")
    return _SPEED_TIMEOUTS.get(speed, 180.0)


_PROBE_TIMEOUT = 5.0


async def _tcp_reachable(base: str) -> bool:
    """Can this host open a TCP connection to the service at all? Used only to word a
    timeout correctly, so any failure means 'no'."""
    import asyncio
    from urllib.parse import urlsplit

    parts = urlsplit(base)
    host, port = parts.hostname, parts.port or (443 if parts.scheme == "https" else 80)
    if not host:
        return False
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=_PROBE_TIMEOUT)
    except (OSError, asyncio.TimeoutError):
        return False
    writer.close()
    try:
        await writer.wait_closed()
    except OSError:
        pass
    return True


async def _call(name: str, inputs: dict[str, Any], timeout: float) -> dict[str, Any]:
    """POST one tool call. `{"inputs": {...}}` is the service's ToolExecuteRequest."""
    import httpx  # lazy, per the convention in tool_backing_service.py's docstring

    base = _base_url()
    try:
        async with httpx.AsyncClient(base_url=base, timeout=timeout) as client:
            response = await client.post(f"/api/general/tool/{name}", json={"inputs": inputs})
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"HTTP {exc.response.status_code} calling {name}: {_describe_error(exc.response)}") from exc
    except httpx.TimeoutException as exc:
        # A missing route to the service's network times out exactly like a slow tool, and
        # the exception type does not separate them (an unroutable address can surface as
        # ReadTimeout). One TCP probe tells the two apart, which matters because the
        # backend host reaches this service over a VPN tunnel: a disconnected client leaves
        # the interface up with no route, and then nothing works, however long the timeout.
        if not await _tcp_reachable(base):
            raise RuntimeError(
                f"The ProEngAgent service at {base} is not reachable from this host: no TCP connection within "
                f"{_PROBE_TIMEOUT:.0f}s. This is a network problem rather than a slow tool -- on the backend "
                f"host that address is routed over a VPN tunnel, so check that the tunnel is up and has a "
                f"route to it."
            ) from exc
        raise RuntimeError(
            f"{name} did not answer within {timeout:.0f}s, though the service itself is reachable. It may still "
            f"be running there; a slower tool can be given more time with run_tool's `timeout`."
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Cannot reach the ProEngAgent service at {base}: {exc}") from exc
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(f"{name} answered with something that is not JSON: {response.text[:300]}") from exc


def _describe_error(response: Any) -> str:
    """Readable text for an API error: FastAPI validation errors arrive as a list of
    {loc, msg} under `detail`, which names the field that is wrong."""
    try:
        detail = response.json().get("detail", response.text)
    except (ValueError, AttributeError):
        return response.text[:400]
    if isinstance(detail, list):
        parts = []
        for item in detail:
            if isinstance(item, dict):
                where = ".".join(str(piece) for piece in item.get("loc", [])[1:]) or "input"
                parts.append(f"{where}: {item.get('msg', '')}")
        return "; ".join(parts) or json.dumps(detail, ensure_ascii=False)[:400]
    if isinstance(detail, dict):
        return json.dumps(detail, ensure_ascii=False)[:400]
    return str(detail)[:400]


def _verdict(answer: dict[str, Any]) -> tuple[str, str]:
    """(state, detail) for one tool answer. Mirrors refresh_catalog.py's _verdict: the
    envelope's `success` is true even when the tool itself reports failure inside `output`."""
    if answer.get("success") is False:
        return "error", str(answer.get("error") or "the service reported failure with no reason")
    output = answer.get("output")
    if isinstance(output, dict):
        if output.get("deployed") is False:
            return "not_deployed", str(output.get("error") or "the tool is not deployed on the service")
        if output.get("success") is False:
            return "failed", str(output.get("error") or "the tool reported failure with no reason")
    if output is None:
        return "empty", "the service answered success but returned no output"
    return "ok", ""


def _downloads(answer: dict[str, Any]) -> list[dict[str, str]]:
    items = answer.get("downloads")
    if not isinstance(items, list):
        return []
    kept = []
    for item in items:
        if isinstance(item, dict) and item.get("url"):
            kept.append({"name": item.get("name") or "", "url": item["url"], "key": item.get("key") or ""})
    return kept


async def _run_tool(name: str, inputs: dict[str, Any], full: bool = False, timeout: Any = None) -> dict[str, Any]:
    """One tool call, with the service's own failure reports turned into errors."""
    answer = await _call(name, inputs, _timeout_for(name, timeout))
    state, detail = _verdict(answer)
    if state == "not_deployed":
        raise RuntimeError(f"{name} is not deployed on this ProEngAgent service: {detail}")
    if state != "ok":
        raise RuntimeError(f"{name} did not produce a result ({state}): {detail}")

    result: dict[str, Any] = {"tool": name, "output": answer.get("output")}
    downloads = _downloads(answer)
    if downloads:
        result["downloads"] = downloads
        result["downloads_note"] = "Fetch any of these with read_output, passing the url's `path` value."
    entry = _CATALOG.get(name) or {}
    if entry.get("reliability") in ("beta", "experimental"):
        result["reliability"] = (
            f"The catalog marks {name} as {entry['reliability']}. Say so when reporting this result."
        )
    if full:
        return result
    return _full_or_compact(result, lambda data: _shrink(data), f"{name} result",
                            "Call again with full=true for everything, or read_output for a result file.")


# --- Size control (same approach as trace_collab.py) -----------------------------------------------
def _json_size(data: Any) -> int:
    return len(json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str))


def _cut(value: Any, limit: int) -> Any:
    if isinstance(value, str) and len(value) > limit:
        return value[:limit].rstrip() + "..."
    return value


def _shrink(value: Any, text_limit: int = 800, list_limit: int = 20, depth: int = 0) -> Any:
    if isinstance(value, str):
        return _cut(value, text_limit)
    if isinstance(value, list):
        kept = [_shrink(item, text_limit, list_limit, depth + 1) for item in value[:list_limit]]
        if len(value) > list_limit:
            kept.append(f"... {len(value) - list_limit} more (use full=true)")
        return kept
    if isinstance(value, dict):
        return {key: _shrink(item, text_limit, list_limit, depth + 1) for key, item in value.items()}
    return value


def _full_or_compact(data: Any, compact, what: str, hint: str) -> Any:
    size = _json_size(data)
    if size <= _FULL_LIMIT:
        return data
    view = compact(data)
    note = f"The full {what} is {size // 1024} KB, more than a chat tool result should hold, so this is cut down. {hint}"
    return {**view, "note": note} if isinstance(view, dict) else {"data": view, "note": note}


def _ok(data: Any) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, default=str)}]}


def _err(message: str) -> dict:
    return {"content": [{"type": "text", "text": message}], "is_error": True}


async def _guarded(coroutine_factory) -> dict:
    try:
        return _ok(await coroutine_factory())
    except (RuntimeError, ValueError, OSError) as exc:
        return _err(str(exc))


# --- The chat user's own folders --------------------------------------------------------------------
def _workspace_roots() -> tuple[Path, list[Path]]:
    """(the user's workspace, the folders a local path may come from). Same pair of
    storage_paths helpers trace_collab.py uses for uploaded files."""
    if not FOUNDRYCLAW_USER_ID:
        raise ValueError(
            "upload_file and saving results need the chat user's own folders, which are only known inside a "
            "FounDryClaw chat."
        )
    from app.services.storage_paths import agent_workdir_for_user, files_dir_for_user

    workspace = agent_workdir_for_user(FOUNDRYCLAW_USER_ID).resolve()
    return workspace, [workspace, files_dir_for_user(FOUNDRYCLAW_USER_ID).resolve()]


def _local_file(path_value: Any) -> Path:
    """An absolute path inside the chat user's own uploads or workspace."""
    _, roots = _workspace_roots()
    text = str(path_value or "").strip()
    path = Path(text).expanduser()
    if not text or not path.is_absolute():
        raise ValueError(f"Give the absolute path of the uploaded file (from the upload note), not `{path_value}`.")
    path = path.resolve()
    if not any(path == root or root in path.parents for root in roots):
        raise ValueError(f"{path} is outside this chat's own uploads and workspace.")
    if not path.is_file():
        raise ValueError(f"{path} is not a file.")
    if path.stat().st_size > _MAX_UPLOAD_BYTES:
        raise ValueError(f"{path.name} is larger than 20 MB, more than this service accepts.")
    return path


def _session_id() -> str:
    """The service groups uploads into a folder per session_id; one stable id per chat user
    keeps a user's uploads together instead of scattering them per call."""
    from_user = str(FOUNDRYCLAW_USER_ID or "anon")
    return f"foundryclaw-{re.sub(r'[^A-Za-z0-9_-]', '', from_user) or 'anon'}"


# --- Typed wrappers --------------------------------------------------------------------------------
def _schema(properties: dict[str, dict], required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


_STRING = {"type": "string"}


def _field(description: str, kind: str = "string") -> dict:
    return {"type": kind, "description": description}


_SEQUENCE_FIELD = _field("Amino-acid sequence, or FASTA text (the header is ignored).")
_PDB_PATH_FIELD = _field(
    "Path of a PDB file on the ProEngAgent service -- from get_pdb (workspace/uploads/<id>.pdb), "
    "esm_fold, or upload_file. Not a path on this machine."
)

# (remote name, description, schema). The description is what reaches the model at call
# time, so what the catalog only hints at is spelled out here; every entry was verified by
# calling the tool. protein_mw is deliberately absent: it answers success with no output
# (its upstream Novopro API gives nothing back), and ProtParam already reports molecular weight.
_WRAPPERS: list[tuple[str, str, dict]] = [
    (
        "sequence_length",
        "Count the residues of a protein sequence (accepts raw sequence or FASTA), and flag any "
        "non-standard characters. Use for a plain length question; ProtParam already includes the length.",
        _schema({"sequence": _SEQUENCE_FIELD}, ["sequence"]),
    ),
    (
        "ProtParam",
        "Basic physico-chemical properties of a protein sequence through Biopython ProtParam: length, "
        "molecular weight, theoretical pI, extinction coefficient, instability index, aliphatic index, GRAVY. "
        "The default choice for 'what are this protein's properties' and for molecular weight.",
        _schema({"sequence": _SEQUENCE_FIELD}, ["sequence"]),
    ),
    (
        "biopython_sequence_features",
        "Numeric sequence features as JSON: molecular_weight, aromaticity, instability_index, "
        "isoelectric_point, gravy, secondary_structure_fraction (helix/turn/sheet). Same ground as ProtParam "
        "but machine-readable rather than a formatted report -- use it when the numbers feed a calculation.",
        _schema({"sequence": _SEQUENCE_FIELD}, ["sequence"]),
    ),
    (
        "AAComposition",
        "Amino-acid composition of a sequence: count and percentage per residue type.",
        _schema({"sequence": _SEQUENCE_FIELD}, ["sequence"]),
    ),
    (
        "AAFormula",
        "Molecular formula of a protein sequence (C/H/N/O/S counts and the assembled formula).",
        _schema({"sequence": _SEQUENCE_FIELD}, ["sequence"]),
    ),
    (
        "uniprot_to_sequence",
        "Fetch a protein sequence from UniProt by accession (e.g. P00698). Returns the sequence and its length.",
        _schema({"uniprot_id": _field("UniProt accession, e.g. P00698.")}, ["uniprot_id"]),
    ),
    (
        "pdb_to_sequence",
        "Fetch the sequence(s) of a PDB entry from RCSB by ID. Returns every chain by default; pass `chain` "
        "for one. Sequence only -- use get_pdb when a structure file is needed.",
        _schema(
            {"pdb_id": _field("PDB ID, e.g. 1CRN."), "chain": _field("One chain ID, e.g. A. Omit for all chains.")},
            ["pdb_id"],
        ),
    ),
    (
        "get_pdb",
        "Download a PDB entry from RCSB onto the ProEngAgent service and report where it was saved "
        "(workspace/uploads/<id>.pdb). That path is what the structure tools below take.",
        _schema({"pdb_id": _field("PDB ID, e.g. 1CRN.")}, ["pdb_id"]),
    ),
    (
        "esm_fold",
        "Predict a structure from sequence through the ESM Atlas API and save it on the service; the result "
        "comes back as a download entry plus a service-side path for the structure tools. Single chains, "
        "medium accuracy -- not a replacement for an experimental structure.",
        _schema({"sequence": _SEQUENCE_FIELD}, ["sequence"]),
    ),
    (
        "biopython_pdb_info",
        "Summarise a structure file: chain IDs, residue count, atom count. The quickest check that an "
        "uploaded or predicted PDB is what it should be.",
        _schema({"pdb_file": _PDB_PATH_FIELD}, ["pdb_file"]),
    ),
    (
        "dssp_assign",
        "Assign secondary structure for a PDB file (pydssp, 3-state H/E/C): per-residue string plus helix, "
        "strand and coil fractions.",
        _schema({"pdb_file": _PDB_PATH_FIELD}, ["pdb_file"]),
    ),
    (
        "Pythia_Mut",
        "Pythia stability scan of a structure. Scores every single substitution at every residue "
        "(sum over pythia-c and pythia-p of -log(P_mut/P_wt): lower, more negative = predicted more "
        "stabilising than wild type) and returns the named mutation's own ddg, the most stabilising ones, "
        "and a result file with all of them. Use it to check whether candidates from the "
        "esm-directed-evolution skill look destabilising before they go to the bench.",
        _schema(
            {
                "pdb_file": _PDB_PATH_FIELD,
                "mutation": _field("The substitution to report, in wild-type/position/mutant form, e.g. T1A. "
                                   "The scan covers every substitution regardless of this value."),
            },
            ["pdb_file", "mutation"],
        ),
    ),
    (
        "Pythia_Seq",
        "One Pythia stability score for a whole structure (mean over both models of -mean(log P(native "
        "residue)) across positions: lower = the native sequence is more likely = predicted more stable). "
        "Use it to compare a designed or predicted variant structure against the wild type, where "
        "Pythia_Mut answers per substitution.",
        _schema({"pdb_file": _PDB_PATH_FIELD}, ["pdb_file"]),
    ),
    (
        "parse_pdf_document",
        "Extract the text of a PDF held on the ProEngAgent service (pypdf): page count and text, capped by "
        "the service. Upload the file with upload_file first -- that already returns the text of a PDF, so "
        "this is for a PDF the service produced or that was uploaded earlier.",
        _schema({"pdf_file": _field("Path of a PDF on the ProEngAgent service, e.g. from upload_file.")},
                ["pdf_file"]),
    ),
]


def _make_wrapper(remote_name: str, description: str, schema: dict):
    full_schema = dict(schema)
    properties = dict(full_schema.get("properties") or {})
    properties["full"] = {"type": "boolean", "description": "Return the whole result instead of a shortened view."}
    full_schema["properties"] = properties

    async def handler(args: dict) -> dict:
        async def work():
            inputs = {key: args[key] for key in (schema.get("properties") or {}) if args.get(key) not in (None, "")}
            missing = [key for key in schema.get("required", []) if key not in inputs]
            if missing:
                raise ValueError(f"{remote_name} needs {', '.join(missing)}.")
            return await _run_tool(remote_name, inputs, full=bool(args.get("full")))

        return await _guarded(work)

    handler.__name__ = f"wrapper_{remote_name}"
    return tool(remote_name, description, full_schema)(handler)


_TYPED_TOOLS = [_make_wrapper(name, description, schema) for name, description, schema in _WRAPPERS]


# --- Utilities -------------------------------------------------------------------------------------
_LIST_LIMIT = 40


@tool(
    "list_tools",
    "List what this ProEngAgent service offers beyond the tools above (110 in the catalogued snapshot): "
    "docking, design, MSA and search, energy and dynamics, embeddings, office-file generation. Filter with "
    "`grep` (matches name and description), `reliability` (stable/beta/experimental) or `state`. `state` is "
    "this repo's own verdict from calling each tool: ok, not_deployed, empty, failed, unreachable, or absent "
    "when it was never probed -- the service itself publishes no such status, so an unprobed tool may still "
    "turn out to be undeployed. Then call it with run_tool.",
    {
        "type": "object",
        "properties": {
            "grep": _field("Case-insensitive text to match against name and description, e.g. 'dock'."),
            "reliability": _field("Keep only this reliability: stable, beta or experimental."),
            "state": _field("Keep only tools whose probed state is this, e.g. 'ok' or 'not_deployed'."),
        },
        "required": [],
    },
)
async def list_tools(args: dict) -> dict:
    async def work():
        if not _CATALOG:
            raise RuntimeError(
                f"The catalog snapshot {_CATALOG_PATH.name} is missing or unreadable; run refresh_catalog.py."
            )
        grep = str(args.get("grep") or "").strip().lower()
        reliability = str(args.get("reliability") or "").strip().lower()
        state = str(args.get("state") or "").strip().lower()
        rows = []
        for name, entry in sorted(_CATALOG.items(), key=lambda item: item[0].lower()):
            if name in ESM_WORKFLOW_TOOLS:
                continue
            description = str(entry.get("description") or "")
            probed = (entry.get("probe") or {}).get("state", "")
            if grep and grep not in name.lower() and grep not in description.lower():
                continue
            if reliability and str(entry.get("reliability", "")).lower() != reliability:
                continue
            if state and probed.lower() != state:
                continue
            row = {
                "name": name,
                "reliability": entry.get("reliability"),
                "speed": entry.get("speed"),
                "inputs": list((entry.get("inputs") or {}).keys()),
                "description": _cut(description, 140),
            }
            if probed:
                row["state"] = probed
            rows.append(row)
        result: dict[str, Any] = {
            "matched": len(rows),
            "catalog_snapshot": _CATALOG_META.get("fetched_at"),
            "tools": rows[:_LIST_LIMIT],
        }
        if len(rows) > _LIST_LIMIT:
            result["note"] = f"Showing {_LIST_LIMIT} of {len(rows)}; narrow with grep, reliability or state."
        return result

    return await _guarded(work)


@tool(
    "describe_tool",
    "Everything the catalogued snapshot holds about one ProEngAgent tool: description, input field names, "
    "outputs, requirements, speed, reliability, and the probed state. Read this before run_tool on a tool "
    "that has no typed wrapper here -- input names in the catalog are occasionally internal ones, so a "
    "failed call's error message about a field is more authoritative than the snapshot.",
    _schema({"name": _field("Exact tool name from list_tools (case-sensitive, e.g. 'ProtParam').")}, ["name"]),
)
async def describe_tool(args: dict) -> dict:
    async def work():
        name = str(args.get("name") or "").strip()
        entry = _CATALOG.get(name)
        if entry is None:
            near = [other for other in _CATALOG if name.lower() in other.lower()][:8]
            raise ValueError(
                f"No tool named {name!r} in the snapshot ({len(_CATALOG)} tools)."
                + (f" Did you mean: {', '.join(near)}?" if near else " Use list_tools to see what there is.")
            )
        if name in ESM_WORKFLOW_TOOLS:
            raise ValueError(_ESM_REFUSAL.format(name=name))
        return entry

    return await _guarded(work)


@tool(
    "run_tool",
    "Call any ProEngAgent tool that has no typed wrapper here, with `inputs` exactly as describe_tool "
    "lists them (names are case-sensitive). Check describe_tool first; a tool marked beta or experimental "
    "still runs, and its status is returned with the result so it can be reported. File arguments are paths "
    "on the service, from upload_file, get_pdb or an earlier result -- never paths on this machine. Use the "
    "typed tools above for everything they cover, and the esm-directed-evolution skill for mutation scoring.",
    {
        "type": "object",
        "properties": {
            "name": _field("Exact tool name, e.g. 'foldseek'."),
            "inputs": {
                "type": "object",
                "additionalProperties": True,
                "description": "The tool's own input fields, as describe_tool lists them.",
            },
            "timeout": _field("Seconds to wait, up to 900. Default comes from the tool's catalogued speed.", "number"),
            "full": _field("Return the whole result instead of a shortened view.", "boolean"),
        },
        "required": ["name", "inputs"],
    },
)
async def run_tool(args: dict) -> dict:
    async def work():
        name = str(args.get("name") or "").strip()
        if not name:
            raise ValueError("`name` is required: the tool to call, as list_tools names it.")
        if name in ESM_WORKFLOW_TOOLS:
            raise ValueError(_ESM_REFUSAL.format(name=name))
        inputs = args.get("inputs")
        if not isinstance(inputs, dict):
            raise ValueError("`inputs` must be an object with that tool's own input fields.")
        if _CATALOG and name not in _CATALOG:
            near = [other for other in _CATALOG if name.lower() in other.lower()][:8]
            raise ValueError(
                f"No tool named {name!r} in the snapshot."
                + (f" Did you mean: {', '.join(near)}?" if near else " Use list_tools to see what there is.")
            )
        return await _run_tool(name, inputs, full=bool(args.get("full")), timeout=args.get("timeout"))

    return await _guarded(work)


@tool(
    "upload_file",
    "Send a file from this chat's own uploads or workspace to the ProEngAgent service, so the tools can "
    "work on it -- they run on another machine and cannot see local paths. Returns the path to use as a "
    "`pdb_file` / `pdf_file` argument, and for a PDF the extracted text as well. Pass the absolute path "
    "from the upload note; never paste a file's content into a tool argument.",
    _schema({"path": _field("Absolute path of the file in this chat's uploads or workspace.")}, ["path"]),
)
async def upload_file(args: dict) -> dict:
    async def work():
        import httpx

        path = _local_file(args.get("path"))
        base = _base_url()
        try:
            async with httpx.AsyncClient(base_url=base, timeout=180.0) as client:
                response = await client.post(
                    "/api/general/upload",
                    data={"session_id": _session_id()},
                    files={"file": (path.name, path.read_bytes())},
                )
                response.raise_for_status()
                answer = response.json()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"HTTP {exc.response.status_code} uploading {path.name}: "
                               f"{_describe_error(exc.response)}") from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"Cannot reach the ProEngAgent service at {base}: {exc}") from exc

        saved = answer.get("saved_path")
        result = {
            "uploaded": path.name,
            "size": path.stat().st_size,
            "service_path": saved,
            "pass_this_as": "Use service_path for a pdb_file / pdf_file argument.",
        }
        for key in ("pages", "chars", "truncated", "text"):
            if key in answer:
                result[key] = answer[key]
        return _full_or_compact(result, lambda data: _shrink(data), "upload result",
                               "The whole extracted text is on the service; parse_pdf_document can re-read it.")

    return await _guarded(work)


@tool(
    "read_output",
    "Fetch a result file the service produced (the `path` inside a download url, or any workspace path a "
    "result reports) and save it into this chat's workspace. Text comes back inline as well, shortened; a "
    "binary file is only saved. Use it for the CSV/TXT files tools like Pythia_Mut write, instead of asking "
    "the model to retype numbers out of a preview.",
    {
        "type": "object",
        "properties": {
            "path": _field("Path on the service, as a result or download url reports it."),
            "max_chars": _field("How much text to return inline (default 4000).", "number"),
            "save": {"type": "boolean", "description": "Save into this chat's workspace (default true)."},
        },
        "required": ["path"],
    },
)
async def read_output(args: dict) -> dict:
    async def work():
        import httpx

        path = str(args.get("path") or "").strip()
        if not path:
            raise ValueError("`path` is required: the service-side file to read.")
        limit = int(args.get("max_chars") or 4000)
        base = _base_url()
        content: bytes | None = None
        try:
            async with httpx.AsyncClient(base_url=base, timeout=180.0) as client:
                response = await client.get(f"/api/upload/file?{urlencode({'path': path})}")
                if response.status_code < 400:
                    content = response.content
        except httpx.RequestError as exc:
            raise RuntimeError(f"Cannot reach the ProEngAgent service at {base}: {exc}") from exc

        result: dict[str, Any] = {"path": path}
        if content is None:
            # The download route refused it (it only serves what it knows); the catalog's own
            # read_file tool can still reach anything inside the service workspace.
            answer = await _run_tool("read_file", {"file_path": path, "max_chars": limit}, full=True)
            result["read_via"] = "read_file tool (the download route would not serve this path)"
            result["output"] = answer.get("output")
            return _full_or_compact(result, lambda data: _shrink(data), "file", "Narrow it with max_chars.")

        result["bytes"] = len(content)
        if args.get("save", True):
            workspace, _ = _workspace_roots()
            folder = workspace / "proengagent"
            folder.mkdir(parents=True, exist_ok=True)
            name = Path(path).name or "download"
            local = folder / name
            local.write_bytes(content)
            result["saved_to"] = str(local)
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            result["content"] = None
            result["note"] = "Not UTF-8 text, so it was only saved."
            return result
        result["content"] = _cut(text, limit)
        if len(text) > limit:
            result["note"] = f"{len(text)} characters in all; raise max_chars or read the saved file."
        return result

    return await _guarded(work)


# Named rather than inlined into create_sdk_mcp_server: the finished server is an
# mcp.server.Server that does not expose its tool list, and selfcheck.py needs the
# handlers to call them without a chat.
TOOLS = [*_TYPED_TOOLS, list_tools, describe_tool, run_tool, upload_file, read_output]

SERVER = create_sdk_mcp_server(name="proengagent", tools=TOOLS)
