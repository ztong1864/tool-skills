---
name: constraint-parser
description: 这是化学实验流程的一部分，用于将自然语言实验指令解析为结构化约束 JSON；只负责提取物料、当量、物态和简短补充信息，不负责生成优化建议或实验步骤。
---

# constraint-parser

## 功能

把自然语言实验指令解析成最小化 JSON，只抽取物料名字、类别、当量、物态和简短补充信息，供后续人工确认或下游条件空间生成使用。

## 强制执行顺序

1. 读取用户输入，支持 `--text`、`--input-file` 或 `--test`。
2. 加载 `KB/constraint_schema.md` 和 `KB/example_constraints.json`。
3. 调用 LLM 将自然语言解析为严格 JSON。
4. 校验顶层字段、列表字段和关键数值字段格式。
5. 写入 `output/parsed_constraints_<timestamp>.json`。

## 输入输出

- 输入：中文或中英混合实验指令，通常包含试剂、底物、变量范围、当量、物态和反应条件。
- 输出：`output/parsed_constraints_<timestamp>.json`
- 输出内容：包含 `items`、`ambiguities`、`source_text` 的 JSON 对象。

## 注意事项

- 只抽取 `name`、`group`、`equivalent`、`quantity`、`physical_state`、`raw_text` 和可选 `note`。
- `equivalent` 只填当量数值，`mmol` 不写入 `equivalent`。
- 在 FounDryClaw 中运行时，模型接口一律使用当前用户在“密钥管理”中保存的 OPENAI-API-KEY（接口地址和 API Key），模型为 `gpt-6-luna`（可用环境变量 `CONSTRAINT_PARSER_MODEL` 覆盖）；未保存该密钥时脚本直接报错并提示先添加，不会改用 `.env`。不需要事先检查密钥或环境变量，直接运行脚本即可；只有脚本实际报错时才把该错误如实回传。下面的 `.env` 设置只用于 FounDryClaw 之外的独立运行。
- 脚本先读仓库根目录 `.env`，再使用当前环境变量覆盖。
- 只能输出 JSON，不输出 Markdown 或解释。

## 相关文件

- `scripts/parse_constraints.py`
- `KB/constraint_schema.md`
- `KB/example_constraints.json`
