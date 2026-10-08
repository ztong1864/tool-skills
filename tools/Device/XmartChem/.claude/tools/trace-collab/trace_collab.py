"""In-process (SDK) tool: TRACE Lab chemical-experiment recommendation loop.

Converts trace-collab-skill (skills/Device/XmartChem/.claude/skills/trace-collab-skill)
into a sdk_python tool -- see tool_backing_service.py's module docstring for the backing
schema. One @tool per TRACE Lab REST endpoint (see api.md in the TRACE-LAB-API backend),
calling out over HTTP to TRACE_LAB_BASE_URL (default http://127.0.0.1:8788, override via
the TRACE_LAB_BASE_URL env var) instead of shelling out to trace_lab_api.py.

The skill's CSV round-trip (save_recommendations.py/save_experiment_results.py writing to
trace-collab-skill/output/) isn't ported: a tool call returns structured JSON straight into
the model's context, so there's nothing for a local file to hand off between rounds. Row
data (design_records/rows/results) can still be supplied as a CSV string, though --
parsed server-side by _parse_csv_rows -- so the model can pass an uploaded CSV's raw text
straight through instead of hand-transcribing every row into JSON itself.

Workflow rules that used to live in SKILL.md / references/trace-lab-workflow.md (don't
call ask_recommendations again while recommendations are still pending, completed results
need the objective value, failed/skipped need a reason) are folded into the individual
tool descriptions below, since that's the only text that reaches the model at call time --
TOOL.md is catalog/human-facing only.

Kept in step with the TRACE Lab API's project-import features: a project's `project_id` is its
handle; create_project uploads design space, descriptor tables, observations and evidence in one
all-or-nothing request; check_project / update_project_config / add_descriptor_table /
import_evidence expose the project check, editable settings, descriptor tables and strict evidence
import. ask_recommendations no longer forces controller_mode (the project's own setting wins), and
API errors are returned as readable lines (see _describe_error). The project setting
evidence_selection ('score' / 'per_variable') is editable through update_project_config, and
evidence_preview shows which cards the decision agent is actually given (the paper-to-card drafting
commands stay in the TRACE Lab CLI: they need PDFs on the server).

Readers return compact views by default (see "Output slimming"); full=true gives the API's whole answer.

import_project brings an existing TRACE project in with its whole history (observations, earlier
recommendation batches, traces): it copies the folder, a .zip of it, or uploaded files into the chat
user's own workspace (`trace_projects/<project_id>/`), repairs what a project.yaml carries over from
another server (a stale agent_config_path, settings this TRACE version does not know), runs TRACE's
folder check and registers the copy in place. The source is never modified. unregister_project undoes
it. Both need FOUNDRYCLAW_USER_ID, which tool_backing_service sets on this module for every session;
TRACE Lab must run on the same machine as the backend (it reads the copied folder by path).

Note for deployment: tool_backing_service re-executes this file for every new chat session and
silently drops the whole tool if the import fails -- import it once with the app's venv after any edit.
"""

import csv
import io
import json
import os
import re
import shutil
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx
from claude_agent_sdk import create_sdk_mcp_server, tool

from app.core.config import TRACE_LAB_BASE_URL

# Set by tool_backing_service before this file runs (one module instance per chat session): whose chat
# this is. Needed for the user's own folders (uploads, import_project), project owners and the user's key.
FOUNDRYCLAW_USER_ID = globals().get("FOUNDRYCLAW_USER_ID")


def _parse_csv_rows(csv_text: str) -> list[dict[str, Any]]:
    text = csv_text.lstrip("\ufeff")
    return list(csv.DictReader(io.StringIO(text)))


# --- Uploaded files --------------------------------------------------------------------------------
# A file the user uploaded is read here, by path, so its content never passes through the model: a model
# that copies a file into a text argument can shorten or rewrite it (in one test it imported three evidence
# cards it had made up), and the group's real files (36-153 KB) do not fit into a tool call anyway.
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
_FILE_HINT = ("When the user uploaded the file, pass its absolute path (from the upload note) here instead of "
              "copying its content into a text argument.")


def _read_upload(path_value: Any, what: str) -> str:
    _, roots = _import_roots()
    path = _importable(path_value, roots)
    if not path.is_file():
        raise ValueError(f"{what}: {path} is not a file.")
    if path.stat().st_size > _MAX_UPLOAD_BYTES:
        raise ValueError(f"{what}: {path.name} is larger than 20 MB.")
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gb18030"):  # Excel on Chinese Windows saves CSV as GBK
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"{what}: {path.name} is neither UTF-8 nor GB18030 text.")


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _pick_rows(args: dict, json_key: str, csv_key: str, file_key: str | None = None) -> list[dict[str, Any]]:
    json_rows = args.get(json_key)
    given = [key for key, present in ((json_key, isinstance(json_rows, list) and len(json_rows) > 0),
                                      (csv_key, _has_text(args.get(csv_key))),
                                      (file_key, bool(file_key) and _has_text(args.get(file_key)))) if present]
    if len(given) != 1:
        raise ValueError("Provide exactly one of " + " or ".join(key for key in (json_key, csv_key, file_key) if key) + ".")
    if given[0] == json_key:
        return [dict(row) for row in json_rows]
    if given[0] == csv_key:
        return _parse_csv_rows(args[csv_key])
    return _parse_csv_rows(_read_upload(args[file_key], file_key))


def _evidence_from_file(path_value: Any, what: str) -> dict[str, str]:
    """{'csv': text} for a .csv evidence file, otherwise {'jsonl': text}."""
    text = _read_upload(path_value, what)
    return {"csv": text} if str(path_value).lower().endswith(".csv") else {"jsonl": text}


def _project_path(project_id: str, suffix: str = "") -> str:
    """API path for one project. The id is the project's handle (its folder name, as shown by
    list_projects), so it is URL-quoted rather than trusted."""
    return f"/api/projects/{quote(project_id, safe='')}{suffix}"


def _describe_error(response: httpx.Response) -> str:
    """Readable text for an API error. Most errors are a plain string; upload, descriptor and
    evidence failures carry {message, check.errors | problems | report}, which the model would
    otherwise have to pick out of raw JSON."""
    text = response.text
    try:
        detail = response.json().get("detail", text)
    except (ValueError, AttributeError):
        return text
    if not isinstance(detail, dict):
        return str(detail)
    lines = [str(detail.get("message") or "").strip()]
    for item in (detail.get("check") or {}).get("errors") or []:
        where = str(item.get("file", "")) + (f" line {item['line']}" if item.get("line") else "")
        lines.append(f"- {where}: {item.get('message', '')}")
    lines.extend(f"- {problem}" for problem in detail.get("problems") or [])
    # A descriptor report repeats its errors in the message; keep only what adds information.
    extra = {key: value for key, value in (detail.get("report") or {}).items() if value and key != "errors"}
    if extra:
        lines.append("report: " + json.dumps(extra, ensure_ascii=False)[:2000])
    return "\n".join(line for line in lines if line)


async def _request(method: str, path: str, json_body: Any = None, timeout: float = 30.0) -> Any:
    try:
        async with httpx.AsyncClient(base_url=TRACE_LAB_BASE_URL, timeout=timeout) as client:
            response = await client.request(method, path, json=json_body)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = _describe_error(exc.response)
        separator = "\n" if "\n" in detail else " "
        raise RuntimeError(f"HTTP {exc.response.status_code} {method} {path}:{separator}{detail}") from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Cannot reach TRACE Lab API at {TRACE_LAB_BASE_URL}: {exc}") from exc
    if not response.text.strip():
        return {}
    return response.json()


def _ok(data: Any) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, separators=(",", ":"))}]}


def _err(message: str) -> dict:
    return {"content": [{"type": "text", "text": message}], "is_error": True}


async def _run(fn) -> dict:
    try:
        data = await fn()
    except (RuntimeError, ValueError) as exc:
        return _err(str(exc))
    return _ok(data)


def _require_project_id(args: dict) -> str:
    project_id = str(args.get("project_id", "")).strip()
    if not project_id:
        raise ValueError("project_id is required.")
    return project_id


def _pick_evidence(args: dict) -> dict[str, Any]:
    """Exactly one of file / cards / jsonl / csv, as the API's evidence import expects."""
    given = {
        key: args[key]
        for key in ("file", "cards", "jsonl", "csv")
        if (isinstance(args.get(key), list) and args[key]) or _has_text(args.get(key))
    }
    if len(given) != 1:
        raise ValueError("Provide exactly one of file (path of an uploaded .jsonl/.csv), cards (JSON objects), "
                         "jsonl (JSON Lines text) or csv (CSV text).")
    if "file" in given:
        return _evidence_from_file(given["file"], "file")
    return given


def _check_descriptor_tables(tables: Any) -> list[dict[str, Any]]:
    """Fail early, with a clear message, on a malformed descriptor table instead of a server 400."""
    if not isinstance(tables, list):
        raise ValueError("descriptor_tables must be a list of {variable, value_column, file | csv, aliases?}.")
    checked = []
    for index, table in enumerate(tables, start=1):
        label = f"descriptor_tables[{index}]"
        if not isinstance(table, dict):
            raise ValueError(f"{label} must be an object.")
        for key in ("variable", "value_column"):
            if not str(table.get(key) or "").strip():
                raise ValueError(f"{label} needs `{key}`.")
        sources = [key for key in ("file", "csv") if _has_text(table.get(key))]
        sources += ["rows"] if isinstance(table.get("rows"), list) and table["rows"] else []
        if len(sources) != 1:
            raise ValueError(f"{label} needs exactly one of `file` (path of the uploaded table), `csv` (raw CSV text) or `rows`.")
        if sources == ["file"]:
            table = {key: value for key, value in table.items() if key != "file"}
            table["csv"] = _read_upload(tables[index - 1]["file"], f"{label}.file")
        aliases = table.get("aliases") or {}
        if not isinstance(aliases, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in aliases.items()
        ):
            raise ValueError(f"{label}.aliases must be an object of {{design option: table value}} strings.")
        checked.append(dict(table, aliases=aliases))
    return checked


