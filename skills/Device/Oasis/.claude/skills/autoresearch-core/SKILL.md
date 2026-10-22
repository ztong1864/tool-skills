---
name: autoresearch-core
description: 在固定数据、固定评估程序和固定指标下，反复测试不同模型参数或决策策略，记录每次结果并冻结当前表现最好的版本。适用于机器学习配置、融合权重或其他可通过命令量化评估的方案搜索。它是通用试验管理器，由领域技能告诉它测试什么和怎样算好；自己不定义领域指标，也不训练领域模型。
---

# 通用 AutoResearch 核心

## 这个技能解决什么问题

当一个任务有多种可选方法时，不能只凭经验判断哪种最好。例如，药效反馈闭环可能需要决定：

- 使用 RandomForest 还是 ExtraTrees；
- 基座分数和反馈分数采用 `0.7/0.3` 还是 `0.5/0.5`；
- 每轮是否加入探索候选；
- 结构相似性去重阈值是多少。

`autoresearch-core` 负责把这些方案逐个交给同一个评估程序测试，再按照同一个数值指标比较结果。它保存每次试验和选择理由，最后把当前实测表现最好的方案复制到一个带版本号的冻结目录。

它是一个通用的试验管理器，不理解药物或疾病本身，也不训练和部署具体领域模型。领域技能负责告诉它“测试什么”和“怎样算好”，它负责可靠地执行、比较和记录。

```text
领域技能准备固定数据、评估器和评价指标
                    ↓
提案器提出一个待测试方案
                    ↓
AutoResearch Core 调用固定评估器
                    ↓
评估器运行试验并返回一个数值指标
                    ↓
AutoResearch Core 与当前最佳结果比较
                    ↓
保留记录，继续试验，最后冻结最佳实测方案
```

## 与药效反馈技能的关系

在当前项目中，`drug-feedback-optimization` 与 `autoresearch-core` 这样分工：

| 工作 | 负责技能 |
|---|---|
| 定义候选药、`base_score`、实验 `activity_score` 和反馈模型 | `drug-feedback-optimization` |
| 模拟多轮“训练反馈模型—融合分数—选择下一批” | `drug-feedback-optimization` 的离线评估器 |
| 提出不同模型、参数、融合权重或探索规则 | 外部提案器 |
| 调用评估器、比较指标、记录试验和停止搜索 | `autoresearch-core` |
| 将最佳实测策略保存成版本 | `autoresearch-core` |
| 在新的真实药效反馈项目中使用冻结策略 | `drug-feedback-optimization` |

因此，AutoResearch 搜索的是“以后用哪套反馈策略”，不负责“这一轮具体推荐哪些药”。真实药效反馈项目开始后，使用已经冻结的策略，不在项目运行过程中继续搜索和更换策略。

## 一次完整试验中有哪些对象

### 基线方案（baseline）

开始搜索前必须先运行一套现有方案，得到基准指标。例如：

```text
RandomForest + 0.7/0.3 融合
acquisition_ncg_auc_mean = 0.699
```

后续候选方案都与这套基线及当前最佳方案比较。

### 候选方案（proposal）

候选方案是一份 JSON，描述本次要测试的改变，并使用唯一 `candidate_id`。例如：

```json
{
  "candidate_id": "rf_weight_06_04",
  "estimator": "RandomForestRegressor",
  "base_weight": 0.6,
  "feedback_weight": 0.4,
  "explore_count": 2
}
```

AutoResearch Core 不判断这些字段的药效含义。字段如何转换成模型和推荐规则，由药效反馈评估器负责。

### 提案器（proposer）

提案器负责生成候选方案，可以是：

- 按预设目录逐个枚举参数的 Python 程序；
- 本地或托管模型的命令行适配器；
- 其他智能体或优化程序；
- 人工创建的 `proposal.json`。

自动提案器从标准输入读取当前目标、基线、最佳指标、已测试方案和剩余预算，只向标准输出返回一个候选 JSON。AutoResearch Core 本身不生成研究假设，也不直接调用模型 API。

### 评估器（evaluator）

评估器是领域技能提供的固定程序。它读取候选方案，在固定数据和固定协议上实际运行试验，最后返回配置指定的指标。例如：

```json
{
  "status": "ok",
  "acquisition_ncg_auc_mean": 0.713,
  "artifacts": [
    "strategy.py",
    "metrics_summary.json"
  ]
}
```

评估器必须负责数据读取、模型训练、泄漏检查和领域指标计算。AutoResearch Core 只读取返回值并比较大小。

### 主指标（metric）

每个搜索任务只能指定一个用于自动选择的主指标：

- `metric_key`：评估器返回的字段名；
- `direction: higher`：数值越高越好；
- `direction: lower`：数值越低越好。

药效反馈示例使用 `acquisition_ncg_auc_mean`，表示在固定实验预算下，多轮推荐策略发现高药效候选的累计效率。这个指标由药效评估器定义和计算，不由 AutoResearch Core 定义。

### Guard

Guard 是试验前后运行的保护程序，用于确认固定数据、评估器、数据划分或策略接口没有被候选方案修改。Guard 失败时，该次试验不能作为有效改进。

