# 协议编排说明

## 概述

这是化学实验流程的一部分，用于把 step JSON 编排成设备可执行协议 JSON。

## 流程视图

当前实现会按步骤类型调用对应的单步 skill，再拼装成设备协议数组。

## 常见输入

- step JSON
- 可选协议模板
- 可选设备参数

## 常见输出

- 设备可执行协议 JSON
- 编排后的动作数组

## 相关文件

- `SKILL.md`
- `../fdu-step-json/SKILL.md`
- `../fdu-add-solid-json/SKILL.md`
- `../fdu-add-liquid-json/SKILL.md`
- `../fdu-reaction-control-json/SKILL.md`