# Settings the API refuses to change because existing observations depend on them.
_LOCKED_SETTINGS = ("project_id", "objective_name", "goal")


def _settings_arg(args: dict) -> dict[str, Any]:
    settings = args.get("settings")
    if not isinstance(settings, dict) or not settings:
        raise ValueError("settings must be a non-empty object, e.g. {\"planner_name\": \"chunked_gp\"}.")
    locked = [key for key in settings if key in _LOCKED_SETTINGS]
    if locked:
        raise ValueError(
            f"{', '.join(locked)} cannot be changed: existing observations depend on it. "
            "Create a new project instead if that really has to differ."
        )
    return dict(settings)


async def _pending_recommendation_ids(project_id: str) -> list[str]:
    """recommendation_ids with status "pending" in a project's latest batch. Shared by
    ask_recommendations' pending-guard and tell_results' completeness check -- port of
    trace_lab_api.py's assert_no_pending, plus save_experiment_results.py's "missing"
    check (both walked the latest/only batch and flagged unresolved recommendation_ids)."""
    encoded = quote(project_id, safe="")
    recs = await _request("GET", f"/api/projects/{encoded}/recommendations")
    batches = recs.get("batches") or []
    if not batches:
        return []
    latest = batches[-1]
    return [
        str(rec.get("recommendation_id"))
        for rec in (latest.get("recommendations") or [])
        if str(rec.get("status") or "pending").lower() == "pending"
    ]


# --- Project owners --------------------------------------------------------------------------------
# The TRACE Lab service is shared by every user, so every project stays visible; but a tool that changes a
# project refuses when the project was created or imported by someone else, until the user has confirmed and
# the call passes others_project_ok=true. Owners are recorded here (TRACE itself has no users); projects from
# before this record have no owner and stay unrestricted.
_OTHERS_OK_PROPERTY = {
    "type": "boolean",
    "description": ("Only after the user confirmed they may change a project that belongs to another user "
                    "(the tool names the owner when it refuses)."),
}


def _owners_path() -> Path:
    from app.core.paths import DATA_ROOT

    return DATA_ROOT / "trace_project_owners.json"


