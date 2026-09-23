"""Shared bridge to the `tooluniverse` package for this codebase's ToolUniverse-backed
sdk_python tool packages. Two granularities share this one engine:

  - tools/Public/*/.claude/tools/<tool-name>/ -- one ToolUniverse *tool* == one FounDryClaw
    tool package (e.g. popgen-hwe-test/), via make_tool(). Used for the local-compute
    categories, where each tool is its own independent calculation.
  - tools/Plugin/.claude/tools/<category-key>/ -- one ToolUniverse *category* == one
    FounDryClaw tool package (e.g. pubchem/, rcsb-pdb/), via make_category_tools(). Used
    for the REST-API-wrapping categories, where a whole external database's several
    endpoints are naturally one multi-tool "research service" connection, the same way
    scitoolagent-chem or scigraph already bundle many sub-tools behind one entry.

`tooluniverse` is vendored at tools/tool-service/vendor/tooluniverse/ (a copy of
https://github.com/mims-harvard/ToolUniverse's src/tooluniverse/, minus its
auto-generated tools/ subdir of typed per-tool wrapper functions, which nothing here
calls) rather than pip-installed. Two reasons: the name `tooluniverse` on PyPI resolves
to an unrelated, much older package (4 categories total, not this project) rather than
the real one; and even installing the real project from its GitHub source pulls in
`markitdown[all]` as a *required* (non-optional) dependency, whose own transitive
requirements (onnxruntime, youtube-transcript-api) have no working resolution on newer
Python/platform combinations, even though nothing in the categories this bridge loads
ever imports markitdown. Vendoring sidesteps both problems: this bridge adds the vendor
directory to sys.path itself (see _vendor_path() below) instead of relying on
site-packages, and only the lightweight runtime dependencies tools/tool-service/
requirements.txt actually lists need installing -- not vendored ToolUniverse's full
declared dependency graph.

Lives under tools/tool-service/ -- deliberately *not* inside api/app/ -- so that adding,
removing, or updating ToolUniverse-backed tools never requires touching the api/ or web/
git-tracked project, or reading either one's core code: everything a tool package needs
(this bridge, its requirements.txt, and the tool packages themselves) lives entirely
under tools/, which isn't git-tracked. Each tool package's tool.py locates this file at
runtime by walking up its own path to find tools/tool-service/tooluniverse_bridge.py
(see any tool.py for the small loader) rather than importing it as a normal `app.*`
package module.

Every tool package needs the same underlying ToolUniverse engine and the same "wrap one
named tool as a claude_agent_sdk @tool" logic. Centralizing it here means it's loaded and
cached exactly once per backend process: each tool.py's loader registers this module in
sys.modules under a fixed name on first load, so every subsequent tool package's loader
gets that cached instance back -- unlike each tool package's own .py file, which
tool_backing_service.py re-execs fresh via importlib.util.spec_from_file_location on
every chat session that includes it.

Tool identity (description, parameter schema) is always introspected live from
`engine.all_tool_dict` -- the installed `tooluniverse` package's own tool registry --
never hardcoded here, so it always matches whatever version is installed and this file
never reproduces any of ToolUniverse's own tool text.

ToolUniverse.load_tools() does a full reload (wipes previously-loaded tools) whenever
called without `include_tools`, so all categories this bridge will ever be asked for
must be loaded together in one call -- see _CATEGORIES below -- rather than
incrementally per tool.
"""

import asyncio
import json
import sys
from pathlib import Path

from claude_agent_sdk import create_sdk_mcp_server, tool

_server_cache: dict = {}


def get_or_build_server(cache_key: str, name: str, build_tools):
    """Cache a fully-built create_sdk_mcp_server() result across repeated calls,
    keyed by cache_key (e.g. the bundle's own slug).

    tool_backing_service.py deliberately re-execs each tool.py fresh via
    importlib.util.spec_from_file_location on every chat session -- by design, so an
    on-disk edit takes effect without a backend restart and a broken tool package can
    never wedge a running process. That's cheap for a single-tool file, but each of
    this bridge's multi-tool bundles rebuilds hundreds of individual @tool wrapper
    objects (one claude_agent_sdk.tool() call per underlying ToolUniverse tool) on
    every re-exec -- measured at ~110s for a single bundle covering all 1307 tools,
    repeated on *every chat message* before this cache existed, independent of
    _get_engine()'s own caching (which only avoids re-parsing ToolUniverse's JSON
    category files, not rebuilding the wrapper objects). Caching the finished SERVER
    itself here means only the very first call after a backend restart pays that
    cost; every call after -- across any number of chat sessions and tool.py
    re-execs -- is an instant dict lookup for the rest of the process's life."""
    cached = _server_cache.get(cache_key)
    if cached is not None:
        return cached
    server = create_sdk_mcp_server(name=name, tools=build_tools())
    _server_cache[cache_key] = server
    return server


