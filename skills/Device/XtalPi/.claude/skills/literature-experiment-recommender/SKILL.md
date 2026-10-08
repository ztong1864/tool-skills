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

## 输出 CSV 的写法

- 推荐结果用 `scripts/write_recommendations.py` 写出，不要手写 CSV：先把所有行写成 JSON 文件（例如 mission artifacts 目录下的 recommendation_rows.json，它只是脚本的输入；每行按列顺序 5 个单元格，列为 metal_salt_1, metal_salt_2, chiral_amine, molecular_sieve, solvent；不要用 `--rows -` 从标准输入传），再运行 `python <本技能目录>/scripts/write_recommendations.py --candidate-space <候选空间 CSV> --rows <这个 JSON 文件的路径> --output <mission artifacts 目录>/literature_recommendations_<日期>.csv`。脚本会自动给含逗号的名称加引号，逐格对照候选空间（不在候选空间里的名称会报错并列出，不会写出文件），写完再读回校验列数。脚本报告 `written: true` 之后才算完成；不要再改动或重写这个文件。
- 推荐 CSV 必须是合法 CSV：名称里含逗号的单元格（例如 `1,4-Dioxane`、`1,4-二氧六环`、`(S)-α,α-二苯基脯氨醇`）要整格用一对双引号包起来，不要在名称内部再重复双引号（写成 `"1,4-Dioxane"`，不是 `1,4-Dioxane` 或 `""(S)-...""`）。最稳妥的做法是用 Python 的 `csv.writer` 生成文件，写完后用 `pandas.read_csv` 读一遍，确认每行都是 5 列（列数与表头一致）再登记；下游 chemical-amount-calculator 读到坏 CSV 会直接报错。

## 缺少文献时

- 先运行一次 `python <本技能目录>/scripts/write_recommendations.py --literature-status`（只读，检查 `KB/pdf_new`、`KB/pdfs`），再看任务输入里有没有用户上传的 PDF；只查这一次。不要用 Glob/Grep 或反复列目录去找 PDF，也不要上网搜索。
- 结果是 `no_literature` 且用户没有上传 PDF 时，这是正常情况，不是失败：基于约束 JSON、用户的候选空间 CSV、`KB/output_format_example.csv` 和 `output/` 中已有的推荐结果完成推荐，照常用 `write_recommendations.py` 写出文件并登记。
- 回复里用一句话说明“本轮推荐未使用文献依据”即可（不得编造文献）；不要说推荐结果不可信，也不要让用户重新发起任务。

## 相关文件

- `KB/output_format_example.csv`
- `KB/chemical_space.csv`
- `output/ata_literature_top10_recommendations_<YYYYMMDD>.csv`
