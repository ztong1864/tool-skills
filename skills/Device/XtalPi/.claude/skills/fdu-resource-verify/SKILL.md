---
name: fdu-resource-verify
description: 这是化学实验流程的一部分，用于对 fdu-multi-step-json 生成的 step JSON 执行资源快照刷新、资源校验和资源回填；支持直接回填资源信息，也支持先校验再回填工作流，不负责生成协议。
---

# fdu-resource-verify

默认模式是校验工作流。

## 功能

分两种工作流处理 step JSON 的资源相关工作：

1. 校验工作流：先刷新资源快照，再做资源校验；如果发现资源缺失、数量不足或不可用，必须先判断是否是别名问题。检测缺失资源在 `KB/resource_info.json` 中是否存在同化学品不同名的情况；若存在，则先将输入 step JSON 中需要校验的化学名纠正为 `KB/resource_info.json` 中的名称并重新校验。只有纠正后仍然缺失、数量不足或不可用时，才提醒用户补充资源；等用户明确说明补充完成后，从刷新资源快照这一步重新开始执行，最后再把校验结果回填到 step JSON
2. 直接回填工作流：跳过校验步骤，直接根据 `KB/resource_info.json` 把资源信息回填到 step JSON

## 强制执行顺序

1. 校验工作流：
   - 使用 `python3 scripts/fetch_resource_info.py` 刷新资源快照，并生成 `KB/resource_info.json`
   - 使用 `python3 scripts/verify_resources.py <step_json_path>` 执行资源校验，生成 `output/verification_result_<timestamp>.json`
   - 如果校验结果显示资源缺失、数量不足或不可用，必须先做别名问题判断，不能直接提醒用户补资源，也不能直接进入回填
   - 别名判断以 `KB/resource_info.json` 为准：检查缺失资源是否能对应到同一化学品的其它名称；如果确认是同化学品不同名，先把输入 step JSON 中对应的 `skill_input.substance` 等化学名字段纠正为 `KB/resource_info.json` 里的名称，再重新执行资源校验
   - 如果名称纠正后校验通过，继续使用新的校验结果进入回填；如果仍然资源缺失、数量不足或不可用，再提醒用户资源缺失/不足，需要补充资源
   - 等用户明确说明补充完成后，从 `scripts/fetch_resource_info.py` 重新开始执行
   - 使用 `python3 scripts/render_step_json.py <step_json_path> <verification_result_path>` 回填资源信息，生成 `output/verified_step_json_<timestamp>.json`
2. 直接回填工作流：
   - 使用 `python3 scripts/render_step_json.py <step_json_path> --direct`，直接根据 `KB/resource_info.json` 回填资源信息

## 输入输出

- 输入：
  - 校验工作流：`fdu-multi-step-json` 生成的 step JSON 文件、设备资源快照、`verification_result` 文件
  - 直接回填工作流：`fdu-multi-step-json` 生成的 step JSON 文件、`KB/resource_info.json`
- 输出：
  - `KB/resource_info.json`
  - `output/verification_result_<timestamp>.json`
  - `output/verified_step_json_<timestamp>.json`
- 约束：`scripts/` 下只保留三个入口脚本，分别对应刷新、校验、渲染；渲染脚本支持“校验回填”和“直接回填”两种模式。

## 注意事项

- 资源缺失、数量不足、资源不可用或找不到匹配项时，必须先排查别名/同化学品不同名问题；只有排查并纠正后仍失败，才向用户提醒补充资源。
- 化学名纠正必须以 `KB/resource_info.json` 中的 `substance` 名称为准，不得自行发明别名或规范名。
- 不得编造资源可用性、数量或位置信息。
- 资源数据应以设备快照和本地缓存为准。
- 普通过滤步骤按 `source_layout_code` 校验来源位点，高滤步骤按 `substance` 校验稀释剂。
- 校验脚本只负责生成验证结果；当验证结果显示资源缺失、数量不足或资源不可用时，流程层面必须先判断并处理别名问题。
- 校验工作流中，资源缺失提醒应发生在别名纠正和重新校验之后；用户明确说明补充完成前不能直接进入回填。
- 渲染脚本在校验回填模式下只负责把验证结果回填到 step JSON；在直接回填模式下只负责从 `KB/resource_info.json` 取资源信息，不再重新校验资源。