## 一次搜索如何运行

1. 校验配置文件以及其中的命令和字段。
2. 保存配置快照和哈希，防止搜索过程中静默改变标准。
3. 运行基线评估，记录初始指标。
4. 提案器生成一个具有唯一 ID 的候选方案，或由人工提交方案文件。
5. 运行 Guard，确认固定输入和评估协议未被改变。
6. 调用领域评估器测试候选方案。
7. 再次运行 Guard，并读取评估器返回的主指标和产物。
8. 根据 `direction` 和 `tolerance` 判断候选是否优于当前最佳方案。
9. 保存候选、日志、指标、产物路径和保留或拒绝决定。
10. 在试验预算用完、连续无改善次数达到上限，或提案器主动停止时结束。
11. 将当前最佳实测方案复制到带版本号的冻结目录。

## 搜索配置中的关键字段

从 [assets/config.template.json](assets/config.template.json) 复制配置。首次使用时需要理解：

| 字段 | 含义 |
|---|---|
| `name` | 本次策略搜索的名称 |
| `goal` | 希望改进的具体目标，提供给提案器阅读 |
| `workspace` | 评估器、数据和策略文件所在目录 |
| `metric_key` | 用于自动比较的指标字段名 |
| `direction` | 指标越高越好或越低越好 |
| `budget` | 最多允许评估多少个候选方案；失败试验也计入 |
| `patience` | 连续多少次没有改进后提前停止 |
| `tolerance` | 新指标至少改善多少才算真正更好 |
| `baseline.command` | 运行基线方案的命令参数数组 |
| `trial.command` | 评估一个候选方案的命令参数数组 |
| `guard.command` | 可选的固定输入保护命令 |
| `proposer.command` | 自动生成下一候选方案的可选命令 |
| `proposal_schema` | 候选 JSON 允许和要求哪些字段 |
| `search_guidance` | 搜索范围、不可修改项及建议变化方式 |

命令以参数数组直接执行，不经过 shell。可使用的路径占位符包括 `{python}`、`{config}`、`{config_dir}`、`{workspace}`、`{run_dir}`、`{trial_dir}` 和 `{proposal_path}`。完整 JSON 协议见 [references/protocol.md](references/protocol.md)；连接外部提案器时读取 [references/provider-adapters.md](references/provider-adapters.md)。

## 运行前检查

在工作区执行（本技能的命令都写成 `python .claude/skills/autoresearch-core/scripts/...`，平台会自动选择 Python 环境，不要激活其他环境或自行安装包）：

```bash
python .claude/skills/autoresearch-core/scripts/check_environment.py
python .claude/skills/autoresearch-core/scripts/autoresearch_core.py --help
```

环境检测只检查 Python 版本、核心脚本、配置模板和参考文档，不启动搜索。领域评估器、数据和提案器的依赖需要由对应项目另行检查。

## 两种使用方式

### 人工或外部系统逐个提交方案

```bash
python scripts/autoresearch_core.py validate-config --config path/to/config.json
python scripts/autoresearch_core.py init --config path/to/config.json --run-dir path/to/run
python scripts/autoresearch_core.py submit --run-dir path/to/run --proposal proposal.json
python scripts/autoresearch_core.py status --run-dir path/to/run
python scripts/autoresearch_core.py freeze --run-dir path/to/run --version strategy_v1
```

这种方式不需要配置 `proposer.command`。外部系统或研究人员负责生成每个 `proposal.json`。

### 配置提案器后自动循环

```bash
python scripts/autoresearch_core.py validate-config --config path/to/config.json
python scripts/autoresearch_core.py loop --config path/to/config.json --run-dir path/to/run
python scripts/autoresearch_core.py status --run-dir path/to/run
python scripts/autoresearch_core.py freeze --run-dir path/to/run --version strategy_v1
```

`loop` 会先运行基线，然后反复调用 `proposer.command` 和评估器，直到满足停止条件。

## 输出在哪里

这里的 `run` 指一次完整策略搜索任务，从固定配置和基线开始，到达到停止条件为止；`trial` 指其中一次候选方案评估。

一个 run 目录通常包含：

```text
run/
├── config.snapshot.json        # 搜索开始时的配置快照
├── state.json                  # 当前基线、最佳方案、预算和停止状态
├── results.jsonl               # 只追加的逐次试验记录
├── results.tsv                 # 便于查看的指标表
├── trials/
│   ├── 000_baseline/           # 基线评估日志和产物
│   └── 001_candidate_id/       # 某个候选方案的日志和产物
└── frozen/
    └── strategy_v1/            # 最佳实测方案及其来源记录
```

“冻结最佳方案”只表示它在本次固定评估协议中取得了最好的主指标。是否具备统计稳定性、是否通过锁定测试、是否适合真实实验，仍由领域技能的验收规则决定。

## 不应使用本技能的情况

- 没有可执行评估器，只能主观讨论方案；
- 没有明确、可计算且方向确定的主指标；
- 不同候选使用不同数据、预算或评价标准，无法公平比较；
- 需要直接处理原始实验数据或推荐下一批药物；
- 正在运行的真实项目已经绑定策略，准备临时改变模型或权重。
