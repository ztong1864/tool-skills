---
name: fdu-multi-step-json
description: 这是化学实验流程的一部分，用于将多个实验方案文件生成的 step JSON 合并为一个总 step JSON；只负责合并与重排，不负责单个方案的步骤抽取或协议执行。
---

# fdu-multi-step-json

## 功能

将多个实验方案文件分别转换为 step JSON，并合并成一个总 step JSON。

## 强制执行顺序

1. 使用 `python scripts/generate_multi_step_json.py --plan-files <file1.md> <file2.md> ...`。
2. 对每个方案文件单独调用一次 `fdu-step-json`。
3. 按当前实现的合并规则拼接各组步骤，并重新整理 `step_index`。
4. 如提供 `--target-layout-codes`，其数量必须与方案文件数量一致。

## 输入输出

- 输入：一个或多个 `.md` 方案文件，可选 `--target-layout-codes` 和 `--task-name`。
- 输出：`output/generated_multi_step_json_<timestamp>.json`。
- 约束：输出为合并后的总 step JSON，必要时保留 `task_name`。

## 注意事项

- 各方案内部顺序应保持不变。
- 方案文件缺失、内容为空或下游生成失败时应直接失败。
- 目标位覆盖时，相关布局字段应保持一致。
- 每个方案文件在调用下游 `fdu-step-json` 时存在固定超时限制，超时应视为失败。
- 输出进度格式与 `fdu-experiment-plan` 一致，使用 `[done/total]` 标签。
