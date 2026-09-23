---
name: scigraph
description: "SciGraph（SCP 广场 #37，浙江大学牵头/上海人工智能实验室联合打造）：面向科学研究的统一知识图谱查询服务，集成生命科学、地球科学、材料科学、数学物理等 70 个学科知识图谱（含约 2309 万节点、7400 余万关系的 ElementKG 化学知识图谱等），支持 Cypher 查询、图谱统计、节点/关系类型检索。"
category: general
---

# SciGraph (SCP Hub #37)

Remote MCP tool server hosted on SCP 广场（由浙江大学牵头，联合上海人工智能实验室共同打造）. Source:
https://scphub.intern-ai.org.cn/detail/37

Connects via `backing.json` in this same folder (streamable-HTTP MCP,
`SCP-HUB-API-KEY` header). Credentials are per-admin, not shared: an admin
registers their own key via `POST /api/tool-credentials` with just
`{"tool_ref": "scigraph", "secret": "..."}` — the backend derives the storage
scope from that admin's own identity server-side (see
`tool_credential_service.admin_owner_scope()`), so this only becomes usable in
*that admin's own* chat sessions. Other admins need to register their own key
separately; there is no shared fallback.

## Tools exposed

- `query_cypher(cypher, kg_name, limit=100)` — run a Cypher query against a knowledge graph. `kg_name` is required (this base server does not aggregate across graphs the way the domain-scoped `SciGraph-*` variants do).
- `get_kg_statistics(kg_name)` — node/relationship counts and type distributions for a graph.
- `get_node_labels(kg_name)` — list node types (labels) in a graph.
- `get_relationship_types(kg_name)` — list relationship types in a graph.

`kg_name` accepts any of 70 graphs spanning life science, earth science, materials
science, math/physics, chemistry, etc. (e.g. `ElementKG`, `ProteinKG25`, `TxGNN`,
`MatKG`). Full list on the upstream detail page above.

Domain-scoped siblings with the same 4-tool interface exist for narrower graph
sets and cross-graph aggregation (omit `kg_name` to query every graph in that
domain at once): `SciGraph-Bio`, `SciGraph-Material`, `SciGraph-MathPhys`,
`SciGraph-Earth`, `SciGraph-TCM` — not yet installed here.
