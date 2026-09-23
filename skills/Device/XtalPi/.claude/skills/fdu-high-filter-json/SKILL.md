---
name: fdu-high-filter-json
description: 这是化学实验流程的一部分，用于将高滤 step_unit 转换为单步 exp_high_filtering_samples JSON；只处理单步高滤映射，不负责整套协议编排或设备提交。
---

# fdu-high-filter-json

## 功能

将高滤 `step_unit` 转换为单步 `exp_high_filtering_samples` JSON。

## 强制执行顺序

1. 使用 `python3 scripts/generate_high_filter_json.py "<step_unit JSON 或文件路径>"`。
2. 读取输入中的 `skill_input` 并生成单步动作。
3. 将结果写入 `output/`。

## 输入输出

- 输入：`step_unit` JSON 对象或对应的 JSON 文件路径。
- 输出：单个 `exp_high_filtering_samples` 动作 JSON 文件。
- 约束：只处理单步动作，输入应包含高滤所需字段。
- 如输入中提供 `resource_info`，脚本会据此补充来源信息。

## 注意事项

- 不处理多步 protocol。
- 不调用 `AddTask` 或 `StartTask`。
