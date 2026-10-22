# 验收案例：skin aging（EFO_0005422）

本案例检验通用脚本的疾病 API 回退、显式候选库、PrimeKG PPI 与双模块网络排序。`assets/skin_aging_case/` 含 45 药名单、Open Targets 原始快照和两份预期药对 CSV；交接文件夹的 `data/` 与 `output/` 含同版本疾病总表和 PrimeKG 准备图。案例路径不写死在脚本中。

预期输入 SHA-256：

| 输入 | SHA-256 |
| --- | --- |
| `disease-gene.csv` | `73429fda9b5d1e67de3340f2c651532a06b5692b7a6b873bdeb1131a5ed73351` |
| PrimeKG `kg_with_cgi.csv` | `28873f2f6e08621e171ba0f809d95c1b9a81f087ba080cadcad3e3ce6893d9cd` |
| 附带 45 药候选表 | `87cbd1fd258abb6d3896b27c22c9af17db91ea508804a8bb273d0b89ba13a5f6` |
| 附带 API 快照 | `6544fe688c14a396fdf9277dfb11201dbcb2fefc1b814c21e78ba7b4c0ee4920` |

在 skill 目录运行：

```bash
python3 scripts/run_combination_network.py \
  --disease-name 'skin aging' --efo-id EFO_0005422 \
  --disease-catalog data/disease-gene.csv \
  --api-snapshot assets/skin_aging_case/open_targets_direct_snapshot.json \
  --ppi output/primekg_cgi_graph_graph_only/prepared/kg_with_cgi.csv \
  --candidates assets/skin_aging_case/candidate_drugs_45.csv \
  --output-dir examples/replay_45_drugs
```

核对 `method_version=network_v2`、`candidate_drugs=45`、`pairs_all=990`、`pairs_scorable=990`、`pairs_separation_eligible=630`、`eligible_pairs=50`，以及输出的 `ranked_pairs.csv` 与 `all_pair_metrics.csv` 是否分别与两个 `expected_*.csv` 逐行相同。`run_summary.json` 的绝对路径和时间会因机器而异。`both_significant_eligible=0`，即入选药对没有同时达到四个单药 z 值均小于 -1.64 的诊断阈值；网络排名不构成实测疗效或组合协同结论。
