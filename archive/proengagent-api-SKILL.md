<!--
归档：原 skills/Device/iBioFoundry/.claude/skills/proengagent-api/SKILL.md
原文只存在于服务器（skills/ 与 tools/ 都在 .gitignore 里），2026-11-13 被
tools/Device/iBioFoundry/.claude/tools/proengagent/ 这个 sdk_python 工具取代后，
原文件备份到服务器 /home/vipuser/backup/proengagent-20261113/ 并在此留档。

留档只为查阅历史，不要再安装成技能：它的 description 承诺突变打分和蛋白设计，
会和 esm-directed-evolution 抢触发；正文里的服务地址是写死的；手写的 Stub 清单
两头都不准（proteinmpnn_api/proteinmpnn_design 实际可用，而 protein_sol_predict、
stride_assign、seqvec_embed 等十个工具实际未部署）。当前的工具目录事实见
tools/Device/iBioFoundry/.claude/tools/proengagent/catalog.json。
-->

---
name: proengagent-api
description: ProEngAgent 通用工具， 通过该工具可以进行蛋白质设计，突变位点推荐等功能。适用工具包括 sequence_length（序列长度）、AAComposition（氨基酸组成）、AAFormula（分子式）、ProtParam 和 protein_mw（蛋白质理化性质/分子量）、biopython_pdb_info（PDB 结构信息）、read_file（读取工作区结果）、create_docx_document、create_xlsx_workbook、create_pptx_deck（生成文档/表格/演示文稿）及 parse_pdf_document（提取 PDF 文本）。目录中还包含突变相关工具：multi_evolve_api 和 multievolve_api 提供零样本突变评分与 Top-K 变体，esm_zeroshot 扫描变体效应，Pythia_Mut、ddgun_predict 和 imutant2_predict 对指定突变进行预测，evmutation_score 标记为 Stub。
---

# ProEngAgent API

使用本技能发现 ProEngAgent 工具，并根据任务选择允许范围内的工具。

## 工具目录与选择

下表说明本技能可调用范围内工具的用途、适用任务及目录中列出的输入字段。每次调用前仍须通过实时目录和 `/docs` 核对名称、输入字段、类型、必填项及可用状态。

| 工具 | 功能 | 适合的任务 | 目录输入字段 |
|---|---|---|---|
| `sequence_length` | 统计氨基酸序列的残基数，支持序列或 FASTA。 | 用户只需知道序列长度时。 | `sequence` |
| `AAComposition` | 计算氨基酸组成。 | 用户想查看各类氨基酸的组成统计时。 | `sequence` |
| `AAFormula` | 根据序列计算分子式。 | 用户需要序列对应的分子式时。 | `sequence` |
| `ProtParam` | 使用 Biopython ProtParam 计算蛋白质基础性质。 | 用户需要常规蛋白质理化性质概览时。 | `sequence` |
| `protein_mw` | 调用 Novopro 分子量 API 计算蛋白质分子量；目录还列出标签和拷贝数参数。 | 用户需要估算给定序列/标签/拷贝数对应的分子量时。 | `sequence`, `tag`, `copies` |
| `biopython_pdb_info` | 提取 PDB 结构文件的描述性信息。 | 用户想检查已有结构文件的基本信息时。 | `pdb_file` |
| `read_file` | 读取 workspace 下的工具输出文件；目录列出 pattern、head、tail、max_chars 等筛选/截取选项。 | 用户要求查看本服务先前生成、且路径符合 workspace 规则的结果时。 | `file_path`, `pattern`, `head`, `tail`, `max_chars` |
| `create_docx_document` | 将 Markdown 内容生成 Word 文档。 | 用户要把已提供或已整理的文本制作为 DOCX 时。 | `content_markdown`, `title` |
| `create_xlsx_workbook` | 根据列名和数据行创建 Excel 工作簿。 | 用户要将表格数据制作为 XLSX 时。 | `columns`, `rows`, `title` |
| `create_pptx_deck` | 根据结构化幻灯片内容创建 PowerPoint。 | 用户要将已整理的标题和要点制作为 PPTX 时。 | `slides`, `title` |
| `parse_pdf_document` | 使用 pypdf 提取 PDF 各页文本。 | 用户要求读取 PDF 中的文字内容时。 | `pdf_file` |

