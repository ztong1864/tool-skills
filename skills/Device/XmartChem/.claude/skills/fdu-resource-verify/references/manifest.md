# 资源校验说明

## 概述

这是化学实验流程的一部分，用于把资源处理拆成刷新、校验、渲染三个入口脚本。也可以单独只读查询装置当前的资源清单（只用刷新脚本）。

## 流程视图

当前实现按以下顺序工作：

1. 校验工作流
   - `scripts/fetch_resource_info.py` 刷新设备资源快照，并生成 `KB/resource_info.json`
   - `scripts/verify_resources.py` 将 step JSON 与资源快照进行匹配，输出 `verification_result`
   - 如果校验发现资源缺失、数量不足或不可用，先判断是否是别名问题，不能直接提醒用户补资源
   - 别名判断以 `KB/resource_info.json` 为准：检测缺失资源是否存在同化学品不同名的情况；如果存在，先将输入 step JSON 中需要校验的化学名纠正为 `KB/resource_info.json` 中的名称，再重新执行校验
   - 如果纠正名称后校验通过，继续进入回填；如果仍然资源缺失、数量不足或不可用，再提醒用户资源缺失/不足，需要补充资源
   - 等用户明确说明补充完成后，从 `scripts/fetch_resource_info.py` 重新开始执行
   - `scripts/render_step_json.py <step_json_path> <verification_result_path>` 根据校验结果回填资源信息，输出 `verified_step_json`
2. 直接回填工作流
   - `scripts/render_step_json.py <step_json_path> --direct` 直接根据 `KB/resource_info.json` 回填资源信息，输出 `verified_step_json`
3. 只读快照模式（流程 `fdu-resource-snapshot`）
   - 只运行 `scripts/fetch_resource_info.py --resource-dir <artifacts 目录>`，写出 `resource_info_<时间戳>.json`（原始快照，带 `timestamp`）和 `resource_info.json`（精简列表）
   - 不需要 step JSON，不运行校验和渲染脚本，不产出 `verified_step_json`
   - 设备接口不可用时直接报错，不退回本地快照；用户明确要看本地快照时才读 `KB/resource_info.json`，并说明它不是设备现状

## 常见输入

以下是校验和回填工作流的输入；只读快照模式不需要输入文件。

- `fdu-multi-step-json` 输出的 step JSON
- 设备资源快照
- `KB/resource_info.json`
- `verification_result` JSON
- `verified_step_json` JSON

## 常见输出

- `KB/resource_info.json`
- `output/verification_result_<timestamp>.json`
- `output/verified_step_json_<timestamp>.json`

## 别名处理原则

- 资源缺失、数量不足、资源不可用或找不到匹配项时，必须先排查是否为别名/同化学品不同名问题。
- 化学名纠正以 `KB/resource_info.json` 中的 `substance` 名称为准，不得自行发明别名或规范名。
- 只有别名纠正并重新校验后仍失败，才提醒用户补充资源。

## 相关文件

- `SKILL.md`
- `scripts/fetch_resource_info.py`
- `scripts/verify_resources.py`
- `scripts/render_step_json.py`
