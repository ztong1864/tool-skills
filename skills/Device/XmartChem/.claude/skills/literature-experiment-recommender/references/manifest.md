# 候选条件推荐说明

## 概览

这是化学实验流程中的候选条件推荐技能，用于从约束 JSON、文献和候选化学空间生成推荐实验条件组合 CSV。

## 流程视图

当前实现会先读取约束 JSON，识别需要推荐的变量列，再结合文献和候选化学空间筛选候选，最终按用户要求数量写出完整条件组合。用户未指定数量时，默认写出 10 条。

## 常见输入

- constraint-parser JSON
- 文献 PDF 目录
- 用户提供的 `chemical_space.csv` 或其它 `.csv` 候选空间文件
- `KB/chemical_space.csv`（仅在用户未提供 CSV 时作为 fallback）
- `KB/output_format_example.csv`

## 常见输出

- `output/literature_recommendations_<YYYYMMDD>.csv`

## 推荐约束

- 每一行必须是一组完整候选条件组合，而不是单个候选项。
- 推荐应覆盖多个变量列，避免重复组合。
- 推荐 CSV 单元格必须完全对应候选空间中的中文名或英文名之一。
- 不允许同一单元格中同时出现中文和英文。
- 不允许使用 `中文/English`、`中文（English）` 或其它中英混写格式。
- 固定材料可来自用户约束、文献或输出格式示例，不要求必须在候选空间 CSV 中；例如分子筛可填写 `4A MS`。
- 如果用户约束写明某个材料或变量可加入也可不加入，应根据具体实验条件推荐加入或不加入；不要定死为全加入、全不加入或固定比例。

## 相关文件

- `SKILL.md`
- `KB/output_format_example.csv`
- 用户输入的 `chemical_space.csv`
- `KB/chemical_space.csv`（fallback）
