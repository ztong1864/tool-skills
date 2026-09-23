---
name: fdu-device-run
description: 这是化学实验流程的一部分，用于将协议 JSON 提交给设备 API 并记录提交结果；默认只创建任务，不启动执行，也不负责协议生成或字段修正。
---

# fdu-device-run

## 功能

将协议 JSON 提交到设备 API，默认只创建任务，不启动执行。

## 强制执行顺序

1. 使用 `python scripts/run_protocol.py` 提交协议。
2. 优先接受 `--protocol-file` 或 `--protocol-json`。
3. 如两者都未提供，再按标准输入或默认回退路径读取。
4. 先调用 `AddTask`，只有显式开启时才调用 `StartTask`。

## 输入输出

- 输入：协议文件、内联 JSON、标准输入或默认回退协议文件。
- 输入既可以是单个 JSON 对象，也可以是 JSON 数组；单个对象会自动包装成列表。
- 输出：`output/submit_<timestamp>.json`，以及终端中的任务信息。
- 约束：默认会重写 `unit_id`，以避免重复冲突。
- 额外可选参数包括 `--task-name`、`--base-url`、`--username`、`--password`、`--timeout`、`--keep-unit-ids`、`--enable-start`、`--skip-curr-taskunit`、`--run-by-single-tube`、`--quick-cap` 和 `--use-tip-type`。

## 注意事项

- 未显式开启时不得调用 `StartTask`。
- 协议结构无效或任务 ID 缺失时应直接失败。
- 需要保持协议输入与实际提交内容一致。
