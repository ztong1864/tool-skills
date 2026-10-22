# Graph CGI e50 通用药效预测交接包

本目录是一个 **已训练模型推理包**，用于对 **PrimeKG/KG 已有候选药物** 在指定疾病下进行适应症预测排序。

当前版本不支持 KG 外新药冷启动，不支持直接输入任意 SMILES 或天然产物库进行完整预测。输出用于研究排序和候选优先级参考，不是临床疗效结论。

## 交接时必须保持完整的内容

请交接整个 `通用药效预测/` 文件夹，而不是只交接源码 zip。

运行预测至少依赖两部分：

| 部分 | 位置 | 作用 |
|---|---|---|
| 模型与 prepared 数据 | `primekg_cgi_graph_graph_only_e50/` | 包含 `prepared/`、`train/`、`eval/`，其中有候选药、疾病目录、模型权重和缓存。 |
| 原模型源码 | `model_source/src/` | 已随技能解压，提供 `primekg_graph_indication_multitoken_cgi_graph` 模型类，供 bundle 加载。 |

`source_archives/*.zip` **只是源码包**，不包含 `best_bundle.pt`、`prepared/` 或候选药数据。单独给源码 zip 不能完成预测。

## 目录结构

```text
通用药效预测/
├── SKILL.md
├── README.md
├── environment.yml
├── manifest.json
├── score.sh
├── verify_handoff.sh
├── primekg_cgi_graph_graph_only_e50/
│   ├── prepared/
│   ├── train/
│   └── eval/
├── source_archives/
│   └── KG-drug-efficacy-models_feature-cgi-graph-e50-handoff-clean_69fef47.zip
├── model_source/
│   └── src/primekg_graph_indication_multitoken_cgi_graph/
├── src/primekg_cgi_graph_delivery/
├── docs/
├── examples/
└── tests/
```

## 快速验证

进入技能目录后使用线上 venv：

```bash
source /home/vipuser/srv/foundryclaw_project/FounDryClaw_Web/venv/Oasis/primekg/bin/activate
bash verify_handoff.sh
```

预期输出类似：

```text
[verify_handoff] ok
[verify_handoff] candidate_pool_rows= 6945
[verify_handoff] test_mrr= 0.3405655491444344
```

这一步检查交接包与必需模块，不运行完整疾病打分。

## 模型源码

技能已经包含解压后的 `model_source/src`，`score.sh` 默认使用该目录，可以直接运行。`source_archives/*.zip` 继续作为同版本源码备份保留。

如需改用私有仓库中的其它源码版本，可设置：

```text
repository: git@github.com:lulu754022140/KG-drug-efficacy-models.git
branch: feature/cgi-graph-e50-handoff-clean
commit: 69fef47 Prepare Graph CGI e50 handoff
```

克隆后设置：

```bash
export KG_PROJECT_SRC=/path/to/KG-drug-efficacy-models/src
```

详见 `docs/source_code_handoff.md`。

## 运行环境

线上技能使用已有 Python venv（`environment.yml` 仅记录服务端环境信息，不是环境创建文件）：`/home/vipuser/srv/foundryclaw_project/FounDryClaw_Web/venv/Oasis/primekg`。当前检查到 Python 3.10.22、NumPy 1.24.3、pandas 2.0.3、scikit-learn 1.3.2、RDKit 2022.09.5 和 PyTorch 1.13.1+cpu。截图中 `python=3.8` 与该 venv 的实际解释器版本不一致；运行时应使用此 venv，不需要 Conda。

```bash
source /home/vipuser/srv/foundryclaw_project/FounDryClaw_Web/venv/Oasis/primekg/bin/activate
bash verify_handoff.sh
bash score.sh "diabetic retinopathy" output_scores.csv python auto 100
```

非交互环境可以直接传入 venv 解释器：

```bash
PYTHON_BIN=/home/vipuser/srv/foundryclaw_project/FounDryClaw_Web/venv/Oasis/primekg/bin/python bash verify_handoff.sh
bash score.sh "diabetic retinopathy" output_scores.csv /home/vipuser/srv/foundryclaw_project/FounDryClaw_Web/venv/Oasis/primekg/bin/python auto 100
```

模型源码需要 DGL，但当前该 venv 中未检测到 DGL。安装并确认 DGL 可导入后，才能通过完整环境验证并运行预测；这属于缺少运行依赖。当前 PyTorch 为 CPU 版本，使用 `auto` 或 `cpu`，不要默认指定 `cuda`。

## 快速运行

```bash
source /home/vipuser/srv/foundryclaw_project/FounDryClaw_Web/venv/Oasis/primekg/bin/activate
bash score.sh "diabetic retinopathy" output_scores.csv python auto 100
bash score.sh 43789 output_scores.csv python auto 100
```

