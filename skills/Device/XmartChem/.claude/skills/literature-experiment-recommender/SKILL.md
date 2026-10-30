---
name: literature-experiment-recommender
description: 这是化学实验流程中的候选条件推荐技能，用于根据约束 JSON、文献依据和候选化学空间 CSV 生成一组可实验执行的候选条件组合 CSV；只负责推荐条件组合，不负责解析自然语言约束、计算投料量或生成实验步骤。
---

# literature-experiment-recommender

## 功能定位

这是一个候选条件推荐技能。

它的职责不是简单复制候选空间，也不是生成实验步骤，而是基于：

- constraint-parser 输出的实验约束 JSON
- 用户提供的候选化学空间 CSV
- 文献 PDF、输出格式示例和已有实验经验

筛选并组合出一批合理的候选实验条件，输出为下游可继续使用的推荐 CSV。

## 推荐目标

生成一张候选条件推荐表。每一行是一组完整候选条件组合，例如催化剂/金属盐、配体、固定材料、溶剂等变量的组合。

推荐应满足：

- 符合约束 JSON 中的物料类别、数量限制、是否可选和变量范围。
- 候选变量优先来自用户输入的候选空间 CSV。
- 组合逻辑应参考文献趋势、输出格式示例和实验合理性。
- 推荐结果应覆盖多样候选，而不是只改动单一变量。
- 只推荐条件组合，不填写投料量、温度、时间、步骤或设备参数。

## 强制执行顺序

1. 读取主输入 JSON，理解 `source_text`、`items`、试剂类别、底物、固定条件和歧义项。
2. 读取用户输入的候选化学空间 CSV；优先使用用户明确给出的 `chemical_space.csv` 或其它 `.csv` 路径。只有用户未提供候选空间文件时，才回退读取 `KB/chemical_space.csv`。
3. 读取输出格式示例，确定输出 CSV 的列名、列顺序和候选条件字段。
4. 结合文献 PDF 或已有文献信息，为每个变量列选择合理候选，并形成完整条件组合。
5. 生成用户要求数量的推荐数据；如果用户没有指定数量，默认生成 10 条。
6. 用 `scripts/write_recommendations.py --output <mission artifacts 目录>/literature_recommendations_<YYYYMMDD>.csv` 写出（见“输出 CSV 的写法”）。

## 输入输出

- 输入：constraint-parser JSON。
- 输入：用户提供的候选空间 CSV；未提供 CSV 时可回退 `KB/chemical_space.csv`。
- 输入：文献 PDF 目录和 `KB/output_format_example.csv`。
- 输入：可选推荐条数；未指定时默认为 10。
- 输出：`<mission artifacts 目录>/literature_recommendations_<YYYYMMDD>.csv`（`--output` 指定的路径；不要写进本技能目录）。

## 候选选择规则

- 推荐候选必须来自本次用户输入的候选空间 CSV。
- 固定材料如果在用户约束、文献或输出格式示例中明确出现，可以直接填写材料名，不要求必须存在于候选空间 CSV；例如约束中出现分子筛时，`molecular_sieve` 可以填写 `4A MS`。
- 固定材料只有在当前候选条件设计中明确不加入或没有依据时，才写 `none`。
- 对可选变量，例如第二种金属盐、添加剂或固定材料，如果设计为不加入，应写 `none`。
- 如果用户约束明确写出“可加入或不加入”的变量或固定材料，例如“分子筛（不加入或20 mg）”，不要机械固定为全加入或全不加入；应根据文献依据、底物/试剂特性、溶剂和整体条件组合判断每一行推荐加入材料名还是 `none`。
- 对这类二元可选因素，是否同时覆盖加入和不加入两类状态取决于实验条件推荐逻辑；只有当两种状态都有合理实验意义时才同时覆盖，不要为了满足固定比例而强行加入或删除。
- 推荐结果要尽量覆盖不同类别和不同组合，不要生成重复行。

## 输出 CSV 约束

