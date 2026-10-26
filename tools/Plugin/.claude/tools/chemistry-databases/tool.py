"""ToolUniverse-backed research service cluster: 化学与小分子数据库.

Bundles these ToolUniverse categories into ONE MCP server (see TOOL.md for why one
server, not one per category): "aopwiki", "bigg_models", "bindingdb", "chebi", "ChEMBL", "classyfire", "cod_crystal", "drug_synergy", "emolecules", "enamine", "gnps", "klifs", "lipidmaps", "lipidmaps_gene", "lotus", "massbank", "mcsa", "metabolite", "mibig", "nci_cactus", "npatlas", "opsin", "pdbe_compound", "pdbe_ligands", "pharmacodb", "protacdb", "pubchem", "pubchem_bioassay", "pubchem_tox", "rcsb_chemcomp", "rhea", "rhea_reaction", "sabiork", "swissadme", "swissdock", "swisslipids", "synergxdb", "t3db", "tdc_dataset", "unichem", "zinc".

All tool identities (description/parameter schema) are introspected live from the
vendored `tooluniverse` package via the shared bridge at
tools/tool-service/tooluniverse_bridge.py -- nothing about these specific tools is
hardcoded here beyond the category keys. That bridge lives outside api/ and web/ on
purpose: adding or editing a ToolUniverse-backed tool never touches the git-tracked
project or its core code, only files under tools/.

One tool is defined here instead: PubChem_get_experimental_property. ToolUniverse's
PubChem tools read computed properties only (PubChem_get_compound_properties_by_CID
rejects BoilingPoint), so a boiling point, melting point or density had no tool, and
the model wrote it from memory.
"""

import asyncio
import importlib.util
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from claude_agent_sdk import ToolAnnotations, tool

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

_PUG_VIEW_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{cid}/JSON?heading={heading}"
_PROPERTY_DESCRIPTION = (
    "Experimental (measured) properties of a PubChem compound, from the 'Experimental Properties' "
    "section of its PubChem record: each reported value with the source PubChem cites for it. Use "
    "it for boiling point, melting point, density and similar data that "
    "PubChem_get_compound_properties_by_CID does not provide (that tool returns computed properties "
    "only). property is the English PubChem heading, for example: Boiling Point, Melting Point, "
    "Density, Flash Point, Vapor Pressure, Solubility, LogP, Refractive Index, Viscosity, "
    "Autoignition Temperature, Odor, Color/Form, Physical Description. Get the CID first with "
    "PubChem_get_CID_by_compound_name."
)


def _experimental_property(cid: int, heading: str) -> dict:
    url = _PUG_VIEW_URL.format(cid=cid, heading=urllib.parse.quote(heading))
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            record = json.load(response)["Record"]
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 404):
            return {"status": "error", "error": f"PubChem has no '{heading}' data for CID {cid} "
                                                 "(or the heading is not a PubChem heading)."}
        return {"status": "error", "error": f"PubChem returned HTTP {exc.code}"}
    references = {ref.get("ReferenceNumber"): ref for ref in record.get("Reference", [])}
    values = []

    def collect(sections):
        for section in sections:
            for info in section.get("Information", []):
                value = info.get("Value", {})
                text = " ".join(part.get("String", "") for part in value.get("StringWithMarkup", [])).strip()
                if not text and value.get("Number"):
                    text = " ".join(str(number) for number in value["Number"]) + (f" {value['Unit']}" if value.get("Unit") else "")
                if not text:
                    continue  # binary tables and the like
                ref = references.get(info.get("ReferenceNumber"), {})
                values.append({"value": text, "source": ref.get("SourceName"), "source_url": ref.get("URL"),
                               "note": " ".join(info.get("Reference", [])) or None})
            collect(section.get("Section", []))

    collect(record.get("Section", []))
    return {
        "status": "success",
        "data": {"cid": cid, "compound": record.get("RecordTitle"), "property": heading, "values": values},
        "metadata": {"source": "PubChem PUG View", "pubchem_url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}"},
    }


@tool(
    "PubChem_get_experimental_property",
    _PROPERTY_DESCRIPTION,
    {
        "type": "object",
        "properties": {
            "cid": {"type": "integer", "description": "PubChem compound ID"},
            "property": {"type": "string", "description": "English PubChem heading, e.g. Boiling Point"},
        },
        "required": ["cid", "property"],
    },
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def _pubchem_experimental_property(args: dict) -> dict:
    try:
        result = await asyncio.to_thread(_experimental_property, int(args["cid"]), str(args["property"]).strip())
    except Exception as exc:  # noqa: BLE001 -- surfaced as tool output, not a crash
        return {"content": [{"type": "text", "text": f"PubChem_get_experimental_property failed: {exc}"}], "is_error": True}
    return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]}


# get_or_build_server() caches the finished SERVER across this file's repeated re-execs
# (tool_backing_service.py re-execs every sdk_python tool.py fresh per chat session) --
# without it, this bundle's ~41 categories' worth of @tool wrapper objects would
# be rebuilt from scratch on every single chat message. See its docstring for the
# measured cost this avoids.
SERVER = _bridge.get_or_build_server(
    _SLUG, _SLUG, lambda: _bridge.make_categories_tools(_CATEGORIES) + [_pubchem_experimental_property])
