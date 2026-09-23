# BO 优化说明

## 概述

这是化学实验流程的一部分，用于在文献抽取和描述符构建完成后，根据 BO 表生成下一轮实验建议。

## 流程视图

当前实现会先读取 `chem-info-extractor` 的发布结果，再调用 BO 优化器输出下一轮候选。

## 常见输入

- BO 表 CSV
- 描述符目录
- `manual_conditions_round0.csv`

## 常见输出

- 下一轮实验建议 CSV
- 优化结果工作目录

## 相关文件

- `SKILL.md`
- `scripts/bayesian_optimization/condition_opt/run_bo_next_round.py`
- `scripts/bayesian_optimization/condition_opt/utils.py`
