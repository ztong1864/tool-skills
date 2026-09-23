# 实验用量换算说明

## 概览

这是化学实验流程的一部分，用于把推荐条件换算成带实际投料量的 CSV。

## 化学条目库

`KB/chemical_space.csv` 是本 skill 的化学条目库。它用于按名称、中文名、英文名、缩写、分子式、SMILES 或 CAS 匹配化学品，并为分子量和体积换算提供本地信息。

如果用户有新的化学信息，应先补充或更新 `KB/chemical_space.csv`，再运行用量换算。

## 常见输入

- constraint-parser JSON
- 推荐 CSV
- `KB/chemical_space.csv`

## 常见输出

- `output/chemical_amount_<YYYYMMDD_HHMMSS>.csv`

## 相关文件

- `SKILL.md`
- `scripts/calculate_amounts.py`
- `KB/chemical_space.csv`
- `KB/pubchem_cache.json`
