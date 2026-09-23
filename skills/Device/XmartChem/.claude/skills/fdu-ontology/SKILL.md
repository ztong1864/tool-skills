---
name: fdu-ontology
description: 这是 FDU 实验自动化任务本体 skill。只要任务涉及复旦装置、化学实验流程、实验方案、step JSON、资源校验、协议编排、设备提交、设备 API、实验数据或材料资源，都必须先使用本 skill 查询任务本体，再决定下一步调用哪个执行型 skill。本 skill 负责指导 Agent 判断当前阶段、输入输出数据、确认点、安全规则和必要设备语义，不直接生成投料量、协议 JSON 或提交设备任务。
---

# fdu-ontology

`fdu-ontology` 是面向 Agent 执行决策的 FDU 实验任务本体。它不是完整实验数据库，也不是单纯的 skill 顺序表。

它的核心目标是让 Agent 在每一步回答清楚：

- 当前用户请求属于哪个 `Process`
- 当前应进入哪个 `TaskStep`
- 这个步骤应调用哪个 skill，或是否只是检查/确认/分支
- 需要哪些 `DataArtifact`
- 会产生哪些 `DataArtifact`
- 是否必须经过 `Checkpoint`
- 哪些 `ExecutionRule` 约束当前动作
- 进入设备阶段时，需要理解哪些 `DeviceAction` 和 `Resource`
- 任务、数据、资源和设备动作涉及哪些 `Condition`、`Property` 和 `Instrument`

## 默认查询顺序

所有 FDU 相关任务先按下面顺序查图谱：

1. 查 `Process`，判断任务场景。
2. 查该 `Process` 对应的 `AgentFlow`。
3. 查当前或第一个 `TaskStep`。
4. 查该 `TaskStep` 的输入 `DataArtifact` 是否已经存在或需要生成。
5. 查该 `TaskStep` 的输出 `DataArtifact`，明确下一步数据形态。
6. 查是否有 `Checkpoint`。如果有，必须停下来展示对应数据并等待用户确认。
7. 查相关 `ExecutionRule`。规则优先级高于流程推进。
8. 只有进入 step JSON、资源校验、协议编排、设备提交阶段时，才展开 `DeviceAction`、`Resource` 和 `Instrument`。
9. 当需要解释步骤前置要求、字段含义或资源/仪器能力时，再查 `Condition` 和 `Property`。

## 核心实体

### Process

任务场景入口，例如：

- FDU 实验目标到设备任务流程
- 资源校验与回填
- 设备协议编排
- 设备任务创建

`Process` 用于判断用户当前请求属于哪类工作，不代表一个具体设备步骤。

### AgentFlow

一条 Agent 可执行流程。主流程为：

`agent-flow:fdu-experiment-to-device-task`

它描述从用户实验目标到设备任务创建的完整路线。

### TaskStep

Agent 可以执行的一步。它通常对应一个 skill 调用，也可以是检查、确认或分支判断。

关键字段：

- `name`
- `step_kind`: `skill_call` / `checkpoint` / `decision` / `inspection`
- `skill_name`
- `input_artifact_ids`
- `output_artifact_ids`
- `requires_user_confirmation_before`
- `requires_user_confirmation_after`
- `failure_policy`
- `agent_should_check`

节点名称应表达动作语义，例如：

- `task-step:parse-experiment-request`
- `task-step:recommend-experiment-conditions`
- `task-step:verify-and-fill-resources`
- `task-step:create-device-task`

### DataArtifact

流程中流转的数据产物。Agent 必须理解它是什么、谁生产、谁消费、是否展示给用户。

关键字段：

- `format`: `json` / `csv` / `markdown` / `directory` / `text`
- `producer_step_id`
- `consumer_step_ids`
- `user_visible`
- `must_confirm`
- `path_hint`
- `required_fields` 或 `required_columns`
- `agent_meaning`

示例：

- `artifact:constraint-json`
- `artifact:recommendation-table`
- `artifact:amount-table`
- `artifact:merged-step-json`
- `artifact:device-protocol-json`

### Checkpoint

必须暂停并让用户确认的节点。

主流程默认包含 4 个确认点：

- 推荐条件确认
- 投料量确认
- 编号实验步骤确认
- 设备任务创建确认

命中 `Checkpoint` 时，Agent 必须展示 `shown_artifact_ids` 指向的数据摘要或路径，然后等待用户明确确认。

### ExecutionRule

流程约束和安全规则。规则优先级高于步骤推进。

关键规则：

- 下游 skill 失败时立即停止并报告，不继续后续步骤。
- `constraint-json` 是内部流转数据，默认不展示给用户。
- 用户可见且 `must_confirm=true` 的数据产物，必须展示并确认后再继续。
- 未经用户明确确认，不得调用 `fdu-device-run` 创建设备任务。
- 只有用户明确要求启动执行时，才允许设备启动参数。
- 资源快照和资源校验结果是设备资源判断的事实来源，不得编造资源。

### Resource

