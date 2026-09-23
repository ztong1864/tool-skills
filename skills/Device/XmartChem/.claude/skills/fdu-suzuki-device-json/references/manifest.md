# Suzuki 设备 JSON 说明

## 概述

这个 skill 用于把 Suzuki 偶联目标整理为最终可提交给设备的 JSON 文件。

## 内部层次

当前流程可以理解为三层：

1. 场景方案构建
2. 逻辑动作生成
3. 最终协议渲染

## 常见输入

- 目标产物
- 芳基卤化物底物
- 硼酸偶联伙伴
- 催化剂和碱偏好
- 溶剂偏好
- 反应后过滤或分析需求

## 常见输出

- `output/generated_suzuki_protocol_<timestamp>.json`
- 一个 JSON 数组形式的最终设备协议

## 相关文件

- `scripts/generate_from_goal.py`
- `scripts/scene_core.py`
- `scripts/scene_utils.py`
- `KB/resource_info.json`
- `KB/action_schema.json`
- `KB/sample_protocol.json`
- `KB/scene_rules_suzuki.json`
