---
name: oasis-pre-distribute-sample
description: 查询 Oasis 中某个临时实验已经分配好的样品信息。当用户已经拿到了 commonlyOrderId / associateId，想看“已分配样品是什么、对应哪个库位、样品 ID 是什么、预分样结果长什么样”时调用本技能；不要把它误当成入库接口或步骤保存接口。
when: 当目标是根据 associateId 查询预分样结果时调用；它只负责读取已分配样品，不负责执行入库、不负责保存步骤，也不负责启动实验。
---
# 获取已分配的样品

## 直接调用（推荐）

```bash
python skills/oasis-pre-distribute-sample/scripts/call.py --associate-id <commonlyOrderId>

# 只输出 data 字段
python skills/oasis-pre-distribute-sample/scripts/call.py --associate-id <commonlyOrderId> --only-data

# 只输出 materialId / holdMId 到 holdMName 的映射
python skills/oasis-pre-distribute-sample/scripts/call.py --associate-id <commonlyOrderId> --material-name-map

# 输出完整 JSON
python skills/oasis-pre-distribute-sample/scripts/call.py --associate-id <commonlyOrderId> --json-output
```

通常只需要传递本技能自己的业务参数，例如 `--associate-id`。脚本默认会直接访问 API；只有在明确需要改回“通过 SSH 在远端执行 curl”时，才追加 `--use-ssh`。如还需要切换 SSH 主机、账号、密码、端口或超时时间，再追加：

```bash
--ssh-host <IP> --ssh-user <用户名> --ssh-password <密码> --ssh-port <端口> --ssh-timeout <秒>
```

## 请求参数

| 字段名 | 类型 | 描述 |
|--------|------|------|
| associateId | string | 临时实验 ID，也就是 `commonlyOrderId` |

## 别名提醒

- `associateId`：和别处的 `commonlyOrderId`、命令行里的 `--order-id` 是同一个 ID
- 返回里的 `holdMId`：语义上就是当前已分配样品的主 `materialId`
- 后续如果要启动实验，通常要把这里的 `holdMId` 作为 `materialIds` 传给 `oasis-start`
- `--material-name-map`：把返回体里出现的多个 `holdMId` / `materialId` 与 `holdMName` 整理成字典，格式为 `{"materialId":"holdMName"}`

## 返回说明

返回的是已分配样品所在库位及样品详情对象。重点字段包括：

- `id`：库位 ID
- `code`：库位编码
- `holdMId`：已分配样品 ID，与 `materialId` / `materialIds` 语义一致
- `holdMName`：已分配样品名称
- `holdMBarcode`：样品条码
- `holdMCode`：样品编码
- `holdMTypeId` / `holdMTypeName`：样品类型
- `material`：样品主对象详情
- `detail[]`：样品明细列表
- `--material-name-map` 输出：把返回体中出现的多个 material 信息整理成字典，便于后续把药物名称映射回执行时要用的 `materialId`

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "code": "2-10",
  "holdMId": "3a207e65-25d1-9fc7-9bdb-77c8202df2d9",
  "holdMName": "string",
  "holdMBarcode": "string",
  "holdMCode": "string",
  "holdMTypeId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "holdMTypeName": "string",
  "material": {},
  "detail": []
}
```

如果使用 `--material-name-map`，输出格式示例：

```json
{
  "3a207e65-25d1-9fc7-9bdb-77c8202df2d9": "Drug A",
  "4b207e65-25d1-9fc7-9bdb-77c8202df2da": "Drug B"
}
```

## 使用提醒

- 这里查的是“已经分配好的样品”，不是空库位。
- `holdMId` 很关键，后续如果要启动实验，通常要用到这个样品 ID 列表。
- 如果要把药物名字和执行时真正要传的 `materialId` 对上，优先使用 `--material-name-map`。
- `associateId` 就是临时实验 ID，通常来自 `oasis-order-progess` 返回的 `data.id`。

