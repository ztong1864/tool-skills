---
name: constraint-parser
description: 这是化学实验流程的一部分，用于将自然语言实验指令解析为结构化约束 JSON，并将用户上传的候选空间表格解析为 CSV；只负责提取物料、当量、物态和简短补充信息，以及表格格式转换，不负责生成优化建议或实验步骤。
---

# constraint-parser

## 功能

读取用户输入的实验指令和候选空间表格文件：

1. 将自然语言实验指令解析成最小化 JSON，只抽取物料名字、类别、当量、物态和简短补充信息。
2. 将用户上传的 `.xlsx`、`.xls` 或 `.csv` 表格规范化输出为 CSV，供下游 `literature-experiment-recommender` 使用。

## 强制执行顺序

1. 读取用户输入，实验指令支持 `--text`、`--input-file` 或 `--test`。
2. 读取用户表格文件，使用 `--table-file <path>`；普通运行必须提供表格文件。
3. 加载 `KB/constraint_schema.md` 和 `KB/example_constraints.json`。
4. 调用 LLM 将自然语言实验指令解析为严格 JSON。
5. 校验 JSON 顶层字段、列表字段和关键数值字段格式。
6. 将 `.xlsx`、`.xls` 或 `.csv` 表格写出为 CSV。
7. 写入 `output/parsed_constraints_<timestamp>.json` 和表格 CSV。

## 输入输出

- 输入：中文或中英混合实验指令，通常包含试剂、底物、变量范围、当量、物态和反应条件。
- 输入：用户上传的候选空间表格文件，支持 `.xlsx`、`.xls` 或 `.csv`。
- 输出：`output/parsed_constraints_<timestamp>.json`
- 输出：`output/<table_stem>_<timestamp>.csv`，或 `--csv-output` 指定的 CSV 路径。
- JSON 内容：包含 `items`、`ambiguities`、`source_text` 的 JSON 对象。

## 命令示例

```bash
python scripts/parse_constraints.py --text "实验指令..." --table-file chemical_space.xlsx
```

```bash
python scripts/parse_constraints.py --input-file instruction.txt --table-file chemical_space.xlsx --csv-output output/chemical_space.csv
```

## 注意事项

- 只抽取 `name`、`group`、`equivalent`、`quantity`、`physical_state`、`raw_text` 和可选 `note`。
- `equivalent` 只填当量数值，`mmol` 不写入 `equivalent`。
- 表格转换默认读取 Excel 的第一个工作表。
- 用户上传的表格默认不存在表头；脚本读取时不把第一行当列名，写出 CSV 时也不生成表头。
- CSV 输出使用 UTF-8 with BOM，便于 Excel 和下游脚本读取中文。
- 在 FounDryClaw 中运行时，模型接口一律使用当前用户在“密钥管理”中保存的 OPENAI-API-KEY（接口地址和 API Key），模型为 `gpt-6-luna`（可用环境变量 `CONSTRAINT_PARSER_MODEL` 覆盖）；未保存该密钥时脚本直接报错并提示先添加，不会改用 `.env`。不需要事先检查密钥或环境变量，直接运行脚本即可；只有脚本实际报错时才把该错误如实回传。下面的 `.env` 设置只用于 FounDryClaw 之外的独立运行。
- 脚本先读仓库根目录 `.env`，再使用当前环境变量覆盖。
- 只能输出 JSON 和 CSV 文件，不输出 Markdown 或解释性文件。

## 相关文件

- `scripts/parse_constraints.py`
- `KB/constraint_schema.md`
- `KB/example_constraints.json`
