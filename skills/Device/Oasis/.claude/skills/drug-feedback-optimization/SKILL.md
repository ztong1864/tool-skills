---
name: drug-feedback-optimization
description: 运行可复现的小分子药效反馈闭环，基于冻结的初始排名和逐轮实验反馈推荐下一批候选，并可离线评估或搜索反馈策略。适用于任务配置、输入校验、反馈接收、候选重排序、批次推荐、模拟评估和策略冻结。不用于把原始图像或原始实验读数直接转换成药效分数。
---

# 药效反馈闭环优化

## 这个技能解决什么问题

药效预测模型可以先给候选药物排一次名，但这份排名来自历史知识或图谱，不包含当前实验体系中新产生的结果。实验室分批测试候选药物后，本技能使用已经测得的药效反馈训练一个轻量模型，重新评估尚未测试的候选，并推荐下一批实验对象。

它不会修改原始药效预测模型。它保留原始分数，同时新增实验反馈分数，再将两者融合成当前项目使用的排序分数。

```text
通用药效预测等上游技能
    └─ 输出初始候选和 indication_score
              ↓ 作为 base_score 冻结保存
第一轮候选推荐与实验
              ↓
HCI、ImageJ 或其他实验分析技能
    └─ 将原始图像或测量值转换为 activity_score
              ↓
本技能训练当前疾病和实验体系的轻量反馈模型
    └─ 输出 feedback_score
              ↓
base_score 与 feedback_score 按冻结规则融合
    └─ 得到 final_score，并据此推荐下一批候选
              ↓
下一轮实验产生新反馈，继续更新轻量反馈模型
```

## 与其他技能如何联动

| 环节 | 可使用的技能 | 交给本技能的内容 |
|---|---|---|
| 初始候选排序 | `primekg-cgi-drug-effect-prediction` 或其他药效预测技能 | 候选 ID、药物名称和 `indication_score`；进入本技能后映射为 `base_score` |
| 原始实验数据处理 | `hci-image-analysis`、`imagej-analyzer` 或其他实验分析流程 | 经过 QC、重复汇总和归一化的实验结果 |
| 多轮候选优化 | `drug-feedback-optimization` | 根据累计反馈生成 `feedback_score`、`final_score` 和下一批候选 |
| 离线搜索更好的反馈策略 | `autoresearch-core` | 比较模型、特征、融合权重或获取策略并冻结胜出版本 |

`indication_score` 只有在候选 ID、候选空间和分数方向对齐后才能作为 `base_score`。本技能不要求上游一定是 PrimeKG；其他模型的初始分数也可以使用，但必须记录模型身份和分数含义。

## 先理解四个核心概念

- **基座模型**：产生初始候选排名的上游模型，例如 PrimeKG Graph CGI e50。它输出的 `indication_score` 可以作为本项目的 `base_score`。
- **冻结基座排名**：campaign 开始后保存候选池、基座模型版本和每个候选的 `base_score`，后续轮次不修改这些值。这里的“冻结”是保持初始参照不变，不是把模型文件做特殊处理。
- **反馈模型**：使用当前疾病、当前实验体系中已经测试过的候选及其 `activity_score` 训练的轻量模型。它输出 `feedback_score`，只修正当前项目的候选优先级，不回写或重新训练基座模型。
- **campaign（药效反馈项目）**：围绕一种疾病、一套实验体系、一个候选池和一套评分规则开展的完整多轮筛选项目。一个 campaign 可以包含多轮“推荐 → 实验 → 反馈 → 再推荐”。

反馈模型通常只适用于它所属的疾病和实验语义。更换疾病、主要实验体系、`activity_score` 定义、基座模型或候选池时，通常应建立新的 campaign，而不是直接沿用旧反馈模型。

## 什么时候使用

- 已有候选药物初始排名，准备分多轮做实验；
- 已获得一轮或多轮标准化药效结果，希望调整剩余候选顺序；
- 需要在固定实验预算下推荐下一批药物；
- 需要用历史完整标签离线比较反馈策略。

以下情况不需要调用本技能：

- 只需要执行一次通用药效预测；
- 只需要分析一批 HCI 或 ImageJ 原始图像；
- 没有后续候选推荐需求，只需要解释已有实验结果。

## 选择运行模式

- **真实 campaign**：实际实验正在分轮开展。每轮接收已经标准化的药效结果，重新训练当前项目的反馈模型，然后推荐下一批尚未测试的候选。
- **离线评估**：已有一份候选药物的完整历史实验结果。程序假装这些结果尚未获得，按照多轮实验顺序逐步揭示标签，用来比较不同推荐策略。
- **Auto-Research**：一种离线策略搜索方式。外部模型、程序或人工流程提出新的反馈模型、融合权重或候选选择规则，固定评估器负责测量效果，`autoresearch-core` 只保留实测更好的候选策略。
- **PRISM 历史基准**：随包提供的肺腺癌回顾性测试案例。PRISM 是药物筛选数据来源，LUAD 是肺腺癌。它用于验证代码和比较策略，不表示该技能只能用于肺腺癌。

