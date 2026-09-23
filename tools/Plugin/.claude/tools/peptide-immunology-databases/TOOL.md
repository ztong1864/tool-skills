---
name: peptide-immunology-databases
description: "肽类与免疫学专项数据库：抗菌肽、抗癌肽、免疫肽组等小众专项数据库（DBAASP、AMPSphere、HLA Ligand Atlas 等），共 13 个 ToolUniverse 类别、约 20 个工具。（基于 ToolUniverse，https://github.com/mims-harvard/ToolUniverse）"
category: life-sciences-bioinformatics
---

# peptide-immunology-databases (ToolUniverse-backed research service)

Runs in this backend's own process via `claude_agent_sdk.create_sdk_mcp_server()` --
no credential needed (every category bundled here is keyless upstream), though the
underlying ToolUniverse tools themselves call out to each database's public API over
HTTP. Bundles 13 ToolUniverse categories -- 肽类与免疫学专项数据库 --
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

Categories bundled: "ampsphere", "ampsphere_record", "cancerppd2", "conoserver", "dbaasp", "hemolytik2", "hlaligandatlas", "mhcmotifatlas", "norine", "pepcalc", "peplife2", "peptideatlas", "tumorhope2".
