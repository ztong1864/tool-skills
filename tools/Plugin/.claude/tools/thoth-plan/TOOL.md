---
name: thoth-plan
description: "Thoth-Plan（SCP 广场 #19，上海人工智能实验室）：面向生物湿实验的 LLM 协议生成智能体，支持根据自然语言需求生成结构化实验方案、将方案转换为可执行 JSON、从 PDF 提取实验方案。不包含物理设备执行能力——execute_json（会向真实 PCR 操作服务器下发指令）已从本工具中排除。"
category: life-sciences-bioinformatics
---

# Thoth-Plan (SCP Hub #19) — protocol generation only

Remote MCP tool server hosted on SCP 广场 (Shanghai AI Lab). Source:
https://scphub.intern-ai.org.cn/detail/19

Exposes 3 of the upstream server's 4 tools:

- `protocol_generation` — generate a structured experiment protocol from a natural-language prompt
- `generate_executable_json` — convert protocol text into executable JSON
- `extract_protocol_from_pdf` — extract a protocol from a PDF

**Deliberately excluded**: `execute_json`, which sends the executable JSON to
a live PCR operation server ("Thoth-OP", defaults to a real hardcoded IP) and
actually runs it on physical lab equipment. FounDryClaw_Web is not yet
integrating real device-manipulation tools — see `backing.json`'s
`disallowed_tools`, which hides this specific function from the model
entirely (not just a permission prompt it could ask to bypass).

Connects via `backing.json` in this same folder (streamable-HTTP MCP,
`SCP-HUB-API-KEY` header, same account-level key already used by
`scp-chem-reaction-calc`). Credentials are per-admin, not shared: an admin
registers their own key via `POST /api/tool-credentials` with just
`{"tool_ref": "thoth-plan", "secret": "..."}` — the backend derives the
storage scope from that admin's own identity server-side (see
`tool_credential_service.admin_owner_scope()`), so this only becomes usable in
*that admin's own* chat sessions. Other admins need to register their own key
separately; there is no shared fallback.