### 选择工具的简要规则

- 只问序列有多长：选 `sequence_length`。
- 需要组成或分子式：分别选 `AAComposition` 或 `AAFormula`。
- 需要基础理化性质：选 `ProtParam`；明确要求分子量时选 `protein_mw`。
- 要检查已有 PDB 文件的描述信息：选 `biopython_pdb_info`。
- 要查看本服务 workspace 中已有的输出：选 `read_file`，并遵守服务端路径规则。
- 要从文本/表格/幻灯片内容生成办公文件：分别选 `create_docx_document`、`create_xlsx_workbook`、`create_pptx_deck`。
- 要提取 PDF 文本：选 `parse_pdf_document`。
- 若用户请求不属于上表，先查目录并判断是否属于本技能范围；不在允许范围内的生物设计、工程或优化任务不要调用。

## 突变相关工具概览

参考文档还列出以下突变相关工具，供理解目录功能和状态：

| 工具 | 文档中的功能说明 |
|---|---|
| `multi_evolve_api`、`multievolve_api` | ESM 零样本突变评分及 Top-K 变体。两者在目录中分别列出，实际差异需查当前部署。 |
| `esm_zeroshot` | ESM 零样本变体效应扫描。 |
| `Pythia_Mut` | 对指定点突变进行稳定性评分。 |
| `ddgun_predict` | 预测指定突变的自由能变化。 |
| `imutant2_predict` | 预测指定突变的稳定性变化。 |
| `evmutation_score` | EVmutation 评分工具；目录标记为 Stub，实际状态需核实。 |

## 服务与请求流程

参考文档列出的开发预览基础 URL 为 `http://10.98.35.223:7861`。该地址仅适用于特定环境。只有在用户为当前任务提供或确认其他主机时才使用其他地址；不要假定当前环境能够访问预览地址。

1. 不确定工具名称或参数时，先请求 `GET {base_url}/api/general/tools`。
2. 只选择适用范围内的工具，并严格使用目录返回的大小写敏感名称。
3. 查看该工具的 `inputs` 映射。不要把输出字段名或内部实现映射误当成 API 输入字段名。
4. 构造 POST 请求前，先查看 `{base_url}/docs` 中当前的 `ToolExecuteRequest` 和工具专属 schema。源文档明确说明，`{"inputs": {...}}` 只是示意，因为它没有提供外层请求模型。
5. 确认请求 schema 后，再发送 `POST {base_url}/api/general/tool/{name}`。只传必需且相关的字段。不要猜测字段类型、默认值、枚举值或文件语义。
6. 返回 HTTP 状态码和简明结果摘要。将任务 ID、文件路径视为响应数据；只有用户要求时才继续读取结果，并遵守服务端说明的 workspace 路径限制。

## 不确定情况与错误处理

- 如果无法访问服务 schema，明确说明请求格式尚未核实。可以将参考文档中的请求体形态标注为“未验证示例”，但不能将其表述为已确认格式。
- 如果目录将工具标记为 `Stub`、`experimental` 或 `beta`，在依赖该工具前说明其状态。`has_wrapper: true` 仅表示找到了可解析的 wrapper，不代表依赖已安装、外部服务可访问或结果可用。
- 如果服务器拒绝请求，依据错误响应或 `/docs` 仅修正有依据的字段名和类型。不要反复猜测。
- 妥善保护密钥和凭据，不要将其写入命令历史或回复内容。不要虚构凭据。

## 原始 API 工具目录（参考资料）

以下内容保留源文档作为工具目录参考；调用仍遵循本技能的适用范围和请求核对流程。

