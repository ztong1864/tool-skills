---
name: protein-structure-databases
description: "蛋白质与结构生物学数据库：UniProt、PDB/PDBe/RCSB、InterPro、AlphaFold 系列及其下游结构分析服务，共 70 个 ToolUniverse 类别、约 300 个工具。（基于 ToolUniverse，https://github.com/mims-harvard/ToolUniverse）"
category: life-sciences-bioinformatics
---

# protein-structure-databases (ToolUniverse-backed research service)

Runs in this backend's own process via `claude_agent_sdk.create_sdk_mcp_server()` --
no credential needed (every category bundled here is keyless upstream), though the
underlying ToolUniverse tools themselves call out to each database's public API over
HTTP. Bundles 70 ToolUniverse categories -- 蛋白质与结构生物学数据库 --
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

Categories bundled: "alphafill", "alphafold", "antibody_registry", "bmrb", "cath", "channelsdb", "complex_portal", "cryoet", "disprot", "dynamut2", "ebi_alignment", "ebi_proteins_coordinates", "ebi_proteins_epitope", "ebi_proteins_ext", "ebi_proteins_features", "ebi_sequence", "elm", "emdb", "empiar", "foldseek", "fpbase", "glygen", "gpcrdb", "hpa", "interpro", "interpro_domain_arch", "interpro_entry", "interpro_ext", "interpro_member_db", "interproscan", "iptmnet", "iupred3", "mddb", "membrane_topology", "mobidb", "pdb_redo", "pdbe_api", "pdbe_graph", "pdbe_kb", "pdbe_search", "pdbe_sifts", "pdbe_validation", "pdbepisa", "pdbtm", "pfam", "prosite", "proteins_api", "proteinsplus", "rcsb_advanced_search", "rcsb_data", "rcsb_graphql", "rcsb_pdb", "rcsb_search", "sabdab", "sasbdb", "scanprosite", "skempi", "structure_annotation", "swissmodel", "tcdb", "therasabdab", "three_d_beacons", "uniparc", "uniprot", "uniprot_idmapping", "uniprot_locations", "uniprot_proteomes", "uniprot_ref", "uniprot_taxonomy", "uniref".