def _load_owners() -> dict[str, Any]:
    try:
        data = json.loads(_owners_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, ImportError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_owners(owners: dict[str, Any]) -> None:
    path = _owners_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(owners, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(temporary, path)


def _current_user() -> str | None:
    if not FOUNDRYCLAW_USER_ID:
        return None
    try:
        from app.services.storage_paths import user_storage_name

        return user_storage_name(FOUNDRYCLAW_USER_ID)
    except Exception:  # noqa: BLE001 - no user lookup outside the backend
        return None


def _record_owner(handle: str, via: str) -> None:
    user = _current_user()
    if not user:
        return
    owners = _load_owners()
    owners[handle] = {"owner": user, "user_id": FOUNDRYCLAW_USER_ID, "via": via,
                      "since": datetime.now().isoformat(timespec="seconds")}
    _save_owners(owners)


def _forget_owner(handle: str) -> None:
    owners = _load_owners()
    if owners.pop(handle, None) is not None:
        _save_owners(owners)


def _owner_fields(handle: Any) -> dict[str, Any]:
    owner = (_load_owners().get(str(handle)) or {}).get("owner")
    user = _current_user()
    return {"owner": owner or "unknown", "yours": bool(owner and user and owner == user)}


def _guard_owner(args: dict, project_id: str, action: str) -> None:
    owner = (_load_owners().get(project_id) or {}).get("owner")
    user = _current_user()
    if owner and user and owner != user and not bool(args.get("others_project_ok", False)):
        raise ValueError(
            f"`{project_id}` belongs to {owner}, not to you ({user}): {action} would change their project. "
            "Tell the user whose project it is and ask whether to go ahead; only if they confirm, call again "
            "with others_project_ok=true.")


# --- Size of full answers --------------------------------------------------------------------------
_FULL_LIMIT = 25_000  # characters; Claude Code stores a tool result over ~30 KB in a file the model cannot read back


def _json_size(data: Any) -> int:
    return len(json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str))


def _full_or_compact(data: Any, compact, what: str, hint: str) -> Any:
    """`data` if it fits into a tool result, otherwise the compact view with a note on how to read the rest."""
    size = _json_size(data)
    if size <= _FULL_LIMIT:
        return data
    view = compact(data)
    note = (f"The full {what} is {size // 1024} KB, more than a chat tool result can hold, so this is the compact "
            f"view. {hint}")
    return {**view, "note": note} if isinstance(view, dict) else {"data": view, "note": note}


# --- The user's own LLM key (设置 → 密钥管理) for TRACE's agentic mode --------------------------------
def _user_llm() -> dict[str, str] | None:
    """{api_key, base_url, model} of the chat user's OPENAI-API-KEY, sent with ask/tell so TRACE's agentic mode
    runs on the user's own key. None when unset, outside a chat, or when TRACE is reached over plain http on
    another host (the key would travel unencrypted)."""
    if not FOUNDRYCLAW_USER_ID:
        return None
    parsed = urlparse(TRACE_LAB_BASE_URL)
    if parsed.scheme != "https" and (parsed.hostname or "") not in {"127.0.0.1", "localhost", "::1"}:
        return None
    try:
        from app.services.tool_credential_service import get_skill_openai_config, skill_openai_base_url

        config = get_skill_openai_config(FOUNDRYCLAW_USER_ID)
    except Exception:  # noqa: BLE001 - no key store outside the backend
        return None
    if not config:
        return None
    return {"api_key": config["api_key"], "base_url": skill_openai_base_url(config["endpoint"]), "model": config["model"]}


def _mark_llm_key(data: Any, sent: bool) -> Any:
    """Say which key the LLM steps used, from TRACE's own `llm_source`."""
    if not isinstance(data, dict):
        return data
    source = data.get("llm_source")
    if data.get("controller_mode") == "bo_only":
        label = "none (bo_only uses no LLM)"
    elif source == "request":
        label = "yours (设置 → 密钥管理)"
    elif source == "server" or not sent:
        label = "the TRACE server's shared key" + ("" if sent else " (you have no OPENAI-API-KEY in 设置 → 密钥管理)")
    else:
        label = "unknown: this TRACE version does not report it (probably the server's shared key)"
    return {**data, "llm_key": label}


# --- Output slimming -------------------------------------------------------------------------------
# The API returns everything a project holds: one agentic batch is ~90 KB (each recommendation carries its
# whole decision trace), all evidence cards ~55 KB, the recommendations of a project ~300 KB. Claude Code
# stores tool results over ~30 KB in a file and shows a short preview, and the model then re-runs the call.
# So every reader returns a compact view by default; `full=true` returns the API's answer unchanged.

def _cut(value: Any, limit: int) -> Any:
    if isinstance(value, str) and len(value) > limit:
        return value[:limit].rstrip() + "..."
    return value


def _shrink(value: Any, text_limit: int = 500, list_limit: int = 12, depth: int = 0) -> Any:
    """Generic size cap for nested JSON: long strings and long lists are cut, with a marker."""
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


_REC_KEEP = (
    "round_id", "recommendation_id", "rank", "status", "candidate", "proposed_by", "model_estimate", "batch_role",
    "controller_action", "planner_error", "planner_warnings", "evidence_refs", "result", "failure_reason", "notes",
)


def _slim_recommendation(rec: Any) -> Any:
    """One recommendation without its decision trace (get_trace has that)."""
    if not isinstance(rec, dict):
        return rec
    slim = {key: rec[key] for key in _REC_KEEP if key in rec and (rec[key] not in ("", [], {}, None) or key == "status")}
    if rec.get("rationale"):
        slim["rationale"] = _cut(rec["rationale"], 500)
    if rec.get("batch_role_reason"):
        slim["batch_role_reason"] = _cut(rec["batch_role_reason"], 300)
    assessment = rec.get("semantic_assessment")
    if isinstance(assessment, dict):
        slim["semantic_assessment"] = {
            key: (_cut(assessment[key], 300) if key == "soft_comment" else assessment[key])
            for key in ("risk_level", "plausibility_score", "novelty_score", "soft_comment") if key in assessment
        }
    return slim


def _slim_ask(data: Any) -> Any:
    if isinstance(data, dict) and isinstance(data.get("recommendations"), list):
        data = dict(data)
        data["recommendations"] = [_slim_recommendation(rec) for rec in data["recommendations"]]
        data["note"] = "Recommendations are shown without their decision trace; use get_trace(project_id, round_id) for the reasoning."
    return data


def _slim_variable(variable: Any) -> Any:
    if not isinstance(variable, dict):
        return variable
    keep = ("name", "type", "active", "unit", "option_count", "low", "high", "step", "role", "fixed_value",
            "descriptor_count")
    slim = {key: variable[key] for key in keep if key in variable and variable[key] not in ("", None)}
    values = variable.get("values")
    if isinstance(values, list) and not variable.get("is_fixed"):
        slim["values"] = values if len(values) <= 12 else values[:8] + [f"... {variable.get('option_count', len(values)) - 8} more"]
    return slim


def _slim_design_space(space: Any) -> Any:
    if not isinstance(space, dict):
        return space
    slim = {key: space[key] for key in ("active_variables", "active_variable_count", "fixed_condition_count",
                                        "controlled_conditions", "inactive_variables") if key in space}
    slim["variables"] = [_slim_variable(item) for item in space.get("variables", [])]
    return slim


def _slim_project_entry(entry: Any) -> Any:
    if not isinstance(entry, dict) or "design_space" not in entry:
        return entry
    slim = dict(entry)
    project = slim.get("project")
    if isinstance(project, dict):
        slim["project"] = {**project, "reaction_scope": _cut(project.get("reaction_scope"), 300)}
    slim["design_space"] = _slim_design_space(entry["design_space"])
    return slim


def _slim_card(card: Any) -> Any:
    if not isinstance(card, dict):
        return card
    slim = {key: card[key] for key in ("card_id", "mapping_status", "confidence", "variable_scope")
            if key in card and card[key] not in ("", [], None)}
    for key, limit in (("source", 100), ("reaction_scope", 100), ("summary", 200)):
        if card.get(key):
            slim[key] = _cut(card[key], limit)
    return slim


_TRACE_KEEP = (
    "rank", "recommendation_id", "candidate", "proposed_by", "batch_role", "batch_role_reason", "controller_action",
    "controller_reasoning", "action_fallback_reason", "planner_error", "semantic_assessment", "selection_trace",
    "diagnosis", "hypothesis_action", "verification_pass", "evidence_refs", "evidence_trace",
)


def _slim_trace(data: Any) -> Any:
    """Per-candidate reasoning without batch contracts, descriptor profiles, skill traces and planner internals."""
    if not isinstance(data, dict) or not isinstance(data.get("trace"), list):
        return _shrink(data, text_limit=500, list_limit=8)
    records = []
    for record in data["trace"]:
        if not isinstance(record, dict):
            continue
        kept = {key: record[key] for key in _TRACE_KEEP if key in record and record[key] not in ("", [], {}, None)}
        evidence = kept.get("evidence_trace")
        if isinstance(evidence, dict):  # the retrieved units repeat the cards' full text and metadata
            kept["evidence_trace"] = {key: evidence[key] for key in
                                      ("retrieved_count", "retrieved_card_ids", "retrieved_mapping_statuses") if key in evidence}
        records.append(kept)
    shared: dict[str, Any] = {}
    if len(records) > 1:  # batch-level reasoning is repeated verbatim on every candidate: show it once
        for key in _TRACE_KEEP:
            values = [json.dumps(record.get(key), sort_keys=True, default=str) for record in records]
            if key in records[0] and len(set(values)) == 1:
                shared[key] = records[0][key]
        records = [{k: v for k, v in record.items() if k not in shared} for record in records]
    result = {**{k: v for k, v in data.items() if k != "trace"}}
    if shared:
        result["batch"] = _shrink(shared, text_limit=400, list_limit=5)
    result["trace"] = [_shrink(record, text_limit=350, list_limit=5) for record in records]
    result["note"] = ("Trace is condensed: reasoning shared by the whole batch is under `batch`, long texts and lists are cut, "
                      "planner internals are left out; full=true returns everything.")
    return result


def _slim_preview(data: Any) -> Any:
    if not isinstance(data, dict):
        return data
    slim = {key: value for key, value in data.items() if key not in ("retrieved", "not_shown")}
    slim["retrieved"] = [
        {key: (_cut(item[key], 140) if key == "source" else item[key])
         for key in ("card_id", "rank", "score", "mapping_status", "slots", "prompt_text", "source") if key in item}
        for item in data.get("retrieved", []) if isinstance(item, dict)
    ]
    slim["not_shown"] = [
        {key: (_cut(item[key], 240) if key == "reason_text" else item[key])
         for key in ("card_id", "rank", "score", "mapping_status", "reason", "reason_text") if item.get(key) not in (None, "")}
        for item in data.get("not_shown", []) if isinstance(item, dict)
    ]
    return slim


_FULL_PROPERTY = {
    "type": "boolean",
    "description": "Return the API's complete answer instead of the compact view (large; only when the compact view lacks what you need).",
}


@tool("health", "Check whether the TRACE Lab API service is reachable and responding.", {})
async def health(args: dict) -> dict:
    async def _do():
        return await _request("GET", "/api/health")

    return await _run(_do)


@tool(
    "list_projects",
    "List every TRACE Lab project that currently exists, with a summary of each (objective, batch size, observation counts, pending recommendations, best value so far, variables with option counts) and its `owner` (`yours` is true for the user's own projects; the service is shared by all users). Each entry's `handle` is the value to pass as `project_id` to every other tool; a project with a `problem` could not be read. Compact by default; full=true returns everything.",
    {"type": "object", "properties": {"full": _FULL_PROPERTY}},
)
async def list_projects(args: dict) -> dict:
    async def _do():
        data = await _request("GET", "/api/projects")
        if not isinstance(data, dict):
            return data
        data = {**data, "projects": [{**item, **_owner_fields(item.get("handle"))} if isinstance(item, dict) else item
                                     for item in data.get("projects", [])]}

        def compact(value):
            return {**value, "projects": [_slim_project_entry(item) for item in value.get("projects", [])]}

        if bool(args.get("full", False)):
            return _full_or_compact(data, compact, "project list", "Use project_summary(project_id, full=true) for one project.")
        return compact(data)

    return await _run(_do)


@tool(
    "project_summary",
    "Get the status summary for one TRACE Lab project: objective, variables (long option lists are shortened), observation and batch counts, current best value, and pending-recommendation count. Check this before generating recommendations to see whether the project already exists and whether a previous batch still needs results submitted. Compact by default; full=true returns every option and descriptor name.",
    {"type": "object", "properties": {"project_id": {"type": "string"}, "full": _FULL_PROPERTY}, "required": ["project_id"]},
)
async def project_summary(args: dict) -> dict:
    async def _do():
        project_id = _require_project_id(args)
        data = await _request("GET", f"/api/projects/{quote(project_id, safe='')}")
        if isinstance(data, dict):
            data = {**data, **_owner_fields(project_id)}
        if bool(args.get("full", False)):
            return _full_or_compact(data, _slim_project_entry, "project summary",
                                    "Long option lists are shortened here; check_project gives the counts.")
        return _slim_project_entry(data)

    return await _run(_do)


_CREATE_PROJECT_SCHEMA = {
    "type": "object",
    "properties": {
        "project_id": {
            "type": "string",
            "description": "Unique id for the new project; used as its storage directory name.",
        },
        "design_records": {
            "type": "array",
            "items": {"type": "object"},
            "description": (
                "Design-space rows as JSON objects (keys like variable/type/value/low/high/unit/role/"
                "active/stage). If the source CSV also has descriptor__<name> columns (see "
                "design_records_csv), do NOT use this field for it -- hand-retyping every numeric "
                "descriptor value for every option is exactly the transcription error this schema is "
                "meant to avoid, and silently produces a project with no usable descriptors even though "
                "planner_use_descriptors=true was requested. Use design_records_file (or design_records_csv) "
                "instead whenever descriptor columns are present. Give exactly one design source."
            ),
        },
        "design_records_file": {
            "type": "string",
            "description": ("Absolute path of the uploaded design-space CSV (from the upload note). Preferred whenever "
                            "the user uploaded the file: the tool reads it itself, every column unchanged. "
                            "Give exactly one of design_records_file, design_records_csv, design_records."),
        },
        "design_records_csv": {
            "type": "string",
            "description": (
                "Raw CSV text of the design-space file (header row: variable,type,value,low,high,step,"
                "unit,stage,active,role,fixed_value, optionally followed by one or more "
                "descriptor__<name> columns holding per-option numeric descriptors -- e.g. "
                "descriptor__HOMO_energy, descriptor__cation_radius_pm_mean). Prefer this over "
                "design_records when the user uploaded a CSV -- pass its content through as-is "
                "instead of retyping every row as JSON. This is the ONLY reliable way to preserve "
                "descriptor__<name> columns: if planner_use_descriptors=true and the uploaded CSV has "
                "them, they MUST be passed through here verbatim, byte-for-byte, including every "
                "descriptor__<name> column -- do not trim, summarize, or drop any columns when "
                "forwarding the CSV text, even though they don't affect the row/option count. Dropping "
                "them silently defeats planner_use_descriptors and forces the planner into a much more "
                "expensive raw-categorical search over the full combinatorial design space instead of a "
                "compact descriptor-based one. Provide this OR design_records, not both."
            ),
        },
        "objective_name": {"type": "string", "description": "Optimization target name, e.g. 'yield'. Defaults to 'yield'."},
        "goal": {"type": "string", "enum": ["maximize", "minimize"], "description": "Optimization direction. Defaults to 'maximize'."},
        "batch_size": {"type": "integer", "description": "Recommendations per batch. Defaults to 6."},
        "planner_name": {
            "type": "string",
            "enum": ["atlas", "chunked_gp", "random"],
            "description": (
                "Optimizer. Defaults to 'chunked_gp', which scores every combination in seconds even on millions "
                "of combinations. 'atlas' only when the user asks for it and the space is small (under about "
                "100,000 combinations): Atlas can take a quarter of an hour or never finish on larger spaces. "
                "'random' is for debugging."
            ),
        },
        "seed": {"type": "integer", "description": "Random seed. Defaults to 7."},
        "reaction_scope": {
            "type": "string",
            "description": "Free-text description of the reaction scope, used to match literature evidence cards.",
        },
        "controller_mode": {
            "type": "string",
            "enum": ["agentic", "bo_only"],
            "description": (
                "'agentic' has an LLM decision layer review and compose the BO optimizer's candidates; "
                "'bo_only' is pure Bayesian optimization with no LLM involved. Defaults to 'agentic'; use "
                "'bo_only' when no OPENAI_API_KEY is configured for the TRACE Lab service, or for debugging. "
                "Stored in the project: later ask_recommendations calls use it unless they override it."
            ),
        },
        "descriptor_tables": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "variable": {"type": "string", "description": "Design variable the table describes, e.g. 'Additive'."},
                    "value_column": {"type": "string", "description": "Table column holding the option names."},
                    "file": {"type": "string", "description": "Absolute path of the uploaded table (preferred). " + _FILE_HINT},
                    "csv": {"type": "string", "description": "Raw CSV text, one row per option, numeric descriptor columns (only when there is no uploaded file)."},
                    "aliases": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                        "description": (
                            "{design option: name used in the table} for options the table spells differently. "
                            "Only for options the user has confirmed are the same substance -- never guess; "
                            "nothing is matched loosely, so an option with no row fails the whole request."
                        ),
                    },
                },
                "required": ["variable", "value_column"],
            },
            "description": (
                "Raw per-option descriptor tables, attached to the design space on the server (one per "
                "variable). Prefer this to merging descriptors into the design CSV by hand when the user "
                "supplies separate descriptor tables. Use together with planner_use_descriptors=true. "
                "The whole create is all-or-nothing: a bad table creates nothing and the error lists what to fix."
            ),
        },
        "observations_file": {
            "type": "string",
            "description": ("Optional absolute path of the uploaded historical-observations CSV, imported in the same "
                            "all-or-nothing request. Preferred over observations_csv. " + _FILE_HINT),
        },
        "observations_csv": {
            "type": "string",
            "description": (
                "Optional raw CSV of historical observations, imported in the same all-or-nothing request "
                "(each value must be a real option of the design space). Same format as import_observations. "
                "Only when there is no uploaded file."
            ),
        },
        "evidence_file": {
            "type": "string",
            "description": ("Optional absolute path of the uploaded evidence cards (.jsonl, or .csv), validated strictly. "
                            "Preferred over evidence_jsonl/evidence_csv. " + _FILE_HINT),
        },
        "evidence_jsonl": {
            "type": "string",
            "description": "Optional evidence cards as JSON Lines text, validated strictly. Only when there is no uploaded file.",
        },
        "evidence_csv": {
            "type": "string",
            "description": "Optional evidence cards as CSV text, validated strictly. Only when there is no uploaded file.",
        },
        "agent_config_path": {"type": "string", "description": "Path to the agent config file. Defaults to 'configs/agent_bo.yaml'."},
        "planner_use_descriptors": {
            "type": "boolean",
            "description": (
                "Whether to enable descriptor-based augmentation. Defaults to false. Only takes effect "
                "if the design space actually carries descriptor__<name> columns per option (see "
                "design_records_csv) -- setting this true without them does nothing useful and leaves "
                "the planner doing raw categorical search."
            ),
        },
        "overwrite": {"type": "boolean", "description": "Overwrite an existing project with the same id. Defaults to false."},
        "others_project_ok": _OTHERS_OK_PROPERTY,
    },
    "required": ["project_id"],
}