创建或校验任务时读取 [references/task-config-and-data.md](references/task-config-and-data.md)。真实 campaign 读取 [references/campaign-workflow.md](references/campaign-workflow.md)。模拟、评估或 Auto-Research 读取 [references/autoresearch-and-evaluation.md](references/autoresearch-and-evaluation.md)。使用随包 PRISM 代码时读取 [references/prism-primary-luad.md](references/prism-primary-luad.md)。

## 开始前需要准备什么

真实 campaign 至少需要三类输入：

1. **候选药物表**：每行一个候选，包含唯一 `candidate_id`、初始 `base_score`、SMILES 和反馈模型需要的分子特征。
2. **任务配置 JSON**：说明疾病、文件路径、字段名称、每轮数量、总预算、反馈启用阈值和策略版本。以 [assets/task_config.template.json](assets/task_config.template.json) 为模板。
3. **实验反馈 CSV**：至少包含 `candidate_id` 和 `[0,1]` 范围内的 `activity_score`。这是已经完成图像分析、重复孔汇总、对照归一化和 QC 后的结果，不是原始图像。

如果还没有任何实验反馈，可以初始化项目并按 `base_score` 推荐第一批。反馈达到配置中的 `min_feedback_to_fit` 后，才启用反馈模型。

## 环境检测

正式运行前先在工作区执行（本技能的命令都写成 `python .claude/skills/drug-feedback-optimization/...`，平台会自动选择 Python 环境，不要激活其他环境或自行安装包）：

```bash
python .claude/skills/drug-feedback-optimization/scripts/check_environment.py
python .claude/skills/drug-feedback-optimization/scripts/validate_task_config.py --help
```

环境检测只确认目录、测试数据、相邻 `autoresearch-core` 和 Python 依赖，不运行评估或训练。真实运行仍需先校验任务配置和输入数据。

## 建立 campaign 时固定什么

初始化时固定并记录哈希或快照：

- 候选池以及唯一候选 ID；
- 上游基座模型的名称和版本；
- 从上游结果映射得到的 `base_score`；
- SMILES、分子特征和特征生成版本；
- 从原始实验结果生成 `activity_score` 的方法、版本和方向；
- 反馈模型、融合公式、候选获取规则和策略版本；
- 每轮批量、总预算和软件来源。

这些内容固定后，后续轮次新增的是实验反馈和候选状态。V1 只根据累计有效反馈重新拟合轻量反馈模型，不微调、不覆盖也不替换基座模型。真实 campaign 进行期间不运行 Auto-Research，也不静默改变已冻结的策略结构。

`activity_score` 必须是 `[0,1]` 内、越大越好的连续数值。原始图像、重复孔和原始测量值必须由 HCI、ImageJ 或其他实验分析流程先完成 QC、聚合和转换；同一 campaign 内冻结转换版本。

例如，PrimeKG 给出药物 A 的 `indication_score=0.80`，当前实验反馈模型预测 `feedback_score=0.60`。若当前冻结融合规则为 `0.7/0.3`，则：

```text
base_score     = 0.80
feedback_score = 0.60
final_score    = 0.7 × 0.80 + 0.3 × 0.60 = 0.74
```

反馈达到启用阈值后，下一批推荐使用 `final_score=0.74` 对药物 A 排序；原始 `indication_score=0.80` 仍保留用于追溯和比较。

## 每轮数量

有效批量大小按以下顺序解析：

1. 当前轮 `--batch-size K`；
2. `campaign.round_batch_sizes[round]`；
3. `campaign.batch_size`，默认 50。

数量必须为正整数，并受剩余候选数和 campaign 剩余预算限制。记录请求数量、实际数量、来源、轮次和缩减原因。只有 `campaign.allow_runtime_batch_size_override=true` 时才接受运行时覆盖。

使用 [assets/task_config.template.json](assets/task_config.template.json) 创建配置，并用 `scripts/validate_task_config.py` 校验和解析批量大小。

## 反馈闭环

1. 校验任务配置、冻结候选表、特征列表、策略版本和反馈 CSV。
2. 拒绝缺失、重复或未知 ID，非数值或越界分数，缺失特征及不一致 campaign 元数据。
3. 排除已推荐、待测、已观测、不可重试失败和其他不可用候选。
4. 有效反馈少于阈值时，只按冻结的 `base_score` 排名；V1 默认阈值为 30。
5. 达到阈值后，用累计有效反馈重新拟合冻结策略，计算 `feedback_score` 和融合后的 `final_score`。此时必须将 `final_score` 作为本轮主排序分数，不能继续默认按 `base_score` 推荐。
6. 保证候选唯一；默认整个 campaign 中每个规范结构组只保留一个代表。
7. 成功返回前写出推荐表、评分池、摘要、报告、模型元数据和只追加事件记录。

