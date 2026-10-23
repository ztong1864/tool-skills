---
name: primekg-cgi-drug-effect-prediction
description: 给定疾病ID或精确疾病名，使用PrimeKG Graph CGI e50已训练模型对candidate_pool.csv中的KG已有候选药物按适应症分数排序，输出按优先级排列的候选药物CSV。用于疾病层面的候选药物推荐、优先级评估和当前通用药效预测；不支持任意SMILES、KG外新药、天然产物库或冷启动预测。
metadata:
  short-description: 按疾病对KG已有候选药物排序的推荐与药效预测
---

# PrimeKG Graph CGI 通用药效预测

本技能是完整的已训练模型推理包。使用前阅读 [README.md](README.md)；需要理解模型输入、输出或限制时，再阅读 `docs/model_io_spec.md`、`docs/model_architecture.md` 和 `docs/limitations.md`。

## 能力边界

- 输入疾病必须能在 `primekg_cgi_graph_graph_only_e50/prepared/disease_catalog.csv` 中按 `disease_id` 或规范化后的精确 `disease_name` 唯一匹配。
- 只对 `prepared/candidate_pool.csv` 中的 6,945 个 KG 已有 DrugBank 药物打分。可用 DrugBank ID 白名单限制候选集，但白名单中的所有 ID 也必须已在 candidate pool 中。
- 不接收任意 SMILES，不支持新 DrugBank ID、KG 外天然产物或其它化合物库的冷启动；遇到这类请求应说明需要单独的结构适配或冷启动模型。
- `indication_score` 是同一疾病下的模型排序分数，不是真实疗效概率、临床治疗结论或处方建议。
- 本包用于推理；重新 prepare 或训练才需要原始 PrimeKG、DrugBank、CMap/CGI 和疾病 embedding 数据。

## 必须保留的包结构

不要只保留 `source_archives/` 中的源码压缩包。推理还依赖：

- `primekg_cgi_graph_graph_only_e50/prepared/`：疾病目录、候选药空间和图谱边数据；
- `primekg_cgi_graph_graph_only_e50/train/`：模型权重、缓存和 embedding；
- `src/primekg_cgi_graph_delivery/`：推理封装；
- `model_source/src/`：已解压的原模型源码；`source_archives/` 同时保留源码压缩包备份。

## 运行前验证

### 使用平台为本技能准备的 Python 环境

本技能用仓库里的 `venv/Oasis/primekg`：它在本 SKILL.md 所在技能目录往上六层的仓库根下（`skills/Device/<设备>/.claude/skills/<本技能>` 往上六层就是仓库根）。解释器在 Linux 上是 `bin/python`，在 Windows 上是 `Scripts/python.exe`。环境里是 Python 3.10、PyTorch 1.13.1+cpu、DGL 1.1.2、NumPy 1.24.3、pandas 2.0.3、scikit-learn 1.3.2 和 RDKit 2022.09.5。技能包里的 `environment.yml` 是旧模板，不是运行环境说明：不要要求创建 Conda 环境，也不要因模板里的 Python 版本拒绝任务。

**不要用对话默认的 `python` 跑本技能**：`score.sh` 以 `python -m` 启动，环境路由在 `-m` 时按当前目录判断，工作区的默认环境没有 PyTorch 和 DGL，验证会报 `missing Python modules`。把上面这个解释器的绝对路径传给 `verify_handoff.sh` 和 `score.sh`。

取得解释器路径并检查交接包（`SKILL_DIR` 写本 SKILL.md 所在目录的绝对路径，从 LabOntology 的输出里原样复制）：

```bash
SKILL_DIR=<本 SKILL.md 所在目录>
PY="$SKILL_DIR/../../../../../../venv/Oasis/primekg/bin/python"
[ -x "$PY" ] || PY="$SKILL_DIR/../../../../../../venv/Oasis/primekg/Scripts/python.exe"
PYTHON_BIN="$PY" bash "$SKILL_DIR/verify_handoff.sh"
```

验证脚本不比较环境名称，也不要求依赖版本与旧模板逐项相同；它检查当前解释器能否导入推理依赖（PyTorch、DGL、RDKit、pandas、NumPy），并检查随包文件。它报 `missing Python modules` 时，是解释器传错了或这个环境没装全，不是 Python 版本不匹配：先按上面的路径重试一次，仍然缺就如实登记失败并告诉用户，不要删掉依赖检查绕过去，也不要用别的模型、文献或联网检索代替本技能的排序结果。

当前 PyTorch 为 CPU 版本，标准命令使用 `auto` 或 `cpu`。只有切换到支持 CUDA 的 PyTorch 环境后才指定 `cuda`。

`score.sh` 默认使用随包 `model_source/src`，正常推理不需要设置源码路径。只有需要改用其它版本源码时，才通过 `KG_PROJECT_SRC` 显式覆盖。

## 选择疾病

`score.sh` 只认 `disease_catalog.csv` 里的 `disease_id` 或完整的 `disease_name`（只忽略大小写和空格），用户说的病名一般都要先查目录。运行前用疾病的英文名搜索：

```bash
grep -i "<英文关键词>" "$SKILL_DIR/primekg_cgi_graph_graph_only_e50/prepared/disease_catalog.csv"
```

从结果里选与用户所说疾病同一层级的那一条，用它的 `disease_id` 运行：

- 不选更宽的上位疾病：肺结核用 `6052 pulmonary tuberculosis`，不用 `18076 tuberculosis`；
- 不选更窄的亚型：脑卒中用 `5098 stroke disorder`，不用 `5490 large artery stroke`；
- 跳过名称里带 `susceptibility`、`obsolete` 的条目，以及把几种病合在一起的综合征条目。

没有合适的条目时，换同义词或全称再搜一次（如 `cerebrovascular`、`non-small cell lung carcinoma`）；两条同样贴切时才问用户。回复里写明用的是哪一条（`disease_id` 和 `disease_name`）。

`score.sh` 报 `Disease '...' was not found` 不是本技能运行失败，只说明传入的不是目录里的完整名称：错误信息列出了名称含有这些词的条目，按上面的规则选一条重新运行，不要登记失败，也不要让用户去查疾病 ID。

## 标准推理

```bash
bash "$SKILL_DIR/score.sh" <disease_id> <artifact_dir>/score_<disease_id>.csv "$PY" auto 20
bash "$SKILL_DIR/score.sh" "diabetic retinopathy" <artifact_dir>/score_dr.csv "$PY" auto 20
```

设备可使用 `auto`、`cpu`、`cuda` 或 `mps`。`top_k=0` 表示输出全部候选药。需要候选白名单时，直接调用 Python CLI 的 `--candidate-drugbank-ids`。

## 输出与报告

输出 CSV 字段：

```text
disease_id,disease_name,rank,drugbank_id,drug_name,indication_score,has_cgi,has_drug_protein_target
```

向用户报告时说明查询疾病及匹配到的 `disease_id`、模型名、结果文件路径和 Top N 候选药。`has_cgi` 和 `has_drug_protein_target` 只是相应图谱信息是否存在的标记，不是疗效证据强度。候选范围仅来自当前 candidate pool，结果用于研究排序。

推理完成后，只有当前任务已经授权维护 ontology 时，才把结果登记为 `Data`，并由通用药效预测 `Process` 通过 `produce` 关系连接；若结果用于某个 Oasis 实验，再在确认具体 Workflow 后建立 `withData` 关系。当前任务未授权图谱写入时，只在报告中列出建议创建的实体和关系，不自动修改 ontology。
