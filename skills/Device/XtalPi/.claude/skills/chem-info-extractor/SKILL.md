---
name: chem-info-extractor
description: 这是化学实验流程的一部分，用于将化学 PDF 依次抽取为页级文本、事实记录、描述符空间和 BO 表；只负责上游抽取与发布，不负责 BO 优化或实验方案生成。
---

# chem-info-extractor

## 功能

把化学论文 PDF 转成可用于 Bayesian optimization 的结构化数据。流程包含 PDF 文本抽取、候选事实提取、事实标准化、描述符构建和 BO 表生成。

## 强制执行顺序

1. 先运行 `pdf_to_text.py`，把 PDF 转成按页保存的文本文件。
2. 再运行 `prepare_bo_table.py --mode process`，提取候选反应并生成事实记录。
3. 然后运行 `prepare_bo_table.py --mode publish`，构建描述符空间并生成 BO 表。
4. 如果要一次跑完，再使用 `prepare_bo_table.py --mode full`。
5. 不要跳过 `process` 直接跑 `publish`，除非 `facts_literature.json` 已经存在。

## 输入输出

- 输入：PDF 文件、PDF 目录、按页文本目录、`.env`、流水线配置。
- 输出：`output/pdf/<pdf_id>/`、`output/<run_name>/process/`、`output/<run_name>/publish/`
- 最终输出：`output/<run_name>/publish/bo_inputs/manual_conditions_round0.csv`

## 注意事项

- 默认配置文件位于 `scripts/text_to_bo/configs/default.yaml`。
- LLM 设置先读仓库根目录 `.env`，再由当前环境变量覆盖。
- `process` 阶段依赖 LLM，必须能访问模型接口。
- `publish` 阶段依赖 `process` 阶段生成的 `facts_literature.json`。

## 相关文件

- `scripts/pdf_to_text.py`
- `scripts/text_to_bo/pipeline_src/pipeline/prepare_bo_table.py`
- `scripts/text_to_bo/pipeline_src/pipeline/process_pipeline.py`
- `scripts/text_to_bo/pipeline_src/pipeline/publish_pipeline.py`
