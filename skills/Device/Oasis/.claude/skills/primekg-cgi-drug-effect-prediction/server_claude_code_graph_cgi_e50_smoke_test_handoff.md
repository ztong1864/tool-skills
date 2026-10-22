# 服务器端 Claude Code 交接文档：Graph CGI e50 通用药效预测 smoke test

## 1. 任务目标

请在服务器环境中验证 `Graph CGI e50` 通用药效预测交接包能否正常调用。只做 smoke test，不训练、不改模型、不改原始数据。

本交接包第一版只支持 PrimeKG/KG 已有 candidate_pool 药物，不支持 KG 外新药、任意新 SMILES、天然产物库冷启动。

## 2. 服务器源码路径

用户确认服务器上的模型源码包路径是：

```text
/slurm/home/yrd/fanlab/zhangjinlu/zjl_desktop/KG/PrimeKG/src/primekg_graph_indication_multitoken_cgi_graph
```

运行时 `KG_PROJECT_SRC` 必须设置为它的上一级 `src` 目录：

```bash
export KG_PROJECT_SRC=/slurm/home/yrd/fanlab/zhangjinlu/zjl_desktop/KG/PrimeKG/src
```

原因是交接调用程序需要同时 import：

```text
primekg_graph_indication_multitoken_cgi_graph
primekg_graph_drug_zero_shot
```

所以不要把 `KG_PROJECT_SRC` 设置成更深一层的 `.../src/primekg_graph_indication_multitoken_cgi_graph`。

## 3. 交接包目录

请进入用户上传到服务器的交接包目录，目录名应类似：

```text
通用药效预测/
```

其中应该包含：

```text
SKILL.md
README.md
score.sh
verify_handoff.sh
manifest.json
src/primekg_cgi_graph_delivery/
primekg_cgi_graph_graph_only_e50/
```

如果目录位置不同，请先定位真实路径，不要移动或重训模型。示例：

```bash
cd /slurm/home/yrd/fanlab/zhangjinlu/zjl_desktop/KG/通用药效预测
```

## 4. 环境检查

在线技能使用已经配置好的 Python venv，不使用 Conda：

```bash
source /home/vipuser/srv/foundryclaw_project/FounDryClaw_Web/venv/Oasis/primekg/bin/activate
```

检查基础依赖：

```bash
python - <<'PY'
import torch
import dgl
from rdkit import Chem
import pandas
print('env ok')
print('torch', torch.__version__)
print('cuda_available', torch.cuda.is_available())
PY
```

如果 `dgl` 导入失败，不要继续跑预测，请记录完整报错。调用这个模型需要 DGL，因为加载 bundle 时会重建 disease heterograph。

## 5. 设置源码路径并检查 import

```bash
export KG_PROJECT_SRC=/slurm/home/yrd/fanlab/zhangjinlu/zjl_desktop/KG/PrimeKG/src
PYTHONPATH="src:${KG_PROJECT_SRC}" python - <<'PY'
import primekg_graph_indication_multitoken_cgi_graph
import primekg_graph_drug_zero_shot
print('project src import ok')
PY
```

## 6. 交接包完整性校验

在交接包目录下运行：

```bash
bash verify_handoff.sh
```

期望看到类似：

```text
[verify_handoff] ok
[verify_handoff] candidate_pool_rows= 6945
[verify_handoff] test_mrr= 0.3405655491444344
```

如果失败，请记录缺失文件路径，不要自行重训。

## 7. disease_id smoke test

先用 disease_id 跑 serum sickness：

```bash
bash score.sh 43789 score_43789_top100.csv python cuda 100
```

如果服务器没有可用 GPU，可以改用：

```bash
bash score.sh 43789 score_43789_top100.csv python cpu 100
```

检查输出：

```bash
python - <<'PY'
import pandas as pd
p = 'score_43789_top100.csv'
df = pd.read_csv(p)
print(df.shape)
print(df.head(10).to_string(index=False))
print(df.columns.tolist())
print('is_sorted_desc=', df['indication_score'].is_monotonic_decreasing)
PY
```

期望字段：

```text
disease_id,disease_name,rank,drugbank_id,drug_name,indication_score,has_cgi,has_drug_protein_target
```

## 8. disease_name smoke test

再用 disease name 跑 diabetic retinopathy：

```bash
bash score.sh "diabetic retinopathy" score_diabetic_retinopathy_top100.csv python cuda 100
```

如果服务器没有可用 GPU：

```bash
bash score.sh "diabetic retinopathy" score_diabetic_retinopathy_top100.csv python cpu 100
```

检查输出：

```bash
python - <<'PY'
import pandas as pd
p = 'score_diabetic_retinopathy_top100.csv'
df = pd.read_csv(p)
print(df.shape)
print(df.head(10).to_string(index=False))
print(df[['disease_id','disease_name']].drop_duplicates().to_string(index=False))
print('is_sorted_desc=', df['indication_score'].is_monotonic_decreasing)
PY
```

期望 disease 解析为：

```text
disease_id: 5266
disease_name: diabetic retinopathy
```

## 9. 负向测试：未知 KG 药物不能进入预测

这个模型只支持 `candidate_pool.csv` 中已有 DrugBank ID。做一个快速负向测试：

```bash
printf "DB_NOT_EXIST\n" > /tmp/unknown_drugbank_ids.txt
PYTHONPATH="src:${KG_PROJECT_SRC}" python -m primekg_cgi_graph_delivery.cli score \
  --bundle-dir ./primekg_cgi_graph_graph_only_e50/train \
  --prepared-dir ./primekg_cgi_graph_graph_only_e50/prepared \
  --disease 43789 \
  --candidate-drugbank-ids /tmp/unknown_drugbank_ids.txt \
  --output /tmp/should_not_exist.csv \
  --device cpu \
  --top-k 10
```

期望：报错提示该 DrugBank ID 不在 `candidate_pool.csv`，当前版本不支持 KG 外冷启动药物。

## 10. 请返回给用户的结果

请把以下内容发回：

1. `pwd` 当前交接包路径。
2. `which python` 的结果及 venv 路径 `/home/vipuser/srv/foundryclaw_project/FounDryClaw_Web/venv/Oasis/primekg`。
3. 依赖检查输出，包括 torch 版本、CUDA 是否可用及 DGL 是否可导入；当前服务端 venv 尚缺 DGL，完整验证会在该依赖补齐后进行。
4. `verify_handoff.sh` 输出。
5. `score_43789_top100.csv` 的前 10 行。
6. `score_diabetic_retinopathy_top100.csv` 的前 10 行。
7. disease_name 是否成功解析为 `5266 diabetic retinopathy`。
8. 负向测试是否按预期拒绝未知 DrugBank ID。
9. 如果有报错，请给完整 traceback，不要只截最后一行。

## 11. 注意事项

- 不要重训模型。
- 不要修改 `primekg_cgi_graph_graph_only_e50/train/*.pt`。
- 不要把任意新 SMILES 当作输入。
- 不要把 `indication_score` 解释为临床疗效概率，它只是当前模型候选池内的排序分数。
- 如果 PyTorch 2.6+ 报 `weights_only` 相关错误，交接 wrapper 已经做了可信本地 bundle 的兼容加载；请确认调用的是本交接包里的 `score.sh` 或 `primekg_cgi_graph_delivery.cli`。