# ProEngAgent API 工具调用说明

> 本说明依据用户提供的 `GET /api/general/tools` 返回目录整理。该目录的 `inputs` 字段是工具参数名映射。它没有提供 `ToolExecuteRequest` 的完整 Pydantic 定义，因此以下给出的请求体采用常见的 `{"inputs": {...}}` 形态作为示例；实际请求字段外层结构请以服务端 OpenAPI `/docs` 中 `ToolExecuteRequest` 为准。

## 1. API 总览

| 用途 | 方法与路径 | 说明 |
|---|---|---|
| 列出可用工具 | `GET /api/general/tools` | 返回工具名、描述、输入/输出映射、依赖、可靠性及 `has_wrapper`。 |
| 执行指定工具 | `POST /api/general/tool/{name}` | 将 `{name}` 替换为目录中的工具名称；请求体需要提供该工具所需参数。 |

基础 URL（开发预览）：`http://10.98.35.223:7861`

完整调用 URL 示例：`http://10.98.35.223:7861/api/general/tool/sequence_length`

所有请求应以 `/api/general/tools` 返回的 `inputs` 为准。不要将输出映射里的字段名误当成输入。

## 2. 通用调用模板

```http
POST /api/general/tool/{name}
Content-Type: application/json
```

请求体示意（顶层键名需要和 `ToolExecuteRequest` OpenAPI schema 核对）：

```json
{
  "inputs": {
    "sequence": "MKWVTFISLL..."
  }
}
```

curl 示例：

```bash
curl -X POST "http://10.98.35.223:7861/api/general/tool/sequence_length" \
  -H "Content-Type: application/json" \
  -d '{"inputs":{"sequence":"MKWVTFISLL..."}}'
```

调用前先查询目录，确认准确名称和输入字段：

```bash
curl -s "http://10.98.35.223:7861/api/general/tools"
```

## 3. 工具目录与参数说明

以下每项的参数字段名来自目录中的 `inputs`。字段类型、是否必填和限制（除描述中明确写出的内容外）应以 `/docs` 的对应请求 schema 或实际工具实现为准。`func_path`、依赖和可靠性等信息不改变 API 参数名。

### 3.1 序列、蛋白属性及注释

