---
name: fdu-reaction-control-json
description: 这是化学实验流程的一部分，用于将反应控制 step_unit 转换为单步 exp_magnetic_stirrer JSON；只处理单步反应控制映射，不负责整套协议编排或设备提交。
---

# fdu-reaction-control-json

## 功能

将反应控制 `step_unit` 转换为单步 `exp_magnetic_stirrer` JSON。

## 强制执行顺序

1. 使用 `python3 scripts/generate_reaction_control_json.py "<step_unit JSON 或文件路径>"`。
2. 读取输入中的 `skill_input` 并生成单步动作。
3. 将结果写入 `output/`。

## 输入输出

- 输入：`step_unit` JSON 对象或对应的 JSON 文件路径。
- 输出：单个 `exp_magnetic_stirrer` 动作 JSON 文件。
- 约束：只处理单步动作，输入应包含反应控制所需字段。

## 注意事项

- 不处理多步 protocol。
- 不调用 `AddTask` 或 `StartTask`。
