---
name: oasis-sub-workflow
description: 查询 Oasis 某个子工作流或步骤节点的详细参数。当用户已经知道 subWorkflowId，并且需要看“这个步骤的参数、字段、执行配置、节点细节”时调用；如果用户还在找可用流程列表，应该先用工作流列表技能，而不是直接用它。
when: 当目标是读取某个已知子工作流的参数详情时调用；前置通常是已经选定了具体流程或步骤。
---
## 直接调用（推荐）

```bash
python skills/oasis-sub-workflow/scripts/call.py --id <subWorkflowId>

# 只输出 data 字段
python skills/oasis-sub-workflow/scripts/call.py --id <subWorkflowId> --only-data

# 输出完整 JSON
python skills/oasis-sub-workflow/scripts/call.py --id <subWorkflowId> --json-output
```

通常只需要传递本技能自己的业务参数，例如 `--id`。脚本默认会直接访问 API；只有在明确需要改回“通过 SSH 在远端执行 curl”时，才追加 `--use-ssh`。如还需要切换 SSH 主机、账号、密码、端口或超时时间，再追加：

```bash
--ssh-host <IP> --ssh-user <用户名> --ssh-password <密码> --ssh-port <端口> --ssh-timeout <秒>
```

## 与结构化流程文档配合使用

如果目标不是单纯查看原始返回，而是要理解或编辑某个工作流程，先配合阅读：

- `../oasis-ontology/references/workflow-docs/`
- `../oasis-ontology/references/Oasis-结构化MD实体规范.md`

使用方式：

1. 先在 `Oasis-实验流程文档` 中找到对应子工作流的结构化 MD，理解步骤语义、设备关系、物料需求和数据产物
2. 再回到本技能返回的原始 JSON，定位真正要修改的 `Editable` 参数
3. 如果要保存修改，保持原始 JSON 结构不变，交给 `oasis-order-progess --parameters-file`

这两层信息的分工是：

- 结构化 MD：帮助理解流程和步骤
- `oasis-sub-workflow` 原始返回：提供可编辑的真实参数

## 别名提醒

- 这里命令行参数名叫 `--id`
- 这个 `id` 实际上就是 `oasis-workflow-category-label` 技能返回的 `subWorkflowId`
- 如果后续进入 `oasis-order-progess`，请求体里的 `workflowId` 要填的也是这个 ID

## 返回说明

`data` 为对象，key 是步骤 ID，value 是步骤参数列表：

```json
{
  "<stepId>": [{"m": 0, "n": 0, "name": "调度等待", "parameterList": [...]}]
}
```

- `m` -> 并行组序号（泳道）
- `n` -> 步骤顺序
- `parameterList[].type` -> `"Editable"` 可修改，`"Hidden"` 不可修改

## 编辑工作流程时的硬约束

- 只修改 `parameterList` 中 `type` 为 `"Editable"` 的参数
- 不删除 `stepId`
- 不删除步骤数组
- 不删除 `parameterList`
- 不改写顶层对象结构
- 不把结构化 MD 里的解释性字段反写回 Oasis `parameters`

结构化 MD 是帮助理解和规划修改的参考，不是可以直接上传回 Oasis 的请求体。

## 返回字段怎么理解

`oasis-sub-workflow` 返回的不是一段普通文本，而是一份“步骤配置树”。生成实验方案时，建议按下面层级理解：

### 第 1 层：`data`

- `data` 是一个对象
- 每个 key 都是一个 `stepId`
- 每个 `stepId` 对应一个步骤数组

也就是说，最外层不是按顺序编号，而是按“步骤 ID -> 步骤内容”组织。

### 第 2 层：步骤对象

每个步骤对象通常长这样：

```json
{
  "m": 0,
  "n": 3,
  "name": "移液站-移液",
  "parameterList": [...]
}
```

这些字段建议这样理解：

- `stepId`
  - 顶层对象的 key
  - 是这一步在 Oasis 里的唯一标识
  - 保存 `parameters` 时要保留，不要丢
- `m`
  - 并行组序号，也就是第几条泳道 / 第几条并行链路
- `n`
  - 该泳道里的执行顺序
- `name`
  - 平台动作名或设备动作名
  - 常见如：`调度-等待`、`移液站-移液`、`高内涵仪-成像`
  - 这是平台名称，不等于最终给用户的实验语言，需要再翻译
- `parameterList`
  - 这一步关联的参数列表
  - 其中既可能有可编辑参数，也可能有内部固定参数

### 第 3 层：`parameterList`

每个参数对象通常包含这些字段：

```json
{
  "Type": "Editable",
  "Key": "protocol",
  "Value": "DemoAddMedcineToCellPlate",
  "DisplayStepName": "移液",
  "DisplayStepDevTypeName": "移液站A",
  "DisplayParaName": "移液协议",
  "DisplayType": "Input",
  "DisplayValidate": "string"
}
```

建议这样理解：

- `Type` / `type`
  - 参数类型
  - `"Editable"` 表示允许修改
  - `"Hidden"` 表示内部参数，通常不改
- `Key` / `key`
  - 参数关键字
  - 常见如 `protocol`、`MethodName`、`DelayTime`
