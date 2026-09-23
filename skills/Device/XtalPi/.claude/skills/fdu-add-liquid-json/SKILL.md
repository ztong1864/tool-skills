---
name: fdu-add-liquid-json
description: 这是化学实验流程的一部分，用于将液体加料 step_unit 转换为单步 exp_add_liquid JSON；只处理单步液体加料映射，不负责整套协议编排或设备提交。
---

# fdu-add-liquid-json

## 功能

将液体加料 `step_unit` 转换为单步 `exp_add_liquid` JSON。

## 强制执行顺序

1. 使用 `python3 scripts/generate_add_liquid_json.py "<step_unit JSON 或文件路径>"`。
2. 读取输入中的 `skill_input` 并生成单步动作。
3. 将结果写入 `output/`。

## 输入输出

- 输入：`step_unit` JSON 对象或对应的 JSON 文件路径。
- 输出：单个 `exp_add_liquid` 动作 JSON 文件。
- 约束：只处理单步动作，输入应包含液体加料所需字段。

## 注意事项

- 不处理多步 protocol。
- 不调用 `AddTask` 或 `StartTask`。
- 如提供 `resource_info`，仅在生成结果中使用，不进行额外推断。