| 工具名称 | 工具描述 | `inputs` 参数 | 使用说明 / 示例参数 |
|---|---|---|---|
| `pdb_to_sequence` | 从 RCSB 获取 PDB 的所有链序列，可指定链。 | `pdb_id`, `chain` | `{"pdb_id":"1ABC","chain":"A"}`；`chain` 可按目录描述选择。 |
| `uniprot_to_sequence` | 通过 UniProt REST API 获取序列。 | `uniprot_id` | `{"uniprot_id":"P01308"}` |
| `sequence_length` | 统计氨基酸残基数，支持原始序列或 FASTA。 | `sequence` | `{"sequence":"MKWVTFISLL..."}` |
| `protein_mw` | Novopro 分子量 API。 | `sequence`, `tag`, `copies` | 序列及可选标签/拷贝数：`{"sequence":"...","tag":"His-tag","copies":1}`。 |
| `protein_iep` | Novopro 等电点 API。 | `sequence`, `pka` | `{"sequence":"...","pka":"..."}`；pka 的具体格式须查 schema。 |
| `ProtParam` | Biopython ProtParam 蛋白性质分析。 | `sequence` | `{"sequence":"..."}` |
| `AAComposition` | 计算氨基酸组成。 | `sequence` | `{"sequence":"..."}` |
| `AAFormula` | 计算分子式。 | `sequence` | `{"sequence":"..."}` |
| `Hydrophathicity` | 生成疏水性 GIF 图。 | `sequence` | `{"sequence":"..."}` |
| `PeptideMass` | 酶切肽段质量计算。 | `sequence`, `enzyme`, `mplus` | `{"sequence":"...","enzyme":"trypsin","mplus":"MH+"}`；枚举值按工具实现确认。 |
| `tmhmm` | 跨膜螺旋预测。 | `sequence` | `{"sequence":"..."}` |
| `SignalP` | SignalP 6.0 信号肽预测。 | `sequence` | `{"sequence":"..."}` |
| `NLStradamus` | 核定位信号预测。 | `sequence` | `{"sequence":"..."}` |
| `filterpro` | 亚细胞定位预测。 | `sequence` | `{"sequence":"..."}` |
| `pecc` | 过氧化物酶体定位信号预测。 | `sequence` | `{"sequence":"..."}` |
| `PSIPRED` | 本地二级结构预测。 | `sequence` | `{"sequence":"..."}` |
| `PSIPRED_API` | UCL PSIPRED REST API。 | `sequence` | `{"sequence":"..."}` |
| `coilcoil` | 卷曲螺旋预测，生成 PNG。 | `sequence` | `{"sequence":"..."}` |
| `ECPred` | Java EC 编号预测。 | `sequence` | `{"sequence":"..."}` |
| `TOMER` | 最适生长温度预测。 | `sequence` | `{"sequence":"..."}` |
| `Prekcatkm` | UniKP + CataPro 动力学参数流程。 | `sequence`, `smiles` | `{"sequence":"...","smiles":"CCO"}` |
| `biopython_sequence_features` | Biopython 序列特征计算。 | `sequence` | `{"sequence":"..."}` |
| `interpro_scan` | 通过 EBI API 做结构域/家族注释。 | `sequence` | `{"sequence":"..."}` |
| `prosite_scan` | 通过 ExPASy 做 ProSite pattern/profile 搜索。 | `sequence` | `{"sequence":"..."}` |
| `deepsol_predict` | DeepSol 可溶性预测。 | `sequence` | `{"sequence":"..."}` |
| `soluprot_predict` | SoluProt 可溶性预测。 | `sequence` | `{"sequence":"..."}` |
| `protein_sol_predict` | Protein-Sol 网页服务可溶性预测。 | `sequence` | `{"sequence":"..."}` |
| `blastp_search` | 通过 NCBI API 执行 BLASTP。 | `sequence` | `{"sequence":"..."}` |
| `Blast` | 通过 Biopython 调用 NCBI BLAST。 | `sequence`, `blastmd`, `db` | `{"sequence":"...","blastmd":"blastp","db":"nr"}`；参数取值按服务端实现确认。 |
| `mmseqs_search` | MMseqs2 序列搜索。 | `query_fasta`, `target_db` | `{"query_fasta":">q\\nSEQUENCE","target_db":"数据库路径或名称"}` |
| `hmmer_search` | HMMER profile 搜索。 | `query_fasta`, `hmm_db` | `{"query_fasta":"...","hmm_db":"HMM数据库路径"}` |
| `cdhit` | cd-hit 序列冗余聚类。 | `sequence` | `{"sequence":"FASTA内容"}` |
| `mmseqs_cluster` | MMseqs2 序列聚类。 | `input_fasta` | `{"input_fasta":"FASTA内容或路径"}`；具体是内容还是路径由实现决定。 |
| `muscle_align` | MUSCLE 多序列比对。 | `sequences` | `{"sequences":["SEQ1","SEQ2"]}`；参数类型以 schema 为准。 |
| `mafft_align` | MAFFT 多序列比对。 | `sequences` | `{"sequences":["SEQ1","SEQ2"]}`；参数类型以 schema 为准。 |
| `filterpro` | 亚细胞定位预测（见上）。 | `sequence` | 此工具仅列一次；同名/同功能项不需重复调用说明。 |
| `multi_evolve_api` | ESM 零样本突变评分及 top-K 变体。 | `sequence` | `{"sequence":"..."}` |
| `multievolve_api` | ESM 零样本突变评分及 top-K 变体。 | `sequence` | `{"sequence":"..."}` |
| `esm_zeroshot` | ESM 零样本变体效应扫描。 | `sequence`, `dms_input`, `dms_output` | 提供序列及输入/输出 DMS 文件参数；示例：`{"sequence":"...","dms_input":"input.csv","dms_output":"out.csv"}`。 |
| `evmutation_score` | EVmutation（目录标为 Stub）。 | `sequence` | 目录将此参数映射到 `fasta_file`；例如 `{"sequence":"..."}`。 |
| `seqvec_embed` | SeqVec 序列嵌入。 | `sequence` | `{"sequence":"..."}` |
| `esm3_embed` | ESM3 embedding，不可用时回退 ESM-2。 | `sequence` | `{"sequence":"..."}` |
| `carp_embed` | CARP 蛋白语言模型 embedding。 | `sequence` | `{"sequence":"..."}` |
| `gremlin_potts` | 从 MSA 推断 GREMLIN Potts 模型。 | `alignment_file` | `{"alignment_file":"对齐文件路径"}` |
| `raptorx_predict` | RaptorX 结构预测服务器。 | `sequence` | `{"sequence":"..."}` |
| `pepfold_predict` | PEP-FOLD3 肽结构预测服务器。 | `sequence` | `{"sequence":"..."}` |

