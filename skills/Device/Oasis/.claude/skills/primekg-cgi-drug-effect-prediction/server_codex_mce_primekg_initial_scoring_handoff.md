# 服务器端 Codex 交接文档：PrimeKG 对160个天然产物进行初始打分

## 1. 任务目标

使用已经训练好的 PrimeKG CGI graph-only e50 基础模型，对天然产物候选进行糖尿病视网膜病变相关性初始打分。

目标疾病：

```text
disease_name: diabetic retinopathy
disease_source: MONDO
disease_id: 5266
```

本阶段只做零样本/结构迁移初始打分，不使用这160个天然产物的真实实验结果训练基础模型。

后续真实实验结果会用于10轮反馈排序，但本交接任务暂时不运行反馈训练。

## 2. 服务器上的已知文件

### 2.1 天然产物候选表

用户已经上传：

```text
/slurm/home/yrd/fanlab/zhangjinlu/zjl_desktop/KG/PrimeKG/data/MCE_lib/mce_selected_160_primekg_match.csv
```

该表包含MCE编号、化合物名称、SMILES、PrimeKG/DrugBank匹配信息等。

### 2.2 基础模型

当前建议使用非五折的 CGI graph-only e50 模型：

```text
/slurm/home/yrd/fanlab/zhangjinlu/zjl_desktop/KG/PrimeKG/output/primekg_cgi_graph_graph_only_e50/
```

实际 bundle 目录应为：

```text
/slurm/home/yrd/fanlab/zhangjinlu/zjl_desktop/KG/PrimeKG/output/primekg_cgi_graph_graph_only_e50/train/
```

优先加载：

```text
best_bundle.pt
```

不要使用之前的五折模型：

```text
output/primekg_graph_ind_multitoken_hgtdr_cv_max80_use_drug1/fold_4/train/
```

除非用户后续明确要求进行五折比较。

## 3. 当前已知数据问题

### 3.1 暂时排除的候选

`Magnesium Lithospermate B` 的原始SMILES含有镁离子配位和环闭合表示，当前RDKit无法通过价态检查，因此本轮暂不进入结构打分。

建议按照MCE编号排除：

```text
HY-126415
```

但要保留在最终候选清单中，并设置：

```text
smiles_status = invalid_rdkit
excluded_reason = invalid_metal_coordination_smiles
```

### 3.2 已修正的候选

`trans-Benzylideneacetone` 原始SMILES末尾的 `[E]` 无法被RDKit解析，已确认可使用以下修正版：

```text
CC(=O)/C=C/C1=CC=CC=C1
```

对应MCE编号：

```text
HY-W012595A
```

请在服务器端先确认候选表中是否已经替换为该SMILES；如果没有，只在运行副本中替换，并保留原始表不覆盖。

### 3.3 结构重复

以下两个候选经过标准化后对应同一结构：

```text
HY-N0060       Ferulic acid
HY-N0060B      (E)-Ferulic acid
```

不要直接删除其中一个。初始打分时可以都保留，但结果中增加：

```text
structure_duplicate_group = ferulic_acid
```

后续实验选择时避免把它们同时作为两个独立结构优先推荐。

## 4. 为什么不能直接使用默认PrimeKG候选打分脚本

CGI graph-only e50模型的compound节点表示主要是训练得到的PrimeKG节点embedding，并不是由SMILES初始化的。对于不在PrimeKG中的天然产物：

```text
有SMILES结构表示
但没有原始PrimeKG compound embedding
没有CGI邻居
通常没有drug-protein机制关系
```

因此不能直接把160个天然产物当作PrimeKG药物ID运行默认脚本，否则可能出现：

1. 只保留已匹配PrimeKG的候选；
2. 过滤掉未匹配的天然产物；
3. 为新候选使用未训练的随机或空白compound embedding。

默认脚本不得直接作为正式结果使用，除非已经确认它能够正确接收外部SMILES并处理未知compound节点。

## 5. 推荐技术方案：冻结基础模型，增加结构适配层

### 5.1 总体流程

```text
MCE候选SMILES
        ↓
现有DrugGraphContextEncoder
        ↓
天然产物结构表示
        ↓
轻量SMILES-to-CGI适配层
        ↓
生成CGI分支所需的compound embedding
        ↓
冻结PrimeKG CGI e50模型
        ↓
输入disease_id=5266
        ↓
输出初始indication score
```

### 5.2 适配层训练原则

不要使用160个天然产物的真实实验结果训练适配层。

建议使用PrimeKG中已有、且在基础模型候选池中的药物进行无监督/表示对齐：

```text
输入：PrimeKG药物的SMILES结构表示
目标：该药物在CGI图中的原始compound embedding
训练：小型Linear或MLP适配层
冻结：PrimeKG基础模型参数
```

可使用MSE损失和cosine loss的组合：

```text
loss = MSE(predicted_compound_embedding, original_compound_embedding)
     + lambda * (1 - cosine_similarity)
```

适配层训练时应按药物划分训练/验证集，避免同一药物同时出现在两边。

