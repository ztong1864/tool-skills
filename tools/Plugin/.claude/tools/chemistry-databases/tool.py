"""ToolUniverse-backed research service cluster: 化学与小分子数据库.

Bundles these ToolUniverse categories into ONE MCP server (see TOOL.md for why one
server, not one per category): "aopwiki", "bigg_models", "bindingdb", "chebi", "ChEMBL", "classyfire", "cod_crystal", "drug_synergy", "emolecules", "enamine", "gnps", "klifs", "lipidmaps", "lipidmaps_gene", "lotus", "massbank", "mcsa", "metabolite", "mibig", "nci_cactus", "npatlas", "opsin", "pdbe_compound", "pdbe_ligands", "pharmacodb", "protacdb", "pubchem", "pubchem_bioassay", "pubchem_tox", "rcsb_chemcomp", "rhea", "rhea_reaction", "sabiork", "swissadme", "swissdock", "swisslipids", "synergxdb", "t3db", "tdc_dataset", "unichem", "zinc".

All tool identities (description/parameter schema) are introspected live from the
vendored `tooluniverse` package via the shared bridge at
tools/tool-service/tooluniverse_bridge.py -- nothing about these specific tools is
hardcoded here beyond the category keys. That bridge lives outside api/ and web/ on
purpose: adding or editing a ToolUniverse-backed tool never touches the git-tracked
project or its core code, only files under tools/.
"""

import importlib.util
import sys
from pathlib import Path

_CATEGORIES = ["aopwiki", "bigg_models", "bindingdb", "chebi", "ChEMBL", "classyfire", "cod_crystal", "drug_synergy", "emolecules", "enamine", "gnps", "klifs", "lipidmaps", "lipidmaps_gene", "lotus", "massbank", "mcsa", "metabolite", "mibig", "nci_cactus", "npatlas", "opsin", "pdbe_compound", "pdbe_ligands", "pharmacodb", "protacdb", "pubchem", "pubchem_bioassay", "pubchem_tox", "rcsb_chemcomp", "rhea", "rhea_reaction", "sabiork", "swissadme", "swissdock", "swisslipids", "synergxdb", "t3db", "tdc_dataset", "unichem", "zinc"]
_SLUG = "chemistry-databases"


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
# without it, this bundle's ~41 categories' worth of @tool wrapper objects would
# be rebuilt from scratch on every single chat message. See its docstring for the
# measured cost this avoids.
SERVER = _bridge.get_or_build_server(_SLUG, _SLUG, lambda: _bridge.make_categories_tools(_CATEGORIES))