### 3.2 PDB、结构预测与修复

| 工具名称 | 工具描述 | `inputs` 参数 | 使用说明 / 示例参数 |
|---|---|---|---|
| `get_pdb` | 从 RCSB 下载 PDB。 | `pdb_id` | `{"pdb_id":"1ABC"}` |
| `chainPDB` | 从 PDB 提取 A 链序列。 | `pdb_file` | `{"pdb_file":"结构文件路径或目录定义所接受的 PDB 输入"}` |
| `esm_fold` | 通过 ESM Atlas API 预测结构，写入固定路径。 | `sequence` | `{"sequence":"..."}` |
| `boltz2` | Boltz-2 结构预测，可处理配体；需 GPU/conda 环境。 | `sequence`, `ligand` | `{"sequence":"...","ligand":"配体信息"}`；配体格式按实现确认。 |
| `alphafold_api` | AlphaFold 外部 API wrapper。 | `sequence` | `{"sequence":"..."}` |
| `modeller_api` | 本地 MODELLER 同源建模。 | `sequence`, `template_pdb` | `{"sequence":"...","template_pdb":"模板结构路径或PDB内容"}`；按实现确认文件语义。 |
| `saves_api` | SAVEs 结构数据库 API。 | `pdb_id` | `{"pdb_id":"1ABC"}` |
| `clean_pdb` | 移除水分子/配体。 | `pdb_content` | `{"pdb_content":"PDB格式文本"}` |
| `pdbfixer_fix` | PDBFixer 补原子、残基和氢原子。 | `pdb_file` | `{"pdb_file":"结构文件路径"}` |
| `omegafold_predict` | OmegaFold 结构预测。 | `sequence` | `{"sequence":"..."}` |
| `trrosetta_predict` | trRosetta 结构预测。 | `sequence` | `{"sequence":"..."}` |
| `chai1_predict` | Chai-1 结构预测。 | `sequence` | `{"sequence":"..."}` |
| `evoformer_predict` | AlphaFold2 架构 Evoformer 结构预测。 | `sequence` | `{"sequence":"..."}` |
| `rfdiffusion_api` | RFdiffusion 无条件骨架生成；序列只决定长度。 | `sequence` | `{"sequence":"..."}`；不要理解为按输入序列约束设计。 |
| `rfdiffusion_design` | RFdiffusion 骨架生成（与上项描述相同）。 | `sequence` | `{"sequence":"..."}` |
| `biopython_pdb_info` | 提取 PDB 结构信息。 | `pdb_file` | `{"pdb_file":"结构文件路径"}` |
| `whatcheck` | WhatCheck 结构验证。 | `pdb_file` | `{"pdb_file":"结构文件路径"}` |
| `molprobity_api` | 本地 MolProbity 全面结构验证。 | `pdb_file` | `{"pdb_file":"结构文件路径"}` |
| `prorefiner_api` | 结构精修占位实现（Stub）。 | `pdb_file` | `{"pdb_file":"结构文件路径"}`；目录标注 Stub。 |
| `prorefiner_refine` | 结构精修占位实现（Stub）。 | `pdb_file` | `{"pdb_file":"结构文件路径"}`；目录标注 Stub。 |
| `Prank` | 结构口袋预测。 | `pdb_file` | `{"pdb_file":"结构文件路径"}` |
| `Prankweb_API` | Prank Web API 口袋预测。 | `pdb_file` | `{"pdb_file":"结构文件路径"}` |
| `dssp_assign` | DSSP 二级结构赋值。 | `pdb_file` | `{"pdb_file":"结构文件路径"}` |
| `stride_assign` | STRIDE 二级结构赋值。 | `pdb_file` | `{"pdb_file":"结构文件路径"}` |
| `prody_analyze` | ProDy 结构分析。 | `pdb_file` | `{"pdb_file":"结构文件路径"}` |
| `dali_search` | DALI 结构比对服务器。 | `pdb_id` | `{"pdb_id":"1ABC"}` |
| `tm_align` | TM-align 结构叠合。 | `pdb1`, `pdb2` | `{"pdb1":"结构1路径","pdb2":"结构2路径"}` |

