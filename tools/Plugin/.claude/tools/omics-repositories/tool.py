"""ToolUniverse-backed research service cluster: 组学数据仓库.

Bundles these ToolUniverse categories into ONE MCP server (see TOOL.md for why one
server, not one per category): "allen_cell_types", "archs4", "arrayexpress", "bgee", "bioimage_archive", "biosamples", "biostudies", "cbioportal", "cellmarker", "cellosaurus", "cellpainting", "celltypist_catalog", "cellxgene_discovery", "dandi", "expression_anova", "expression_atlas", "gdc", "geo", "gmrepo", "gtex", "gtex_v2", "gxa", "hca_tools", "hubmap", "hubmap_sample", "idr", "idr_searchengine", "l1000fwd", "lincs", "massive", "metaboanalyst", "metabolights", "metabolomics_workbench", "mgnify", "mgnify_expanded", "ncbi_sra", "neurovault", "omicsdi", "openneuro", "panglaodb", "pdc", "pride", "proteomexchange", "proteomicsdb", "proteomicsdb_meltome", "scxa", "single_cell_portal", "sra", "tcia", "ucsc_cell_browser".

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

_CATEGORIES = ["allen_cell_types", "archs4", "arrayexpress", "bgee", "bioimage_archive", "biosamples", "biostudies", "cbioportal", "cellmarker", "cellosaurus", "cellpainting", "celltypist_catalog", "cellxgene_discovery", "dandi", "expression_anova", "expression_atlas", "gdc", "geo", "gmrepo", "gtex", "gtex_v2", "gxa", "hca_tools", "hubmap", "hubmap_sample", "idr", "idr_searchengine", "l1000fwd", "lincs", "massive", "metaboanalyst", "metabolights", "metabolomics_workbench", "mgnify", "mgnify_expanded", "ncbi_sra", "neurovault", "omicsdi", "openneuro", "panglaodb", "pdc", "pride", "proteomexchange", "proteomicsdb", "proteomicsdb_meltome", "scxa", "single_cell_portal", "sra", "tcia", "ucsc_cell_browser"]
_SLUG = "omics-repositories"


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
# without it, this bundle's ~50 categories' worth of @tool wrapper objects would
# be rebuilt from scratch on every single chat message. See its docstring for the
# measured cost this avoids.
SERVER = _bridge.get_or_build_server(_SLUG, _SLUG, lambda: _bridge.make_categories_tools(_CATEGORIES))
