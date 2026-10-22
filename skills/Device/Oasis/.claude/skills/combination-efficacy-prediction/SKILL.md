---
name: combination-efficacy-prediction
description: Rank disease-specific two-compound candidates using PrimeKG PPI, supplied human targets, local disease genes and Open Targets fallback. Accept generic compound IDs or DrugBank candidates; reproducibly sample 100 DrugBank drugs when no list is supplied. Outputs network priorities, not measured efficacy or synergy.
---

# 通用双药组合网络排序

给定疾病名称或本地疾病 ID，使用 PrimeKG 蛋白相互作用网络、疾病基因与两药靶点，按 t10+t50 双模块规则输出药对排名。先看[计算规则与证据边界](references/method.md)；交接输入格式见[输入与输出](references/input_output.md)。`skin aging` 仅是验收案例，不能写死在通用流程中。

## 运行环境与调用

- 本技能要求 Python 3.10 和 `requirements.txt` 中固定的 NumPy 1.23.5。常规网络排序只依赖 NumPy 与 Python 标准库；只有重建 HDF/BATMAN 身份审计数据时才需要 RDKit 和联网访问。
- 当前 Oasis Linux 服务器已配置独立环境：`/home/vipuser/srv/foundryclaw_project/FounDryClaw_Web/venv/Oasis/combination-efficacy-prediction/bin/python`。运行验收、查看帮助和正式任务时都使用这个解释器，不要调用系统 `python3` 或 PrimeKG CGI 的环境。
- 先根据本 `SKILL.md` 的位置解析技能根目录，并在该目录执行脚本；不要假设 Agent 当前工作目录就是技能目录。
- 直接调用 venv 中的 Python 绝对路径，不需要激活环境，也不会改变当前 shell 的环境。其他主机部署时，应从本目录的 `requirements.txt` 建立独立 venv，并使用该环境中的 Python。

服务器环境检查示例：

```bash
PYTHON=/home/vipuser/srv/foundryclaw_project/FounDryClaw_Web/venv/Oasis/combination-efficacy-prediction/bin/python
"$PYTHON" scripts/verify_package.py
"$PYTHON" scripts/run_combination_network.py --help
```

## 数据选择

1. **疾病**：精确匹配本地 `disease-gene.csv` 的疾病 ID 或名称，映射至 PPI 最大连通分量后，按有值的本地 `overall_score` 取最多 50 个。空分数的 TTD 关联保留在原始表，但不参与有序模块；有分数的本地基因不足 20 个时，保留已选基因并用 Open Targets **直接遗传关联**补至最多 50 个。本地无匹配时全部从 API 取；未命中的 `--disease-id` 也尝试作为 API ID 查询。`--efo-id` 与 `--disease-name` 同用时固定 API ID 并优先走 API，名称须与 API 规范名称一致。保存 API 原始快照，重放时用 `--api-snapshot`。两个来源的分数只在各自来源内排序，不混合比较。
2. **PPI 与靶点**：使用 PrimeKG 准备图中 `protein_protein` 边，去空端点、自环和无向重复，取最大连通分量。候选文件若提供 `human_target_genes`，优先使用；缺靶点时仅对真实 DrugBank ID 从同一 PrimeKG 图的 `drug_protein` 且 `display_relation=target` 边补全。外部靶点须另附逐边来源和筛选分数；不能从 SMILES 默认为药物已有靶点。
3. **候选药物**：默认传入 `--candidates` CSV，可用 `candidate_id,candidate_name,human_target_genes` 提供 PubChem 等标识，也兼容旧的 `drugbank_id,drug_name`。未提供时，脚本在标准 KG 项目布局中自动读取 `data/candidate_pool.csv`，也可用 `--candidate-pool` 指定 DrugBank 池；先筛选至少一个靶点可映射到 PPI 的药，再以固定 `--random-seed` 无放回抽取 100 个（`--random-count` 可改）。保存实际抽样名单、合格池大小和种子。随机抽样只用于流程测试，不按疾病优选药物。

## 通用运行

```bash
PYTHON=/home/vipuser/srv/foundryclaw_project/FounDryClaw_Web/venv/Oasis/combination-efficacy-prediction/bin/python
"$PYTHON" scripts/run_combination_network.py \
  --disease-name '疾病英文精确名称' \
  --disease-catalog /path/to/disease-gene.csv \
  --ppi /path/to/primekg/prepared/kg_with_cgi.csv \
  --candidates /path/to/candidate_drugs.csv \
  --output-dir /path/to/output
```

若没有候选文件，去掉 `--candidates`；标准 KG 目录下会自动找到候选池。其他布局加 `--candidate-pool /path/to/candidate_pool.csv`。默认随机抽取 100 个，可加 `--random-seed 20261010` 固定重现，或用 `--api-snapshot /path/to/open_targets_direct_snapshot.json` 离线复核 API 分支。已有疾病 ID 时可用 `--disease-id` 代替 `--disease-name`；本地未命中时会尝试按该 ID 查询 API。

为防止误将全部 DrugBank 药物两两枚举，默认最多计算 100,000 对；有明确需求时用 `--max-pairs` 调整，并核算运行时间与输出体积。

## 交付与判读

交付 `candidate_drugs_selected.csv`、`disease_genes_selected.csv`、`single_drug_network.csv`、`all_pair_metrics.csv`、`ranked_pairs.csv`、`run_summary.json`，如调用 API 还需快照。核对候选数、PPI 映射数、总药对数、可评分数、合格数、输入及脚本哈希与随机种子。排名按 `network_score` 降序，门槛为两药各有至少 2 个 PPI 可映射靶点、`s_AB>0`，且两模块内 `z_A<0`、`z_B<0`；不满足者仍留在全药对表，不能补零当阴性。

本交接文件夹含 `data/disease-gene.csv`、`data/candidate_pool.csv` 和 `output/primekg_cgi_graph_graph_only/prepared/kg_with_cgi.csv`，可直接运行 [DrugBank 45 药验收案例](references/skin_aging_case.md)或[HDF 51 成分 BATMAN 案例](references/hdf_skin_aging_51_case.md)。另有 `examples/skin_aging_random100/` 用于验收无候选库时的抽样入口。`network_score` 只是网络优先级，不是临床药效、实测协同或安全概率；Graph CGI `indication_score` 如已按 DrugBank ID 对齐，只可先作为单药注释，不能直接当作组合标签。
