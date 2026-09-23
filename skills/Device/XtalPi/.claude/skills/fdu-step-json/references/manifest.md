# 步骤 JSON 说明

## 概述

这是化学实验流程的一部分，用于把结构化实验方案拆成下游单步 skill 可直接读取的 step JSON。

## 流程视图

当前实现会先拆分实验方案，再按步骤类型映射到对应下游 skill。

## 常见输入

- 结构化实验方案 Markdown
- `KB/example_step.md`
- `KB/step_schema.md`

## 常见输出

- `output/generated_step_<timestamp>.json`

## 相关文件

- `SKILL.md`
- `KB/example_step.json`
- `KB/example_step.md`
- `KB/step_schema.md`
