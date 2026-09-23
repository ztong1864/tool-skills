# 实验总控参考

## 定位

这份文件只做参考说明，用来描述各下游 skill 的职责边界和整体流程关系。
具体的流程控制、确认节点、失败重试和提交规则，以 `SKILL.md` 为准。
运行时如果上下文被稀释，可以重新读取这里和 `SKILL.md` 来恢复规则。

## 职责划分

### 上游解析与推荐
- `constraint-parser`：把用户输入解析成结构化约束数据。
- `literature-experiment-recommender`：基于约束和候选空间生成 ATA 推荐条件。
- `chemical-amount-calculator`：把推荐条件换算成实际投料用量。

### 步骤与方案
- `experiment-step-generator`：把约束和推荐结果整理成编号实验步骤。
- `fdu-experiment-plan`：把步骤和用量整理成中文实验方案文件。

### 协议与执行
- `fdu-multi-step-json`：把一个或多个方案整理成总 step JSON。
- `fdu-resource-verify`：对 step JSON 做资源校验和补全。
- `fdu-unit-orchestration-json`：把验证后的步骤编排成设备协议。
- `fdu-device-run`：把协议提交给设备侧执行。

## 流程关系

流程中的停顿时机是：候选推荐后、化学品用量后、实验步骤后、实验方案文件后、任务提交前。其余节点默认继续，不额外停顿。
这些停顿点对应的确认内容分别是：推荐表格、用量表格、步骤列表、方案文件摘要、待提交任务摘要。

### 方案生成链路
用户输入实验目标或约束条件后，通常按下面顺序推进：

1. `constraint-parser`
2. `literature-experiment-recommender`
3. `chemical-amount-calculator`
4. `experiment-step-generator`
5. `fdu-experiment-plan`

### 方案执行链路
当用户已经有方案文件，或者要继续到设备协议时，通常按下面顺序推进：

1. `fdu-multi-step-json`
2. `fdu-resource-verify`
3. `fdu-unit-orchestration-json`
4. `fdu-device-run`

## 数据边界

- `constraint-parser` 的输出只作为内部流转数据。
- `chemical-amount-calculator` 只负责用量换算，不负责推荐。
- `experiment-step-generator` 只负责步骤组织，不负责设备协议。
- `fdu-experiment-plan` 只负责方案文档，不负责设备提交。
- `fdu-multi-step-json`、`fdu-resource-verify`、`fdu-unit-orchestration-json` 只负责协议前置流程，不直接执行实验。

## 失败处理

- 如果某个下游 skill 失败，先告诉用户失败发生在什么环节。
- 如果用户提供了修正反馈，再从对应节点重试。
- 如果用户没有提供足够信息，先补足信息再继续。

## 相关文件

- `../SKILL.md`
- `../constraint-parser/SKILL.md`
- `../literature-experiment-recommender/SKILL.md`
- `../chemical-amount-calculator/SKILL.md`
- `../experiment-step-generator/SKILL.md`
- `../fdu-experiment-plan/SKILL.md`
- `../fdu-multi-step-json/SKILL.md`
- `../fdu-resource-verify/SKILL.md`
- `../fdu-unit-orchestration-json/SKILL.md`
- `../fdu-device-run/SKILL.md`
