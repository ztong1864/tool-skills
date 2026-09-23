---
name: biodiversity-taxonomy-ecology
description: "生物多样性、分类学与生态学：GBIF、Catalogue of Life、WoRMS、iNaturalist 等物种分类与分布数据库，共 17 个 ToolUniverse 类别、约 60 个工具（不含需密钥的 IUCN）。（基于 ToolUniverse，https://github.com/mims-harvard/ToolUniverse）"
category: earth-environment-agriculture
---

# biodiversity-taxonomy-ecology (ToolUniverse-backed research service)

Runs in this backend's own process via `claude_agent_sdk.create_sdk_mcp_server()` --
no credential needed (every category bundled here is keyless upstream), though the
underlying ToolUniverse tools themselves call out to each database's public API over
HTTP. Bundles 17 ToolUniverse categories -- 生物多样性、分类学与生态学 --
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

Categories bundled: "col", "ebi_taxonomy", "ebird_taxonomy", "eol", "gbif", "gbif_ext", "gbif_taxonomy", "goat", "idigbio", "inaturalist", "itis", "obis", "opentree", "paleobiology", "powo", "usda_plants", "worms".