### 实际排序分数

每轮必须显式解析并记录：

```text
if valid_feedback < strategy.min_feedback_to_fit:
    ranking_score = base_score
    ranking_source = "base_only"
else:
    ranking_score = final_score
    ranking_source = "base_feedback_fusion"
```

- 默认贪心获取按 `ranking_score` 降序选择候选。
- 若冻结策略包含探索或结构多样性规则，`ranking_score` 仍是利用部分的主排序依据；探索候选可以偏离纯分数顺序，但必须在 `selection_reason` 中说明。
- 反馈模型启用后，不得只计算或展示 `final_score`，却仍用 `base_score` 产生下一批候选。
- 输出必须包含 `base_score`、`feedback_score`、`final_score`、`ranking_score`、`ranking_source`、`base_rank`、`final_rank` 和 `selection_reason`。

通用 V1 配置以 RandomForest 回归、`base_score + Morgan256`、`0.7 × base_score + 0.3 × feedback_score` 和贪心获取作为起始策略。随包 PRISM smoke 的冻结历史策略实际使用 `0.5 / 0.5`，报告时必须以实际 `strategy.py` 和策略版本为准。

其中：

- RandomForest 是根据已测候选学习“分子特征与当前实验药效之间关系”的回归模型；
- Morgan256 是把分子结构编码成 256 个二进制特征的指纹表示；
- 贪心获取表示直接选择当前 `ranking_score` 最高的候选；
- 获取策略（acquisition strategy）是“如何从剩余候选中组成下一批”的规则，可以在高分候选之外加入少量探索或结构多样性候选。

## 反馈状态

- `valid`：实验完成且 `activity_score` 有效，可以用于训练反馈模型。
- `compound_failure`：化合物本身无法完成实验，例如溶解性或稳定性问题。它会消耗实验资源，但不能伪造成“药效为零”的训练标签。
- `technical_failure`：由成像、移液、仪器或数据质量问题导致失败，不参与训练；默认允许重试一次，之后排除。
- `pending`：已经推荐并进入实验，但结果尚未返回；候选暂时保留，不得再次推荐。

所有状态变化写入只追加 ledger 或事件日志，已经测试或保留的候选不得再次推荐。

## Auto-Research

只在证据条件满足时离线运行：

- 至少有 `max(100, 2 × 默认批量大小)` 条同语义有效历史观测时，可搜索反馈模型、特征和融合权重；
- 有完整回顾性标签池，且规模至少是模拟获取预算两倍时，才搜索 warm start 和 acquisition 行为。

使用相邻的 `$autoresearch-core` 和 `generic_autoresearch_config.*.json` 运行通用 JSON 循环。保持评估器、冻结输入和主指标不变，并在每次 trial 前后运行 `guard_autoresearch.py`。

这里的“冻结策略”是把已经通过离线评估的模型代码、参数、指标和来源保存成一个不可静默修改的版本。真实 campaign 只绑定和使用这个版本，不在实验进行中继续搜索策略。

稳定性和冻结规则见 [references/autoresearch-and-evaluation.md](references/autoresearch-and-evaluation.md)。冻结产物至少包括 `strategy.py`、`strategy_config.json`、`metrics_summary.json`、`selection_report.md` 和 `provenance.json`。

## 当前实现边界

运行命令前检查实际脚本及其 `--help`。规划中的通用真实实验命令 `init-campaign`、`ingest-feedback`、`recommend-next` 和 `close-campaign` 尚未实现，不能当作现有入口。

当前已经实现并随包验证的是 PRISM 离线 smoke、闭环评估、获取曲线评估、通用 AutoResearch 的药效评估器适配、配置校验和策略冻结链路。

## 报告要求

报告至少说明策略版本、累计有效反馈数、轮次、请求和实际批量大小、融合规则、`ranking_source`、候选 ID 与各项分数、实际排序分数、排名变化、选择原因、结构组、失败或待测数量、缩减情况，以及冻结输入的路径或哈希。

不能用逐批原始均值下降直接判断策略失效，因为候选池耗竭本身会降低后续批次均值。优先报告累计效用、模拟中的 oracle 归一化获取曲线、高活性候选发现数和固定留出集排序指标。

## 随包 PRISM 验证

在工作区运行（`--output-dir` 必须写到工作区，不能写进技能目录）：

```bash
python .claude/skills/drug-feedback-optimization/test-data/prism-primary-luad-smoke-v1/run_smoke.py --rounds 2 --batch-size 17 --top-k 17 --output-dir outputs/prism_smoke
```

回顾性 `activity_score` 只能供评估器使用，在线推荐器在获取候选前不得看到未观测标签。