### 3.3 对接、抗体和复合物设计

| 工具名称 | 工具描述 | `inputs` 参数 | 使用说明 / 示例参数 |
|---|---|---|---|
| `equibind` | 深度学习蛋白-配体对接。 | `receptor_pdb`, `ligand` | `{"receptor_pdb":"受体PDB路径","ligand":"配体文件路径"}` |
| `equidock` | 蛋白-蛋白对接。 | `receptor_pdb`, `ligand` | `{"receptor_pdb":"受体PDB路径","ligand":"配体PDB路径"}` |
| `diffdock_api` | DiffDock 盲对接。 | `receptor_pdb`, `ligand` | `{"receptor_pdb":"受体PDB路径","ligand":"SMILES字符串"}` |
| `hdock_api` | HDOCK Web API wrapper。 | `receptor_pdb`, `ligand` | `{"receptor_pdb":"受体PDB路径","ligand":"配体结构路径"}` |
| `vina_dock` | AutoDock Vina 分子对接。 | `receptor_pdb`, `ligand_pdb` | `{"receptor_pdb":"受体PDB路径","ligand_pdb":"配体PDB路径"}` |
| `diffab_api` | DiffAb 抗体 CDR 扩散设计；目录说明合并链且不进行物理对接。 | `antibody_pdb`, `antigen_pdb` | `{"antibody_pdb":"抗体PDB路径","antigen_pdb":"抗原PDB路径"}` |
| `diffab_structure` | 保留天然序列，重采样 CDR 主链构象。 | `antibody_pdb`, `antigen_pdb`, `num_samples` | `{"antibody_pdb":"抗体PDB路径","antigen_pdb":"抗原PDB路径","num_samples":10}` |
| `diffab_sequence` | 在天然骨架上重设计 CDR 序列。 | `antibody_pdb`, `antigen_pdb`, `num_samples` | 同上，`num_samples` 为样本数量。 |
| `diffab_codesign` | 联合设计 CDR 序列与结构。 | `antibody_pdb`, `antigen_pdb`, `mode`, `num_samples` | `{"antibody_pdb":"...","antigen_pdb":"...","mode":"codesign","num_samples":10}`；mode 值按 schema 确认。 |
| `diffab_structure` | 抗体/抗原输入下的结构模式设计（见上）。 | `antibody_pdb`, `antigen_pdb`, `num_samples` | 只需调用一次。 |
| `diffab_sequence` | 抗体/抗原输入下的序列模式设计（见上）。 | `antibody_pdb`, `antigen_pdb`, `num_samples` | 只需调用一次。 |

