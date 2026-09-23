---
name: pathway-network-annotation
description: "通路、网络与功能注释：Reactome、KEGG、Gene Ontology、STRING/BioGRID/IntAct、WikiPathways、MSigDB、Enrichr 等，共 37 个 ToolUniverse 类别、约 160 个工具（不含需密钥的 BioGRID）。（基于 ToolUniverse，https://github.com/mims-harvard/ToolUniverse）"
category: life-sciences-bioinformatics
---

# pathway-network-annotation (ToolUniverse-backed research service)

Runs in this backend's own process via `claude_agent_sdk.create_sdk_mcp_server()` --
no credential needed (every category bundled here is keyless upstream), though the
underlying ToolUniverse tools themselves call out to each database's public API over
HTTP. Bundles 37 ToolUniverse categories -- 通路、网络与功能注释 --
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

Categories bundled: "biomodels_tools", "ebi_proteins_interactions", "Enrichr", "enrichr_ext", "go", "go_api", "gprofiler", "harmonizome", "hocomoco", "HumanBase", "indra", "intact", "jaspar", "kegg", "kegg_brite", "kegg_ext", "kegg_network_variant", "msigdb", "ndex", "omnipath", "panther", "pathwaycommons", "plant_reactome", "ppi", "quickgo", "reactome", "reactome_analysis", "reactome_content", "reactome_interactors", "remap", "signor", "stitch", "string_ext", "string_network", "unibind", "wikipathways", "wikipathways_ext".
