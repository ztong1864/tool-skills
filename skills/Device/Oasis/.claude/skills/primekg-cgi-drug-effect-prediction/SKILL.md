---
name: primekg-cgi-drug-effect-prediction
description: 使用已训练的 PrimeKG Graph CGI e50 模型，对疾病目录中可匹配的疾病及候选药物库中的 KG 已有药物进行适应症排序，并输出排名 CSV。需要进行药物推荐时优先使用该技能。
metadata:
  short-description: 对 KG 已有候选药物进行疾病条件下的适应症排序
---

# PrimeKG Graph CGI 通用药效预测

本技能使用随包提供的已训练模型进行推理。开始前阅读 README.md。需要了解模型输入输出、架构或适用限制时，再阅读：

- docs/model_io_spec.md
- docs/model_architecture.md
- docs/limitations.md

## 输入范围与适用限制

- 疾病必须能在 primekg_cgi_graph_graph_only_e50/prepared/disease_catalog.csv 中通过 disease_id 或完整疾病名唯一匹配。疾病名匹配会忽略大小写和空格。
- 默认候选范围为 prepared/candidate_pool.csv 中的 6,945 个 KG 已有 DrugBank 药物。可通过 DrugBank ID 白名单限制候选范围；白名单中的每个 ID 都必须存在于该候选库中。
- 本技能不接受任意 SMILES，不支持新的 DrugBank ID、KG 外天然产物或其他化合物库的冷启动预测。
- indication_score 是用于同一疾病内候选药排序的模型分数，不代表疗效概率、临床治疗结论或处方建议。
- 随包模型用于推理。重新准备数据或训练模型时，才需要原始 PrimeKG、DrugBank、CMap/CGI 和疾病 embedding 数据。

## 推理所需文件

部署时保留完整技能包。模型推理依赖以下内容：

- primekg_cgi_graph_graph_only_e50/prepared/：疾病目录、候选药物库及图谱数据。
- primekg_cgi_graph_graph_only_e50/train/：模型权重、缓存和 embedding。
- src/primekg_cgi_graph_delivery/：推理封装。
- model_source/src/：已解压的模型源码。
- source_archives/：源码压缩包备份；不能单独作为推理包使用。

## 运行环境

运行本技能必须使用服务器上的 primekg 虚拟环境：

/home/vipuser/srv/foundryclaw_project/FounDryClaw_Web/venv/Oasis/primekg

不得使用系统 Python、对话默认 Python 或其他技能的虚拟环境。运行前激活该环境，并在验证和打分命令中显式指定该环境的 Python 解释器：

~~~bash
source /home/vipuser/srv/foundryclaw_project/FounDryClaw_Web/venv/Oasis/primekg/bin/activate
PY=/home/vipuser/srv/foundryclaw_project/FounDryClaw_Web/venv/Oasis/primekg/bin/python
~~~

该环境使用 Python 3.10，主要依赖为 PyTorch 1.13.1+cpu、DGL 1.1.2、NumPy 1.24.3、pandas 2.0.3、scikit-learn 1.3.2 和 RDKit 2022.09.5。包内的 environment.yml 是旧环境模板，不用于判断当前环境是否可用，也不代表需要创建 Conda 环境。

当前 PyTorch 为 CPU 版本，设备参数使用 auto 或 cpu。只有切换到支持 CUDA 的 PyTorch 环境后，才使用 cuda。

score.sh 默认使用随包的 model_source/src。正常推理不需要设置源码路径；只有需要替换源码版本时，才设置 KG_PROJECT_SRC。

## 运行前验证

将 SKILL_DIR 设置为本技能目录的绝对路径，然后执行交接包验证：

~~~bash
SKILL_DIR="<本技能目录的绝对路径>"
source /home/vipuser/srv/foundryclaw_project/FounDryClaw_Web/venv/Oasis/primekg/bin/activate
PY=/home/vipuser/srv/foundryclaw_project/FounDryClaw_Web/venv/Oasis/primekg/bin/python

PYTHON_BIN="$PY" bash "$SKILL_DIR/verify_handoff.sh"
~~~

