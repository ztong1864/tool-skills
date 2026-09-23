---
name: model-organism-databases
description: "模式生物与物种基因组数据库：WormBase、FlyBase、ZFIN、SGD、MGI、RGD、BV-BRC 等物种特异性基因组资源，共 20 个 ToolUniverse 类别、约 100 个工具。（基于 ToolUniverse，https://github.com/mims-harvard/ToolUniverse）"
category: life-sciences-bioinformatics
---

# model-organism-databases (ToolUniverse-backed research service)

Runs in this backend's own process via `claude_agent_sdk.create_sdk_mcp_server()` --
no credential needed (every category bundled here is keyless upstream), though the
underlying ToolUniverse tools themselves call out to each database's public API over
HTTP. Bundles 20 ToolUniverse categories -- 模式生物与物种基因组数据库 --
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

Categories bundled: "alliance_genome", "bacdive", "bvbrc", "flybase", "flymine", "gtdb", "impc", "mediadive", "mgi", "mousemine", "mpd", "pombase", "rgd", "rgd_strain", "sgd", "sgd_protein", "veupathdb", "wormbase", "xenbase", "zfin".
