---
name: tooluniverse-bioinformatics-tools
description: "生物信息学计算工具集：23 个基于 ToolUniverse 的本地生物信息学计算工具（RNA-seq 差异表达与富集分析、GWAS/群体遗传学统计、蛋白质理化性质、VCF 统计等），纯本地计算，无需网络请求。（基于 ToolUniverse，https://github.com/mims-harvard/ToolUniverse）"
category: life-sciences-bioinformatics
---

# tooluniverse-bioinformatics-tools (ToolUniverse-backed local tool bundle)

Runs in this backend's own process via `claude_agent_sdk.create_sdk_mcp_server()` --
no network call, no credential. Bundles 23 local-compute ToolUniverse
tools -- 生物信息学计算工具集 -- into ONE MCP server via the shared bridge's `make_tools()`
at `tools/tool-service/tooluniverse_bridge.py`; every tool's exact description and
parameter schema is introspected live from the vendored
[ToolUniverse](https://github.com/mims-harvard/ToolUniverse) package at runtime, not
hand-copied here.

**Why bundled instead of one tool per folder**: the Claude Agent SDK's CLI transport
serializes every registered MCP server into one JSON blob passed as a single
`--mcp-config` command-line argument -- cost scales with the number of *server
entries*, not the number of tools inside each one. An earlier one-server-per-tool
layout (65 entries just for this domain's local-compute tools, ~460 across the whole
ToolUniverse port) exceeded the effective command-line length limit through this
platform's `claude.CMD` npm shim (which routes through `cmd.exe`'s ~8,191-character
limit, well under the raw Windows 32,767 limit) and broke chat session startup
entirely -- not just for sessions using these tools. Bundling keeps every individual
tool just as callable while cutting the entry count the CLI invocation actually scales
with.

Tools bundled: "Activity_infer_ulm", "coding_variant_fraction", "Coexpression_modules", "Coloc_abf_test", "Finemap_credible_set", "GSEA_prerank", "GSVA_score", "MR_estimate", "Network_proximity", "phykit_batch_analysis", "PopGen_fst", "PopGen_haplotype_count", "PopGen_hwe_test", "PopGen_inbreeding", "ProtParam_calculate", "RNAseq_edger_limma_de", "run_deseq2_analysis", "Sequence_dn_ds", "SPrediXcan_associate", "ssGSEA_score", "VCF_count_variants", "VCF_normalize", "VCF_summary_stats".
