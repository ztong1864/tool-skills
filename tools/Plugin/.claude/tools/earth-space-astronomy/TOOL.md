---
name: earth-space-astronomy
description: "地球科学、气象与天文：Open-Meteo 系列、NASA 系列、USGS、天文星表（SDSS、SIMBAD、JPL Horizons）等，共 26 个 ToolUniverse 类别、约 50 个工具。（基于 ToolUniverse，https://github.com/mims-harvard/ToolUniverse）"
category: earth-environment-agriculture
---

# earth-space-astronomy (ToolUniverse-backed research service)

Runs in this backend's own process via `claude_agent_sdk.create_sdk_mcp_server()` --
no credential needed (every category bundled here is keyless upstream), though the
underlying ToolUniverse tools themselves call out to each database's public API over
HTTP. Bundles 26 ToolUniverse categories -- 地球科学、气象与天文 --
into ONE multi-tool "research service" entry via the shared bridge's
`make_categories_tools()` at `tools/tool-service/tooluniverse_bridge.py`; every tool
name, description, and parameter schema is introspected live from the vendored
[ToolUniverse](https://github.com/mims-harvard/ToolUniverse) package at runtime, not
hand-copied here.

**Why one entry for this many categories**: the Claude Agent SDK's CLI transport
serializes every registered MCP server into one JSON blob passed as a single
`--mcp-config` command-line argument -- cost scales with the number of *server
entries*, not the number of tools inside each one. An earlier one-server-per-category
layout (~400 entries total across all ToolUniverse-backed tools) exceeded the OS
command-line length limit and broke chat session startup entirely, not just sessions
using these tools. Grouping by research theme keeps every individual tool just as
callable while cutting the entry count this scales with.

Categories bundled: "ceda", "epa_envirofacts", "erddap", "jpl_horizons", "marine_regions", "metnorway", "nasa_cmr", "nasa_donki", "nasa_eonet", "nasa_exoplanet", "nasa_ned", "nasa_osdr", "nasa_sbdb", "nws", "open_meteo", "open_meteo_airquality", "open_meteo_climate", "open_meteo_flood", "open_meteo_marine", "opentopodata", "sdss", "simbad", "sunrise_sunset", "usgs_earthquake", "usgs_water", "waqi".
