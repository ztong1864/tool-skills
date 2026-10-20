---
name: experiment-step-generator
description: 这是化学实验流程的一部分，用于基于 constraint-parser 输出的约束 JSON 和参考模板生成编号实验步骤；只在 ATA 场景输出步骤列表，不负责完整实验方案、设备 JSON 或孔位编排。
---

# experiment-step-generator

## 功能

读取 constraint-parser 的输出 JSON 和参考模板，先判断反应类型；若为 ATA，则生成编号实验步骤的 Markdown 列表。

## 强制执行顺序

1. 读取 constraint JSON 的 `source_text`。
2. 用 LLM 判断反应类型。
3. 若为 ATA，参考 `KB/ata_step.md` 和实验方案样式生成编号步骤；给了 `--amounts`/`--rows` 时写选定条件的具体物料和用量。
4. 非 ATA 反应直接报错，提示未支持模板。
5. 输出只保留步骤列表，不附加其它章节。

## 输入输出

- 输入：constraint JSON、`KB/ata_step.md`、`KB/reference_experiment_plan.md`、可选参考目录；可选的投料量 CSV（`--amounts`）和条件编号（`--rows`）。
- 输出：`output/generated_experiment_steps_<timestamp>.md`
- 约束：只输出 Markdown 编号步骤列表。

## 只为选定条件写步骤（可选）

用户只要其中一组或几组条件（例如“只保留第一条”）时，加 `--amounts <投料量 CSV> --rows 1`（多组写 `1,3`，范围写 `2-4`）：
步骤写这几组的具体物料和用量，标为 none 的物料不写。投料量 CSV 是投料计算步骤的输出（列成对出现：`xxx` 和
`xxx_amount`），`--rows` 是它的数据行号（从 1 开始）。不带这两个参数时照旧输出含候选类别的通用步骤。

多组条件在工作站上**同时进行**：每组占一个反应位（fdu-experiment-plan 为每组单独生成方案和反应位），各反应位一起预搅拌、
一起反应，总时长与一组相同。所以多组时输出第一行说明这一点，之后每组前有一行 `### 条件 N`，组内步骤从 1 编号；脚本逐组
生成后合并，不会把各组写成先后进行的一长串步骤。只传用户在投料量确认时选定的组（`--rows`）；用户没有选定时再写全部条件。

## 条件修改

反应条件（预搅拌、温度、时间、转速）只从约束 JSON 的 `source_text` 读取，模板只提供步骤顺序、写法、后处理和用户没写的
条件。用户改了条件（例如“只能室温反应”）时，用同一份约束 JSON 重跑只会得到原来的结果：要先用改过的指令（原指令加上
修改）重新运行约束解析得到新的约束 JSON，再用它运行本 skill。不要手改约束 JSON 或已生成的步骤文件。

## 注意事项

- 不生成完整实验方案，不生成设备 JSON。
- 不绑定孔位、托盘、QR code 或仪器运行字段。
- 参考 md 只用于学习语气和步骤粒度。

## 相关文件

- `scripts/generate_steps.py`
- `KB/ata_step.md`
- `KB/reference_experiment_plan.md`
