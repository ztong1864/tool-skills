# Skin aging：指定 45 药验收结果

在交接文件夹根目录运行：

```bash
python3 scripts/run_combination_network.py \
  --disease-name 'skin aging' --efo-id EFO_0005422 \
  --disease-catalog data/disease-gene.csv \
  --api-snapshot assets/skin_aging_case/open_targets_direct_snapshot.json \
  --ppi output/primekg_cgi_graph_graph_only/prepared/kg_with_cgi.csv \
  --candidates assets/skin_aging_case/candidate_drugs_45.csv \
  --output-dir examples/replay_45_drugs
```

`skin aging` 在本地疾病表无精确同名条目，使用 Open Targets 直接遗传关联快照。45 药形成 990 对，均可评分；其中 630 对满足两药各至少 2 个 PPI 靶点的分离度门槛，最终筛出 50 对。复跑输出的 `all_pair_metrics.csv` 和 `ranked_pairs.csv` 分别与 `assets/skin_aging_case/expected_all_pair_metrics.csv`、`assets/skin_aging_case/expected_ranked_pairs.csv` 逐行一致。

目录下 `run_summary.json` 记录方法版本、输入与脚本 SHA-256、参数和覆盖率。`both_significant_eligible=0`；`network_score` 是网络优先分，不是实测药效或协同。
