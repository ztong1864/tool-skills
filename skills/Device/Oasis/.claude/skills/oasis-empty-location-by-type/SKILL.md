---
name: oasis-empty-location-by-type
description: 为 Oasis 中的样品、试剂或耗材查询可用空库位。当用户要“分配库位、找空位、按物料类型找能放哪、入库前先找位置”时调用本技能；如果用户已经拿到了库位并要真正执行入库，不要停留在本技能，而应切换到入库技能。
when: 当目标是查询某类物料当前可用的空闲库位时调用；它只负责找位置，不负责实际入库，也不负责保存实验步骤。
---
# 获取空闲库位

## 直接调用（推荐）

```bash
# 获取样品库位（materialTypeMode=1）
python skills/oasis-empty-location-by-type/scripts/call.py \
  --workflow-id <subWorkflowId> \
  --order-id <commonlyOrderId> \
  --type 1

# 获取耗材库位（materialTypeMode=0），数量=2
python skills/oasis-empty-location-by-type/scripts/call.py \
  --workflow-id <subWorkflowId> \
  --order-id <commonlyOrderId> \
  --type 0 --count 2

# 获取试剂库位（materialTypeMode=2）
python skills/oasis-empty-location-by-type/scripts/call.py \
  --workflow-id <subWorkflowId> \
  --order-id <commonlyOrderId> \
  --type 2

# 输出完整 JSON（包含 locationId 和 materialTypeId）
python skills/oasis-empty-location-by-type/scripts/call.py \
  --workflow-id <id> --order-id <id> --type 1 --json-output
```

通常只需要传递本技能自己的业务参数，例如 `--workflow-id`、`--order-id`、`--type`、`--count`。脚本默认会直接访问 API；只有在明确需要改回“通过 SSH 在远端执行 curl”时，才追加 `--use-ssh`。如还需要切换 SSH 主机、账号、密码、端口或超时时间，再追加：

```bash
--ssh-host <IP> --ssh-user <用户名> --ssh-password <密码> --ssh-port <端口> --ssh-timeout <秒>
```

**`--type` 枚举：`0`=耗材，`1`=样品，`2`=试剂**

成功后从返回中取出 `locationId` 和 `materialTypeId`，传给入库接口。

执行本技能后不要自动继续后续步骤，必须先做下面这件事：

- 先向用户汇报是否分配到了可用库位，以及拿到了哪些 `locationId` / `materialTypeId`
- 如果返回为空、数量不足，或缺少后续必需字段，立即停止，不要继续入库
- 只有在库位分配结果完整且用户确认继续后，才能进入入库步骤

## 别名提醒

- `--workflow-id`：这里传的是子工作流 ID，也就是别处的 `subWorkflowId`
- `--order-id`：这里传的是临时实验 ID，也就是 `commonlyOrderId`
- 返回里的 `locations[].id`：后续入库接口里通常叫 `locationId`
- 返回里的 `materialTypeId`：后续入库接口里同名继续使用
---

## 参数说明

| 参数 | 类型 | 描述 |
|------|------|------|
| `--type` | int | 0=耗材，1=样品，2=试剂 |
| `--count` | int | 需要分配的数量，默认 1 |
| `--workflow-id` | guid | 子工作流 ID |
| `--order-id` | guid | 临时实验 ID，也就是 `commonlyOrderId` |
| `--material-type-id` | string | 可选，默认留空 |

## 返回说明

`data[]` 数组，每项包含：
- `materialTypeId` -> 传给入库接口
- `locations[].id` -> `locationId`，传给入库接口
- `locations[].code` -> 库位编号，例如 `2-10`
```json
{
  "data": [{
    "materialTypeId": "8fe77e43-...",
    "materialTypeName": "药板",
    "locations": [{"id": "3a47f06b-...", "code": "2-10"}]
  }],
  "code": 1
}
```

