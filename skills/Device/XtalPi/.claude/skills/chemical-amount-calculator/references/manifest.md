# 实验用量换算说明

## 概述

这是化学实验流程的一部分，用于把推荐条件换算成带实际投料量的 CSV。

## 流程视图

当前实现会结合约束 JSON、推荐 CSV 和化学空间信息，逐项换算质量或体积。

## 常见输入

- constraint-parser JSON
- 推荐 CSV
- `KB/chemical_space.csv`

## 常见输出

- `chemical_amount_<YYYYMMDD_HHMMSS>.csv`

## 相关文件

- `SKILL.md`
- `scripts/calculate_amounts.py`
- `KB/chemical_space.csv`
