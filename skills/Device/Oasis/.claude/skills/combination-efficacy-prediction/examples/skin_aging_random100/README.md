# Skin aging：缺省候选库随机 100 药验收结果

在交接文件夹根目录运行；命令不提供候选药文件，脚本自动读取同文件夹的 `data/candidate_pool.csv`：

```bash
python3 scripts/run_combination_network.py \
  --disease-name 'skin aging' --efo-id EFO_0005422 \
  --disease-catalog data/disease-gene.csv \
  --api-snapshot assets/skin_aging_case/open_targets_direct_snapshot.json \
  --ppi output/primekg_cgi_graph_graph_only/prepared/kg_with_cgi.csv \
  --output-dir examples/replay_random100
```

在本包数据版本与默认种子 `20261010` 下，6,945 药候选池中有 5,085 个药物存在可映射至 PPI 的已知靶点；随机抽取 100 个，形成 4,950 对，均可评分。其中 561 对满足两药各至少 2 个 PPI 靶点的分离度门槛，最终 27 对满足双模块排名门槛。`candidate_drugs_selected.csv` 保存抽中的名单。该抽样只用于流程测试，并未按疾病适应证筛药。

检查 `run_summary.json` 的 `method_version=network_v2`、`candidate_mode=random_target_mapped`、`random_pool_eligible=5085`、`pairs_all=4950`、`eligible_pairs=27` 与输入及脚本哈希。`both_significant_eligible=0`；网络排名不代表实测疗效、协同或安全。
