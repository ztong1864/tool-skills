# Drug Feedback Optimization

面向小分子药效实验的反馈闭环技能。它从冻结的基座模型排序出发，接收逐轮数值反馈，训练轻量反馈模型，融合 `base_score` 与 `feedback_score`，再推荐下一批候选分子。

本包还包含一个不绑定特定模型、智能体框架或模型厂商的 `autoresearch-core`。它通过标准 JSON 和外部命令连接任意提案器与固定评估器，可用于离线搜索反馈模型、融合方式和探索参数。

## 1. 本项目整合的两个组件

```text
drug-feedback-optimization/  药效反馈协议、PRISM 数据、评估器和领域适配器
autoresearch-core/           通用 propose → evaluate → select → freeze 核心
```

`autoresearch-core` 是通用接口。它可以连接托管或本地模型、自建智能体、确定性搜索程序或人工提案。

## 2. 安装

将下面两个目录复制到目标项目：

```text
<项目目录>/.agents/skills/drug-feedback-optimization/
<项目目录>/.agents/skills/autoresearch-core/
```

两个目录应保持为 `.agents/skills/` 下的同级目录，以保证随包 PRISM 配置中的相对路径有效。

在支持技能调用的智能体中，可用自然语言调用药效闭环：

```text
$drug-feedback-optimization 读取第3轮反馈，本轮推荐35个分子
```

通用 AutoResearch 也可以完全从命令行运行，无需技能系统。

## 3. 能做什么

- 校验任务配置、候选表、基座分数和分子特征。
- 接收统一后的数值型 `activity_score`。
- 基于累计有效反馈重新训练轻量反馈模型。
- 按可修改的每轮批量大小推荐候选。
- 排除已测试、待测和已保留候选。
- 在回顾性完整标签数据上模拟闭环获取过程。
- 用固定指标比较候选策略并冻结最佳实测版本。
- 记录每个提案、评估结果、保留或拒绝决定和最终来源。

当前包已实现并验证 PRISM 离线评估与通用 AutoResearch。规划中的真实实验通用 CLI（如 `init-campaign`、`ingest-feedback`、`recommend-next`）尚未实现，不能当作现有命令使用。

## 4. 目录结构

```text
drug-feedback-optimization/
├── SKILL.md
├── README.md
├── assets/task_config.template.json
├── references/
├── scripts/validate_task_config.py
└── test-data/prism-primary-luad-smoke-v1/

autoresearch-core/
├── SKILL.md
├── README.md
├── assets/config.template.json
├── references/protocol.md
├── references/provider-adapters.md
└── scripts/autoresearch_core.py
```

PRISM 测试目录主要包含：

- `base_scored_oracle.csv`：4,684 个候选、冻结基座分数、268 个特征及回顾性活性标签。
- `feature_columns.json`：反馈模型可用的268个特征字段。
- `split_manifest.json`：seed 42–51 的固定划分。
- `strategy.py`：基线反馈策略。
- `run_smoke.py`：基础反馈模拟。
- `run_acquisition_eval.py`：闭环获取评估器。
- `generic_evaluator.py`：通用 AutoResearch 到药效评估器的适配器。
- `generic_catalog_proposer.py`：不调用任何大模型的测试提案器。
- `generic_autoresearch_config.smoke.json`：已验证的通用测试配置。
- `generic_autoresearch_config.full.json`：30次正式搜索模板，需替换模型适配器。
- `guard_autoresearch.py`、`frozen_inputs.sha256`：冻结数据和评估协议保护。
- `checksums.sha256`：测试目录文件完整性校验。

`base_scored_oracle.csv` 的未观测活性只能用于离线评估，不得作为真实实验反馈泄漏给训练过程。

## 5. 安装测试依赖

进入测试目录：

```bash
cd .agents/skills/drug-feedback-optimization/test-data/prism-primary-luad-smoke-v1
python -m pip install -r requirements-smoke.txt
```

主要依赖为 NumPy、pandas、SciPy 和 scikit-learn。`autoresearch-core` 自身只使用 Python 标准库。

## 6. 基础反馈 Smoke Test

```bash
python run_smoke.py --rounds 2 --batch-size 17 --top-k 17
```

已验证参考结果：

```text
round2_dev_ndcg_at_17_mean = 0.6227200396731953
round2_dev_ndcg_at_17_std  = 0.07756418834125085
```

结构检查应保持一致：10个种子；每个种子包含第0、1、2轮；每个活动轮获取17个不重复候选。

修改每轮数量，例如每轮35个：

```bash
python run_smoke.py --rounds 2 --batch-size 35 --top-k 35
```

正式比较策略时，轮数、每轮数量、总预算、数据划分和主指标必须相同。

## 7. 运行通用 AutoResearch

仍在 PRISM 测试目录中执行。先确定通用核心位置：

```text
../../../autoresearch-core/scripts/autoresearch_core.py
```

### 7.1 校验配置

```bash
python ../../../autoresearch-core/scripts/autoresearch_core.py \
  validate-config \
  --config generic_autoresearch_config.smoke.json
```

### 7.2 自动运行 baseline 加两个候选

```bash
python ../../../autoresearch-core/scripts/autoresearch_core.py \
  loop \
  --config generic_autoresearch_config.smoke.json \
  --run-dir generic-autoresearch-run
```

