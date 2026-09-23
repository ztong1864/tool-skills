---
name: chemistry-databases
description: "化学与小分子数据库：PubChem、ChEMBL、ZINC、BindingDB 等化合物结构/活性/性质数据库，共 41 个 ToolUniverse 类别、约 190 个工具（不含需付费/双因素登录的 BRENDA、MetaCyc、Clue、mcule）。（基于 ToolUniverse，https://github.com/mims-harvard/ToolUniverse）"
category: chemistry
---

# chemistry-databases (ToolUniverse-backed research service)

Runs in this backend's own process via `claude_agent_sdk.create_sdk_mcp_server()` --
no credential needed (every category bundled here is keyless upstream), though the
underlying ToolUniverse tools themselves call out to each database's public API over
HTTP. Bundles 41 ToolUniverse categories -- 化学与小分子数据库 --
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

Categories bundled: "aopwiki", "bigg_models", "bindingdb", "chebi", "ChEMBL", "classyfire", "cod_crystal", "drug_synergy", "emolecules", "enamine", "gnps", "klifs", "lipidmaps", "lipidmaps_gene", "lotus", "massbank", "mcsa", "metabolite", "mibig", "nci_cactus", "npatlas", "opsin", "pdbe_compound", "pdbe_ligands", "pharmacodb", "protacdb", "pubchem", "pubchem_bioassay", "pubchem_tox", "rcsb_chemcomp", "rhea", "rhea_reaction", "sabiork", "swissadme", "swissdock", "swisslipids", "synergxdb", "t3db", "tdc_dataset", "unichem", "zinc".