### 5.3 160个候选的推理方式

对于每个有效SMILES：

1. 使用现有药物结构编码器生成 `drug_global` 和 `atom_tokens`；
2. 使用适配层生成 `compound_global`；
3. 如果候选没有PrimeKG drug-protein关系，将 `mechanism_emb`置为零向量；
4. 如果没有CGI或扰动关系，将对应分支置为零或按模型接口使用空输入；
5. 使用疾病ID `5266`计算最终分数。

对于 `HY-126415`：跳过结构编码，不输出有效初始分数。

## 6. 需要服务器端先完成的检查

在正式写适配层之前，请先执行只读检查，不要训练或修改基础模型：

### 6.1 检查模型文件

确认以下文件存在：

```text
.../output/primekg_cgi_graph_graph_only_e50/train/best_bundle.pt
.../output/primekg_cgi_graph_graph_only_e50/train/bundle.pt
.../output/primekg_cgi_graph_graph_only_e50/train/disease_hetero_graph.pt
```

### 6.2 检查模型配置

从 `best_bundle.pt` 中读取并记录：

- `embed_dim`；
- `use_graph_cgi`；
- `use_drug_protein_branch`；
- `use_perturbation_branch`；
- `candidate_pool`的药物数量；
- candidate pool是否包含SMILES；
- compound embedding的维度和来源。

### 6.3 检查疾病

确认：

```text
model.disease_encoder.has_disease("5266") == True
```

如果为False，不要自行替换成相近疾病ID。需要检查bundle使用的疾病图和PrimeKG疾病映射是否一致。

### 6.4 检查候选表

确认候选表：

- 行数是否为160；
- `HY-126415`是否被标记为排除；
- `HY-W012595A`是否使用修正版SMILES；
- 有效SMILES数量；
- MCE编号是否唯一；
- DrugBank匹配ID是否存在重复或空值。

## 7. 运行顺序

服务器端不要一开始就跑160个候选。建议按以下顺序：

### 第一步：环境检查

确认Python、PyTorch、DGL、RDKit、pandas和transformers可以导入，并记录版本。

### 第二步：bundle加载测试

只加载 `best_bundle.pt`，确认模型可以初始化，不进行训练。

### 第三步：疾病测试

用 `disease_id=5266`构建疾病表示，确认疾病存在。

### 第四步：单候选测试

先测试一个有有效SMILES、且已匹配DrugBank/PrimeKG的候选，再测试一个未匹配PrimeKG但有有效SMILES的候选。

每个测试至少记录：

```text
mce_id
compound_name
smiles_valid
primekg_match_status
mechanism_available
compound_embedding_source
indication_score
```

### 第五步：小批量测试

先运行10个候选，确认输出无NaN、无重复ID、分数范围合理。

### 第六步：正式初始打分

对排除无效SMILES后的候选运行初始评分，输出完整结果表。

## 8. 建议输出文件

建议在服务器生成单独的结果目录：

```text
/slurm/home/yrd/fanlab/zhangjinlu/zjl_desktop/KG/PrimeKG/output/mce_diabetic_retinopathy_initial_score/
```

至少包含：

```text
initial_scores.csv
initial_scores_sorted.csv
candidate_qc.csv
adapter_train_summary.json
run_manifest.json
```

其中 `initial_scores_sorted.csv` 至少包含：

```text
mce_id
compound_name
plate
well
smiles
smiles_status
primekg_match_status
drugbank_id
mechanism_available
compound_embedding_source
disease_id
disease_name
indication_score
```

## 9. 结果解释边界

初始分数应解释为：

```text
基于PrimeKG通用知识和分子结构迁移得到的候选排序分数
```

不能解释为：

```text
天然产物已经经过模型监督学习验证
真实实验效力
确定的药效概率
```

真实实验结果加入后，再使用反馈模块进行排序校正，并保存每一轮的候选、实验结果和模型状态。

## 10. 如果服务器端无法完成适配层，需要用户确认的信息

如果检查发现以下任一项缺失，请暂停正式打分并向用户确认：

1. `best_bundle.pt`不存在；
2. bundle目录实际名称不同；
3. DGL与PyTorch版本不兼容；
4. `disease_id=5266`不在bundle疾病图中；
5. bundle中没有可恢复的PrimeKG compound embedding；
6. 当前DrugGraphContextEncoder不能从外部SMILES生成结构表示；
7. 服务器上缺少本项目对应的源代码版本；
8. 候选表列名与本地版本不一致。

向用户提问时请同时提供：

```text
实际路径
缺失文件
完整错误信息
已完成的检查
需要用户提供的具体文件或选择
```

## 11. 当前不应做的事情

- 不要重新训练PrimeKG基础模型；
- 不要把160个天然产物的实验结果加入基础模型训练；
- 不要直接删除SMILES无效候选的原始记录；
- 不要把随机compound embedding作为正式初始结果；
- 不要直接运行默认PrimeKG候选脚本并把被过滤后的结果当作160个候选的完整结果；
- 不要在没有保存manifest和参数的情况下覆盖已有模型或结果。