@tool(
    "create_project",
    (
        "Create a new TRACE Lab project from a design-space definition. Use this the first time a user "
        "provides a design-space CSV (or equivalent JSON records) for a reaction -- not on every round; "
        "check an existing project with project_summary instead of recreating it. Everything given "
        "(design space, descriptor tables, historical observations, evidence cards) is validated together "
        "and the project is only created if all of it is valid. The response includes `check`: read its "
        "warnings before continuing (for example Atlas on a very large design space -- switch to "
        "chunked_gp with update_project_config)."
    ),
    _CREATE_PROJECT_SCHEMA,
)
async def create_project(args: dict) -> dict:
    async def _do():
        project_id = _require_project_id(args)
        has_records = isinstance(args.get("design_records"), list) and bool(args["design_records"])
        design_csv = args.get("design_records_csv")
        has_csv = _has_text(design_csv)
        has_file = _has_text(args.get("design_records_file"))
        if has_records + has_csv + has_file != 1:
            raise ValueError("Provide exactly one of design_records_file (path of the uploaded CSV), "
                             "design_records_csv or design_records.")
        if has_file:
            design_csv, has_csv = _read_upload(args["design_records_file"], "design_records_file"), True
        if bool(args.get("overwrite", False)):
            _guard_owner(args, project_id, "create_project with overwrite")
        config: dict[str, Any] = {"project_id": project_id}
        for key in (
            "objective_name",
            "goal",
            "batch_size",
            "planner_name",
            "seed",
            "reaction_scope",
            "controller_mode",
            "agent_config_path",
            "planner_use_descriptors",
        ):
            if args.get(key) is not None:
                config[key] = args[key]
        config.setdefault("planner_name", "chunked_gp")  # TRACE's own default, Atlas, may never finish on a large space
        payload: dict[str, Any] = {
            "project_id": project_id,
            "config": config,
            "overwrite": bool(args.get("overwrite", False)),
        }
        if has_csv:
            # Sent as-is: the server parses and validates it, so no descriptor__<name> column can be
            # lost or reshaped by a client-side round trip.
            payload["design_csv"] = design_csv.lstrip("﻿")
        else:
            payload["design_records"] = [dict(row) for row in args["design_records"]]
        if args.get("descriptor_tables") is not None:
            payload["descriptor_tables"] = _check_descriptor_tables(args["descriptor_tables"])
        if _has_text(args.get("observations_file")) and _has_text(args.get("observations_csv")):
            raise ValueError("Provide observations_file OR observations_csv, not both.")
        if _has_text(args.get("observations_file")):
            payload["observations_csv"] = _read_upload(args["observations_file"], "observations_file")
        elif _has_text(args.get("observations_csv")):
            payload["observations_csv"] = args["observations_csv"].lstrip("﻿")
        evidence_given = [key for key in ("evidence_file", "evidence_jsonl", "evidence_csv") if _has_text(args.get(key))]
        if len(evidence_given) > 1:
            raise ValueError("Provide one of evidence_file, evidence_jsonl or evidence_csv.")
        for key in evidence_given:
            if key == "evidence_file":
                payload.update({f"evidence_{kind}": text
                                for kind, text in _evidence_from_file(args[key], key).items()})
            else:
                payload[key] = args[key].lstrip("﻿")
        # Large/descriptor-heavy design spaces can take a long time to enumerate server-side
        # (observed up to ~13 min); a shorter client-side timeout here would give up and let
        # the model retry into an overlapping second request against the same project.
        created = await _request("POST", "/api/projects", payload, timeout=1200.0)
        _record_owner(project_id, "create_project")
        return {**created, **_owner_fields(project_id)} if isinstance(created, dict) else created

    return await _run(_do)


_IMPORT_OBSERVATIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "project_id": {"type": "string"},
        "rows": {
            "type": "array",
            "items": {"type": "object"},
            "description": (
                "Historical observation rows as JSON objects (one key per design variable, plus the "
                "objective value and status). Provide this OR rows_csv, not both."
            ),
        },
        "rows_file": {
            "type": "string",
            "description": ("Absolute path of the uploaded CSV of historical results (preferred). " + _FILE_HINT
                            + " Give exactly one of rows_file, rows_csv, rows."),
        },
        "rows_csv": {
            "type": "string",
            "description": (
                "Raw CSV text of historical experiment results (columns: each design variable, the "
                "objective e.g. yield, status). Only when there is no uploaded file."
            ),
        },
        "others_project_ok": _OTHERS_OK_PROPERTY,
        "source": {"type": "string", "description": "Label for where this data came from. Defaults to 'historical'."},
        "allow_duplicates": {
            "type": "boolean",
            "description": "Allow importing rows whose conditions match an existing observation. Defaults to false.",
        },
    },
    "required": ["project_id"],
}


@tool(
    "import_observations",
    (
        "Import historical experiment data into an existing TRACE Lab project as prior observations, "
        "before the first ask_recommendations call for that project. Not for submitting results of TRACE "
        "Lab's own recommendations -- use tell_results for that."
    ),
    _IMPORT_OBSERVATIONS_SCHEMA,
)
async def import_observations(args: dict) -> dict:
    async def _do():
        project_id = _require_project_id(args)
        _guard_owner(args, project_id, "import_observations")
        rows = _pick_rows(args, "rows", "rows_csv", "rows_file")
        payload = {
            "rows": rows,
            "source": str(args.get("source") or "historical"),
            "allow_duplicates": bool(args.get("allow_duplicates", False)),
        }
        return await _request("POST", f"/api/projects/{quote(project_id, safe='')}/observations/import", payload)

    return await _run(_do)


_ASK_SCHEMA = {
    "type": "object",
    "properties": {
        "project_id": {"type": "string"},
        "batch_size": {"type": "integer", "description": "Number of recommendations in this batch. Defaults to the project's configured batch size."},
        "planner_name": {
            "type": "string",
            "enum": ["atlas", "chunked_gp", "random"],
            "description": "Defaults to the project's configured planner. To change it for good, use update_project_config.",
        },
        "controller_mode": {
            "type": "string",
            "enum": ["agentic", "bo_only"],
            "description": (
                "Leave unset to use the project's own setting (see project_summary). Set it only to override "
                "for this ask, e.g. 'bo_only' to skip the LLM: an unset value must not be replaced with "
                "'agentic', because that would override a project deliberately set to 'bo_only'."
            ),
        },
        "agent_config_path": {"type": "string"},
        "planner_use_descriptors": {"type": "boolean"},
        "full": _FULL_PROPERTY,
        "others_project_ok": _OTHERS_OK_PROPERTY,
        "allow_pending": {
            "type": "boolean",
            "description": (
                "By default this tool refuses to generate a new batch while the project's latest batch "
                "still has pending (not yet completed/failed/skipped) recommendations -- submit their "
                "results with tell_results first. Set true to force a new batch anyway."
            ),
        },
    },
    "required": ["project_id"],
}