- 只输出 CSV 文件，不输出解释文字。
- 每行必须是一组完整候选条件组合。
- 推荐 CSV 只填写化学品名、材料名或 `none`。
- 不要填写 `20 mg`、`1 mL`、当量、温度、时间、反应规模、实验步骤或设备参数。
- 输出 CSV 的每个推荐单元格必须完全对应候选空间中的中文名或英文名之一；不允许在同一个单元格中同时出现中文和英文。
- 不允许使用 `中文/English`、`中文（English）` 或其它中英混写格式。
- 如果候选空间同一行同时提供中文名和英文名，优先选择与下游/示例一致的一种名称体系，并在整张输出 CSV 中保持一致。
- 候选空间 CSV 可为规范表头表，也可为无表头分区表；读取时必须识别可用候选名称列。
- 文件必须保留用户要求数量的推荐数据；默认 10 条。不要加入 `DATA` 占位行。

## 输出 CSV 的写法

- 推荐结果用 `scripts/write_recommendations.py` 写出，不要手写 CSV：先把所有行写成 JSON 文件（例如 mission artifacts 目录下的 recommendation_rows.json，它只是脚本的输入；每行按列顺序 5 个单元格，列为 metal_salt_1, metal_salt_2, chiral_amine, molecular_sieve, solvent；不要用 `--rows -` 从标准输入传），再运行 `python <本技能目录>/scripts/write_recommendations.py --candidate-space <候选空间 CSV> --rows <这个 JSON 文件的路径> --output <mission artifacts 目录>/literature_recommendations_<日期>.csv`。脚本会自动给含逗号的名称加引号，逐格对照候选空间（不在候选空间里的名称会报错并列出，不会写出文件），写完再读回校验列数。脚本报告 `written: true` 之后才算完成；不要再改动或重写这个文件。
- 推荐 CSV 必须是合法 CSV：名称里含逗号的单元格（例如 `1,4-Dioxane`、`1,4-二氧六环`、`(S)-α,α-二苯基脯氨醇`）要整格用一对双引号包起来，不要在名称内部再重复双引号（写成 `"1,4-Dioxane"`，不是 `1,4-Dioxane` 或 `""(S)-...""`）。最稳妥的做法是用 Python 的 `csv.writer` 生成文件，写完后用 `pandas.read_csv` 读一遍，确认每行都是 5 列（列数与表头一致）再登记；下游 chemical-amount-calculator 读到坏 CSV 会直接报错。

## 在回复里列出推荐表

之后每次向用户汇报这一步的结果（包括随后审查的暂停和审查未通过时），都在回复里完整列出全部推荐组，不要只写“已推荐 10 组”：Markdown 表格，每组一行，第一列是组号（从 1 开始，与 CSV 的行顺序一致，用户按组号选择，例如“只保留第一组”），其余列为金属盐（两种时写成“CuI + ZnBr₂”）、手性胺、分子筛（`none` 写“不加”）、溶剂。审查指出问题时，在表下写明是哪几组。

## 缺少文献时

- 先运行一次 `python <本技能目录>/scripts/write_recommendations.py --literature-status`（只读，检查 `KB/pdf_new`、`KB/pdfs`），再看任务输入里有没有用户上传的 PDF；只查这一次。不要用 Glob/Grep 或反复列目录去找 PDF，也不要上网搜索。
- 结果是 `no_literature` 且用户没有上传 PDF 时，这是正常情况，不是失败：基于约束 JSON、用户的候选空间 CSV 和 `KB/output_format_example.csv` 完成推荐（不要读本技能目录里以前的推荐结果，它们与本次任务无关），照常用 `write_recommendations.py` 写出文件并登记。
- 回复里用一句话说明“本轮推荐未使用文献依据”即可（不得编造文献）；不要说推荐结果不可信，也不要让用户重新发起任务。

## 相关文件

- `KB/output_format_example.csv`
- 用户输入的 `chemical_space.csv` 或其它 `.csv` 候选空间文件
- `KB/chemical_space.csv`（仅作为未提供 CSV 时的 fallback）
- 输出写到 `--output` 指定的 mission artifacts 目录，不写进本技能目录
