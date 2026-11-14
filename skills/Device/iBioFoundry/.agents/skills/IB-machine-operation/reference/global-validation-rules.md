# Global Validation Rules

将本文件作为 `IB-machine-operation` 的全局校验规则来源。

这些规则适用于整份脚本生成与最终交付，不属于单一设备、单一容器或单一步骤的局部规则。

## 通用生成禁令

- 禁止创造 reference 中不存在的设备名
- 禁止创造 reference 中不存在的动作名
- 禁止补全未在模板中声明的顶层字段

## 模板一致性禁令

- 禁止根据 example 自行推断 full script 头部结构
- 禁止修改 `runtime/devices/pools/variables` 模板内容
- 禁止替换 reference 中未标明“可修改”的参数

## 输出质量禁令

- 禁止输出“可能可以运行”的脚本，必须标注“已按清单校对/未校对”

## Process 顺序

- 每个容器必须在第一次被设备动作使用之前 `Acquire`，配平板也要 `Acquire`。
- `set ... Status` 必须紧接其对应的 `Acquire` 块。
- 任何设备动作都不得出现在 `Acquire` 与 `set ... Status` 之间。
- 多个 `Acquire` 块、流程中段的 `set`、不带 `where` 的 `Acquire` 这三种写法，
  以 `container-and-status-rules/references/acquire-and-status.md` 的"允许的三种例外"为准；
  不在那三种情形内的，按上面三条校验。

## 控制结构

- `parallel` 的每个 `branch` 的 `// i of n` 必须与实际分支数一致。
- 每个 `Acquire(变量)` 必须有同层的 `Release(变量)`。
- 并行分支里争用同一台设备时必须加设备锁。
- `AddWork` 的 `ProcessName` 不带目录前缀、不带时间戳，`SourceName` 等于 `E_` + `ProcessName`。
- 锁变量只能用 `variables` 固定模板里已声明的那几个，不得新增。

## 适用范围

- 完整脚本结构
- 固定模板复制
- 设备动作模板调用
- 容器与状态规则使用
- 最终输出质量说明
