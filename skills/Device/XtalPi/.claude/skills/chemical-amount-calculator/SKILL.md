---
name: chemical-amount-calculator
description: 这是化学实验流程的一部分，用于把约束 JSON 和推荐 CSV 换算为带实际投料量的 CSV；只负责分子量、质量和体积换算，不负责生成推荐或解析自然语言。
---

# chemical-amount-calculator

## 功能

读取实验约束 JSON、推荐 CSV 和 `chemical_space.csv`，结合 PubChem 和 KB 分子式/密度信息，生成带投料重量与体积的新 CSV。

## 强制执行顺序

1. 显式传入 `--constraints`、`--recommendations-csv`，必要时再传 `--chemical-space`。
2. 先解析约束 JSON 中的基准 mmol 和物料信息。
3. 再根据 CAS No.、名称和分子式顺序查询分子量。
4. 计算质量或体积换算结果。
5. 将结果写入输出 CSV。

## 输入输出

- 输入：constraint-parser JSON、推荐 CSV、`KB/chemical_space.csv`。
- 输出：`chemical_amount_<YYYYMMDD_HHMMSS>.csv`。
- 约束：必须显式传入文件路径，不自动猜测上游 output 目录。

## 注意事项

- 分子量优先用 PubChem，必要时回退到 KB 分子式本地计算。
- `none`、`DATA` 和空值不计算，直接留空。
- 已给出质量或体积的物料直接保留原始 `quantity`。

## 相关文件

- `scripts/calculate_amounts.py`
- `KB/chemical_space.csv`
