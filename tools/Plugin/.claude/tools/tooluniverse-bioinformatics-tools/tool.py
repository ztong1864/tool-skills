"""ToolUniverse-backed local tool bundle: 生物信息学计算工具集.

Bundles these local-compute ToolUniverse tools into ONE MCP server (see TOOL.md for
why one server, not one per tool): "Activity_infer_ulm", "coding_variant_fraction", "Coexpression_modules", "Coloc_abf_test", "Finemap_credible_set", "GSEA_prerank", "GSVA_score", "MR_estimate", "Network_proximity", "phykit_batch_analysis", "PopGen_fst", "PopGen_haplotype_count", "PopGen_hwe_test", "PopGen_inbreeding", "ProtParam_calculate", "RNAseq_edger_limma_de", "run_deseq2_analysis", "Sequence_dn_ds", "SPrediXcan_associate", "ssGSEA_score", "VCF_count_variants", "VCF_normalize", "VCF_summary_stats".

All tool identities (description/parameter schema) are introspected live from the
vendored `tooluniverse` package via the shared bridge at
tools/tool-service/tooluniverse_bridge.py -- nothing about these specific tools is
hardcoded here beyond their names. That bridge lives outside api/ and web/ on
purpose: adding or editing a ToolUniverse-backed tool never touches the git-tracked
project or its core code, only files under tools/.
"""

import importlib.util
import sys
from pathlib import Path

_TOOL_NAMES = ["Activity_infer_ulm", "coding_variant_fraction", "Coexpression_modules", "Coloc_abf_test", "Finemap_credible_set", "GSEA_prerank", "GSVA_score", "MR_estimate", "Network_proximity", "phykit_batch_analysis", "PopGen_fst", "PopGen_haplotype_count", "PopGen_hwe_test", "PopGen_inbreeding", "ProtParam_calculate", "RNAseq_edger_limma_de", "run_deseq2_analysis", "Sequence_dn_ds", "SPrediXcan_associate", "ssGSEA_score", "VCF_count_variants", "VCF_normalize", "VCF_summary_stats"]
_SLUG = "tooluniverse-bioinformatics-tools"


def _tooluniverse_bridge():
    cached = sys.modules.get("foundryclaw_tooluniverse_bridge")
    if cached is not None:
        return cached
    for ancestor in Path(__file__).resolve().parents:
        candidate = ancestor / "tool-service" / "tooluniverse_bridge.py"
        if candidate.exists():
            spec = importlib.util.spec_from_file_location("foundryclaw_tooluniverse_bridge", candidate)
            module = importlib.util.module_from_spec(spec)
            sys.modules["foundryclaw_tooluniverse_bridge"] = module
            spec.loader.exec_module(module)
            return module
    raise ImportError("tooluniverse_bridge.py not found under tools/tool-service/")


_bridge = _tooluniverse_bridge()

# get_or_build_server() caches the finished SERVER across this file's repeated re-execs
# (tool_backing_service.py re-execs every sdk_python tool.py fresh per chat session) --
# without it, these 23 tools' @tool wrapper objects would be rebuilt from
# scratch on every single chat message. See its docstring for the measured cost this avoids.
SERVER = _bridge.get_or_build_server(_SLUG, _SLUG, lambda: _bridge.make_tools(_TOOL_NAMES))
