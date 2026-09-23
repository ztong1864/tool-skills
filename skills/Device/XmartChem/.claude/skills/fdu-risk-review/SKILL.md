---
name: fdu-risk-review
description: FDU 实验规划阶段风险审查 skill。用于候选条件推荐、投料量计算、编号实验步骤生成之后、对应用户确认之前，检查已生成规划产物的反应可行性、安全风险、设备能力和动作边界；本 skill 只负责审查和给出风险结论，不生成推荐、不计算用量、不编写实验步骤、不生成协议 JSON，也不提交设备任务。
---

# fdu-risk-review

本 skill 是 FDU 实验自动化流程中的规划阶段风险守卫。

它由 ontology 规则 `rule:risk-review-after-planning-output` 在以下规划产物生成后、对应用户确认前触发：

- `task-step:recommend-experiment-conditions`
- `task-step:calculate-reagent-amounts`
- `task-step:generate-numbered-steps`

## 职责范围

在 Agent 将当前规划产物展示给用户确认之前，审查该产物是否可以接受。

需要检查：

- 反应可行性
- 安全风险
- 设备能力
- 动作边界
- 当前步骤是否需要停止并要求用户调整或确认

不负责：

- 生成推荐条件
- 计算投料量
- 编写编号实验步骤
- 创建或修改 step JSON
- 生成协议 JSON
- 提交或启动设备任务

## 输入

根据当前阶段读取已经存在的上下文和产物：

- 用户实验请求
- `artifact:constraint-json`
- `artifact:reaction-space-table`
- `artifact:recommendation-table`
- `artifact:amount-table`
- 草稿编号步骤
- 来自 `fdu-ontology` 的设备动作、资源约束或仪器能力信息

如果关键上下文缺失，不要猜测，返回 `needs_human_review`。

## 风险知识库

审查前必须读取：

- `references/risk_knowledge_base.md`

该文件包含当前可维护的风险依据，包括：

- verdict 判定规则
- 各阶段必需上下文
- FDU 设备能力边界
- skill 职责边界
- 安全风险信号
- 用量和单位风险信号

如果知识库没有覆盖某个风险，不要自行补充成确定结论；应返回 `needs_human_review` 并说明缺少什么依据。

## 审查流程

1. 判断当前处于哪个 `TaskStep`。
2. 读取 `references/risk_knowledge_base.md`。
3. 读取该步骤已经生成的规划产物和可用上游上下文。
4. 检查可行性：化学条件、物料类别、用量、温度、时间或步骤顺序是否自洽。
5. 检查安全性：是否存在明显危险条件、不兼容物料、失控加热、压力、挥发性或不受支持的处理方式。
6. 检查设备能力：当前计划是否符合已知 FDU 设备动作、资源或仪器能力边界。
7. 检查动作边界：当前下游 skill 是否被要求执行超出其职责范围的工作。
8. 输出简短结论；如果存在阻断问题，说明原因。

## 风险提醒流程

审查过程中一旦发现风险，不要等到后续步骤再提醒。

处理顺序：

1. 判断风险等级。
2. 如果风险可能通过补充信息判断，立即返回 `needs_human_review`。
3. 如果风险已经明显越过安全边界、设备能力边界或 skill 职责边界，立即返回 `block`。
4. 在 `findings` 中写清楚风险来源、涉及的物料/条件/动作、为什么不能继续。
5. 在 `required_action` 中写清楚用户下一步应该做什么，例如补充沸点/危险性信息、确认人工处理、修改用量、替换条件、删除不支持动作或停止流程。

提醒内容必须直接、具体、可执行。不要只写“存在风险”。

当返回 `needs_human_review` 或 `block` 时，Agent 必须停止进入对应用户确认点和后续流程，不得将该规划产物作为已通过审查的结果继续使用。

## 输出格式

返回简洁的审查结果：

```text
verdict: pass | needs_human_review | block
stage: <当前 TaskStep id 或简短阶段名>
checked: feasibility, safety, device_capability, action_boundary
findings:
- <具体问题，或 none>
required_action:
- <continue | ask_user | revise_input | stop>
```

判定规则：

- 使用 `pass`：当前上下文中没有发现阻断问题。
- 使用 `needs_human_review`：风险无法通过当前上下文判断，需要用户或实验人员确认。
- 使用 `block`：继续推进会明显越过安全边界或设备能力边界。