### 3.4 突变效应、稳定性与能量评分

| 工具名称 | 工具描述 | `inputs` 参数 | 使用说明 / 示例参数 |
|---|---|---|---|
| `Pythia_Mut` | Pythia 定点突变稳定性评分。 | `pdb_file`, `mutation` | `{"pdb_file":"结构文件路径","mutation":"A23V"}`；突变命名按实现确认。 |
| `Pythia_Seq` | Pythia 序列/结构稳定性预测。 | `pdb_file` | `{"pdb_file":"结构文件路径"}` |
| `rosetta_api` | Rosetta ddg_monomer 批量突变评分。 | `pdb_file`, `mutations` | `{"pdb_file":"结构文件路径","mutations":["A23V","G45D"]}`；容器类型按 schema 确认。 |
| `foldx_api` | FoldX Stability 计算。 | `pdb_file` | `{"pdb_file":"结构文件路径"}` |
| `mutcompute_api` | MutCompute 特征计算。 | `sequence` | `{"sequence":"..."}`；目录把参数映射至 fasta_file。 |
| `foldx_stability` | FoldX BuildModel 稳定性分析。 | `pdb_file`, `mutations` | `{"pdb_file":"结构文件路径","mutations":["A23V"]}`；具体格式按 schema 确认。 |
| `rosetta_relax` | Rosetta Relax 结构精修。 | `pdb_file` | `{"pdb_file":"结构文件路径"}` |
| `rosetta_ddg` | Rosetta ddg_monomer 突变评分。 | `pdb_file`, `mutations` | `{"pdb_file":"结构文件路径","mutations":"A23V"}`；目录输入映射字段标为 `mutation`。 |
| `ddgun_predict` | DDGun 突变自由能变化预测。 | `wildtype_pdb`, `mutation` | `{"wildtype_pdb":"野生型PDB路径","mutation":"A23V"}` |
| `thermonet_predict` | ThermoNet 热稳定性预测。 | `pdb_file` | `{"pdb_file":"结构文件路径"}` |
| `imutant2_predict` | I-Mutant2.0 网页稳定性预测。 | `sequence`, `mutation` | `{"sequence":"...","mutation":"A23V"}` |
| `multi_evolve_api` | ESM 零样本突变评分与进化变体建议。 | `sequence` | `{"sequence":"..."}` |
| `multievolve_api` | ESM 零样本突变评分与进化变体建议。 | `sequence` | `{"sequence":"..."}` |
| `evmutation_score` | EVmutation（目录标为 Stub）。 | `sequence` | `{"sequence":"FASTA内容或路径"}`；实际字段映射为 `fasta_file`。 |

### 3.5 动力学、相互作用与结构性质

| 工具名称 | 工具描述 | `inputs` 参数 | 使用说明 / 示例参数 |
|---|---|---|---|
| `gromacs_api` | GROMACS MD 轨迹流程（目录标注 Stub、可能耗时数小时）。 | `pdb_file` | `{"pdb_file":"结构文件路径"}` |
| `mdtraj_analyze` | MDTraj 轨迹分析。 | `trajectory_file`, `topology_file` | `{"trajectory_file":"轨迹路径","topology_file":"拓扑路径"}` |
| `gromacs_minimize` | GROMACS 能量最小化。 | `pdb_file` | `{"pdb_file":"结构文件路径"}` |
| `prodigy_predict` | PRODIGY 结合亲和力预测。 | `pdb_file` | `{"pdb_file":"复合物PDB路径"}` |
| `propka_run` | PROPKA pKa 预测。 | `pdb_file` | `{"pdb_file":"结构文件路径"}` |
| `fpocket_run` | FPocket 结合口袋检测。 | `pdb_file` | `{"pdb_file":"结构文件路径"}` |
| `plip_analyze` | PLIP 蛋白-配体相互作用分析。 | `pdb_file` | `{"pdb_file":"蛋白-配体复合物路径"}` |
| `arpeggio_contacts` | Arpeggio 原子接触分析。 | `pdb_file` | `{"pdb_file":"结构文件路径"}` |
| `freesasa_run` | FreeSASA 溶剂可及表面积计算。 | `pdb_file` | `{"pdb_file":"结构文件路径"}` |
| `biopython_pdb_info` | Biopython PDB 信息提取。 | `pdb_file` | `{"pdb_file":"结构文件路径"}` |
| `prody_analyze` | ProDy 结构分析。 | `pdb_file` | `{"pdb_file":"结构文件路径"}` |

