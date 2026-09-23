---
name: scitoolagent-chem
description: "SciToolAgent-Chem（SCP 广场 #31，浙江大学）：面向化学实验、反应工程及材料科学的综合性辅助工具库，集成化学结构格式互转（SMILES/InChI/CAS/SELFIES）、分子性质与描述符计算（分子量、拓扑指纹、电子描述符、TPSA）、化学反应预测与逆合成路径规划、分子相似度与子结构匹配、官能团识别与立体化学分配、安全性与爆炸性评估、分子聚类与机器学习分类等 169 个工具。"
category: chemistry
---

# SciToolAgent-Chem (SCP Hub #31)

Remote MCP tool server hosted on SCP 广场（浙江大学）. Source:
https://scphub.intern-ai.org.cn/detail/31

Built on the open-source [SciToolAgent](https://github.com/HICAI-ZJU/SciToolAgent)
project (HICAI-ZJU lab, Zhejiang University).

Connects via `backing.json` in this same folder (streamable-HTTP MCP,
`SCP-HUB-API-KEY` header). Credentials are per-admin, not shared: an admin
registers their own key via `POST /api/tool-credentials` with just
`{"tool_ref": "scitoolagent-chem", "secret": "..."}` — the backend derives the
storage scope from that admin's own identity server-side (see
`tool_credential_service.admin_owner_scope()`), so this only becomes usable in
*that admin's own* chat sessions. Other admins need to register their own key
separately; there is no shared fallback.

169 individual tools are exposed (structure conversion, descriptor/property
calculators, reaction prediction & retrosynthesis, similarity/substructure
matching, functional-group and stereochemistry assignment, safety/explosivity
assessment, ML-based molecule clustering/classification). No fixed shared
schema across them the way `SciGraph`/`SciGraph-*` share one — each is its
own named tool; see the upstream detail page for the full list.
