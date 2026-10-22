# 组合药物网络排序 Skill 交接

完整数据与命令的交接入口见 [HANDOFF_START_HERE.md](HANDOFF_START_HERE.md)。

这个文件夹包含通用 skill、运行脚本、所需数据和 `skin aging` 验收案例。复制整个文件夹后，在本目录运行命令；原项目中的 `.agents/skills/combination-efficacy-prediction` 只是指向此处的符号链接。

## 内容

| 路径 | 用途 |
| --- | --- |
| `SKILL.md`、`references/` | 通用规则、输入输出契约和方法边界 |
| `scripts/run_combination_network.py` | 主流程：任意疾病、显式药物库或随机 100 药 |
| `scripts/build_batman_candidates.py` | 从 MCE 审计、PubChem 与 BATMAN 构建可追溯的通用候选表 |
| `data/disease-gene.csv` | 本地疾病及基因关联 |
| `data/candidate_pool.csv` | 6,945 个 DrugBank 候选药物；随机入口使用 |
| `output/primekg_cgi_graph_graph_only/prepared/kg_with_cgi.csv` | PrimeKG PPI 和 DrugBank 靶点边 |
| `assets/skin_aging_case/` | 45 药名单、API 快照、预期结果 |
| `assets/hdf_skin_aging_51/` | HDF 51 成分的 PubChem 身份审计、BATMAN 逐边证据、候选表与来源哈希 |
| `examples/skin_aging_45_drugs/` | 显式候选库案例输出 |
| `examples/skin_aging_random100/` | 无候选库时随机抽样案例输出 |
| `examples/hdf_skin_aging_51/` | HDF 51 成分网络排序输出 |

## 环境与验收

已在 Python 3.10.9、NumPy 1.23.5 下运行。主脚本除 NumPy 外只使用标准库；重建 HDF 身份审计还需要 RDKit 和联网访问 PubChem/BATMAN。建议先运行 [45 药验收命令](references/skin_aging_case.md)：应得到 990 对可评分药对、50 对进入排名，两份药对 CSV 与 `assets/skin_aging_case/expected_*.csv` 逐行一致。HDF 51 成分案例的命令与证据边界见[案例说明](references/hdf_skin_aging_51_case.md)。

默认候选库入口可直接执行：

```bash
python3 scripts/run_combination_network.py \
  --disease-name 'skin aging' --efo-id EFO_0005422 \
  --disease-catalog data/disease-gene.csv \
  --api-snapshot assets/skin_aging_case/open_targets_direct_snapshot.json \
  --ppi output/primekg_cgi_graph_graph_only/prepared/kg_with_cgi.csv \
  --output-dir examples/replay_random100
```

没有 `--candidates` 时，脚本自动读取本文件夹 `data/candidate_pool.csv`，从 5,085 个 PPI 靶点可映射药物中固定种子抽取 100 个；应得到 4,950 对可评分药对，其中 561 对满足两药各至少 2 个 PPI 靶点的门槛，最终 27 对进入排名。实际药物名单、种子和输入及脚本哈希记录在输出中。需要用户指定库时加 `--candidates /path/to/drugs.csv`；接受的列和疾病回退规则见 [输入与输出契约](references/input_output.md)。

原有 DrugBank 45 药和随机 100 药两个案例的 `both_significant_eligible` 均为 0；HDF 51 成分案例为 2。入选只表示满足网络筛选门槛，不代表实测药效、协同或安全。需要联网获取新疾病时，Open Targets 查询会保存快照；此处的 `skin aging` 案例可用随包快照离线复核。