def _ensure_vendor_on_path() -> None:
    """Put tools/tool-service/vendor/ (containing the vendored tooluniverse/ package)
    on sys.path, ahead of any same-named package a broader `pip install` might have
    put in site-packages, so `from tooluniverse import ToolUniverse` below resolves to
    the vendored copy every time."""
    vendor_dir = str(Path(__file__).resolve().parent / "vendor")
    if vendor_dir not in sys.path:
        sys.path.insert(0, vendor_dir)

# Every ToolUniverse category wired up by any tools/Public or tools/Plugin package. Kept
# in sync with that set by hand; a category referenced by a package but missing here
# would raise ValueError in make_tool()/make_category_tools() rather than silently
# misbehaving. Grouped by which packages use them, purely for human readability -- the
# engine loads them all together regardless (see the module docstring on why).

# Local-compute categories (tools/Public/*/.claude/tools/<tool-name>/, via make_tool()):
_LOCAL_COMPUTE_CATEGORIES = [
    "aging_cohort", "chem_compute", "clinical_calculators", "clinical_trial_stats",
    "coexpression_module", "colocalization", "crystal_structure", "data_quality",
    "decoupler_ulm", "degrees_of_unsaturation", "deseq2", "dn_ds", "dose_response",
    "drug_properties", "edger_limma", "epidemiology", "finemap_abf", "gsea_prerank",
    "gsva", "health_disparities", "mendelian_randomization", "meta_analysis",
    "visualization_molecule_3d", "nca", "network_proximity", "phykit", "popgen", "protparam",
    "rdkit_cheminfo", "roc_analysis", "smiles_verify", "spredixcan", "ssgsea",
    "survival", "tooluniverse_page", "variant_fraction", "vcf_stats",
]

