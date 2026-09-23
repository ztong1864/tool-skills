---
name: scitoolagent-mat
description: "SciToolAgent-Mat（SCP 广场 #30，浙江大学）：面向材料科学、固体物理及电化学领域的专业化工具库，集成 MOF 框架结构解析（晶格参数、分数坐标、拓扑特征）、Materials Project 数据库对接（材料搜索、带隙/能量/密度查询、电子结构分析、磁性与介电性质获取）、电池材料性能评估（工作电压、容量、循环稳定性）、分子热力学与振动性质计算、材料吸附与稳定性预测、晶体对称性与键合信息分析等 8 个工具。"
category: physics-materials-science
---

# SciToolAgent-Mat (SCP Hub #30)

Remote MCP tool server hosted on SCP 广场（浙江大学）. Source:
https://scphub.intern-ai.org.cn/detail/30

Built on the open-source [SciToolAgent](https://github.com/HICAI-ZJU/SciToolAgent)
project (HICAI-ZJU lab, Zhejiang University).

Connects via `backing.json` in this same folder (streamable-HTTP MCP,
`SCP-HUB-API-KEY` header). Credentials are per-admin, not shared: an admin
registers their own key via `POST /api/tool-credentials` with just
`{"tool_ref": "scitoolagent-mat", "secret": "..."}` — the backend derives the
storage scope from that admin's own identity server-side (see
`tool_credential_service.admin_owner_scope()`), so this only becomes usable in
*that admin's own* chat sessions. Other admins need to register their own key
separately; there is no shared fallback.

8 individual tools are exposed (MOF framework structure parsing, Materials
Project database lookups, battery-material performance evaluation, molecular
thermodynamics/vibrational property calculation, adsorption & stability
prediction, crystal symmetry & bonding analysis). No fixed shared schema
across them the way `SciGraph`/`SciGraph-*` share one — each is its own named
tool; see the upstream detail page for the full list.
