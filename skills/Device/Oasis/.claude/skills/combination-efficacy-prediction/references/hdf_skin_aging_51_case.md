# HDF 51 成分 BATMAN 网络排序案例

这是通用组合排序 skill 的一个固定输入案例，疾病为 `skin aging`（`EFO_0005422`）。案例的 51 种成分来自 HDF 的 81 种成分名单；入选条件是本地 MCE SMILES 与 PubChem CID 的立体结构严格一致，并且 BATMAN 已知靶点与预测分数 `>0.6` 的靶点合并后，至少有 2 个基因映射到 PrimeKG PPI 最大连通分量。候选使用真实 `PubChem:CID`，不填写虚构的 DrugBank ID。

`assets/hdf_skin_aging_51/` 中的 `candidate_compounds.csv` 是网络脚本输入；`identity_audit.csv` 记录 81 种成分的结构核对与靶点覆盖；`excluded_compounds.csv` 记录未入选的 30 种；`target_edges.csv` 逐条保留 BATMAN 已知或预测关系、预测分数及 PPI 映射状态。`source_manifest.json` 记录输入、BATMAN 下载文件和案例产物的 SHA-256。`source/` 保存 BATMAN 原始压缩文件、本地 MCE 审计快照和仅含两端名称的 HDF 组合名单，案例可随 skill 文件夹一起交接。

## 重跑固定网络排序

在 skill 目录运行，使用含 NumPy 的 Python 环境：

```bash
python scripts/run_combination_network.py \
  --disease-name 'skin aging' --efo-id EFO_0005422 \
  --disease-catalog data/disease-gene.csv \
  --api-snapshot assets/skin_aging_case/open_targets_direct_snapshot.json \
  --ppi output/primekg_cgi_graph_graph_only/prepared/kg_with_cgi.csv \
  --candidates assets/hdf_skin_aging_51/candidate_compounds.csv \
  --output-dir examples/hdf_skin_aging_51_replay
```

原始运行输出在 `examples/hdf_skin_aging_51/`。验收计数：51 个候选均有至少 2 个 PPI 靶点；疾病模块为 t10=10、t50=50；全部 1,275 个无序药对均可评分并满足双靶点门槛，其中 504 对进入 `ranked_pairs.csv`。另有 214/480 个 HDF 组合的两端名称均在候选集中，其中 80 对满足主排名门槛；这些计数只使用组合名单，不使用 Ki67 恢复率、复孔或总核数列。实验布板没有供应商目录号，名称交集不能替代实物身份核对。

运行 `python scripts/verify_hdf_batman_case.py` 可核对文件哈希、逐药靶点集合、候选数量、组合名单覆盖和网络输出计数。

`ranked_pairs.csv` 按 `network_score` 降序。当前前五对为 Morin + Nobiletin、Morin + Puerarin、Syringic acid + Morin、Morin + Betulinic acid、Isovanillic acid + Morin。这是当前靶点和 PPI 规则下的**网络优先级**，不能解释为实测药效或协同效应。预测靶点数差异明显，Methylmalonic acid 有 948 条 BATMAN 预测靶点、909 个 PPI 可用靶点；阅读排名时应同时查看 `identity_audit.csv` 的逐药靶点数。

## 重建候选证据

需有 RDKit，并联网查询 PubChem。命令使用随包的 MCE 审计与仅含药名的组合名单；若 `source/` 下的 BATMAN 文件已存在，脚本会直接使用这些冻结文件：

```bash
python scripts/build_batman_candidates.py \
  --mce-audit assets/hdf_skin_aging_51/source/mce_name_audit.csv \
  --pair-list assets/hdf_skin_aging_51/source/hdf_pair_names.csv \
  --ppi output/primekg_cgi_graph_graph_only/prepared/kg_with_cgi.csv \
  --output-dir assets/hdf_skin_aging_51 \
  --expect-candidates 51
```

当前审计计数为 56 种严格结构一致，51 种入选；其余 30 种分别是 13 种缺本地结构、10 种仅连接关系一致、2 种结构不一致、4 种没有 BATMAN 靶点、1 种不足 2 个 PPI 靶点。入选 51 种中，36 种有 BATMAN 已知靶点，51 种有预测分数 `>0.6` 的靶点；逐边证据共 967 条已知关系、3,555 条预测关系。BATMAN 分数不是结合概率；`>0.6` 是此案例固定的预测边纳入阈值，并未经过本案例的实验效果优化。