@tool(
    "ask_recommendations",
    (
        "Generate the next batch of candidate experiment recommendations for a TRACE Lab project -- covers "
        "both the first batch and every later round; there is no separate 'next round' tool. Refuses by "
        "default if the project's latest batch has unresolved (pending) recommendations: gather each "
        "pending recommendation's outcome from the user first (status completed/failed/skipped, plus the "
        "objective value for completed ones) and submit it with tell_results before calling this again. "
        "Failed and skipped conditions are not proposed again. With chunked_gp each recommendation has "
        "`model_estimate` {predicted, uncertainty (1 sd)} and `proposed_by` (ei/ucb): use them to explain why "
        "a candidate was recommended. `planner_switched` means TRACE ran chunked_gp instead of the project's "
        "Atlas because the design space is too large for Atlas: tell the user in one sentence."
    ),
    _ASK_SCHEMA,
)
async def ask_recommendations(args: dict) -> dict:
    async def _do():
        project_id = _require_project_id(args)
        encoded = quote(project_id, safe="")
        _guard_owner(args, project_id, "ask_recommendations (it adds a batch)")
        if not bool(args.get("allow_pending", False)):
            pending = await _pending_recommendation_ids(project_id)
            if pending:
                shown = ", ".join(pending[:10])
                more = "" if len(pending) <= 10 else f", ... ({len(pending)} total)"
                raise ValueError(
                    "Pending recommendations exist for this project: "
                    f"{shown}{more}. Submit their results with tell_results before asking again, "
                    "or pass allow_pending=true."
                )
        payload: dict[str, Any] = {}
        for key in ("batch_size", "planner_name", "agent_config_path", "planner_use_descriptors", "controller_mode"):
            if args.get(key) not in (None, ""):
                payload[key] = args[key]
        llm = _user_llm()
        if llm:
            payload["llm"] = llm  # agentic mode then runs on the user's own key; never echoed back
        # Acquisition search over a large design space can legitimately take many minutes
        # (observed up to ~13 min) -- a shorter timeout here would abandon the request
        # client-side while the server keeps computing, and a subsequent retry can then race
        # the still-running attempt over the same project's log file.
        data = _mark_llm_key(await _request("POST", f"/api/projects/{encoded}/ask", payload, timeout=1200.0), bool(llm))
        if bool(args.get("full", False)):
            # The batch exists now: an oversized answer falls back to the compact view instead of failing.
            return _full_or_compact(data, _slim_ask, "batch", "Use get_trace(round_id, recommendation_id) for the reasoning.")
        return _slim_ask(data)

    return await _run(_do)


_TELL_RESULTS_SCHEMA = {
    "type": "object",
    "properties": {
        "project_id": {"type": "string"},
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "recommendation_id": {"type": "string"},
                    "status": {"type": "string", "enum": ["completed", "failed", "skipped"]},
                    "failure_reason": {"type": "string"},
                    "notes": {"type": "string"},
                    "observed_at": {"type": "string"},
                    "stage": {"type": "string"},
                    "chemist_override": {"type": "string"},
                },
                "required": ["recommendation_id", "status"],
                "additionalProperties": True,
            },
            "description": (
                "Result rows as JSON objects. status='completed' requires the objective value as an extra "
                'field (e.g. "yield": 82.4); status=\'failed\'/\'skipped\' should include failure_reason. A failed '
                "run that was measured (e.g. no product: yield 0) also gets its value, which the model learns from; "
                "leave it out when nothing was measured (e.g. an equipment problem). Provide this OR results_csv, "
                "not both."
            ),
        },
        "results_file": {
            "type": "string",
            "description": ("Absolute path of an uploaded results CSV (columns recommendation_id,status,<objective>,"
                            "failure_reason,notes). " + _FILE_HINT + " Give exactly one of results, results_csv, results_file."),
        },
        "results_csv": {
            "type": "string",
            "description": (
                "Raw CSV text with columns recommendation_id,status,<objective>,failure_reason,notes. "
                "Only for results the user typed, not for an uploaded file."
            ),
        },
        "others_project_ok": _OTHERS_OK_PROPERTY,
        "defer_reflection": {
            "type": "boolean",
            "description": "Skip the synchronous LLM reflection pass on submitted results. Defaults to false.",
        },
    },
    "required": ["project_id"],
}


@tool(
    "tell_results",
    (
        "Submit real experiment outcomes for a TRACE Lab project's pending recommendations, feeding them "
        "back into the model that generates the next batch. Every pending recommendation from the latest "
        "batch must be included -- gather each one's status from the user first (completed with the "
        "objective value, e.g. yield; or failed/skipped with a reason, plus the value if a failed run was "
        "measured). Failed and skipped conditions are not proposed again. Rejected without calling the API "
        "if any pending recommendation_id is missing from results/results_csv."
    ),
    _TELL_RESULTS_SCHEMA,
)
async def tell_results(args: dict) -> dict:
    async def _do():
        project_id = _require_project_id(args)
        _guard_owner(args, project_id, "tell_results")
        results = _pick_rows(args, "results", "results_csv", "results_file")
        pending = await _pending_recommendation_ids(project_id)
        if pending:
            submitted_ids = {str(row.get("recommendation_id", "")).strip() for row in results}
            missing = [rec_id for rec_id in pending if rec_id not in submitted_ids]
            if missing:
                shown = ", ".join(missing[:10])
                more = "" if len(missing) <= 10 else f", ... ({len(missing)} total)"
                raise ValueError(
                    "Missing outcomes for pending recommendations: "
                    f"{shown}{more}. Every pending recommendation from the latest batch must be included "
                    "in results/results_csv before submitting."
                )
        payload: dict[str, Any] = {"results": results, "defer_reflection": bool(args.get("defer_reflection", False))}
        llm = _user_llm()
        if llm:
            payload["llm"] = llm  # the reflection pass runs on the user's own key too
        # Same rationale as create_project/ask_recommendations above: the LLM reflection pass
        # triggered here can run long, and a premature client-side timeout risks a retry
        # racing a still-running attempt.
        data = await _request("POST", f"/api/projects/{quote(project_id, safe='')}/tell", payload, timeout=1200.0)
        return _mark_llm_key(data, bool(llm))

    return await _run(_do)


@tool(
    "get_recommendations",
    (
        "Get a project's recommendation batches with each recommendation's status and result. By default only the "
        "latest batch (or the batch `round_id`) is returned, without the decision traces (use get_trace for the "
        "reasoning); `rounds` lists every round id. full=true returns all batches with their traces (very large)."
    ),
    {"type": "object", "properties": {"project_id": {"type": "string"}, "round_id": {"type": "string"}, "full": _FULL_PROPERTY},
     "required": ["project_id"]},
)
async def get_recommendations(args: dict) -> dict:
    async def _do():
        project_id = _require_project_id(args)
        data = await _request("GET", f"/api/projects/{quote(project_id, safe='')}/recommendations")
        if not isinstance(data, dict):
            return data
        wanted = str(args.get("round_id") or "").strip()
        rounds = [str(batch.get("round_id")) for batch in data.get("batches", []) if isinstance(batch, dict)]
        if wanted and wanted not in rounds:
            raise ValueError(f"No batch `{wanted}`. Existing rounds: {', '.join(rounds) or 'none'}.")

        def compact(value):
            batches = [batch for batch in value.get("batches", []) if isinstance(batch, dict)]
            batches = [batch for batch in batches if str(batch.get("round_id")) == wanted] if wanted else batches[-1:]
            return {
                "rounds": rounds,
                "batches": [
                    {**{key: item for key, item in batch.items() if key not in ("recommendations", "trace_records")},
                     "recommendations": [_slim_recommendation(rec) for rec in batch.get("recommendations", [])]}
                    for batch in batches
                ],
            }

        if bool(args.get("full", False)):
            if wanted:
                data = {**data, "batches": [b for b in data.get("batches", []) if str(b.get("round_id")) == wanted]}
            return _full_or_compact(data, compact, "recommendation history",
                                    f"Read the batches one at a time with round_id ({', '.join(rounds)}); "
                                    "get_trace has the reasoning.")
        return compact(data)

    return await _run(_do)


@tool(
    "get_observations",
    ("Get the observations (completed, failed and skipped) recorded for a TRACE Lab project, with counts per status. "
     "Returns the latest 50 by default; pass offset/limit to read other rows."),
    {"type": "object", "properties": {"project_id": {"type": "string"}, "offset": {"type": "integer"},
                                      "limit": {"type": "integer"}}, "required": ["project_id"]},
)
async def get_observations(args: dict) -> dict:
    async def _do():
        project_id = _require_project_id(args)
        data = await _request("GET", f"/api/projects/{quote(project_id, safe='')}/observations")
        rows = [row for row in (data or {}).get("observations", []) if isinstance(row, dict)] if isinstance(data, dict) else []
        if not isinstance(data, dict):
            return data
        limit = max(int(args.get("limit") or 50), 1)
        offset = int(args["offset"]) if args.get("offset") is not None else max(len(rows) - limit, 0)
        offset = min(max(offset, 0), len(rows))
        shown = rows[offset:offset + limit]
        result = {**{k: v for k, v in data.items() if k != "observations"},
                  "observation_count": len(rows),
                  "status_counts": dict(Counter(str(row.get("status") or "") for row in rows)),
                  "offset": offset, "observations": shown}
        if len(shown) < len(rows):
            result["note"] = (f"Rows {offset + 1}-{offset + len(shown)} of {len(rows)}; "
                              "pass offset/limit for the others.")
        return result

    return await _run(_do)


