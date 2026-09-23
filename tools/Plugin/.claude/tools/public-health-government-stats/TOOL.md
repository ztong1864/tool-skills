---
name: public-health-government-stats
description: "公共卫生与政府统计数据：CDC、WHO GHO、World Bank、Eurostat、NIH RePORTER 等公共卫生与社会经济统计数据，共 13 个 ToolUniverse 类别、约 50 个工具（不含需密钥的 US Census）。（基于 ToolUniverse，https://github.com/mims-harvard/ToolUniverse）"
category: medicine-clinical-research
---

# public-health-government-stats (ToolUniverse-backed research service)

Runs in this backend's own process via `claude_agent_sdk.create_sdk_mcp_server()` --
no credential needed (every category bundled here is keyless upstream), though the
underlying ToolUniverse tools themselves call out to each database's public API over
HTTP. Bundles 13 ToolUniverse categories -- 公共卫生与政府统计数据 --
into ONE multi-tool "research service" entry via the shared bridge's
`make_categories_tools()` at `tools/tool-service/tooluniverse_bridge.py`; every tool
name, description, and parameter schema is introspected live from the vendored
[ToolUniverse](https://github.com/mims-harvard/ToolUniverse) package at runtime, not
hand-copied here.

**Why one entry for this many categories**: the Claude Agent SDK's CLI transport
serializes every registered MCP server into one JSON blob passed as a single
`--mcp-config` command-line argument -- cost scales with the number of *server
entries*, not the number of tools inside each one. An earlier one-server-per-category
layout (~400 entries total across all ToolUniverse-backed tools) exceeded the OS
command-line length limit and broke chat session startup entirely, not just sessions
using these tools. Grouping by research theme keeps every individual tool just as
callable while cutting the entry count this scales with.

Categories bundled: "cdc", "cms_open_payments", "datagov", "dhs_program", "disease_sh_ext", "diseasesh", "euhealth", "eurostat", "nhanes", "nih_reporter", "odphp", "who_gho", "worldbank".
