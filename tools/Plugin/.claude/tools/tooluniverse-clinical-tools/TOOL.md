---
name: tooluniverse-clinical-tools
description: "临床与流行病学计算工具集：30 个基于 ToolUniverse 的本地临床/流行病学计算工具（临床风险评分、剂量-反应拟合、非房室药代动力学、流行病学指标、meta 分析、生存分析、ROC 分析等），纯本地计算，无需网络请求。（基于 ToolUniverse，https://github.com/mims-harvard/ToolUniverse）"
category: medicine-clinical-research
---

# tooluniverse-clinical-tools (ToolUniverse-backed local tool bundle)

Runs in this backend's own process via `claude_agent_sdk.create_sdk_mcp_server()` --
no network call, no credential. Bundles 30 local-compute ToolUniverse
tools -- 临床与流行病学计算工具集 -- into ONE MCP server via the shared bridge's `make_tools()`
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

Tools bundled: "AgingCohort_search", "clinical_trial_ae_severity_test", "ClinicalCalc_ASCVD_risk", "ClinicalCalc_CHA2DS2_VASc", "ClinicalCalc_Child_Pugh", "ClinicalCalc_CURB_65", "ClinicalCalc_eGFR_CKD_EPI", "ClinicalCalc_HAS_BLED", "ClinicalCalc_MELD_Na", "ClinicalCalc_qSOFA", "ClinicalCalc_Wells_DVT", "ClinicalCalc_Wells_PE", "DoseResponse_calculate_ic50", "DoseResponse_compare_potency", "DoseResponse_fit_curve", "Epidemiology_bayesian", "Epidemiology_diagnostic", "Epidemiology_nnt", "Epidemiology_r0_herd", "Epidemiology_vaccine_coverage", "health_disparities_get_county_rankings_info", "health_disparities_get_svi_info", "MetaAnalysis_run", "NCA_calculate_bioavailability", "NCA_compute_parameters", "NCA_fit_one_compartment", "ROC_analysis", "Survival_cox_regression", "Survival_kaplan_meier", "Survival_log_rank_test".
