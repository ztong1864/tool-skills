# 化学文献抽取说明

## 概述

这是化学实验流程的一部分，用于把化学 PDF 转成可用于 BO 和推荐的结构化数据。

## 流程视图

当前实现先做 PDF 文本抽取，再做事实提取与描述符构建，最后发布 BO 表。

## 常见输入

- PDF 文件或 PDF 目录
- 按页文本目录
- 流水线配置

## 常见输出

- `output/pdf/<pdf_id>/`
- `output/<run_name>/process/`
- `output/<run_name>/publish/bo_inputs/manual_conditions_round0.csv`

## 相关文件

- `SKILL.md`
- `scripts/pdf_to_text.py`
- `scripts/text_to_bo/pipeline_src/pipeline/prepare_bo_table.py`
