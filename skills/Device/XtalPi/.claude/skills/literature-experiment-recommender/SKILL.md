---
name: literature-experiment-recommender
description: 这是化学实验流程的一部分，用于从约束 JSON、文献 PDF 和候选化学空间推导 ATA 推荐实验条件 CSV；只负责生成 10 条推荐数据，不负责解析自然语言约束或换算实际投料量。
---

# literature-experiment-recommender

## 功能

读取 constraint-parser 的 JSON、文献 PDF 和候选化学空间，生成 10 条 ATA 推荐实验条件 CSV。列名由约束 JSON 的 `items` 信息推导。

## 强制执行顺序

1. 先读取主输入 JSON，理解 `source_text`、`items`、试剂类别和约束。
2. 再参考文献 PDF 和输出格式示例，推导 CSV 列名与列顺序。
3. 然后读取 `KB/chemical_space.csv`，筛选可用候选。
4. 生成正好 10 条推荐数据。
5. 写入固定输出路径。

## 输入输出

- 输入：constraint-parser JSON、文献目录、`KB/chemical_space.csv`、输出格式示例。
- 输出：`output/ata_literature_top10_recommendations_<YYYYMMDD>.csv`
- 约束：只输出 CSV，不输出解释文字。

## 注意事项

- 推荐 CSV 只填写化学品名、材料名或 `none`；不要填写 `20 mg`、`1 mL`、当量、温度、时间等用量或条件值。
- 推荐候选必须来自 `KB/chemical_space.csv`；固定材料如分子筛可写材料名，例如 `4A MS`。
- `metal_salt_2` 没有第二种金属盐时写 `none`。
- 文件必须正好保留 10 条推荐数据，不要加入 `DATA` 占位行。

## 相关文件

- `KB/output_format_example.csv`
- `KB/chemical_space.csv`
- `output/ata_literature_top10_recommendations_<YYYYMMDD>.csv`
