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
"""

import csv
import io
import json
from typing import Any
from urllib.parse import quote

import httpx
from claude_agent_sdk import create_sdk_mcp_server, tool

from app.core.config import TRACE_LAB_BASE_URL


def _parse_csv_rows(csv_text: str) -> list[dict[str, Any]]:
    text = csv_text.lstrip("\ufeff")
    return list(csv.DictReader(io.StringIO(text)))


def _pick_rows(args: dict, json_key: str, csv_key: str) -> list[dict[str, Any]]:
    json_rows = args.get(json_key)
    csv_text = args.get(csv_key)
    has_json = isinstance(json_rows, list) and len(json_rows) > 0
    has_csv = isinstance(csv_text, str) and bool(csv_text.strip())
    if has_json == has_csv:
        raise ValueError(f"Provide exactly one of {json_key} or {csv_key}.")
    if has_json:
        return [dict(row) for row in json_rows]
    return _parse_csv_rows(csv_text)


async def _request(method: str, path: str, json_body: Any = None, timeout: float = 30.0) -> Any:
    try:
        async with httpx.AsyncClient(base_url=TRACE_LAB_BASE_URL, timeout=timeout) as client:
            response = await client.request(method, path, json=json_body)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        raise RuntimeError(f"HTTP {exc.response.status_code} {method} {path}: {detail}") from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Cannot reach TRACE Lab API at {TRACE_LAB_BASE_URL}: {exc}") from exc
    if not response.text.strip():
        return {}
    return response.json()


def _ok(data: Any) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}]}


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


@tool("health", "Check whether the TRACE Lab API service is reachable and responding.", {})
async def health(args: dict) -> dict:
    async def _do():
        return await _request("GET", "/api/health")

    return await _run(_do)


@tool(
    "list_projects",
    "List every TRACE Lab project that currently exists, with a summary of each (objective, batch size, observation counts, best value so far).",
    {},
)
async def list_projects(args: dict) -> dict:
    async def _do():
        return await _request("GET", "/api/projects")

    return await _run(_do)


@tool(
    "project_summary",
    "Get the full status summary for one TRACE Lab project: objective, active variables, observation and batch counts, current best value, and pending-recommendation count. Check this before generating recommendations to see whether the project already exists and whether a previous batch still needs results submitted.",
    {"project_id": str},
)
async def project_summary(args: dict) -> dict:
    async def _do():
        project_id = _require_project_id(args)
        return await _request("GET", f"/api/projects/{quote(project_id, safe='')}")

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
                "planner_use_descriptors=true was requested. Use design_records_csv instead whenever "
                "descriptor columns are present. Provide this OR design_records_csv, not both."
            ),
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
        "planner_name": {"type": "string", "description": "Optimizer name: 'atlas' or 'random'. Defaults to 'atlas'."},
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
                "'bo_only' when no OPENAI_API_KEY is configured for the TRACE Lab service, or for debugging."
            ),
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
    },
    "required": ["project_id"],
}


@tool(
    "create_project",
    (
        "Create a new TRACE Lab project from a design-space definition. Use this the first time a user "
        "provides a design-space CSV (or equivalent JSON records) for a reaction -- not on every round; "
        "check an existing project with project_summary instead of recreating it."
    ),
    _CREATE_PROJECT_SCHEMA,
)
async def create_project(args: dict) -> dict:
    async def _do():
        project_id = _require_project_id(args)
        design_records = _pick_rows(args, "design_records", "design_records_csv")
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
        payload = {
            "project_id": project_id,
            "config": config,
            "design_records": design_records,
            "overwrite": bool(args.get("overwrite", False)),
        }
        # Large/descriptor-heavy design spaces can take a long time to enumerate server-side
        # (observed up to ~13 min); a shorter client-side timeout here would give up and let
        # the model retry into an overlapping second request against the same project.
        return await _request("POST", "/api/projects", payload, timeout=1200.0)

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
        "rows_csv": {
            "type": "string",
            "description": (
                "Raw CSV text of historical experiment results (columns: each design variable, the "
                "objective e.g. yield, status). Prefer this over rows when the user uploaded a CSV. "
                "Provide this OR rows, not both."
            ),
        },
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
        rows = _pick_rows(args, "rows", "rows_csv")
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
        "planner_name": {"type": "string", "description": "'atlas' or 'random'. Defaults to the project's configured planner."},
        "controller_mode": {"type": "string", "enum": ["agentic", "bo_only"], "description": "Defaults to 'agentic'."},
        "agent_config_path": {"type": "string"},
        "planner_use_descriptors": {"type": "boolean"},
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
        "objective value for completed ones) and submit it with tell_results before calling this again."
    ),
    _ASK_SCHEMA,
)
async def ask_recommendations(args: dict) -> dict:
    async def _do():
        project_id = _require_project_id(args)
        encoded = quote(project_id, safe="")
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
        for key in ("batch_size", "planner_name", "agent_config_path", "planner_use_descriptors"):
            if args.get(key) is not None:
                payload[key] = args[key]
        payload["controller_mode"] = args.get("controller_mode") or "agentic"
        # Acquisition search over a large design space can legitimately take many minutes
        # (observed up to ~13 min) -- a shorter timeout here would abandon the request
        # client-side while the server keeps computing, and a subsequent retry can then race
        # the still-running attempt over the same project's log file.
        return await _request("POST", f"/api/projects/{encoded}/ask", payload, timeout=1200.0)

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
                'field (e.g. "yield": 82.4); status=\'failed\'/\'skipped\' should include failure_reason '
                "instead and no objective value. Provide this OR results_csv, not both."
            ),
        },
        "results_csv": {
            "type": "string",
            "description": (
                "Raw CSV text with columns recommendation_id,status,<objective>,failure_reason,notes. "
                "Provide this OR results, not both."
            ),
        },
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
        "objective value, e.g. yield; or failed/skipped with a reason). Rejected without calling the API "
        "if any pending recommendation_id is missing from results/results_csv."
    ),
    _TELL_RESULTS_SCHEMA,
)
async def tell_results(args: dict) -> dict:
    async def _do():
        project_id = _require_project_id(args)
        results = _pick_rows(args, "results", "results_csv")
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
        payload = {"results": results, "defer_reflection": bool(args.get("defer_reflection", False))}
        # Same rationale as create_project/ask_recommendations above: the LLM reflection pass
        # triggered here can run long, and a premature client-side timeout risks a retry
        # racing a still-running attempt.
        return await _request("POST", f"/api/projects/{quote(project_id, safe='')}/tell", payload, timeout=1200.0)

    return await _run(_do)


@tool(
    "get_recommendations",
    "Get every recommendation batch TRACE Lab has generated so far for a project, including each recommendation's status and result.",
    {"project_id": str},
)
async def get_recommendations(args: dict) -> dict:
    async def _do():
        project_id = _require_project_id(args)
        return await _request("GET", f"/api/projects/{quote(project_id, safe='')}/recommendations")

    return await _run(_do)


@tool(
    "get_observations",
    "Get every observation (completed, failed, and skipped) recorded for a TRACE Lab project.",
    {"project_id": str},
)
async def get_observations(args: dict) -> dict:
    async def _do():
        project_id = _require_project_id(args)
        return await _request("GET", f"/api/projects/{quote(project_id, safe='')}/observations")

    return await _run(_do)


@tool(
    "get_evidence",
    "Get the literature/domain-knowledge evidence cards TRACE Lab is using to inform recommendations for a project.",
    {"project_id": str},
)
async def get_evidence(args: dict) -> dict:
    async def _do():
        project_id = _require_project_id(args)
        return await _request("GET", f"/api/projects/{quote(project_id, safe='')}/evidence")

    return await _run(_do)


@tool(
    "get_trace",
    (
        "Get the full decision trace for one round of a TRACE Lab project -- every reasoning step "
        "(stagnation diagnosis, hypothesis, evidence citations) behind that round's recommendations. Use "
        "when the user asks why a candidate was recommended."
    ),
    {"project_id": str, "round_id": str},
)
async def get_trace(args: dict) -> dict:
    async def _do():
        project_id = _require_project_id(args)
        round_id = str(args.get("round_id", "")).strip()
        if not round_id:
            raise ValueError("round_id is required.")
        return await _request(
            "GET",
            f"/api/projects/{quote(project_id, safe='')}/trace/{quote(round_id, safe='')}",
        )

    return await _run(_do)


@tool(
    "reset_project",
    (
        "Clear a TRACE Lab project's run state (recommendations, traces, observations) while keeping its "
        "config, design space, and evidence cards. Destructive -- confirm with the user before calling."
    ),
    {"project_id": str, "backup": bool, "keep_historical": bool},
)
async def reset_project(args: dict) -> dict:
    async def _do():
        project_id = _require_project_id(args)
        payload = {
            "backup": bool(args.get("backup", True)),
            "keep_historical": bool(args.get("keep_historical", False)),
        }
        return await _request("POST", f"/api/projects/{quote(project_id, safe='')}/reset", payload)

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
        get_trace,
        reset_project,
    ],
)
