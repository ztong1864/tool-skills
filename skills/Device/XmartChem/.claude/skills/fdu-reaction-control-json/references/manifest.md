# 反应控制说明

## 概述

这是化学实验流程的一部分，用于把反应控制 `step_unit` 转成单步 JSON。

## 流程视图

当前实现直接读取 `skill_input` 中的反应控制信息并输出规范 JSON。

## 常见输入

- 包含反应控制字段的 JSON 对象
- 指向该对象的 JSON 文件路径

## 常见输出

- 单步反应控制 JSON

## 相关文件

- `SKILL.md`
- `scripts/generate_reaction_control_json.py`
- `KB/action_schema.json`
