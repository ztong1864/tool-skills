---
name: chemical-amount-calculator
description: 这是化学实验流程的一部分，用于把约束 JSON 和推荐 CSV 换算为带实际投料量的 CSV；使用 KB/chemical_space.csv 作为化学条目库，负责分子量、质量和体积换算，不负责生成推荐或解析自然语言。
---

# chemical-amount-calculator

## 功能

读取实验约束 JSON、推荐 CSV 和化学条目库 `KB/chemical_space.csv`，结合 PubChem 和本地条目中的分子式、SMILES、CAS、密度信息，生成带投料重量与体积的新 CSV。

`KB/chemical_space.csv` 是本 skill 的长期化学条目库，而不是一次性推荐候选空间。默认计算时就使用这个文件；如果用户提供新的化学信息，应先补充或更新该条目库，再进行用量换算。

## 化学条目库

默认条目库：

- `KB/chemical_space.csv`

字段格式：

```csv
section,no,name,cn_name,en_name,abbr,formula,smiles,cas,density_g_ml
```

字段含义：

- `section`：类别，例如 `chiral_amine`、`solvent`、`metal_salt`。
- `no`：序号。
- `name`：推荐使用的主名称。
- `cn_name`：中文名。
- `en_name`：英文名。
- `abbr`：缩写或别名。
- `formula`：分子式或可用于本地计算的式子。
- `smiles`：SMILES。
- `cas`：CAS 号；建议尽量填写，缺失时脚本可能无法建立可靠条目。
- `density_g_ml`：密度，液体体积换算需要时填写。

用户有新的化学信息时：

1. 先检查 `KB/chemical_space.csv` 是否已有同一 `cas`、`name`、`cn_name`、`en_name`、`abbr` 或 `formula`。
2. 如果已有条目，补全缺失字段，不要重复添加。
3. 如果没有条目，追加新行。
4. 新增行应尽量包含 `name`、`cn_name` 或 `en_name`、`cas`，并补充分子式、SMILES 或密度信息。
5. 条目库更新后，再运行用量换算。

## 强制执行顺序

1. 显式传入 `--constraints` 和 `--recommendations-csv`。
2. 默认使用 `KB/chemical_space.csv` 作为化学条目库；只有需要临时测试其它库时才传 `--chemical-space`。
3. 如果用户提供新的化学信息，先更新 `KB/chemical_space.csv`。
4. 解析约束 JSON 中的基准 mmol 和物料信息。
5. 根据 CAS、名称、别名、分子式和 SMILES 查询分子量。
6. 计算质量或体积换算结果。
7. 将结果写入输出 CSV。

## 输入输出

- 输入：constraint-parser JSON。
- 输入：推荐条件 CSV。
- 输入：`KB/chemical_space.csv` 化学条目库；默认自动使用，也可通过 `--chemical-space` 显式指定。
- 输出：`output/chemical_amount_<YYYYMMDD_HHMMSS>.csv`。
- 约束：必须显式传入 `--constraints` 和 `--recommendations-csv`，不自动猜测上游 output 目录。

## 注意事项

- `KB/chemical_space.csv` 是化学条目库，应随项目积累维护。
- 分子量优先用 PubChem，必要时回退到本地条目的分子式计算。
- `none`、`DATA` 和空值不计算，直接留空。
- 已给出质量或体积的物料直接保留原始 `quantity`。
- 液体体积换算需要密度时，应在 `density_g_ml` 中补充密度。
- 不要把推荐条件 CSV 当成化学条目库；推荐 CSV 只提供本轮实验条件组合。

## 相关文件

- `scripts/calculate_amounts.py`
- `KB/chemical_space.csv`
- `KB/pubchem_cache.json`
