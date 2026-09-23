"""ToolUniverse-backed local tool bundle: 临床与流行病学计算工具集.

Bundles these local-compute ToolUniverse tools into ONE MCP server (see TOOL.md for
why one server, not one per tool): "AgingCohort_search", "clinical_trial_ae_severity_test", "ClinicalCalc_ASCVD_risk", "ClinicalCalc_CHA2DS2_VASc", "ClinicalCalc_Child_Pugh", "ClinicalCalc_CURB_65", "ClinicalCalc_eGFR_CKD_EPI", "ClinicalCalc_HAS_BLED", "ClinicalCalc_MELD_Na", "ClinicalCalc_qSOFA", "ClinicalCalc_Wells_DVT", "ClinicalCalc_Wells_PE", "DoseResponse_calculate_ic50", "DoseResponse_compare_potency", "DoseResponse_fit_curve", "Epidemiology_bayesian", "Epidemiology_diagnostic", "Epidemiology_nnt", "Epidemiology_r0_herd", "Epidemiology_vaccine_coverage", "health_disparities_get_county_rankings_info", "health_disparities_get_svi_info", "MetaAnalysis_run", "NCA_calculate_bioavailability", "NCA_compute_parameters", "NCA_fit_one_compartment", "ROC_analysis", "Survival_cox_regression", "Survival_kaplan_meier", "Survival_log_rank_test".

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

_TOOL_NAMES = ["AgingCohort_search", "clinical_trial_ae_severity_test", "ClinicalCalc_ASCVD_risk", "ClinicalCalc_CHA2DS2_VASc", "ClinicalCalc_Child_Pugh", "ClinicalCalc_CURB_65", "ClinicalCalc_eGFR_CKD_EPI", "ClinicalCalc_HAS_BLED", "ClinicalCalc_MELD_Na", "ClinicalCalc_qSOFA", "ClinicalCalc_Wells_DVT", "ClinicalCalc_Wells_PE", "DoseResponse_calculate_ic50", "DoseResponse_compare_potency", "DoseResponse_fit_curve", "Epidemiology_bayesian", "Epidemiology_diagnostic", "Epidemiology_nnt", "Epidemiology_r0_herd", "Epidemiology_vaccine_coverage", "health_disparities_get_county_rankings_info", "health_disparities_get_svi_info", "MetaAnalysis_run", "NCA_calculate_bioavailability", "NCA_compute_parameters", "NCA_fit_one_compartment", "ROC_analysis", "Survival_cox_regression", "Survival_kaplan_meier", "Survival_log_rank_test"]
_SLUG = "tooluniverse-clinical-tools"


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
# without it, these 30 tools' @tool wrapper objects would be rebuilt from
# scratch on every single chat message. See its docstring for the measured cost this avoids.
SERVER = _bridge.get_or_build_server(_SLUG, _SLUG, lambda: _bridge.make_tools(_TOOL_NAMES))
