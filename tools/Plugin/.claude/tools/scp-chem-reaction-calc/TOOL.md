---
name: scp-chem-reaction-calc
description: "化学与反应计算-Tool（SCP 广场 #24，上海人工智能实验室）：面向化学实验、反应工程及材料科学的综合计算工具库，涵盖化学反应参数计算、物质量与溶液浓度分析、反应速率与平衡常数求解、质量守恒与能量平衡核查、配比与产率估算等 105 个工具。"
category: chemistry
---

# 化学与反应计算 (SCP Hub #24)

Remote MCP tool server hosted on SCP 广场 (Shanghai AI Lab). Source:
https://scphub.intern-ai.org.cn/detail/24

Connects via `backing.json` in this same folder (streamable-HTTP MCP,
`SCP-HUB-API-KEY` header). Credentials are per-admin, not shared: an admin
registers their own key via `POST /api/tool-credentials` with just
`{"tool_ref": "scp-chem-reaction-calc", "secret": "..."}` — the backend derives
the storage scope from that admin's own identity server-side (see
`tool_credential_service.admin_owner_scope()`), so this only becomes usable in
*that admin's own* chat sessions. Other admins need to register their own key
separately; there is no shared fallback.
