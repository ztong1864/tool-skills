# 固体加料说明

## 概述

这是化学实验流程的一部分，用于把固体加料 `step_unit` 转成单步 JSON。

## 流程视图

当前实现直接读取 `skill_input` 中的固体加料信息并输出规范 JSON。

## 常见输入

- 包含 `skill_input` 的 JSON 对象
- 指向该对象的 JSON 文件路径

## 常见输出

- 单步固体加料 JSON

## 相关文件

- `SKILL.md`
- `../fdu-step-json/SKILL.md`
