---
name: fdu-resource-fetch
description: 只读查询复旦智能合成工作站（XmartChem）当前的设备资源清单：刷新设备资源快照，按区域、托盘和资源类型汇总位点、物质和余量，给出快照时间。不需要 step JSON，不做资源校验或回填，不创建、启动或修改设备任务。用户说“刷新资源快照”“看看机器的资源状态”“列出资源清单”“库位有多少”时用本技能。
---

# fdu-resource-fetch

只读查询装置现在有哪些资源。它只调用设备的登录和 `GetResourceInfo` 接口，把结果写成一份资源快照 JSON 并汇总。

不做的事：不读取或修改 step JSON，不做资源校验和回填，不生成设备协议，不创建、启动或修改设备任务。

## 执行顺序

1. 运行（在 LabOntology 中 `<artifacts 目录>` 是 mission 的 artifacts 目录）：

   ```bash
   python3 scripts/fetch_resources.py --output <artifacts 目录>/resource_snapshot.json
   ```

   只关心某个区域或托盘时加 `--layout-prefix <前缀>`，例如 `--layout-prefix T-8`、`--layout-prefix W4`；不加就是全量。
   不带 `--output` 时写进本技能的 `output/`，那是所有用户共用的目录，服务器上可能不可写。
2. 读写出的 JSON，按下面的“汇报口径”回复用户。
3. 在 LabOntology 中登记这一份文件：

   ```
   resume … --agent-completed --provide-artifact "artifact:resource-snapshot=<artifacts 目录>/resource_snapshot.json" --summary "<资源条数、快照时间>"
   ```

   `do_next` 给出的 `--register-all` 也可以，它会把这份文件登记成同一个产物。

## 输入输出

- 输入：无。不需要 step JSON、实验方案或任何上传文件。
- 输出：`--output` 指定的资源快照 JSON（默认 `output/resource_snapshot_<timestamp>.json`），字段：
  - `timestamp`：快照时间（读取设备的时间，带时区）；`source`：`device`（设备）或 `file`（已有快照文件）
  - `resource_count`：位点总数；`with_substance_count`：有物质的位点数
  - `resource_types`：各资源类型（`resource_type`，托盘或耗材型号）的位点数
  - `areas`：按区域（`layout_code` 第一个 `-` 之前，例如 `T`、`W4`、`N1`）的位点数、托盘数、有物质的位点数和资源类型
  - `trays`：按托盘（`layout_code` 的 `:` 之前，例如 `T-8`）的位点数、资源类型、托盘二维码和其上的物质及余量
  - `resources`：每个位点的完整记录

## 汇报口径

- 先给快照时间、来源和位点总数、有物质的位点数，再按区域列位点数和托盘数，最后列有物质的位点（位点、物质、余量和单位）。资源多时用表格，不要贴整份 JSON。
- 数字只取自这份快照，不估算、不补全。
- 快照只有区域、托盘、资源类型和物质，没有“加液位”“固体加样位”“反应位”这类分类。用户按这类类别问数量时，按资源类型和区域如实列出，说明快照里没有这种分类；不要自己把资源类型对应成类别。
- 回复里不要写设备接口的地址、账号或口令。

## 设备接口不可用时

- 设备接口的配置（`FDU_DEVICE_BASE_URL`、`FDU_DEVICE_USERNAME`、`FDU_DEVICE_PASSWORD`，可选 `FDU_DEVICE_TIMEOUT`）是服务器环境变量或设备目录的 `.env`，由管理员配置。缺少时脚本报“设备接口没有配置”并列出缺少的项；连不上或接口报错时报“刷新资源快照失败”和原因。两种情况脚本都以非零状态退出，**不会**退回本地快照。
- 这时照实告诉用户刷新没有成功、需要管理员处理，不给任何资源数字；在 LabOntology 中用 `--agent-failed` 登记报错原文。不要自己去找或填写这些配置。
- 只有用户明确说要看本地或缓存的快照时，才用 `--from-file <快照文件>` 汇总那份文件（例如工作站资源校验技能目录下的 `KB/resource_info.json`，那是本地备用快照）。输出的 `source` 是 `file`；回复第一句说明这是本地快照、不是设备现状、不能当成当前库存。

## 注意事项

- 本技能只读：每次查询都重新读取设备，不复用以前的快照文件冒充当前结果。
- 不得编造资源的有无、数量或位置。