- `Value` / `value`
  - 当前参数值
  - 例如等待时间、协议名、成像协议路径
- `DisplayStepIndex`
  - 这个参数在人机界面里的步骤显示顺序
  - 对方案生成不是主排序依据，真正流程顺序优先看 `m` 和 `n`
- `DisplayStepName`
  - 给界面展示的步骤名称
  - 比 `name` 更偏向用户可见标签
- `DisplayStepDevTypeName`
  - 设备类型名称
  - 常见如 `移液站A`、`成像`
  - 对翻译实验方案很有帮助，可以据此判断是加药、移液还是成像
- `DisplayParaName`
  - 参数的人类可读名称
  - 常见如 `移液协议`、`成像协议`
  - 这是生成实验方案时非常重要的字段
- `DisplayParaUnit`
  - 参数单位
  - 若不为空，可以帮助判断时间、体积、浓度等实验含义
- `DisplayType`
  - UI 输入类型
  - 常见如 `Input`
  - 对实验语义帮助较小，但能判断参数是自由输入还是选项型
- `DisplayValidate`
  - 校验规则
  - 常见如 `string`
  - 可辅助判断参数值的格式
- `DisplayOptionLabels` / `DisplayOptionValues` / `DisplayOptionDefaultValue`
  - 枚举型选项参数的候选值
  - 如果为空，通常表示自由输入
- `DisplayDescription`
  - 参数说明
  - 如果有内容，优先用它辅助翻译实验方案

## 方案生成时优先看哪些字段

如果目标是“把子工作流翻译成实验方案”，优先级建议如下：

1. 先看 `m` 和 `n`
   - 先还原流程结构
2. 再看 `name`
   - 判断这一步是等待、移液、成像还是其它设备动作
3. 再看 `DisplayStepDevTypeName`
   - 判断设备类别
4. 再看 `DisplayParaName` + `Key` + `Value`
   - 判断这一步具体执行哪个协议、哪个参数真正决定实验动作
5. 最后看 `DisplayDescription`、`DisplayOption*`
   - 补充细节

## 生成实验方案时不要这样用

- 不要只看 `name` 就下结论
- 不要只看 `DisplayStepIndex` 就判断真实执行顺序
- 不要忽略顶层 `stepId`
- 不要把所有 `Hidden` 参数都当成完全没意义
  - 例如 `DelayTime` 虽然不可编辑，但它仍然说明这一步在等待
- 不要把 `protocol` 当成普通字符串
  - 它往往就是决定“这一步到底在搬板、加药还是成像”的核心字段

## m / n 的正确理解

生成实验方案时，不能只看 `name`，还必须结合 `m` 和 `n` 理解流程结构：

- `m` 表示并行组序号，也就是“第几条泳道 / 第几条并行执行链”
- `n` 表示该泳道内部的步骤顺序
- 同一个 `m` 下，按 `n` 从小到大读取，才能还原这一条泳道上的真实执行顺序
- 不同 `m` 之间通常表示不同泳道、不同板位链路或不同设备链路，不能简单拼成一条线性单链流程

推荐理解方式：

- 先按 `m` 分组
- 再在每个 `m` 组内按 `n` 排序
- 最后再根据 `name` 和 `parameterList` 判断这一步在实验上的意义

不要犯下面这些错误：

- 把所有 step 只按 `n` 排序后混成一条总流程
- 忽略 `m`，导致并行泳道被错误串联
- 只看步骤名字，不看它属于哪条泳道
- 把 `调度-等待` 机械理解成实验核心步骤，而不结合上下文判断它是在给哪个动作留时间

一个最小示例：

```json
[
  {"m": 0, "n": 0, "name": "调度-等待"},
  {"m": 0, "n": 1, "name": "移液站-移液"},
  {"m": 1, "n": 0, "name": "调度-等待"},
  {"m": 1, "n": 1, "name": "高内涵仪-成像"}
]
```

正确理解不是 4 个步骤首尾相接，而是：

- 泳道 `m=0`：等待 -> 移液
- 泳道 `m=1`：等待 -> 成像

后续生成实验方案时，应把它解释成“存在两条设备/板位链路”，而不是单一串行 SOP。

## 可编辑参数识别规则

`oasis-sub-workflow --only-data` 返回的 `data` 是后续 `oasis-order-progess` 的 `parameters` 来源。如果用户要调整实验流程参数，先在这里定位可改项，再把修改后的完整 JSON 对象交给 `oasis-order-progess --parameters-file` 保存。

- 只修改 `parameterList` 中 `type` 为 `"Editable"` 的参数；这些参数通常可以改 `value` 字段。
- 不要修改 `type` 为 `"Hidden"` 的参数，也不要删除原有字段。
- 定位参数时优先看 `key`、`displayParaName`、`displayStepName`、`name` 等字段，不要只凭数组顺序判断。
- 修改后必须保留原始结构：顶层仍然是以 `stepId` 为 key 的对象，value 仍然是步骤数组，每个步骤内保留原有 `parameterList`。
- 文档和返回示例通常使用小写 `type`；如果实际返回中出现大小写差异，应按字段语义识别，但写回时不要随意改字段名。