### 3.6 序列/结构文件与文档工具

| 工具名称 | 工具描述 | `inputs` 参数 | 使用说明 / 示例参数 |
|---|---|---|---|
| `read_file` | 读取 workspace 下工具输出文件；支持 pattern/head/tail/max_chars。 | `file_path`, `pattern`, `head`, `tail`, `max_chars` | `{"file_path":"workspace/result.txt","pattern":"可选正则","head":50,"tail":0,"max_chars":12000}`；路径受 workspace 白名单限制。 |
| `pubmed_pdf_download` | 根据 PMID/DOI/标题下载论文 PDF 并返回文本预览。 | `paper_id` | `{"paper_id":"PMID、DOI 或标题"}` |
| `create_docx_document` | 将 Markdown 渲染为 Word 文档。 | `content_markdown`, `title` | `{"content_markdown":"# 报告\\n正文","title":"报告标题"}` |
| `create_xlsx_workbook` | 根据列名和数据行创建 Excel 工作簿。 | `columns`, `rows`, `title` | `{"columns":["名称","分数"],"rows":[["A",0.8]],"title":"结果表"}` |
| `create_pptx_deck` | 根据结构化幻灯片创建 PowerPoint。 | `slides`, `title` | `{"slides":[{"title":"结果","bullets":["要点"]}],"title":"报告"}` |
| `parse_pdf_document` | 使用 pypdf 提取 PDF 页面文本。 | `pdf_file` | `{"pdf_file":"PDF路径"}`；路径可访问性按部署与 wrapper 校验。 |

## 4. 目录中注明的依赖/状态提醒

- 需要 GPU 或 Conda 环境的工具：以目录 `requirements` 字段为准，例如 `boltz2`、DiffAb、RFdiffusion、OmegaFold 等。
- 目录明确标注 Stub 的项目包括：`prorefiner_api`、`prorefiner_refine`、`proteinmpnn_api`、`proteinmpnn_design`、`gromacs_api`、`evmutation_score`。实际状态应以当前部署代码为准。
- `reliability` 标记为 `experimental` 或 `beta` 的工具，调用前应核对其依赖和服务端实现。
- 有 `has_wrapper: true` 只表示目录找到可解析的 wrapper；不保证依赖已经安装、外部 API 可访问或结果达到生产稳定性。

## 5. 请求参数注意事项

1. `{name}` 必须使用 `/api/general/tools` 返回的工具名称，注意大小写（如 `ProtParam`、`SignalP`）。
2. 请求内参数以各工具的 `inputs` 键为准。例如 `pdb_to_sequence` 用 `pdb_id` 和 `chain`；不能把输出字段 `chains` 当作输入。
3. 序列、PDB、FASTA、SMILES、文件路径等参数的具体内容格式需匹配工具实现。目录有些时候显示内部映射字段（如 `fasta_file`），而 API 的 `inputs` 名可能仍是 `sequence`。
4. 目录未明确标注必填/可选、默认值、字段类型、单位或 enum 时，不在本说明中臆测；请通过服务端 `/docs` 查看请求模型并按错误响应修正。
5. 异步任务或大型计算工具可能返回任务 ID 或文件路径；结果字段以响应中的 `outputs`/返回内容为准。