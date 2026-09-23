# 实验步骤生成说明

## 概述

这是化学实验流程的一部分，用于基于约束 JSON 生成编号实验步骤。

## 流程视图

当前实现先识别反应类型，再决定是否生成 ATA 步骤。

## 常见输入

- constraint-parser JSON
- `KB/ata_step.md`
- `KB/reference_experiment_plan.md`

## 常见输出

- `output/generated_experiment_steps_<timestamp>.md`

## 相关文件

- `SKILL.md`
- `scripts/generate_steps.py`
- `KB/ata_step.md`
