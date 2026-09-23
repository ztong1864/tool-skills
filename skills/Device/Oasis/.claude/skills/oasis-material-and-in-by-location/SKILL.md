---
name: oasis-material-and-in-by-location
description: 在 Oasis 中执行样品、试剂或耗材入库，并把指定物料放入指定库位。当用户已经明确了 order、物料和 location，目标是“正式入库/放入库位/提交入库结果”时调用本技能；如果还在查询空位或只是在同步步骤，不要误用它。
when: 当用户要把具体物料入到具体库位时调用；通常发生在已拿到空库位之后。不要把它用于查询库位，也不要把它用于仅保存实验步骤。
---
## 直接调用（推荐）

```bash
# 命令行里的 --order-id 会在请求体里写入 associateId
python skills/oasis-material-and-in-by-location/scripts/call.py \
  --order-id <commonlyOrderId> \
  --location-ids <locationId1> <locationId2> \
  --material-type-id <materialTypeId>

# 输出完整 JSON
python skills/oasis-material-and-in-by-location/scripts/call.py ... --json-output
```

通常只需要传递本技能自己的业务参数，例如 `--order-id`、`--location-ids`、`--material-type-id`。脚本默认会直接访问 API；只有在明确需要改回“通过 SSH 在远端执行 curl”时，才追加 `--use-ssh`。如还需要切换 SSH 主机、账号、密码、端口或超时时间，再追加：

```bash
--ssh-host <IP> --ssh-user <用户名> --ssh-password <密码> --ssh-port <端口> --ssh-timeout <秒>
```

## 别名提醒

- `--order-id`：这里传的是临时实验 ID，也就是 `commonlyOrderId`
- `associateId`：请求体里实际写入的就是这个字段；命令行中的 `--order-id` 会映射到请求体里的 `associateId`
- `--location-ids`：命令行里传的是一个或多个库位 ID；这些 ID 一般来自空库位查询结果里的 `locations[].id`
- `--material-type-id`：一般来自空库位查询结果里的 `materialTypeId`

注意：**请求体是数组格式；当前协议写法是在单个对象里传 `locationIds` 数组。**

```json
[
  {
    "associateId": "<commonlyOrderId>",
    "locationIds": ["<locationId1>", "<locationId2>"],
    "materialTypeId": "<materialTypeId>",
    "verifyLocs": null
  }
]
```

## 请求参数

| 字段名 | 类型 | 描述 |
|--------|------|------|
| associateId | guid | 临时实验 ID（`commonlyOrderId`），每个对象都要填写 |
| locationIds | guid[] | 库位 ID 数组，对应命令行里的 `--location-ids` |
| materialTypeId | guid | 物料类型 ID |
| verifyLocs | null | 固定传 `null` |

## 返回示例

```json
{"data": true, "code": 1, "message": "", "timestamp": 1775637122504}
```

`data=true` 表示入库成功。

