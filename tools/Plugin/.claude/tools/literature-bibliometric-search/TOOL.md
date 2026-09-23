---
name: literature-bibliometric-search
description: "文献与文献计量检索：PubMed、Europe PMC、Semantic Scholar、CrossRef、arXiv、bioRxiv、ORCID、Zenodo 等文献检索与元数据服务，共 41 个 ToolUniverse 类别、约 120 个工具（不含需密钥的 literature_search、OpenAlex）。（基于 ToolUniverse，https://github.com/mims-harvard/ToolUniverse）"
category: research-writing-lab-management
---

# literature-bibliometric-search (ToolUniverse-backed research service)

Runs in this backend's own process via `claude_agent_sdk.create_sdk_mcp_server()` --
no credential needed (every category bundled here is keyless upstream), though the
underlying ToolUniverse tools themselves call out to each database's public API over
HTTP. Bundles 41 ToolUniverse categories -- 文献与文献计量检索 --
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

Categories bundled: "arxiv", "bgpt", "biorxiv", "biorxiv_ext", "core", "crossref", "datacite", "dataone", "dataverse", "dblp", "doaj", "dryad", "epmc_annotations", "EuropePMC", "europepmc_annotations", "europepmc_citations", "fatcat", "figshare", "hal", "icite", "inspirehep", "litvar", "medrxiv", "mesh", "openaire", "openaire_dataset", "opencitations", "orcid", "osf_preprints", "pmc", "pubmed", "pubtator", "pubtator3_ext", "re3data", "retraction", "ror", "scite", "semantic_scholar", "semantic_scholar_ext", "unpaywall", "zenodo".
