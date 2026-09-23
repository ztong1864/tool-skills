# 实验方案生成说明

## 概述

这是化学实验流程的一部分，用于根据实验步骤 Markdown 和用量推荐 CSV 生成中文实验方案。

## 流程视图

当前实现会按推荐条目逐条生成独立 Markdown 文件，并写入带时间戳的输出目录。

## 常见输入

- 实验步骤参考 Markdown
- 带用量推荐 CSV
- `KB/example_plan.md` 示例模板

## 常见输出

- `output/experiment_plan_<timestamp>/experiment_plan_<tray>_<index>.md`

## 相关文件

- `SKILL.md`
- `KB/plan_schema.md`
- `KB/example_plan.md`
- `scripts/generate_plan.py`
