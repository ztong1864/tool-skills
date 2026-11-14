---
name: proengagent
description: 调用 ProEngAgent 蛋白质工程服务：按序列算理化性质（ProtParam、分子式、氨基酸组成、序列特征）、按 UniProt/PDB 编号取序列与结构、ESMFold 预测结构、DSSP 指认二级结构、Pythia 做稳定性打分（单点突变全扫描与整体结构打分）、解析 PDF；另有 list_tools / describe_tool / run_tool 可查用目录里其余约 95 个工具（对接、设计、比对检索、能量与动力学、嵌入、办公文档生成），upload_file 把本对话的文件送到服务端，read_output 取回结果文件。突变打分与定向进化请用 esm-directed-evolution 技能。
category: life-sciences-bioinformatics
---

# proengagent (local/in-process tool)

Runs in this backend's own process via `claude_agent_sdk.create_sdk_mcp_server()`, calling
the ProEngAgent REST service (`PROENGAGENT_BASE_URL`, set in `api/.env`) over HTTP.
Source: `tool.py` in this same folder, loaded via `backing.json`'s `module_path`.

This replaces the `proengagent-api` skill
(`skills/Device/iBioFoundry/.claude/skills/proengagent-api`), which was 25 KB of prose the
model had to read before hand-writing its own HTTP calls, and whose own description
advertised mutation and design work it then forbade. Nothing of substance is lost: the
tool catalog it pasted in now lives in `catalog.json`, which `refresh_catalog.py` re-fetches.

No credential: the service's tool endpoints are open on the deployment we use. Should it
ever require a token, add a `credential` block to `backing.json` — the framework already
supports it, and nothing in `tool.py` would change.

## Tools (19)

**Sequence** — `sequence_length`, `ProtParam` (the default properties answer, molecular
weight included), `biopython_sequence_features` (the same ground as JSON numbers),
`AAComposition`, `AAFormula`, `uniprot_to_sequence`, `pdb_to_sequence`.

**Structure** — `get_pdb` (fetch from RCSB onto the service), `esm_fold` (predict from
sequence), `biopython_pdb_info`, `dssp_assign`.

**Stability** — `Pythia_Mut` scores every single substitution at every residue and reports
the named one plus the most stabilising ones; `Pythia_Seq` gives one score for a whole
structure. Meant as the filter after the `esm-directed-evolution` skill has ranked
candidates, before they go to the bench.

**Documents** — `parse_pdf_document`.

**Catalog and files** — `list_tools`, `describe_tool`, `run_tool` reach the other ~95 tools
(docking, ProteinMPNN/RFdiffusion design, Foldseek/MMseqs/BLAST search, FoldX/Rosetta
energy, embeddings, docx/xlsx/pptx generation); `upload_file` sends a file from the chat's
own uploads to the service, since the service runs on another machine and cannot see local
paths; `read_output` fetches a result file and saves it into the chat user's workspace.

## Two deliberate decisions

**Mutation scoring is refused here.** `multievolve_api`, `multi_evolve_api` and
`esm_zeroshot` belong to the `esm-directed-evolution` skill, whose workflow — the round
structure, the pauses where the user picks candidates, the required reply format — is the
point of it. A bare tool call would be a way around all of it, so `run_tool` refuses those
three by name and says where to go instead. It is the only hard refusal in the file.

**Everything else is allowed to fail honestly.** The service's catalog has no "is this
usable" field, and an undeployed tool still answers HTTP 200 — with `{"success": false,
"deployed": false}` buried inside `output`. Every handler reads both layers and turns such
an answer into an error carrying the service's own reason. `catalog.json` additionally
carries a `probe` verdict per tool from calling it; as of the 2026-11-13 snapshot, of the
62 tools probed, 41 work, 10 are not deployed (`protein_sol_predict`, `stride_assign`,
`seqvec_embed`, `carp_embed`, `thermonet_predict`, `soluprot_predict`, `arpeggio_contacts`,
`alphafold_api`, `ddgun_predict`, `imutant2_predict`), 5 time out against their upstream
web servers (`blastp_search`, `interpro_scan`, `PSIPRED`, `PSIPRED_API`, `whatcheck`), and
3 answer with no output at all, `protein_mw` among them. The old
skill's hand-written "Stub" list was wrong in both directions — it listed
`proteinmpnn_api` and `proteinmpnn_design`, which both work.

## Keeping it current

```bash
python refresh_catalog.py --probe     # after the service is upgraded
python selfcheck.py --live            # after any edit, with the backend's venv
```

`selfcheck.py` loads `tool.py` exactly the way `tool_backing_service._load_sdk_server()`
does. Run it after every edit and after deploying: a failed import is swallowed silently,
so a broken file does not raise anywhere — the tool simply stops appearing in chats.
