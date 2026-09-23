---
name: omics-repositories
description: "组学数据仓库：基因表达、单细胞、蛋白质组、代谢组及影像组学数据仓库（GEO、GTEx、cBioPortal、PRIDE、MetaboLights 等），共 50 个 ToolUniverse 类别、约 220 个工具。（基于 ToolUniverse，https://github.com/mims-harvard/ToolUniverse）"
category: life-sciences-bioinformatics
---

# omics-repositories (ToolUniverse-backed research service)

Runs in this backend's own process via `claude_agent_sdk.create_sdk_mcp_server()` --
no credential needed (every category bundled here is keyless upstream), though the
underlying ToolUniverse tools themselves call out to each database's public API over
HTTP. Bundles 50 ToolUniverse categories -- 组学数据仓库 --
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

Categories bundled: "allen_cell_types", "archs4", "arrayexpress", "bgee", "bioimage_archive", "biosamples", "biostudies", "cbioportal", "cellmarker", "cellosaurus", "cellpainting", "celltypist_catalog", "cellxgene_discovery", "dandi", "expression_anova", "expression_atlas", "gdc", "geo", "gmrepo", "gtex", "gtex_v2", "gxa", "hca_tools", "hubmap", "hubmap_sample", "idr", "idr_searchengine", "l1000fwd", "lincs", "massive", "metaboanalyst", "metabolights", "metabolomics_workbench", "mgnify", "mgnify_expanded", "ncbi_sra", "neurovault", "omicsdi", "openneuro", "panglaodb", "pdc", "pride", "proteomexchange", "proteomicsdb", "proteomicsdb_meltome", "scxa", "single_cell_portal", "sra", "tcia", "ucsc_cell_browser".