@tool(
    "get_evidence",
    (
        "Get the literature/domain-knowledge evidence cards TRACE Lab holds for a project. Cards are shortened by "
        "default (id, mapping status, source, scope, first part of the summary); pass `card_ids` to get those cards "
        "in full, or full=true for every card completely; the listing shows 12 cards at a time (offset/limit). To see which cards the agent is actually shown in ask, use "
        "evidence_preview."
    ),
    {"type": "object", "properties": {"project_id": {"type": "string"},
                                      "card_ids": {"type": "array", "items": {"type": "string"}},
                                      "offset": {"type": "integer"}, "limit": {"type": "integer"},
                                      "full": _FULL_PROPERTY}, "required": ["project_id"]},
)
async def get_evidence(args: dict) -> dict:
    async def _do():
        project_id = _require_project_id(args)
        data = await _request("GET", f"/api/projects/{quote(project_id, safe='')}/evidence")
        if not isinstance(data, dict):
            return data
        cards = [card for card in data.get("cards", []) if isinstance(card, dict)]
        wanted = [str(item) for item in (args.get("card_ids") or [])]
        if wanted:
            data = {**{k: v for k, v in data.items() if k != "cards"},
                    "cards": [c for c in cards if str(c.get("card_id")) in wanted]}
            cards = data["cards"]
        offset = max(int(args.get("offset") or 0), 0)
        limit = max(int(args.get("limit") or 12), 1)

        def compact(value):
            shown = cards[offset:offset + limit]
            note = "Cards are shortened; pass card_ids for full cards."
            if offset + limit < len(cards):
                note += (f" Showing {offset + 1}-{offset + len(shown)} of {len(cards)}; "
                         f"pass offset={offset + limit} for the next ones.")
            return {**{k: v for k, v in value.items() if k != "cards"}, "cards": [_slim_card(card) for card in shown],
                    "note": note}

        if bool(args.get("full", False)) or wanted:
            return _full_or_compact(data, compact, "evidence card set",
                                    "Pass up to about 10 card_ids at a time for full cards.")
        return compact(data)

    return await _run(_do)


@tool(
    "evidence_preview",
    (
        "Show which evidence cards the decision agent is actually given in ask for this project (top-k, each card "
        "cut to the prompt length limit) and why each of the other cards never appears (outranked, duplicate "
        "summary, no matching variable...). Call it after import_evidence or after changing evidence_selection: "
        "a narrow card often does not make the top 5 in a project that already has broad cards. Report `warnings` "
        "to the user; do not guess which cards are read."
    ),
    {"type": "object", "properties": {"project_id": {"type": "string"}}, "required": ["project_id"]},
)
async def evidence_preview(args: dict) -> dict:
    async def _do():
        project_id = _require_project_id(args)
        return _slim_preview(await _request("GET", _project_path(project_id, "/evidence/preview"), timeout=60.0))

    return await _run(_do)


@tool(
    "get_trace",
    (
        "Get the full decision trace for one round of a TRACE Lab project -- every reasoning step "
        "(stagnation diagnosis, hypothesis, evidence citations) behind that round's recommendations. Use "
        "when the user asks why a candidate was recommended. Long texts and lists are cut by default (full=true for everything)."
    ),
    {"type": "object", "properties": {"project_id": {"type": "string"}, "round_id": {"type": "string"},
                                      "recommendation_id": {"type": "string", "description": "Only this recommendation's trace."},
                                      "full": _FULL_PROPERTY},
     "required": ["project_id", "round_id"]},
)
async def get_trace(args: dict) -> dict:
    async def _do():
        project_id = _require_project_id(args)
        round_id = str(args.get("round_id", "")).strip()
        if not round_id:
            raise ValueError("round_id is required.")
        data = await _request(
            "GET",
            f"/api/projects/{quote(project_id, safe='')}/trace/{quote(round_id, safe='')}",
        )
        wanted = str(args.get("recommendation_id") or "").strip()
        if wanted and isinstance(data, dict) and isinstance(data.get("trace"), list):
            data = {**data, "trace": [r for r in data["trace"] if isinstance(r, dict) and str(r.get("recommendation_id")) == wanted]}
        if bool(args.get("full", False)):
            return _full_or_compact(data, _slim_trace, "trace",
                                    "Pass recommendation_id to read one candidate's full trace." if not wanted else
                                    "This candidate's full trace is too large; the compact view keeps its reasoning.")
        return _slim_trace(data)

    return await _run(_do)


@tool(
    "reset_project",
    (
        "Clear a TRACE Lab project's run state (recommendations, traces, observations) while keeping its "
        "config, design space, and evidence cards. Destructive -- confirm with the user before calling, and name "
        "the project's owner when it is not the user's own (project_summary shows `owner`)."
    ),
    {"project_id": str, "backup": bool, "keep_historical": bool, "others_project_ok": bool},
)
async def reset_project(args: dict) -> dict:
    async def _do():
        project_id = _require_project_id(args)
        _guard_owner(args, project_id, "reset_project")
        payload = {
            "backup": bool(args.get("backup", True)),
            "keep_historical": bool(args.get("keep_historical", False)),
        }
        return await _request("POST", f"/api/projects/{quote(project_id, safe='')}/reset", payload)

    return await _run(_do)


@tool(
    "check_project",
    (
        "Check a TRACE Lab project's files for problems and get its key facts: errors (must be fixed "
        "before asking), warnings (e.g. Atlas on a very large design space, evidence cards that can never "
        "be shown), and facts such as the number of design combinations, observations, pending "
        "recommendations and evidence cards. Call it right after create_project, and whenever a project "
        "behaves unexpectedly or runs slowly."
    ),
    {"project_id": str},
)
async def check_project(args: dict) -> dict:
    async def _do():
        project_id = _require_project_id(args)
        # Parsing a very large design space is slow; a short timeout would just invite a retry.
        return await _request("GET", _project_path(project_id, "/check"), timeout=300.0)

    return await _run(_do)


_UPDATE_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "project_id": {"type": "string"},
        "settings": {
            "type": "object",
            "description": (
                "Settings to change, e.g. {\"planner_name\": \"chunked_gp\"}. Editable: reaction_name, "
                "reaction_scope, planner_name, acquisition_function, planner_options, controller_mode, "
                "agent_config_path, batch_size, seed, planner_use_descriptors, allow_random_fallback, "
                "repeat_failed_conditions (true lets skipped and unmeasured failed conditions be proposed again), "
                "evidence_selection. project_id, objective_name and goal cannot be changed. Existing "
                "observations and recommendation batches are untouched. evidence_selection is 'score' "
                "(default: cards ranked by score) or 'per_variable' (each optimized variable first gets its "
                "most specific evidence card); change it only when the user asks, because it changes which "
                "evidence the decision agent reads."
            ),
        },
        "others_project_ok": _OTHERS_OK_PROPERTY,
    },
    "required": ["project_id", "settings"],
}


@tool(
    "update_project_config",
    (
        "Change an existing project's settings without recreating it -- most importantly switch a large "
        "project from Atlas to chunked_gp, or set controller_mode/batch_size/seed. Returns which settings "
        "changed. Refused (HTTP 409) while an ask is running for the project: wait for it to finish, do not "
        "retry in a loop."
    ),
    _UPDATE_CONFIG_SCHEMA,
)
async def update_project_config(args: dict) -> dict:
    async def _do():
        project_id = _require_project_id(args)
        _guard_owner(args, project_id, "update_project_config")
        settings = _settings_arg(args)
        return await _request("PATCH", _project_path(project_id, "/config"), settings)

    return await _run(_do)


_ADD_DESCRIPTOR_TABLE_SCHEMA = {
    "type": "object",
    "properties": {
        "project_id": {"type": "string"},
        "variable": {"type": "string", "description": "Design variable the table describes, e.g. 'Additive'."},
        "value_column": {"type": "string", "description": "Table column holding the option names."},
        "file": {"type": "string", "description": "Absolute path of the uploaded table (preferred). " + _FILE_HINT},
        "csv": {"type": "string", "description": "Raw CSV text: one row per option plus numeric descriptor columns (only without an uploaded file)."},
        "aliases": {
            "type": "object",
            "additionalProperties": {"type": "string"},
            "description": (
                "{design option: name used in the table}. Only for options the user has confirmed are the "
                "same substance; nothing is matched loosely."
            ),
        },
        "replace": {
            "type": "boolean",
            "description": "Drop the variable's existing descriptors first. Without it, a column that already exists is an error.",
        },
        "others_project_ok": _OTHERS_OK_PROPERTY,
    },
    "required": ["project_id", "variable", "value_column"],
}