材料、试剂、样品、耗材、孔位、设备资源等。普通流程不强制展开；资源校验和设备协议阶段需要读取。

### Condition

实验或执行步骤必须满足的条件。它不是普通自然语言说明，而是 Agent 推进流程前需要检查的前置要求。

典型条件：

- 推荐表已确认
- 投料量已确认
- 资源校验通过
- 仅包含支持的设备动作
- 设备任务创建已被用户确认

### Property

用于解释资源、条件、设备动作或仪器的关键属性。

典型属性：

- `layout_code`
- `unit_column` / `unit_row`
- `substance`
- `add_weight`
- `add_volume`
- `temperature`
- `reaction_duration`
- `resource_availability`

### Instrument

表示复旦装置中的仪器或设备模块。它用于说明某个 `DeviceAction` 由哪个设备模块支持或使用。

典型仪器：

- FDU automation platform
- FDU solid dispenser
- FDU liquid handler
- FDU magnetic stirrer
- FDU filter module
- FDU high-filter module

### DeviceAction

设备层可执行动作类型。只在 step JSON、资源校验、协议编排和设备提交阶段展开。

当前核心动作：

- `device-action:add-solid`
- `device-action:add-liquid`
- `device-action:reaction-control`
- `device-action:filter`
- `device-action:high-filter`

`DeviceAction` 描述 step JSON 中真实设备动作需要哪些字段、资源和下游单步生成 skill。

## 主执行链路

主流程以 `experiment-skills-ctrl` 的顺序为准，但由本体表达输入输出和确认点：

1. `constraint-parser`: 解析用户实验目标和候选空间，产出 `artifact:constraint-json`。
2. `literature-experiment-recommender`: 生成候选推荐，产出 `artifact:recommendation-table`。
3. `checkpoint:review-recommendations`: 展示并确认推荐表。
4. `chemical-amount-calculator`: 计算投料量，产出 `artifact:amount-table`。
5. `checkpoint:review-amounts`: 展示并确认投料量。
6. `experiment-step-generator`: 生成编号实验步骤，产出 `artifact:numbered-experiment-steps`。
7. `checkpoint:review-numbered-steps`: 展示并确认实验步骤。
8. `fdu-experiment-plan`: 生成中文实验方案，产出 `artifact:experiment-plan-md`。
9. `fdu-multi-step-json`: 读取一个或多个方案 Markdown，内部调用 `fdu-step-json`，产出 `artifact:merged-step-json`。
10. `fdu-resource-verify`: 刷新资源快照、校验并回填资源，产出 `artifact:resource-snapshot`、`artifact:verified-step-json` 和资源校验报告。
11. `fdu-unit-orchestration-json`: 编排设备协议，产出 `artifact:device-protocol-json`。
12. `checkpoint:approve-device-task-creation`: 展示待提交任务摘要并请求确认。
13. `fdu-device-run`: 创建设备任务，产出 `artifact:device-submit-result`。
14. 可选 `fdu-execution-monitoring`: 在设备任务已创建后只读监控任务状态、通知、故障和告警，产出 `artifact:device-monitor-result`。

## 与执行型 skill 的边界

本 skill 只负责查图谱和维护语义，不直接执行下游任务。

- `constraint-parser`: 解析自然语言约束。
- `fdu-risk-review`: 在推荐、用量和编号步骤生成后、对应用户确认前，审查规划产物的反应可行性、安全风险、设备能力和动作边界。
- `literature-experiment-recommender`: 生成候选条件。
- `chemical-amount-calculator`: 换算投料量。
- `experiment-step-generator`: 生成编号实验步骤。
- `fdu-experiment-plan`: 生成中文方案。
- `fdu-step-json`: 将单个方案拆成 step JSON；主流程通常由 `fdu-multi-step-json` 内部调用。
- `fdu-multi-step-json`: 从一个或多个方案 Markdown 生成合并后的 step JSON。
- `fdu-resource-verify`: 刷新资源快照、校验资源、回填资源。
- `fdu-unit-orchestration-json`: 生成设备协议 JSON。
- `fdu-device-run`: 提交设备任务；默认只创建任务，启动执行必须单独确认。
- `fdu-execution-monitoring`: 设备任务创建后的可选只读监控；可读取状态并推送异常提醒，不得启动、暂停、取消、恢复、重试、跳过、提交或修改设备任务。

## CLI

统一入口：

```bash
python .agents/skills/fdu-ontology/scripts/graph_cli.py <command> [options]
```

常用查询：

```bash
python .agents/skills/fdu-ontology/scripts/graph_cli.py entity-list --type Process --text FDU
python .agents/skills/fdu-ontology/scripts/graph_cli.py entity-get --type AgentFlow --id agent-flow:fdu-experiment-to-device-task
python .agents/skills/fdu-ontology/scripts/graph_cli.py entity-list --type TaskStep
python .agents/skills/fdu-ontology/scripts/graph_cli.py entity-list --type DataArtifact --text amount
python .agents/skills/fdu-ontology/scripts/graph_cli.py relation-list --type nextStep
```
