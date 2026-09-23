---
name: trace-collab
description: 操作 TRACE Lab 闭环实验推荐工作流：创建/查询项目、导入历史实验、生成候选推荐（ask）、提交实验结果（tell）、查看推荐/观测/证据/决策 trace，以及重置项目运行状态。
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
