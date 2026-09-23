"""ToolUniverse-backed local tool bundle: 化学计算工具集.

Bundles these local-compute ToolUniverse tools into ONE MCP server (see TOOL.md for
why one server, not one per tool): "Chem_sa_score", "CrystalStructure_validate", "DegreesOfUnsaturation_calculate", "DrugProps_calculate_qed", "DrugProps_lipinski_filter", "DrugProps_pains_filter", "RDKit_matched_molecular_pair", "RDKit_pharmacophore_features", "SMILES_verify", "visualize_molecule_3d".

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

_TOOL_NAMES = ["Chem_sa_score", "CrystalStructure_validate", "DegreesOfUnsaturation_calculate", "DrugProps_calculate_qed", "DrugProps_lipinski_filter", "DrugProps_pains_filter", "RDKit_matched_molecular_pair", "RDKit_pharmacophore_features", "SMILES_verify", "visualize_molecule_3d"]
_SLUG = "tooluniverse-chemistry-tools"


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
# without it, these 10 tools' @tool wrapper objects would be rebuilt from
# scratch on every single chat message. See its docstring for the measured cost this avoids.
SERVER = _bridge.get_or_build_server(_SLUG, _SLUG, lambda: _bridge.make_tools(_TOOL_NAMES))
