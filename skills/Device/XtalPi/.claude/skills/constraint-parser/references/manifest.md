# 约束解析说明

## 概述

这是化学实验流程的一部分，用于把自然语言实验指令解析为结构化约束 JSON。

## 流程视图

当前实现由 LLM 完成语义解析，再做基础 schema 校验后输出 JSON。

## 常见输入

- 实验指令文本
- `KB/constraint_schema.md`
- `KB/example_constraints.json`

## 常见输出

- `output/parsed_constraints_<timestamp>.json`

## 相关文件

- `SKILL.md`
- `scripts/parse_constraints.py`
- `KB/constraint_schema.md`
