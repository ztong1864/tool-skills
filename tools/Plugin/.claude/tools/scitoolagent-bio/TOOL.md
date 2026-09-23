---
name: scitoolagent-bio
description: "SciToolAgent-Bio（SCP 广场 #29，浙江大学）：面向蛋白质组学、基因组学及生物分子设计的综合性工具库，集成蛋白质理化性质计算（等电点、分子量、消光系数、疏水性）、DNA/RNA 序列分析与密码子优化、蛋白质结构预测与折叠、序列比对与相似度分析、信号肽/跨膜区/无序区预测、肽库与突变库设计、酶切位点分析、抗体 CDR 标注、药物-靶标相互作用预测等 57 个工具。"
category: life-sciences-bioinformatics
---

# SciToolAgent-Bio (SCP Hub #29)

Remote MCP tool server hosted on SCP 广场（浙江大学）. Source:
https://scphub.intern-ai.org.cn/detail/29

Built on the open-source [SciToolAgent](https://github.com/HICAI-ZJU/SciToolAgent)
project (HICAI-ZJU lab, Zhejiang University).

Connects via `backing.json` in this same folder (streamable-HTTP MCP,
`SCP-HUB-API-KEY` header). Credentials are per-admin, not shared: an admin
registers their own key via `POST /api/tool-credentials` with just
`{"tool_ref": "scitoolagent-bio", "secret": "..."}` — the backend derives the
storage scope from that admin's own identity server-side (see
`tool_credential_service.admin_owner_scope()`), so this only becomes usable in
*that admin's own* chat sessions. Other admins need to register their own key
separately; there is no shared fallback.

57 individual tools are exposed (protein physicochemical property calculators,
DNA/RNA sequence analysis & codon optimization, structure prediction/folding,
sequence alignment/similarity, signal peptide / transmembrane / disorder
prediction, peptide & mutation library design, restriction-site analysis,
antibody CDR annotation, drug-target interaction prediction, solubility
assessment). No fixed shared schema across them the way `SciGraph`/`SciGraph-*`
share one — each is its own named tool; see the upstream detail page for the
full list.
