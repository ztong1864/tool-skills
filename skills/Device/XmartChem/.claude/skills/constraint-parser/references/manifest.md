# 约束解析说明

## 概览

这是化学实验流程的一部分，用于把自然语言实验指令解析为结构化约束 JSON，并把用户上传的候选空间表格转换为 CSV。

## 流程视图

当前实现由 LLM 完成实验指令语义解析，再做基础 schema 校验后输出 JSON；同时读取用户提供的 `.xlsx`、`.xls` 或 `.csv` 表格，并输出规范 CSV。表格默认没有表头，第一行会作为数据保留。

## 常见输入

- 实验指令文本
- 用户上传的候选空间表格文件：`.xlsx`、`.xls` 或 `.csv`
- `KB/constraint_schema.md`
- `KB/example_constraints.json`

## 常见输出

- `output/parsed_constraints_<timestamp>.json`
- `output/<table_stem>_<timestamp>.csv`

## 相关文件

- `SKILL.md`
- `scripts/parse_constraints.py`
- `KB/constraint_schema.md`