# REST-API-wrapping categories (tools/Plugin/.claude/tools/<category-key>/, via
# make_category_tools()) -- keyless-only for now; categories that hard-require a
# credential (cluspro, clue, mcule, biogrid, literature_search, OpenAlex, iucn,
# uscensus) and the two paired-login chemistry ones (brenda, metacyc) are deliberately
# not included yet.
_PLUGIN_CATEGORIES = [
    # Protein & structural biology databases
    "alphafill", "alphafold", "antibody_registry", "bmrb", "cath", "channelsdb",
    "complex_portal", "cryoet", "disprot", "dynamut2", "ebi_alignment",
    "ebi_proteins_coordinates", "ebi_proteins_epitope", "ebi_proteins_ext",
    "ebi_proteins_features", "ebi_sequence", "elm", "emdb", "empiar", "foldseek",
    "fpbase", "glygen", "gpcrdb", "hpa", "interpro", "interpro_domain_arch",
    "interpro_entry", "interpro_ext", "interpro_member_db", "interproscan", "iptmnet",
    "iupred3", "mddb", "membrane_topology", "mobidb", "pdb_redo", "pdbe_api",
    "pdbe_graph", "pdbe_kb", "pdbe_search", "pdbe_sifts", "pdbe_validation", "pdbepisa",
    "pdbtm", "pfam", "prosite", "proteins_api", "proteinsplus", "rcsb_advanced_search",
    "rcsb_data", "rcsb_graphql", "rcsb_pdb", "rcsb_search", "sabdab", "sasbdb",
    "scanprosite", "skempi", "structure_annotation", "swissmodel", "tcdb",
    "therasabdab", "three_d_beacons", "uniparc", "uniprot", "uniprot_idmapping",
    "uniprot_locations", "uniprot_proteomes", "uniprot_ref", "uniprot_taxonomy",
    "uniref",
    # Omics data repositories
    "allen_cell_types", "archs4", "arrayexpress", "bgee", "bioimage_archive",
    "biosamples", "biostudies", "cbioportal", "cellmarker", "cellosaurus",
    "cellpainting", "celltypist_catalog", "cellxgene_discovery",
    "dandi", "expression_anova", "expression_atlas", "gdc", "geo", "gmrepo", "gtex",
    "gtex_v2", "gxa", "hca_tools", "hubmap", "hubmap_sample", "idr", "idr_searchengine",
    "l1000fwd", "lincs", "massive", "metaboanalyst", "metabolights",
    "metabolomics_workbench", "mgnify", "mgnify_expanded", "ncbi_sra", "neurovault",
    "omicsdi", "openneuro", "panglaodb", "pdc", "pride", "proteomexchange",
    "proteomicsdb", "proteomicsdb_meltome", "scxa", "single_cell_portal", "sra", "tcia",
    "ucsc_cell_browser",
    # Chemistry & small-molecule databases (brenda/metacyc excluded: paired-login auth)
    "aopwiki", "bigg_models", "bindingdb", "chebi", "ChEMBL", "classyfire",
    "cod_crystal", "drug_synergy", "emolecules", "enamine", "gnps", "klifs",
    "lipidmaps", "lipidmaps_gene", "lotus", "massbank", "mcsa", "metabolite", "mibig",
    "nci_cactus", "npatlas", "opsin", "pdbe_compound", "pdbe_ligands", "pharmacodb",
    "protacdb", "pubchem", "pubchem_bioassay", "pubchem_tox", "rcsb_chemcomp", "rhea",
    "rhea_reaction", "sabiork", "swissadme", "swissdock", "swisslipids", "synergxdb",
    "t3db", "tdc_dataset", "unichem", "zinc",
    # Pathway, network & functional annotation (biogrid excluded: requires API key)
    "biomodels_tools", "ebi_proteins_interactions", "Enrichr", "enrichr_ext", "go",
    "go_api", "gprofiler", "harmonizome", "hocomoco", "HumanBase", "indra", "intact",
    "jaspar", "kegg", "kegg_brite", "kegg_ext", "kegg_network_variant", "msigdb",
    "ndex", "omnipath", "panther", "pathwaycommons", "plant_reactome", "ppi", "quickgo",
    "reactome", "reactome_analysis", "reactome_content", "reactome_interactors",
    "remap", "signor", "stitch", "string_ext", "string_network", "unibind",
    "wikipathways", "wikipathways_ext",
    # Literature & bibliometric search (literature_search, OpenAlex excluded: need a key)
    "arxiv", "bgpt", "biorxiv", "biorxiv_ext", "core", "crossref", "datacite",
    "dataone", "dataverse", "dblp", "doaj", "dryad", "epmc_annotations", "EuropePMC",
    "europepmc_annotations", "europepmc_citations", "fatcat", "figshare", "hal",
    "icite", "inspirehep", "litvar", "medrxiv", "mesh", "openaire", "openaire_dataset",
    "opencitations", "orcid", "osf_preprints", "pmc", "pubmed", "pubtator",
    "pubtator3_ext", "re3data", "retraction", "ror", "scite", "semantic_scholar",
    "semantic_scholar_ext", "unpaywall", "zenodo",
    # Model-organism & taxon-specific genome databases
    "alliance_genome", "bacdive", "bvbrc", "flybase", "flymine", "gtdb", "impc",
    "mediadive", "mgi", "mousemine", "mpd", "pombase", "rgd", "rgd_strain", "sgd",
    "sgd_protein", "veupathdb", "wormbase", "xenbase", "zfin",
    # Earth science, weather & space/astronomy
    "ceda", "epa_envirofacts", "erddap", "jpl_horizons", "marine_regions", "metnorway",
    "nasa_cmr", "nasa_donki", "nasa_eonet", "nasa_exoplanet", "nasa_ned", "nasa_osdr",
    "nasa_sbdb", "nws", "open_meteo", "open_meteo_airquality", "open_meteo_climate",
    "open_meteo_flood", "open_meteo_marine", "opentopodata", "sdss", "simbad",
    "sunrise_sunset", "usgs_earthquake", "usgs_water", "waqi",
    # Biodiversity, taxonomy & ecology (iucn excluded: requires API key)
    "col", "ebi_taxonomy", "ebird_taxonomy", "eol", "gbif", "gbif_ext",
    "gbif_taxonomy", "goat", "idigbio", "inaturalist", "itis", "obis", "opentree",
    "paleobiology", "powo", "usda_plants", "worms",
    # Public health, socioeconomic & government statistics (uscensus excluded: needs key)
    "cdc", "cms_open_payments", "datagov", "dhs_program", "disease_sh_ext",
    "diseasesh", "euhealth", "eurostat", "nhanes", "nih_reporter", "odphp", "who_gho",
    "worldbank",
    # Niche peptide/antimicrobial/immunology databases
    "ampsphere", "ampsphere_record", "cancerppd2", "conoserver", "dbaasp",
    "hemolytik2", "hlaligandatlas", "mhcmotifatlas", "norine", "pepcalc", "peplife2",
    "peptideatlas", "tumorhope2",
]

