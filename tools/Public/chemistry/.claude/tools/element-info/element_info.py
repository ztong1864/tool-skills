"""In-process (SDK) tool: element symbol -> periodic table data.

First "sdk_python" backing (see tool_backing_service.py's module docstring
for the schema) -- runs in this backend's own process via
claude_agent_sdk.create_sdk_mcp_server(), no network call and no credential.

Data comes from the `periodictable` package (IUPAC-sourced) rather than
hand-typed values, to avoid transcription errors across 118 elements.

Convention for local tools (mirrors ToolUniverse's chem_compute_tool.py):
import optional/heavy dependencies lazily, inside the @tool handler, not at
module top level. That way the module still imports and the tool still
registers even if the dependency isn't installed -- only calling it fails,
with a message naming exactly what's missing. A top-level import instead
fails the whole module import, which tool_backing_service.py's
_load_sdk_server() swallows silently: the tool just wouldn't appear in the
catalog, with no clue why.
"""

from claude_agent_sdk import create_sdk_mcp_server, tool


@tool(
    "element_info",
    "Look up periodic table information for a chemical element by its symbol (e.g. 'Fe', 'O', 'Au').",
    {"symbol": str},
)
async def element_info(args: dict) -> dict:
    try:
        import periodictable as pt
    except ImportError as exc:
        return {
            "content": [{"type": "text", "text": f"periodictable is required for element_info: {exc}"}],
            "is_error": True,
        }

    symbol = str(args.get("symbol", "")).strip()
    try:
        element = pt.elements.symbol(symbol.capitalize())
    except (ValueError, KeyError):
        return {
            "content": [{"type": "text", "text": f"Unknown element symbol: {symbol!r}"}],
            "is_error": True,
        }

    density = getattr(element, "density", None)
    covalent_radius = getattr(element, "covalent_radius", None)
    isotopes = sorted(element.isotopes)

    lines = [
        f"Symbol: {element.symbol}",
        f"Name: {element.name}",
        f"Atomic number: {element.number}",
        f"Atomic mass: {element.mass:.4f} g/mol",
        f"Density: {density:.4g} g/cm^3" if density is not None else "Density: unknown",
        f"Covalent radius: {covalent_radius:.3g} Å" if covalent_radius is not None else "Covalent radius: unknown",
        f"Known isotopes (mass numbers): {', '.join(str(i) for i in isotopes)}" if isotopes else "Known isotopes: none listed",
    ]
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


SERVER = create_sdk_mcp_server(name="element-info", tools=[element_info])
