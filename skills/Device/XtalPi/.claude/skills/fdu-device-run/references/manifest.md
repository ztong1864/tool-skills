# 设备提交说明

## 概述

这是化学实验流程的一部分，用于把协议 JSON 提交到设备接口并记录结果。

## 流程视图

当前实现会先读取协议 JSON，再提交给设备接口，默认只创建任务。

## 常见输入

- `--protocol-file`
- `--protocol-json`
- 标准输入

## 常见输出

- 任务创建结果
- 设备执行结果

## 相关文件

- `SKILL.md`
- `scripts/run_protocol.py`
- `scripts/protocol_utils.py`
