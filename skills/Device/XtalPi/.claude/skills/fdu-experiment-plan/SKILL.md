---
name: fdu-experiment-plan
description: 这是化学实验流程的一部分，用于根据实验步骤 Markdown 和用量推荐 CSV 批量生成中文 FDU 实验方案；只负责把推荐条件写成规范 Markdown，不负责解析约束、计算用量或生成 step JSON。
---

# fdu-experiment-plan

## 功能

读取实验步骤参考、带用量推荐 CSV 和 `KB/example_plan.md`，用 LLM 为每一条推荐生成一份独立的中文 Markdown 实验方案。

## 强制执行顺序

1. 使用 `python scripts/generate_plan.py --steps-file <path> --amounts-csv <path>` 运行批量生成。
2. `--output-dir` 可选，不提供时默认写入 `output/experiment_plan_<timestamp>/`。
3. `--tray` 可选，不提供时默认使用 `T-3`。
4. 每条推荐条件单独生成一份 Markdown 文件。
5. 输出必须严格遵守 `KB/example_plan.md` 的四段结构。

## 输入输出

- 输入：实验步骤 Markdown、带用量推荐 CSV、`KB/example_plan.md` 示例模板。
- 输出：`output/experiment_plan_<timestamp>/experiment_plan_<tray>_<index>.md`。
- 约束：输出仅限 Markdown，并只包含 `## 实验概述`、`## 试剂作用与用量`、`## 实验步骤`、`## 反应位置与过滤信息` 四个章节。

## 注意事项

- 不输出 `layout_code`、`chemical_id`、`tray_QR_code`、`QR_code`。
- 反应位由 `--tray` 指定，默认 `T-3`。
- 若某个试剂为 `none` 或空值，则不写入该试剂条目。
- 生成过程由 LLM 完成。

## 相关文件

- `scripts/generate_plan.py`
- `KB/plan_schema.md`
- `KB/example_plan.md`
- `references/manifest.md`