@tool(
    "add_descriptor_table",
    (
        "Attach a per-option numeric descriptor table to one variable of an existing project (needed for "
        "planner_use_descriptors). Every option of the variable must find a row -- by exact name or an "
        "alias the user has confirmed -- and options must not end up with identical descriptors; otherwise "
        "nothing is changed and the error lists the unmatched options. Do not loosen the request or guess "
        "aliases to make it pass: show the user the list. The old design_space.csv is backed up."
    ),
    _ADD_DESCRIPTOR_TABLE_SCHEMA,
)
async def add_descriptor_table(args: dict) -> dict:
    async def _do():
        project_id = _require_project_id(args)
        _guard_owner(args, project_id, "add_descriptor_table")
        table = _check_descriptor_tables(
            [{key: args.get(key) for key in ("variable", "value_column", "file", "csv", "aliases") if args.get(key) is not None}]
        )[0]
        payload = dict(table, replace=bool(args.get("replace", False)))
        payload["csv"] = payload["csv"].lstrip("﻿")
        return await _request("POST", _project_path(project_id, "/descriptors"), payload, timeout=300.0)

    return await _run(_do)


_IMPORT_EVIDENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "project_id": {"type": "string"},
        "file": {
            "type": "string",
            "description": ("Absolute path of the uploaded evidence file (.jsonl or .csv), or a snapshot_file from an "
                            "earlier import_evidence. Always use this for a file: the cards are imported exactly as "
                            "the file holds them. Give exactly one of file, cards, jsonl, csv."),
        },
        "cards": {
            "type": "array",
            "items": {"type": "object"},
            "description": "Evidence cards as JSON objects, only for cards written in this chat (not for a file).",
        },
        "jsonl": {"type": "string", "description": "Evidence cards as JSON Lines text, only when there is no file."},
        "csv": {"type": "string", "description": "Evidence cards as CSV text, only when there is no file."},
        "mode": {
            "type": "string",
            "enum": ["append", "replace"],
            "description": "'append' (default) adds to the existing cards; 'replace' swaps them all. The old file is backed up.",
        },
        "others_project_ok": _OTHERS_OK_PROPERTY,
    },
    "required": ["project_id"],
}


@tool(
    "import_evidence",
    (
        "Add (or replace) literature/domain-knowledge evidence cards for a project. Validated strictly and "
        "all-or-nothing: every card needs a unique card_id and a non-empty summary, and mapping_status must "
        "be one of direct, same_start_end, same_reaction_family, variable_level, background, out_of_scope -- "
        "anything else is an error, never silently changed. The error lists every problem card. For a file the "
        "user uploaded, pass its path in `file`. Before importing, the current cards are saved to `snapshot_file`; "
        "to undo, import_evidence(file=<snapshot_file>, mode=\"replace\"). Use get_evidence afterwards to see what is stored."
    ),
    _IMPORT_EVIDENCE_SCHEMA,
)
async def import_evidence(args: dict) -> dict:
    async def _do():
        project_id = _require_project_id(args)
        _guard_owner(args, project_id, "import_evidence")
        payload = _pick_evidence(args)
        if isinstance(payload.get("jsonl"), str):
            payload["jsonl"] = payload["jsonl"].lstrip("﻿")
        if isinstance(payload.get("csv"), str):
            payload["csv"] = payload["csv"].lstrip("﻿")
        payload["mode"] = str(args.get("mode") or "append")
        snapshot = await _snapshot_evidence(project_id)
        result = await _request("POST", _project_path(project_id, "/evidence/import"), payload, timeout=60.0)
        if snapshot and isinstance(result, dict):
            result = {**result, "snapshot_file": snapshot,
                      "undo": f"import_evidence(project_id=\"{project_id}\", file=\"{snapshot}\", mode=\"replace\")"}
        return result

    return await _run(_do)


async def _snapshot_evidence(project_id: str) -> str | None:
    """Save the project's current cards as JSONL in the user's workspace, so an import can be undone exactly
    (TRACE's own backup lives on the server where the chat cannot reach it). None when there is nothing to save."""
    if not FOUNDRYCLAW_USER_ID:
        return None
    data = await _request("GET", _project_path(project_id, "/evidence"))
    cards = [card for card in (data or {}).get("cards", []) if isinstance(card, dict)] if isinstance(data, dict) else []
    if not cards:
        return None
    workdir, _ = _import_roots()
    folder = workdir / "trace_projects" / "_evidence_snapshots"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{project_id}_{datetime.now():%Y%m%d_%H%M%S_%f}.jsonl"
    path.write_text("".join(json.dumps(card, ensure_ascii=False) + "\n" for card in cards), encoding="utf-8")
    return str(path)


# --- Importing an existing project -----------------------------------------------------------------
_HANDLE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")  # TRACE's own handle rule
_UPLOAD_COPY_SUFFIX = re.compile(r"\s*[（(]\d+[）)](?=\.[^.]+$)")  # "design_space（1）.csv" from a repeated upload
_SKIP_WHEN_COPYING = shutil.ignore_patterns(".git", "__pycache__", "*.lock", ".DS_Store", "__MACOSX")


def _import_roots() -> tuple[Path, list[Path]]:
    """(the user's workspace, the folders this user may import from)."""
    if not FOUNDRYCLAW_USER_ID:
        raise ValueError("import_project needs the chat user's workspace, which is only known inside a FounDryClaw chat.")
    from app.services.storage_paths import agent_workdir_for_user, files_dir_for_user

    workdir = agent_workdir_for_user(FOUNDRYCLAW_USER_ID).resolve()
    roots = [workdir, files_dir_for_user(FOUNDRYCLAW_USER_ID).resolve()]
    roots += [Path(item).expanduser().resolve()
              for item in os.getenv("TRACE_IMPORT_ALLOWED_ROOTS", "").split(os.pathsep) if item.strip()]
    return workdir, roots


def _importable(path_value: Any, roots: list[Path]) -> Path:
    path = Path(str(path_value or "")).expanduser()
    if not str(path_value or "").strip() or not path.is_absolute():
        raise ValueError(f"Give the absolute path of the uploaded file or folder, not `{path_value}`.")
    path = path.resolve()
    if not any(path == root or root in path.parents for root in roots):
        raise ValueError(
            f"{path} is outside the folders this chat can import from: the user's uploads and workspace"
            + (" and TRACE_IMPORT_ALLOWED_ROOTS" if os.getenv("TRACE_IMPORT_ALLOWED_ROOTS") else "")
            + ". Upload the project files (or a .zip of the project folder) into the chat first.")
    if not path.exists():
        raise ValueError(f"{path} does not exist.")
    return path


def _nested_projects(folder: Path) -> list[str]:
    return sorted(str(item.parent) for item in folder.rglob("project.yaml") if item.parent != folder)[:10]


def _stage_project(destination: Path, source: Any, files: Any, named_files: Any, roots: list[Path]) -> list[str]:
    """Copy the project into `destination` (a new folder); the source is only read."""
    destination.mkdir(parents=True)
    if source:
        origin = _importable(source, roots)
        if origin.is_dir():
            if not (origin / "project.yaml").exists() and _nested_projects(origin):
                raise ValueError(f"{origin} holds several projects; import one of them as `source`: "
                                 + ", ".join(_nested_projects(origin)))
            shutil.copytree(origin, destination, dirs_exist_ok=True, ignore=_SKIP_WHEN_COPYING)
        elif origin.suffix.lower() == ".zip":
            _extract_zip(origin, destination)
        else:
            raise ValueError(f"`source` must be a project folder or a .zip of one, not {origin.name}; "
                             "pass single files in `files`.")
    items = [(_UPLOAD_COPY_SUFFIX.sub("", Path(str(path)).name), path) for path in (files or [])]
    items += list(dict(named_files or {}).items())
    if items:
        for name, path in items:
            origin = _importable(path, roots)
            name = Path(str(name)).name
            if not origin.is_file() or not name:
                raise ValueError(f"{origin} is not a file.")
            if (destination / name).exists():
                raise ValueError(f"Two files would both be `{name}`; pass them in `named_files` "
                                 "({file name: path}) to say which upload is which.")
            shutil.copy2(origin, destination / name)
    if not source and not items:
        raise ValueError("Give `source` (a project folder or .zip) or `files` (the uploaded project files).")
    return sorted(str(path.relative_to(destination)).replace("\\", "/")
                  for path in destination.rglob("*") if path.is_file())


def _extract_zip(archive_path: Path, destination: Path) -> None:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = [name for name in archive.namelist()
                     if not name.endswith("/") and not name.startswith("__MACOSX/")]
            tops = {name.split("/", 1)[0] for name in names}
            strip = len(tops) == 1 and all("/" in name for name in names)  # a zipped folder: drop its name
            for name in names:
                relative = name.split("/", 1)[1] if strip else name
                target = (destination / relative).resolve()
                if destination.resolve() not in target.parents:
                    raise ValueError(f"Unsafe path in the zip: {name}")
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name) as source, open(target, "wb") as sink:
                    shutil.copyfileobj(source, sink)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"{archive_path.name} is not a readable zip file: {exc}") from exc
    if not (destination / "project.yaml").exists() and _nested_projects(destination):
        raise ValueError("The zip holds several projects; zip one project folder: "
                         + ", ".join(Path(path).name for path in _nested_projects(destination)))


def _write_project_yaml(destination: Path, handle: str, settings: dict[str, Any]) -> str:
    """A minimal project.yaml for uploaded data files that came without one."""
    if not str(settings.get("objective_name") or "").strip():
        raise ValueError("No project.yaml among the files. Pass `settings` with at least objective_name (the "
                         "observations column that holds the result, e.g. lactone_yield); goal, batch_size, "
                         "planner_name, controller_mode, planner_use_descriptors and reaction_scope are optional.")
    values = {"project_id": handle, "planner_name": "chunked_gp"}
    for key in ("reaction_name", "objective_name", "goal", "batch_size", "planner_name", "acquisition_function",
                "controller_mode", "planner_use_descriptors", "reaction_scope", "seed", "evidence_selection"):
        if settings.get(key) not in (None, ""):
            values[key] = settings[key]
    # JSON scalars are valid YAML scalars, so no YAML library is needed here.
    (destination / "project.yaml").write_text(
        "".join(f"{key}: {json.dumps(value, ensure_ascii=False)}\n" for key, value in values.items()), encoding="utf-8")
    return "project.yaml written from `settings` (the files had none)"


