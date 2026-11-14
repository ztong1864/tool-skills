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
- 输出：`output/generated_experiment_steps_<timestamp>/generated_experiment_steps_<N>.md`，每组推荐条件一份（N 是投料量 CSV 的行号）；不带 `--amounts` 时只有一份 `generated_experiment_steps.md`（含候选类别的通用步骤）。
- 约束：每份文件只有一行 `### 条件 N` 和这组条件的 Markdown 编号步骤列表。

运行：

```
python scripts/generate_steps.py --constraints <约束 JSON> --amounts <投料量 CSV> --steps-output-dir <输出目录>
```

在 LabOntology 中 `--steps-output-dir` 写 mission 的 artifacts 目录下的一个新子目录（例如 `<artifacts 目录>/numbered_steps`），
`--register-all` 会登记这个目录和其中的步骤文件。重跑（修订）时写进另一个新子目录（例如 `numbered_steps_v2`），不要改旧目录
里的文件。

## 每组推荐条件一份步骤

带 `--amounts <投料量 CSV>` 时，投料量 CSV 的每一行（每组推荐条件）各生成一份步骤文件，写这组条件的具体物料和用量，标为
none 的物料不写，组内步骤从 1 编号。投料量 CSV 是投料计算步骤的输出（列成对出现：`xxx` 和 `xxx_amount`）。

用户只要其中一组或几组条件（例如“只保留第一条”）时加 `--rows`（`1`，多组写 `1,3`，范围写 `2-4`；是投料量 CSV 的数据行号，
从 1 开始），只为这几组生成文件。用户没有选定时不加 `--rows`，每组都生成。

各组推荐条件不一定步骤完全相同（例如不加分子筛的组少一项物料），按各组自己的条件写，不要为了和其他组一致而补步骤或删步骤。

多组条件在工作站上**同时进行**：每组占一个反应位，各反应位一起预搅拌、一起反应，总时长与一组相同，不是一组做完再做下一组。
fdu-experiment-plan 把整个目录作为 `--steps-file`，每组用自己的那份步骤写方案。

向用户汇报时按组列出步骤；各组相同的步骤可以只写一次，再说明哪几组在哪一步不同（例如第 2 组不加分子筛）。

## 条件修改

反应条件（预搅拌、温度、时间、转速）只从约束 JSON 的 `source_text` 读取，模板只提供步骤顺序、写法、后处理和用户没写的
条件。用户改了条件（例如“只能室温反应”）时，用同一份约束 JSON 重跑只会得到原来的结果：要先用改过的指令（原指令加上
修改）重新运行约束解析得到新的约束 JSON，再用它运行本 skill。不要手改约束 JSON 或已生成的步骤文件。

## 注意事项

- 不生成完整实验方案，不生成设备 JSON。
- 用户指令里关于流程的要求（创建设备任务、先不启动、暂停确认等）不是实验操作，不写进步骤。
- 不绑定孔位、托盘、QR code 或仪器运行字段。
- 参考 md 只用于学习语气和步骤粒度。

## 相关文件

- `scripts/generate_steps.py`
- `KB/ata_step.md`
- `KB/reference_experiment_plan.md`