验证脚本检查指定解释器能否导入 PyTorch、DGL、RDKit、pandas 和 NumPy，并检查随包文件。验证通过后再运行正式推理。若报告 missing Python modules，先确认使用的是上述 primekg 解释器；该环境仍缺少依赖时，记录缺失模块并停止推理，不得跳过检查或用其他模型结果替代。

## 疾病匹配

正式打分前，必须先从 primekg_cgi_graph_graph_only_e50/prepared/disease_catalog.csv 中确认疾病记录。优先使用 disease_id 调用模型；使用疾病名时，必须使用目录中的完整名称。不得根据记忆或外部资料自行猜测疾病 ID。

可以通过疾病英文名或关键词搜索目录：

~~~bash
grep -i "<英文关键词>" \
  "$SKILL_DIR/primekg_cgi_graph_graph_only_e50/prepared/disease_catalog.csv"
~~~

选择与用户指定疾病概念和层级相符的记录。不要仅因名称相似就改用更宽泛的上位疾病或更具体的亚型。标记为 susceptibility 或 obsolete 的条目通常不等同于当前疾病概念；只有在其含义确实符合用户请求时才考虑使用。若多个目录条目同样符合，且无法根据请求判断，应先向用户澄清。

运行结果中注明从 disease_catalog.csv 选用的 disease_id 和 disease_name。

若打分脚本报告疾病未找到，应重新核对 disease_catalog.csv 中的完整名称或 ID。只有脚本成功生成并通过检查的排名文件，才能报告为推理结果。

## 执行推理

使用任务系统提供的产物目录；如果没有提供，在当前任务工作区创建专用目录，避免将结果写入模型或 prepared 数据目录。

~~~bash
ARTIFACT_DIR="<任务产物目录的绝对路径>"
mkdir -p "$ARTIFACT_DIR"
~~~

score.sh 参数顺序为：

~~~text
score.sh <disease_id 或 disease_name> <output_csv> <python_executable> <device> <top_k>
~~~

优先使用已从 disease_catalog.csv 确认过的 disease_id：

~~~bash
bash "$SKILL_DIR/score.sh" \
  43789 \
  "$ARTIFACT_DIR/score_43789.csv" \
  "$PY" \
  auto \
  20
~~~

使用 disease_catalog.csv 中完整疾病名的示例：

~~~bash
bash "$SKILL_DIR/score.sh" \
  "diabetic retinopathy" \
  "$ARTIFACT_DIR/score_dr.csv" \
  "$PY" \
  auto \
  20
~~~

设备参数支持 auto、cpu、cuda 或 mps，但必须与当前 PyTorch 环境相符。top_k=0 表示输出全部候选药物。指定 DrugBank ID 白名单时，先确认所有 ID 都在 candidate_pool.csv 中，再按 Python CLI 的 --help 使用 --candidate-drugbank-ids 参数。

运行后检查输出文件存在、非空，并包含预期字段。推理失败时记录实际命令、错误信息和环境检查结果；不得将失败运行描述为已完成的排名。

## 输出与报告

本技能单次推理的必需产物是一份候选药物排名 CSV。核心字段为：

~~~text
disease_id,disease_name,rank,drugbank_id,drug_name,indication_score,has_cgi,has_drug_protein_target
~~~

输出目录用于存放该 CSV，不是额外的模型产物。本技能不生成反馈前后排名对比或多轮评估指标；需要反馈闭环评估时，应另行使用 drug-feedback-optimization，并按该技能的实际输出登记产物。

向用户报告时，说明：

- 从 disease_catalog.csv 匹配到的疾病名称和 disease_id
- 模型名称
- 结果 CSV 路径
- Top N 候选药及其排序分数

has_cgi 和 has_drug_protein_target 表示对应图谱信息是否存在，不表示疗效证据强弱。结果仅用于候选药研究排序。

## Ontology 登记

只有当前任务已获授权维护 ontology 时，才将推理结果登记为 Data，并通过通用药效预测 Process 的 produce 关系关联。若结果用于具体 Oasis 实验，只有在确认对应 Workflow 后，才建立 withData 关系。

当前任务未授权图谱写入时，不自动修改 ontology；在报告中列出建议登记的实体和关系即可。