def _set_top_level_key(destination: Path, key: str, value: str) -> None:
    path = destination / "project.yaml"
    text = path.read_text(encoding="utf-8")
    backup = destination / "_backups" / f"project.yaml.before-import-{datetime.now():%Y%m%d_%H%M%S}"
    if not backup.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(text, encoding="utf-8")
    line = f"{key}: {json.dumps(value)}"
    pattern = re.compile(rf"^{re.escape(key)}:.*$", re.MULTILINE)
    text = pattern.sub(line, text, count=1) if pattern.search(text) else text.rstrip("\n") + f"\n{line}\n"
    path.write_text(text, encoding="utf-8")


def _repair_imported_config(destination: Path, report: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Fix what project.yaml carries over from the server it came from. Returns (repairs, keys to drop)."""
    repairs: list[str] = []
    drop: list[str] = []
    for problem in report.get("errors") or []:
        message = str((problem or {}).get("message") or "")
        if message.startswith("Unknown setting"):
            drop += re.findall(r"`([^`]+)`", message.split("(", 1)[0])
        elif message.startswith("Agent config `"):
            old = message.split("`")[1]
            new = "agent_bo.yaml" if (destination / "agent_bo.yaml").is_file() else "configs/agent_bo.yaml"
            _set_top_level_key(destination, "agent_config_path", new)
            repairs.append(f"agent_config_path `{old}` does not exist on this server; set to `{new}`"
                           + (" (the project's own agent config)" if new == "agent_bo.yaml" else " (TRACE's default)"))
    return repairs, list(dict.fromkeys(drop))


def _blocking_errors(report: dict[str, Any], dropped: list[str]) -> list[dict[str, Any]]:
    return [problem for problem in report.get("errors") or []
            if not (dropped and str((problem or {}).get("message") or "").startswith("Unknown setting"))]


def _import_next_steps(summary: dict[str, Any], warnings: list[Any]) -> list[str]:
    steps = []
    if any("Atlas on" in str((item or {}).get("message", "")) for item in warnings):
        steps.append("The design space is large for Atlas: switch with update_project_config "
                     "settings={\"planner_name\": \"chunked_gp\"} before asking.")
    if summary.get("pending_recommendation_count"):
        steps.append("The imported project has a pending batch (recommendations without results): collect the results "
                     "and submit them with tell_results, or ask the user whether that batch was never run.")
    steps.append("Tell the user in Chinese what was imported (observations, rounds, evidence cards, repairs, warnings), "
                 "then continue with ask_recommendations.")
    return steps


_IMPORT_PROJECT_SCHEMA = {
    "type": "object",
    "properties": {
        "project_id": {"type": "string",
                       "description": "New handle for the imported project: letters, digits, '-' or '_' (e.g. bbb_lactonization)."},
        "source": {"type": "string",
                   "description": ("Absolute path of the project folder (with project.yaml, design_space.csv, observations.csv, "
                                   "evidence cards, recommendations_round_*, trace_round_* ...) or of a .zip of that folder, "
                                   "as given in the upload note.")},
        "files": {
            "type": "array", "items": {"type": "string"},
            "description": ("Instead of (or in addition to) `source`: absolute paths of the uploaded project files. "
                            "A repeated upload's suffix such as design_space（1）.csv is dropped automatically."),
        },
        "named_files": {
            "type": "object", "additionalProperties": {"type": "string"},
            "description": ("Uploaded files under the name they need in the project, {file name: path}, when two uploads "
                            "would get the same name, e.g. {\"design_space.csv\": \".../design_space（2）.csv\"}."),
        },
        "settings": {
            "type": "object",
            "description": ("Only when the files include no project.yaml: objective_name (required), goal, batch_size, "
                            "planner_name (default chunked_gp), controller_mode, planner_use_descriptors, reaction_scope."),
        },
        "dry_run": {"type": "boolean", "description": "Only check (and report repairs); import nothing. Defaults to false."},
    },
    "required": ["project_id"],
}


@tool(
    "import_project",
    (
        "Import an existing TRACE project (a folder or .zip from another TRACE server, or its uploaded files) with its "
        "whole history: observations, earlier recommendation batches and traces. Use it instead of create_project "
        "whenever the user brings a project that already has a project.yaml or history -- nothing is retyped, so large "
        "design spaces and evidence files come in unchanged. The files are copied into the user's workspace "
        "(trace_projects/<project_id>/); the source is never modified. A stale agent_config_path and settings this TRACE "
        "version does not know are repaired automatically and reported; anything else the project check finds is returned "
        "as an error list and nothing is imported. Report the warnings (evidence cards treated as background, Atlas on a "
        "large space...) to the user."
    ),
    _IMPORT_PROJECT_SCHEMA,
)
async def import_project(args: dict) -> dict:
    async def _do():
        handle = str(args.get("project_id") or "").strip()
        if not _HANDLE_PATTERN.match(handle):
            raise ValueError(f"Invalid project_id `{handle}`: use letters, digits, '-' or '_', starting with a letter or digit.")
        workdir, roots = _import_roots()
        destination = workdir / "trace_projects" / handle
        if destination.exists():
            raise ValueError(f"{destination} already exists. Choose another project_id, or unregister_project "
                             f"`{handle}` with delete_files=true first.")
        dry_run = bool(args.get("dry_run", False))
        try:
            try:
                files = _stage_project(destination, args.get("source"), args.get("files"),
                                       args.get("named_files"), roots)
            except OSError as exc:
                raise ValueError(f"Could not copy the project files: {exc}") from exc
            repairs: list[str] = []
            if not (destination / "project.yaml").exists():
                repairs.append(_write_project_yaml(destination, handle, dict(args.get("settings") or {})))
            report = await _request("POST", "/api/projects/check", {"path": str(destination)}, timeout=120.0)
            fixed, drop = _repair_imported_config(destination, report)
            repairs += fixed
            if fixed:
                report = await _request("POST", "/api/projects/check", {"path": str(destination)}, timeout=120.0)
            errors = _blocking_errors(report, drop)
            if errors:
                raise ValueError("The project did not pass TRACE's project check; nothing was imported:\n"
                                 + "\n".join(f"- {item.get('file', '')}: {item.get('message', '')}" for item in errors))
            if dry_run:
                shutil.rmtree(destination, ignore_errors=True)
                return {"dry_run": True, "project_id": handle, "would_import_files": files, "repairs": repairs,
                        "drop_settings": drop, "warnings": report.get("warnings", []), "facts": report.get("facts", {})}
            registered = await _request("POST", "/api/projects/register",
                                        {"path": str(destination), "handle": handle, "drop_config_keys": drop},
                                        timeout=120.0)
        except BaseException:
            shutil.rmtree(destination, ignore_errors=True)
            raise
        check = registered.get("check") or {}
        _record_owner(handle, "import_project")
        summary = _slim_project_entry(await _request("GET", _project_path(handle)))
        if drop:
            repairs.append(f"removed settings this TRACE version does not use: {', '.join(drop)} "
                           f"(original project.yaml kept in {registered.get('config_backup_path') or '_backups/'})")
        return {"imported": True, "project_id": handle, "project_dir": str(destination), "files": files,
                "repairs": repairs, "warnings": check.get("warnings", []), "facts": check.get("facts", {}),
                "summary": summary, "next": _import_next_steps(summary, check.get("warnings", []))}

    return await _run(_do)


@tool(
    "unregister_project",
    (
        "Remove an imported project (see import_project) from TRACE Lab. Its files stay in the user's workspace unless "
        "delete_files=true, which deletes the copy made by import_project (only folders under the user's "
        "trace_projects/). Confirm with the user before deleting files."
    ),
    {"type": "object", "properties": {"project_id": {"type": "string"}, "delete_files": {"type": "boolean"},
                                      "others_project_ok": _OTHERS_OK_PROPERTY},
     "required": ["project_id"]},
)
async def unregister_project(args: dict) -> dict:
    async def _do():
        handle = _require_project_id(args)
        _guard_owner(args, handle, "unregister_project")
        result = await _request("DELETE", _project_path(handle, "/registration"))
        _forget_owner(handle)
        folder = Path(str(result.get("project_dir") or ""))
        result["files_deleted"] = False
        if args.get("delete_files") and str(folder):
            workdir, _ = _import_roots()
            imports = (workdir / "trace_projects").resolve()
            if imports in folder.resolve().parents:
                shutil.rmtree(folder, ignore_errors=True)
                result["files_deleted"] = True
            else:
                result["note"] = f"{folder} was not created by import_project, so its files were left in place."
        return result

    return await _run(_do)


SERVER = create_sdk_mcp_server(
    name="trace-collab",
    tools=[
        health,
        list_projects,
        project_summary,
        create_project,
        import_observations,
        ask_recommendations,
        tell_results,
        get_recommendations,
        get_observations,
        get_evidence,
        evidence_preview,
        get_trace,
        reset_project,
        check_project,
        update_project_config,
        add_descriptor_table,
        import_evidence,
        import_project,
        unregister_project,
    ],
)
