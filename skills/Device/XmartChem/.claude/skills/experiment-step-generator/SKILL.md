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
3. 若为 ATA，参考 `KB/ata_step.md` 和实验方案样式生成编号步骤。
4. 非 ATA 反应直接报错，提示未支持模板。
5. 输出只保留步骤列表，不附加其它章节。

## 输入输出

- 输入：constraint JSON、`KB/ata_step.md`、`KB/reference_experiment_plan.md`、可选参考目录。
- 输出：`output/generated_experiment_steps_<timestamp>.md`
- 约束：只输出 Markdown 编号步骤列表。

## 注意事项

- 不生成完整实验方案，不生成设备 JSON。
- 不绑定孔位、托盘、QR code 或仪器运行字段。
- 参考 md 只用于学习语气和步骤粒度。

## 相关文件

- `scripts/generate_steps.py`
- `KB/ata_step.md`
- `KB/reference_experiment_plan.md`
