"""ToolUniverse-backed research service cluster: 蛋白质与结构生物学数据库.

Bundles these ToolUniverse categories into ONE MCP server (see TOOL.md for why one
server, not one per category): "alphafill", "alphafold", "antibody_registry", "bmrb", "cath", "channelsdb", "complex_portal", "cryoet", "disprot", "dynamut2", "ebi_alignment", "ebi_proteins_coordinates", "ebi_proteins_epitope", "ebi_proteins_ext", "ebi_proteins_features", "ebi_sequence", "elm", "emdb", "empiar", "foldseek", "fpbase", "glygen", "gpcrdb", "hpa", "interpro", "interpro_domain_arch", "interpro_entry", "interpro_ext", "interpro_member_db", "interproscan", "iptmnet", "iupred3", "mddb", "membrane_topology", "mobidb", "pdb_redo", "pdbe_api", "pdbe_graph", "pdbe_kb", "pdbe_search", "pdbe_sifts", "pdbe_validation", "pdbepisa", "pdbtm", "pfam", "prosite", "proteins_api", "proteinsplus", "rcsb_advanced_search", "rcsb_data", "rcsb_graphql", "rcsb_pdb", "rcsb_search", "sabdab", "sasbdb", "scanprosite", "skempi", "structure_annotation", "swissmodel", "tcdb", "therasabdab", "three_d_beacons", "uniparc", "uniprot", "uniprot_idmapping", "uniprot_locations", "uniprot_proteomes", "uniprot_ref", "uniprot_taxonomy", "uniref".

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

_CATEGORIES = ["alphafill", "alphafold", "antibody_registry", "bmrb", "cath", "channelsdb", "complex_portal", "cryoet", "disprot", "dynamut2", "ebi_alignment", "ebi_proteins_coordinates", "ebi_proteins_epitope", "ebi_proteins_ext", "ebi_proteins_features", "ebi_sequence", "elm", "emdb", "empiar", "foldseek", "fpbase", "glygen", "gpcrdb", "hpa", "interpro", "interpro_domain_arch", "interpro_entry", "interpro_ext", "interpro_member_db", "interproscan", "iptmnet", "iupred3", "mddb", "membrane_topology", "mobidb", "pdb_redo", "pdbe_api", "pdbe_graph", "pdbe_kb", "pdbe_search", "pdbe_sifts", "pdbe_validation", "pdbepisa", "pdbtm", "pfam", "prosite", "proteins_api", "proteinsplus", "rcsb_advanced_search", "rcsb_data", "rcsb_graphql", "rcsb_pdb", "rcsb_search", "sabdab", "sasbdb", "scanprosite", "skempi", "structure_annotation", "swissmodel", "tcdb", "therasabdab", "three_d_beacons", "uniparc", "uniprot", "uniprot_idmapping", "uniprot_locations", "uniprot_proteomes", "uniprot_ref", "uniprot_taxonomy", "uniref"]
_SLUG = "protein-structure-databases"


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
# without it, this bundle's ~70 categories' worth of @tool wrapper objects would
# be rebuilt from scratch on every single chat message. See its docstring for the
# measured cost this avoids.
SERVER = _bridge.get_or_build_server(_SLUG, _SLUG, lambda: _bridge.make_categories_tools(_CATEGORIES))