_CATEGORIES = _LOCAL_COMPUTE_CATEGORIES + _PLUGIN_CATEGORIES

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        import inspect

        _ensure_vendor_on_path()
        from tooluniverse import ToolUniverse

        _engine = ToolUniverse()
        # ToolUniverse.load_tools()'s accepted kwargs vary by installed version: the
        # upstream GitHub source has a rich `categories=`/`quiet=`/... signature, but
        # the published PyPI release a bare `pip install tooluniverse` resolves to
        # today (0.2.0) only has the older, minimal `load_tools(tool_type=None)` --
        # `categories=` and `quiet=` both raise TypeError there. Introspect what's
        # actually available rather than hardcoding one shape, so this keeps working
        # whichever version ends up installed.
        params = inspect.signature(_engine.load_tools).parameters
        kwargs = {"categories" if "categories" in params else "tool_type": _CATEGORIES}
        if "quiet" in params:
            kwargs["quiet"] = True
        _engine.load_tools(**kwargs)
    return _engine


def make_tool(tool_name: str):
    """Build one claude_agent_sdk @tool object for a named ToolUniverse tool. Its
    description and parameter schema are read live from the installed package; only the
    tool_name string (a functional identifier, e.g. "PopGen_hwe_test") is passed in by
    the caller."""
    engine = _get_engine()
    config = engine.all_tool_dict.get(tool_name)
    if config is None:
        raise ValueError(f"ToolUniverse tool not found after loading categories {_CATEGORIES}: {tool_name!r}")
    description = config.get("description") or tool_name
    schema = config.get("parameter") or {"type": "object", "properties": {}}

    async def _handler(args: dict) -> dict:
        try:
            result = await asyncio.to_thread(engine.run_one_function, {"name": tool_name, "arguments": args})
            text = json.dumps(result, ensure_ascii=False, default=str, indent=2)
            return {"content": [{"type": "text", "text": text}]}
        except Exception as exc:  # noqa: BLE001 -- surfaced as tool output, not a crash
            return {"content": [{"type": "text", "text": f"{tool_name} failed: {exc}"}], "is_error": True}

    _handler.__name__ = f"tu_{tool_name}"
    return tool(tool_name, description, schema)(_handler)


def make_tools(tool_names: list) -> list:
    """Build a claude_agent_sdk @tool object for each of several named ToolUniverse
    tools, for bundling into one MCP server. Used to group the local-compute tools
    (originally one server per tool) into a handful of domain-level bundles for the
    same command-line-length reason make_categories_tools() exists for -- see that
    function's docstring."""
    return [make_tool(name) for name in tool_names]


def make_category_tools(category_key: str) -> list:
    """Build a claude_agent_sdk @tool object for every tool in one ToolUniverse
    category, for bundling into a single multi-tool MCP server (tools/Plugin/).

    Filters by each loaded tool's `source_file` (the category's own JSON config path,
    stamped unconditionally by execute_function.py's load_tools()) rather than by its
    `category` field: a handful of categories (e.g. cellmarker, pdbepisa) hard-code
    their own human-readable `category` string in their JSON, and load_tools() only
    back-fills `category` with the loader key when the field is absent -- so filtering
    on `category` silently misses exactly those. `source_file` has no such escape
    hatch; it's always set from the same category->file mapping this bridge itself
    requested the category by, so it's the reliable match."""
    return _tools_for_category(category_key)


def make_categories_tools(category_keys: list) -> list:
    """Like make_category_tools(), but for several categories bundled into ONE MCP
    server (tools/Plugin/<cluster>/). Each MCP server -- regardless of how many @tool
    functions it holds -- costs one entry in the JSON blob the Claude Agent SDK's CLI
    transport serializes into a single `--mcp-config` command-line argument
    (subprocess_cli.py's _build_command()); with ~400 categories each as their own
    server, that combined argument exceeded the OS command-line length limit and broke
    session startup entirely (not just for sessions using these tools). Bundling many
    categories behind one server keeps every individual tool callable while cutting the
    entry count the CLI invocation actually scales with."""
    tools = []
    for key in category_keys:
        tools.extend(_tools_for_category(key))
    return tools


def _tools_for_category(category_key: str) -> list:
    engine = _get_engine()
    expected_file = engine.tool_files.get(category_key)
    if expected_file is None:
        raise ValueError(f"Category {category_key!r} not in this engine's tool_files")
    expected_path = str(Path(expected_file).resolve())
    names = [
        t["name"]
        for t in engine.all_tools
        if t.get("name") and t.get("source_file") and str(Path(t["source_file"]).resolve()) == expected_path
    ]
    if not names:
        raise ValueError(f"No ToolUniverse tools found for category {category_key!r} after loading categories {_CATEGORIES}")
    return [make_tool(name) for name in names]
