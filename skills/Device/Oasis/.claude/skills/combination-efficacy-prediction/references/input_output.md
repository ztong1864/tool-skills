# 输入与输出契约

## 必需数据

- `--disease-catalog`：CSV，列为 `disease_id,disease_name,gene,gene_id,source,overall_score`。疾病按 ID 或名称精确匹配；基因符号必须与 PPI 蛋白名称对应。一个名称若对应多个 ID，改用 `--disease-id`。空 `overall_score` 的关联没有可用的排序证据，不进入 t10/t50；实际入选数可能少于 50。
- `--ppi`：PrimeKG 准备图 CSV，至少包含 `relation,display_relation,x_id,x_type,x_name,y_id,y_type,y_name`。`protein_protein` 构建 PPI；`drug_protein` 且 `display_relation=target` 提供药物已知靶点。这个参数指向图数据，不是仅含蛋白边的裁剪文件，否则无法为缺靶点的候选药补全。
- `--output-dir`：独立输出目录；不同疾病、候选库和随机种子使用不同目录，避免覆盖。
- `--disease-name` 或 `--disease-id`：二选一。名称先查本地；本地未命中时按精确英文名查 Open Targets。`--disease-id` 先查本地，未命中则作为 API 疾病 ID 查询。`--disease-name` 加 `--efo-id` 会固定 API ID 并直接使用 API，名称必须与其规范名称一致；`--efo-id` 不能和 `--disease-id` 混用。`--api-snapshot` 可重放之前保存的结果。API 使用直接关联 `enableIndirect:false`，只取 `genetic_association` 分数大于零的基因。若本地有分数且 PPI 可用的基因不足 20 个，保留这些基因在前，再按 API 分数追加未重复基因，最多 50 个；不跨来源比较分数。API 查询失败时会报错；若 API 无可用基因，则仅用本地已有的有分数基因，不拿无分数基因按字母序充数。

## 候选药物

- 首选 `--candidates`：CSV 可用 `candidate_id,candidate_name`（PubChem 等通用标识），也可用旧的 `drugbank_id,drug_name`。可含 `human_target_genes`，多个 HGNC 基因符号用分号分隔；通用输入可附 `target_source`。若靶点列为空，仅当 ID 本身是 DrugBank ID 且在 PrimeKG 中有对应边时才能从 `drug_protein,target` 补全，不能把 PubChem CID 伪装成 DrugBank ID。提供候选文件时，所有药物保留，按输入 ID 排序；未能映射靶点的药物和药对在输出中标记状态。外部靶点的逐边证据与过滤规则应和候选文件一起保存。
- 无候选文件时使用 DrugBank 候选池：标准 KG 项目布局自动查找 `data/candidate_pool.csv`，其他布局用 `--candidate-pool` 指定；同样至少含 `drugbank_id,drug_name`。建议使用 PrimeKG/Graph CGI 的 6,945 药物候选池。先按 DrugBank ID 与 PrimeKG 已知靶点对齐，再筛选至少一个靶点在 PPI 最大连通分量中的药物；从合格池以 `--random-seed` 无放回抽取 `--random-count` 个，默认 100。固定候选池版本、种子和输出的 `candidate_drugs_selected.csv` 才能复现。
- `smiles` 可保留在原始候选文件中，但本网络方法不使用分子结构推断靶点，也不把 SMILES 用作药效特征。Graph CGI 单药 `indication_score` 可按真实 DrugBank ID 另行连接作注释。

## 输出与验收

| 文件 | 内容 |
| --- | --- |
| `candidate_drugs_selected.csv` | 本次实际选择的药物、靶点来源及 PPI 映射数 |
| `disease_genes_selected.csv` | t50 基因名单；前 10 个构成 t10；含来源和原始分数类型 |
| `single_drug_network.csv` | 单药 PPI 靶点覆盖、t10/t50 最近距离和 z 值 |
| `all_pair_metrics.csv` | 所有无序药对、分离度、邻近度、得分、靶点数门槛、合格标记与状态 |
| `ranked_pairs.csv` | 满足双模块门槛的药对，按 `network_score` 降序 |
| `run_summary.json` | 疾病及候选来源、PPI 覆盖、药对计数、方法版本、随机参数与输入及脚本 SHA-256 |
| `open_targets_direct_snapshot.json` | 仅在实时调用 Open Targets 时产生；离线重放需提供原快照 |

显式通用候选表的输出列使用 `candidate_id,candidate_name` 及药对 A/B 后缀，并含 `selection_status`，列出未进入排名的网络门槛原因；旧 DrugBank 输入仍使用原有 `drugbank_id,drug_name` 输出列。两种输入的网络计算和合格门槛相同。

检查 `pairs_all=N(N-1)/2`，并核对 `pairs_scorable`、`pairs_separation_eligible`、`eligible_pairs` 与排名行数。两药各至少 2 个 PPI 靶点、`s_AB>0` 与两个模块的四个单药 z 值 `<0` 才算合格。单靶点药对保留在全表，`separation_eligible=0`，不进入主排名。`both_significant` 只是更严格的诊断标记，不是排名门槛。任何网络得分均不代表实测协同、疗效或安全性。
