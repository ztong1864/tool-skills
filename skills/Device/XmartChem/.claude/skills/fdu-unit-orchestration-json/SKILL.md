---
name: fdu-unit-orchestration-json
description: 这是化学实验流程的一部分，用于将 step JSON 逐步编排为设备可执行协议 JSON；只负责把步骤映射成协议数组，不负责上游步骤抽取或设备任务提交。
---

# fdu-unit-orchestration-json

## 功能

将 step JSON 按步骤顺序编排为设备可执行协议 JSON，并调用对应的单步 skill 生成动作。

## 强制执行顺序

1. 使用 `python scripts/generate_orchestration_json.py --step-json "<step_json_path>"`。
2. 如需自定义输出路径，可附加 `--output "<输出路径>"`。
3. 按输入 step 的顺序读取每个步骤。
4. 根据 `unit_type` 调用对应的单步 skill。
5. 汇总各步骤结果，生成最终协议数组。

## 输入输出

- 输入：`fdu-step-json` 生成的 step JSON 文件。
- 输出：`output/generated_protocol_<timestamp>.json`。
- 约束：输出为 JSON 数组，每个元素对应一个步骤的执行协议。

## 注意事项

- 步骤顺序不得打乱。
- 下游步骤缺失必要字段或单步 skill 执行失败时应直接失败。
- 传递给单步 skill 的内容仅限 `skill_input` 和需要时的 `resource_info`。
