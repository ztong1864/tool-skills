---
name: trace-collab
description: 操作 TRACE Lab 闭环实验推荐工作流：创建/查询/检查项目（一次上传设计空间、描述符表、历史实验、证据卡，全有或全无）、导入已有项目（文件夹、zip 或上传的项目文件，连同历史推荐批次和 trace）、修改项目设置、补充描述符表、导入证据卡、生成候选推荐（ask）、提交实验结果（tell）、查看推荐/观测/证据/决策 trace，以及重置项目运行状态。
---

# trace-collab (local/in-process tool)

Runs in this backend's own process via `claude_agent_sdk.create_sdk_mcp_server()`, calling
the TRACE Lab API (`TRACE_LAB_BASE_URL`, default `http://127.0.0.1:8788`) over HTTP.
Source: `trace_collab.py` in this same folder, loaded via `backing.json`'s `module_path`.

This replaces `trace-collab-skill` (`skills/Device/XmartChem/.claude/skills/trace-collab-skill`)
for TRACE Lab's ask/tell recommendation loop: instead of a CLI script and local CSV files,
each step (health, list/create/summarize project, import historical observations, ask for
recommendations, tell results, read recommendations/observations/evidence/trace, reset) is
its own tool call, returning structured JSON directly. Design-space, historical-observation,
and result rows can be passed either as JSON or as raw CSV text (parsed server-side), so an
uploaded CSV can be forwarded as-is instead of being retyped as JSON.

Tools (19): `health`, `list_projects`, `project_summary`, `create_project`, `import_project`, `unregister_project`,
`import_observations`,
`ask_recommendations`, `tell_results`, `get_recommendations`, `get_observations`, `get_evidence`,
`evidence_preview`, `get_trace`, `reset_project`, plus `check_project` (errors/warnings/facts), `update_project_config`
(change planner, seed, batch size, controller mode without recreating the project),
`add_descriptor_table` (per-option numeric table for one variable, explicit aliases only) and
`import_evidence` (strictly validated evidence cards).

`create_project` uploads the design space, descriptor tables, historical observations and evidence
cards in one all-or-nothing request. `ask_recommendations` uses the project's own `controller_mode`
unless one is given. API errors are returned as readable lines, not raw JSON. A project's
`project_id` is its handle (see `list_projects`).

`import_project` brings in an existing project (a folder, a .zip of it, or its uploaded files) with its whole
history -- observations, earlier recommendation batches, traces -- without retyping anything, so large design
spaces and evidence files come in unchanged. It copies the files into the chat user's workspace
(`workspace/<device>/<user>/trace_projects/<project_id>/`, never touching the source), repairs a stale
`agent_config_path` and drops settings this TRACE version does not know (both reported), runs TRACE's folder check
and registers the copy in place (`POST /api/projects/register`). Files without a project.yaml need `settings`
(at least `objective_name`). Sources must be inside the user's uploads or workspace, or a folder listed in the
backend env `TRACE_IMPORT_ALLOWED_ROOTS` (os.pathsep-separated, for folders an admin shares on the server).
`unregister_project` removes it from TRACE (and with `delete_files` the copy); for a project made with `create_project` it calls TRACE's `DELETE /api/projects/{id}`, which keeps the folder in the server's `_backups/`. Requirements: TRACE Lab runs on the
same machine as the backend (it reads the copy by path), and `tool_backing_service` sets `FOUNDRYCLAW_USER_ID` on
this module for each session (without it import_project reports that it only works inside a chat).

Uploaded files are read by the tool itself: `create_project` (`design_records_file`, `observations_file`,
`evidence_file`, `descriptor_tables[].file`), `import_observations` (`rows_file`), `tell_results` (`results_file`),
`add_descriptor_table` and `import_evidence` (`file`) take the absolute path from the upload note, restricted to the
user's uploads/workspace (and `TRACE_IMPORT_ALLOWED_ROOTS`), UTF-8 or GB18030, at most 20 MB. A model copying a file
into a text argument can rewrite it (it once imported made-up evidence cards), so the text arguments are only for
data typed in the chat. `import_evidence` saves the current cards to `trace_projects/_evidence_snapshots/` first and
returns `snapshot_file` plus an `undo` call.

Owners: the TRACE service is shared, so all projects stay visible, with `owner`/`yours` in `list_projects` and
`project_summary` (recorded in `data/trace_project_owners.json` by `create_project`/`import_project`). Tools that change
a project (ask, tell, import_observations, update_project_config, add_descriptor_table, import_evidence, reset,
unregister, create with overwrite) refuse another user's project until the user confirmed and the call passes
`others_project_ok: true`. Projects from before the record have owner `unknown` and are not restricted.

Keys: `ask_recommendations` and `tell_results` send the chat user's OPENAI-API-KEY (设置 → 密钥管理) to TRACE as `llm`
(only to a localhost or https TRACE_LAB_BASE_URL), so agentic mode runs on the user's own key; without one TRACE uses
its server key. The result's `llm_key` says which (from TRACE's `llm_source`). `create_project` defaults to
`chunked_gp` (newer TRACE versions default to it too, and run chunked_gp for a round when an Atlas project has more
than 100k combinations, reported as `planner_switched`).

TRACE behavior the tool passes through: failed and skipped conditions are not proposed again (project setting
`repeat_failed_conditions`), a failed result reported with a number is learned from, chunked_gp recommendations carry
`model_estimate` {predicted, uncertainty} (kept in the compact views), numeric variables need no descriptor table,
and evidence `mapping_status` aliases (`same_redox_manifold`, `same_reaction`) are stored as `same_reaction_family`
(`status_notes` in the import result).

Readers return compact views by default (a full agentic batch is ~90 KB, all recommendation batches of a project
~300 KB, all evidence cards ~55 KB, and Claude Code stores tool results over ~30 KB in a file the model then
re-reads or re-runs): `ask_recommendations`/`get_recommendations` leave out the decision traces (`get_trace` has them),
`get_recommendations` returns the latest batch (`round_id` picks another), `get_evidence` lists 12 shortened cards at a
time (`card_ids` for full cards), `get_trace` hoists batch-level reasoning and can be limited to one `recommendation_id`.
`full: true` returns the API's complete answer when it fits (about 25 KB); a larger one comes back as the compact
view with a note on how to read it in parts. `get_observations` returns the latest 50 rows (offset/limit).

Deployment: `tools/` is not under git in FounDryClaw_Web; the tracked copy is the `tool-skills`
repo. The backend re-executes `trace_collab.py` for every new chat session (no restart needed), but
silently drops the whole tool if its import fails -- import it once with the app's venv after editing.

Agentic `ask`/`tell` results carry `llm_model` and `llm_adjustments`; agentic recommendations carry `relation_to_measured` and, when TRACE caught a contradicting comment, `semantic_assessment.consistency_warnings` (all kept in the compact views).