等价 Python 命令：

```bash
PYTHONPATH=src:model_source/src /home/vipuser/srv/foundryclaw_project/FounDryClaw_Web/venv/Oasis/primekg/bin/python -m primekg_cgi_graph_delivery.cli score \
  --bundle-dir ./primekg_cgi_graph_graph_only_e50/train \
  --prepared-dir ./primekg_cgi_graph_graph_only_e50/prepared \
  --disease "diabetic retinopathy" \
  --output output_scores.csv \
  --device auto \
  --top-k 100
```

`--top-k 0` 或不传 `--top-k` 时输出全部候选药物。

## 输入

| 参数 | 是否必需 | 说明 |
|---|---|---|
| `--bundle-dir` | 是 | 训练 bundle 目录，通常是 `primekg_cgi_graph_graph_only_e50/train`。 |
| `--prepared-dir` | 是 | prepared CSV 目录，通常是 `primekg_cgi_graph_graph_only_e50/prepared`。 |
| `--disease` | 是 | `disease_id` 或 `disease_catalog.csv` 中的精确 `disease_name`。 |
| `--output` | 是 | 输出 CSV 路径。 |
| `--device` | 否 | `auto`、`cpu`、`cuda` 或 `mps`。默认 `auto`。 |
| `--top-k` | 否 | 正整数输出前 K；0 表示全量。 |
| `--candidate-drugbank-ids` | 否 | 可选 DrugBank ID 白名单，每行一个 ID；所有 ID 必须在 `candidate_pool.csv`。 |

## 输出字段

```text
disease_id,disease_name,rank,drugbank_id,drug_name,indication_score,has_cgi,has_drug_protein_target
```

`indication_score` 是模型输出 logit 经过 sigmoid 后的概率型排序分数。它适合用于同一疾病下候选药物排序，不应解释为真实临床疗效概率。

## 已包含和未包含的数据

本交接包已包含推理需要的：

```text
primekg_cgi_graph_graph_only_e50/prepared/
primekg_cgi_graph_graph_only_e50/train/
primekg_cgi_graph_graph_only_e50/eval/
```

只做推理时不需要原始：

```text
kg.csv
DrugBank XML
CMap / CGI 原始文件
disease embedding pkl
```

如果要重新 prepare 或重新训练，才需要另行提供 PrimeKG、DrugBank、CMap/CGI 和 disease embedding 数据。

## 支持疾病和药物范围

`prepared/disease_catalog.csv` 来自 `graph_diseases.csv`，包含当前 disease graph 中可编码的疾病。模型可以对这些疾病构建 disease 表征并输出候选药排序。

候选药范围固定为 `prepared/candidate_pool.csv` 中的 6945 个 DrugBank 药物。当前版本不支持 candidate pool 之外的新 DrugBank ID、任意 SMILES 或天然产物库。

## 当前模型规模和性能

| 项目 | 数值 |
|---|---:|
| candidate drugs | 6945 |
| indication anchor drugs | 1596 |
| background-only drugs | 5349 |
| indication diseases | 1279 |
| perturbation edges | 720768 |
| perturbation drugs | 1809 |
| CGI-U edges | 360147 |
| CGI-D edges | 360621 |
| best epoch | 27 |
| test MRR | 0.3406 |
| test NDCG@10 | 0.3111 |
| test Hit@10 | 0.5143 |
| test AUROC | 0.9747 |

## 常见错误

- `Disease was not found`：输入疾病不在 `disease_catalog.csv`。
- `Disease name is ambiguous`：同一名称对应多个 disease_id，需要改用 disease_id。
- `Unknown DrugBank IDs`：传入候选药不在当前 `candidate_pool.csv`。
- `CUDA is not available`：指定了 `--device cuda` 但环境没有可用 GPU；可改用 `--device auto` 或 `cpu`。
- `Cannot import primekg_graph_indication_multitoken_cgi_graph`：随包 `model_source/src` 缺失，或 `KG_PROJECT_SRC` 指向了不兼容源码。

## 重要限制

1. 只支持当前 candidate pool 内的 KG 已有药物。
2. 不支持任意 SMILES、新 DrugBank ID、天然产物库冷启动。
3. 不做模型重训。
4. 不纳入 CMI 或反馈模型。
5. 分数只用于研究排序，不是临床用药建议。

## PyTorch 2.6+ bundle 加载说明

该交接包加载的是本地可信训练 bundle。PyTorch 2.6+ 默认 `torch.load(weights_only=True)` 可能拒绝包含 pandas DataFrame 的旧式 bundle；调用程序已在本地可信 bundle 加载路径中显式使用兼容加载。不要把这个加载逻辑用于不可信来源的 checkpoint。
