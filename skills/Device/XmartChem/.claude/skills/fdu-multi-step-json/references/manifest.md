# 多方案合并说明

## 概述

这是化学实验流程的一部分，用于把多个实验方案文件合并成一个总 step JSON。

## 流程视图

当前实现会分别转换每个方案文件，再按顺序合并步骤并整理 `step_index`。每份方案要调一次模型，10 份要跑 5-10 分钟，所以执行命令时超时至少给 15 分钟。

## 常见输入

- 多个 `.md` 方案文件
- 可选 `--target-layout-codes`
- 可选 `--task-name`
- 可选 `--cache-dir`、`--no-cache`

## 常见输出

- `output/generated_multi_step_json_<timestamp>.json`
- 单份方案的 step JSON 缓存：`<输出目录>/step_json_cache/<方案名>_<摘要>.json`，中途失败后重跑同一条命令只补还缺的那几份

## 相关文件

- `SKILL.md`
- `../fdu-step-json/SKILL.md`
- `scripts/generate_multi_step_json.py`
