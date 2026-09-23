---
name: element-info
description: 元素符号查询：给定化学元素符号（如 Fe、O、Au），返回元素名称、原子序数、原子质量、密度、共价半径与已知同位素。
category: chemistry
---

# element-info (local/in-process tool)

Runs in this backend's own process via `claude_agent_sdk.create_sdk_mcp_server()`
-- no network call, no credential. Source: `element_info.py` in this same folder,
loaded via `backing.json`'s `module_path`. Data from the `periodictable` package
(IUPAC-sourced).

This is the reference example for the `sdk_python` backing type documented
in `tool_backing_service.py`'s module docstring.