这个测试由普通 Python 提案器读取 stdin 中的研究上下文并在 stdout 返回 JSON 提案，不需要任何模型 API。

### 7.3 查看状态

```bash
python ../../../autoresearch-core/scripts/autoresearch_core.py \
  status --run-dir generic-autoresearch-run
```

### 7.4 冻结最佳实测版本

```bash
python ../../../autoresearch-core/scripts/autoresearch_core.py \
  freeze \
  --run-dir generic-autoresearch-run \
  --version prism_luad_feedback_v1
```

冻结目录包含：

```text
strategy.py
strategy_config.json
metrics_summary.json
selection_report.md
provenance.json
```

## 8. 接入其他大模型或智能体

通用核心不直接调用任何模型 SDK。`proposer.command` 指向一个很小的适配器程序：

1. 从标准输入读取核心提供的 JSON 上下文；
2. 调用任意模型、智能体或搜索算法；
3. 向标准输出返回一个带唯一 `candidate_id` 的 JSON 提案；
4. 无合理候选时返回 `{"action":"stop","reason":"..."}`。

配置示例：

```json
{
  "proposer": {
    "command": ["{python}", "my_model_adapter.py"]
  }
}
```

适配器可以调用 Claude、Gemini、Qwen、DeepSeek、Ollama、vLLM、OpenHands 或 OpenAI-compatible 服务。API key 放在适配器读取的环境变量中，不写入配置、提案或日志。

不能提供本地命令的网页大模型也能用：先执行 `init`，让外部系统生成 `proposal.json`，再逐个执行 `submit`。

完整协议见 `autoresearch-core/references/protocol.md` 和 `provider-adapters.md`。

## 9. 已完成的通用接入测试

当前版本已在 PRISM primary LUAD 上使用确定性 Python 提案器完成 baseline、两个自动提案、评估、选择和冻结：

| 策略 | `acquisition_ncg_auc_mean` | 决策 |
|---|---:|---|
| RandomForest baseline | 0.6990998931 | 保留 |
| ExtraTrees 候选 | 0.6330990162 | 拒绝 |
| RandomForest + 每轮2个 Morgan 多样性候选 | 0.6973041836 | 拒绝 |

两个候选均未超过 baseline，因此最终保留 baseline。这验证了：

```text
任意提案器 → JSON 提案 → 固定药效评估器 → 指标比较
→ 保留/拒绝 → 预算与早停状态 → 冻结最佳策略
```

这次只用于验证系统链路。正式30次模型驱动搜索尚未运行；需要把 `generic_autoresearch_config.full.json` 中的占位 proposer 命令替换为目标计算机上的模型适配器。

## 10. 提案器选择

使用 `autoresearch-core` 的 JSON 协议连接目标模型、确定性搜索程序或人工提案流程，无需修改核心和药效评估器。这样 AutoResearch 的实验记录、预算、主指标和冻结格式在不同提案器之间保持一致。

## 11. 使用边界

- AutoResearch 只用于离线策略发现，不在正在进行的真实实验 campaign 中临时改变策略结构。
- 真实 campaign 初始化时绑定明确的 `strategy_version`。
- 反馈模型可以在每轮累计有效反馈后重新拟合；V1 冻结深度基座模型。
- 提案器不得修改评估器、固定标签、划分、主指标或 guard。
- 核心依据实测主指标选最佳候选；领域稳定性、多种子置信区间和 locked-test 准入由评估器或后续验收步骤负责。
- 同一疾病和实验方案使用固定候选池；已测试或已保留候选不得重复推荐。

离线搜索的数据门槛：

- 至少 `max(100, 2 × 默认批量大小)` 条有效历史观测时，可搜索反馈模型、输入特征和融合权重。
- 有完整回顾性标签池且规模至少为模拟获取预算两倍时，可进一步搜索 warm start 和 acquisition 行为。

## 12. 每轮数量与任务配置

任务模板中的默认设置：

```json
{
  "campaign": {
    "num_rounds": 10,
    "batch_size": 50,
    "round_batch_sizes": {},
    "allow_runtime_batch_size_override": true,
    "max_total_candidates": 500
  }
}
```

数量优先级：运行时 `--batch-size` > 当前轮 `round_batch_sizes` > 默认 `batch_size`。实际数量还受剩余预算和候选池限制。

校验示例：

```bash
python scripts/validate_task_config.py \
  --config assets/task_config.template.json \
  --round 1 \
  --remaining-candidates 4684 \
  --valid-feedback 0
```

## 13. 完整性检查与推荐顺序

在 PRISM 测试目录执行：

```bash
shasum -a 256 -c checksums.sha256
```

建议顺序：

1. 运行 `run_smoke.py` 验证依赖和基础反馈评估。
2. 运行 `guard_autoresearch.py` 验证冻结输入。
3. 用通用核心校验 smoke 配置。
4. 运行通用 `loop`，确认提案、评估、比较和记录链路。
5. 把 full 配置中的 proposer 替换为目标模型适配器。
6. 正式离线搜索并按稳定性规则验收。
7. 运行 `freeze`，在真实实验初始化时绑定该版本。
