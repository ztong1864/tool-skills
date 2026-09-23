---
name: IB-machine-operation
description: 编写完整 Momentum DSL 实验脚本的总入口技能。用于理解实验需求、协调容器与状态规则、调用设备动作模板、组织 process，并结合固定的 runtime/devices/pools/variables 模板输出完整脚本。
---

# IB-machine-operation

将这个技能作为完整 Momentum DSL 实验脚本的总入口。

最终输出应为可运行的 `.txt` 脚本文件。

## 职责边界

- 本技能负责：理解实验需求、判断涉及的设备与容器、组织 `process`、整合完整脚本、做最终一致性检查。
- [$container-and-status-rules](../container-and-status-rules/SKILL.md) 负责：容器命名、耗材选择、`Acquire` 写法、`Status` 更新规则。
- [$device-operation-library](../device-operation-library/SKILL.md) 负责：设备动作模板、可修改参数、设备家族模板、跨设备 workflow rule。
- [process-flow-planner](../process-flow-planner/SKILL.md) 负责：`process` 的步骤顺序与流程约束。
- [script-assembler](../script-assembler/SKILL.md) 负责：将固定模板与 `process` 组装为完整脚本。

不要在本技能中重复维护设备动作、容器目录或固定模板正文。

## 优先读取顺序

1. 先读 [$container-and-status-rules](../container-and-status-rules/SKILL.md)。
2. 如果用户需求命中已知固定实验类型，读 `reference/nl-to-process-mapping.md`，先确定 `process { ... }` 的核心骨架。
3. 再读 [$device-operation-library](../device-operation-library/SKILL.md)。
4. 按需读 [process-flow-planner](../process-flow-planner/SKILL.md)。
5. 按需读 [script-assembler](../script-assembler/SKILL.md)。
6. 最终检查时读 `reference/global-validation-rules.md`。

## 固定脚本结构

完整脚本结构固定为：

```txt
profile [My System]
{
    runtime (...)  ;
    devices { ... }
    pools { ... }
    variables { ... }
    process [Name] { ... }
}
```

其中：

- `runtime` 直接复制 `../script-assembler/instructions/runtime.md`
- `devices` 直接复制 `../script-assembler/instructions/devices.md`
- `pools` 直接复制 `../script-assembler/instructions/pools.md`
- `variables` 直接复制 `../script-assembler/instructions/variables.md`
- `process` 根据实验需求编写

## 脚本与 process 命名

- 输出脚本文件名必须使用唯一命名：`foundry_<standard_name>_<YYYYMMDD_HHMMSS>.txt`。
- `foundry_` 是固定前缀；`<standard_name>` 使用标准实验名，需转为 ASCII 兼容的小写下划线格式，避免空格、中文和特殊字符；时间后缀使用生成脚本时的本地日期时间，精确到秒。
- `process[...]` 名称必须与输出脚本文件名保持一致，但去掉 `.txt` 后缀。
- 示例：输出文件名为 `foundry_cell_seeding_384well_20260508_153012.txt` 时，脚本内应写 `process [foundry_cell_seeding_384well_20260508_153012]`。

## 工作流程

1. 理解实验目标，列出需要的设备、动作、容器和状态。
2. 如果需求命中 `reference/nl-to-process-mapping.md` 中的固定类型，先按映射确定 `process` 的核心设备步骤顺序。
3. 到 `$container-and-status-rules` 中确定容器、耗材、`Acquire` 和 `Status`。
4. 到 `$device-operation-library` 中读取相关设备模板与 workflow rule。
5. 使用 `process-flow-planner` 组织 `process` 顺序，并将步骤落实成 DSL。
6. 先确定唯一脚本文件名，并让 `process[...]` 使用该文件名去掉 `.txt` 后的内容。
7. 从 `script-assembler/instructions/` 复制固定部分，并整合完整脚本。
8. 输出前按 `reference/global-validation-rules.md` 做一致性核查。

## 固定需求映射

对以下已知需求，优先使用 `reference/nl-to-process-mapping.md` 里的步骤映射来稳定生成结果：

- 单板酶活检测
- 微孔板离心
- 微孔板液体转移
- PCR扩增
- 微孔板振荡培养

映射只约束 `process { ... }` 中的核心步骤顺序与设备组合。

- `process[...]` 名称、输出文件名不作为映射依据。
- 即使历史映射中未显式写出 `Acquire` 或 `set`，实际生成时也要按现行技能补齐，并保持 `Acquire → set → 设备动作`。

## 强规则

1. 不要脑补。
   缺少依据时，不要创造 reference 中不存在的设备名、动作名、参数名或容器名。
2. 找不到就停止。
   如果在 `$device-operation-library` 或相关规则中找不到所需动作，输出缺失项，不要给出“可能能跑”的脚本。
3. 只改可修改字段。
   未明确标注为可修改的内容必须原样保留。
4. 固定部分不改。
   `runtime/devices/pools/variables` 必须直接复制，不要自行设计。
5. 盖子管理使用统一规则。
   `Acquire` 默认值以 `$container-and-status-rules/references/lid-management.md` 为准；设备动作中的盖子写法以 `$device-operation-library` 的具体模板或 workflow rule 为准。
6. `Acquire` 与 `set` 顺序固定。
   `set ... Status` 必须紧接 `Acquire`，所有设备动作必须位于 `set` 之后。
7. 设备动作只来自模板库。
   只从 `$device-operation-library` 的模板和 workflow rule 组装 device action。
8. 容器命名以容器目录为准。
   如设备模板或 workflow rule 与 `container-and-status-rules/references/container-catalog.md` 冲突，以容器目录为准，并把冲突视为待修复 reference 缺陷。

## 最终检查

- [ ] 脚本结构正确
- [ ] 固定部分与 `script-assembler/instructions/` 完全一致
- [ ] 输出文件名符合 `foundry_<standard_name>_<YYYYMMDD_HHMMSS>.txt`
- [ ] `process[...]` 名称等于输出文件名去掉 `.txt`
- [ ] 设备动作来自 `$device-operation-library`
- [ ] 未使用 reference 之外的设备 / 动作 / 容器
- [ ] 未修改禁止修改的参数
- [ ] `process` 使用 `Acquire → set → 设备动作` 顺序
- [ ] `process` 顺序符合流程约束
