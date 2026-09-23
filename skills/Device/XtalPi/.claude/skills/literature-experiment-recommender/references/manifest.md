# 文献实验推荐说明

## 概述

这是化学实验流程的一部分，用于从约束 JSON、文献和候选空间生成 ATA 推荐实验条件 CSV。

## 流程视图

当前实现会先读约束 JSON，再结合文献和化学空间筛选候选并写出 10 条推荐。

## 常见输入

- constraint-parser JSON
- 文献 PDF 目录
- `KB/chemical_space.csv`
- `KB/output_format_example.csv`

## 常见输出

- `output/ata_literature_top10_recommendations_20260427.csv`

## 相关文件

- `SKILL.md`
- `KB/output_format_example.csv`
- `KB/chemical_space.csv`
