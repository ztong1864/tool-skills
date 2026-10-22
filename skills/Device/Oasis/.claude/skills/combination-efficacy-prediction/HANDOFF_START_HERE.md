# 组合药物网络排序 Skill：计算机团队交接入口

请传递整个 `combination-efficacy-prediction` 文件夹，或同名交接 ZIP。解压后直接进入该文件夹运行；不要只复制项目中的 `.agents/skills/combination-efficacy-prediction` 符号链接。此包已包含运行所需的数据，不依赖原项目目录。建议保留文件夹内部的相对路径。

## 包内有什么

| 路径 | 内容 |
| --- | --- |
| `SKILL.md`、`references/` | 通用组合网络排序流程、输入输出契约、HDF 案例说明 |
| `scripts/run_combination_network.py` | 通用疾病与双成分网络排序主程序 |
| `scripts/verify_hdf_batman_case.py` | 51 成分案例的哈希、身份、靶点与结果校验 |
| `scripts/build_batman_candidates.py` | 重建 PubChem/BATMAN 候选证据；仅重建时需要 RDKit 和 PubChem 网络 |
| `data/disease-gene.csv` | 通用疾病及相关基因表 |
| `data/candidate_pool.csv` | 6,945 个 DrugBank 候选药物；未提供候选表时用于固定种子抽样 |
| `output/primekg_cgi_graph_graph_only/prepared/kg_with_cgi.csv` | PrimeKG PPI 与 DrugBank 靶点边，约 1 GB |
| `assets/skin_aging_case/open_targets_direct_snapshot.json` | 皮肤衰老疾病基因的固定 Open Targets 快照 |
| `assets/hdf_skin_aging_51/` | 81 成分审计、51 成分候选表、BATMAN 逐边靶点、来源文件与哈希；其中 `source/hdf_pair_names.csv` 只含 480 对名称 |
| `examples/hdf_skin_aging_51/` | 已生成的单药指标、1,275 对全部指标、504 对合格排名及运行摘要 |
| `assets/skin_aging_case/`、`examples/skin_aging_45_drugs/` | 旧 DrugBank 45 药回归案例 |
| `examples/skin_aging_random100/` | 未提供候选表时，从 DrugBank 候选池固定种子抽样的回归案例 |

本包提供的是**网络排序案例**。没有纳入 HDF 原始图像、Ki67 恢复率或其他实验标签；本次候选选择和排序均未使用它们。实验布板未提供商品目录号，名称交集不能证明实验实物与数据库结构完全一致。

## 接收后先验收

建议使用 Python 3.10。主程序只需 NumPy；在包根目录安装 `python3 -m pip install -r requirements.txt`。如果 `python3` 指向其他环境，请换成已安装 NumPy 的 Python 3.10 解释器。重建 BATMAN/PubChem 身份审计时才需要 RDKit。

```bash
cd combination-efficacy-prediction
python3 scripts/verify_package.py
python3 scripts/verify_hdf_batman_case.py
```

第一条校验随包文件的 SHA-256；第二条应输出 `51 compounds, 214 observed name pairs (80 eligible), 1275 scored pairs, 504 ranked pairs`。若校验失败，先检查是否漏传文件或改变了 CSV，再考虑重跑。

## 重跑 HDF 51 成分案例

```bash
python3 scripts/run_combination_network.py \
  --disease-name 'skin aging' --efo-id EFO_0005422 \
  --disease-catalog data/disease-gene.csv \
  --api-snapshot assets/skin_aging_case/open_targets_direct_snapshot.json \
  --ppi output/primekg_cgi_graph_graph_only/prepared/kg_with_cgi.csv \
  --candidates assets/hdf_skin_aging_51/candidate_compounds.csv \
  --output-dir examples/hdf_skin_aging_51_replay
```

`run_summary.json` 应显示 `candidate_drugs=51`、`pairs_all=1275`、`pairs_scorable=1275`、`eligible_pairs=504`。重跑后的 `candidate_drugs_selected.csv`、`disease_genes_selected.csv`、`single_drug_network.csv`、`all_pair_metrics.csv`、`ranked_pairs.csv` 应与 `examples/hdf_skin_aging_51/` 中对应文件逐字节相同；时间与绝对路径相关的摘要字段可不同。以上命令使用随包快照，不需要访问 Open Targets。

## 补充回归：不提供候选表时随机抽取 100 药

这一步验证通用流程的默认候选库入口。随机抽样仅测试流程，不代表按疾病推荐药物。

```bash
python3 scripts/run_combination_network.py \
  --disease-name 'skin aging' --efo-id EFO_0005422 \
  --disease-catalog data/disease-gene.csv \
  --api-snapshot assets/skin_aging_case/open_targets_direct_snapshot.json \
  --ppi output/primekg_cgi_graph_graph_only/prepared/kg_with_cgi.csv \
  --output-dir examples/skin_aging_random100_replay
```

此命令不传 `--candidates`，自动从随包的 `data/candidate_pool.csv` 中以固定种子 `20261010` 抽取 100 药。`run_summary.json` 应显示 `candidate_drugs=100`、`pairs_all=4950`、`pairs_scorable=4950`、`pairs_separation_eligible=561`、`eligible_pairs=27`。将重跑得到的五份核心 CSV 与 `examples/skin_aging_random100/` 同名文件逐字节比较。旧 DrugBank 45 药回归命令见 [案例说明](references/skin_aging_case.md)。

## 通用输入与结果解释

对其他疾病，按 [输入输出契约](references/input_output.md)传入疾病名称或 ID、同一 PrimeKG 图，以及 `candidate_id,candidate_name,human_target_genes` 候选 CSV。多个基因符号用分号分隔；也兼容旧的 `drugbank_id,drug_name` 输入。不提供候选 CSV 时，默认从包内 DrugBank 池固定种子抽取 100 药。新疾病若不在本地表且没有 API 快照，需要访问 Open Targets；实时查询会保存快照。

`ranked_pairs.csv` 是满足网络门槛的优先级顺序；`all_pair_metrics.csv` 保留全部药对和未入选原因。`network_score` 不代表实测药效、协同效应、安全性或临床获益。HDF 案例的 BATMAN 已知靶点与预测靶点分开保存在 `target_edges.csv`；只有预测边使用 `score > 0.6`。详细结果与重建命令见[HDF 案例说明](references/hdf_skin_aging_51_case.md)。
