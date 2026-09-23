---
name: fdu-suzuki-device-json
description: 将 Suzuki coupling 目标转换为最终设备可执行 JSON。
---

# fdu-suzuki-device-json

## 功能

将 Suzuki 偶联目标转换为最终可提交给设备的 JSON。

## 强制执行顺序

1. 用户提供反应目标时，使用 `python3 scripts/generate_from_goal.py --goal "<反应目标>"`。
2. 需要内置示例时，使用 `python3 scripts/generate_from_goal.py --test`。
3. 如需显式指定场景类型，可使用 `--reaction-type suzuki`。
4. 如需在部分资源校验失败时继续尝试生成，可加 `--allow-fallback-reagents`。
5. 脚本完成后输出最终协议文件。

## 输入输出

- 输入：Suzuki 偶联反应目标，或内置测试模式。
- 输出：`output/generated_suzuki_protocol_<timestamp>.json`。
- 约束：输出为最终设备可执行 JSON，不暴露中间场景计划或逻辑协议。

## 注意事项

- 仅支持 Suzuki 偶联场景。
- 出现硬性校验失败时应停止，不继续伪造后续内容。
- 资源相关字段应来自真实资源信息，不应臆造。
- `--allow-fallback-reagents` 只影响生成时的资源容错，不改变场景限制。
