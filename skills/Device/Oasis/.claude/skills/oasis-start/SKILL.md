---
name: oasis-start
description: 在 Oasis 中真正启动实验执行。这个技能会触发真实实验或仪器运行，只能在用户已经明确授权“开始执行、现在启动、确认开跑”之后调用；如果用户只是查询信息、准备参数、分配库位、入库或保存步骤，绝不能提前调用它。
when: 仅在用户对启动实验给出明确确认后调用；任何含糊表达、推测意图或准备阶段都不能使用本技能。
---
## 直接调用（推荐）

```bash
python skills/oasis-start/scripts/call.py --material-ids <id1> <id2> <id3> --confirm

# 输出完整 JSON
python skills/oasis-start/scripts/call.py --material-ids <id1> <id2> <id3> --confirm --json-output
```

通常只需要传递本技能自己的业务参数，例如 `--material-ids` 和 `--confirm`。脚本默认会直接访问 API；只有在明确需要改回“通过 SSH 在远端执行 curl”时，才追加 `--use-ssh`。如还需要切换 SSH 主机、账号、密码、端口或超时时间，再追加：

```bash
--ssh-host <IP> --ssh-user <用户名> --ssh-password <密码> --ssh-port <端口> --ssh-timeout <秒>
```

## 别名提醒

- `materialIds`：这里要传的是样品/物料主 ID 列表
- 在预分样结果里，这个 ID 往往叫 `holdMId`
- 也可以把它理解成“当前要启动实验的 materialId 列表”
- 这个脚本要求显式加 `--confirm` 才会真正执行

## 请求参数

| 字段名 | 类型 | 描述 |
|--------|------|------|
| materialIds | guid[] | 物料 ID 列表，是 `oasis-pre-distribute-sample` 技能返回的 `holdMId` |

## 返回说明

```json
{"data": null, "code": 1, "message": "成功", "timestamp": 1775638291766}
```

