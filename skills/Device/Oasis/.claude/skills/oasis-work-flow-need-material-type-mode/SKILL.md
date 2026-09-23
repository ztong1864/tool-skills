---
name: oasis-work-flow-need-material-type-mode
description: 查询 Oasis 某个工作流或子工作流所需的物料类型。当用户要弄清楚“这个流程需要样品、试剂还是耗材，各自是否需要”时调用本技能；如果目标已经变成找具体库位或执行入库，就应该转去后续技能。
when: 当需要在执行前确认某个流程的物料需求类型时调用；它负责回答“需要什么物料”，不负责回答“放到哪里”或“怎么入库”。
---
## 直接调用（推荐）

```bash
python skills/oasis-work-flow-need-material-type-mode/scripts/call.py --id <subWorkflowId>

# 只输出 data 字段
python skills/oasis-work-flow-need-material-type-mode/scripts/call.py --id <subWorkflowId> --only-data

# 输出完整 JSON
python skills/oasis-work-flow-need-material-type-mode/scripts/call.py --id <subWorkflowId> --json-output
```

通常只需要传递本技能自己的业务参数，例如 `--id`。脚本默认会直接访问 API；只有在明确需要改回“通过 SSH 在远端执行 curl”时，才追加 `--use-ssh`。如还需要切换 SSH 主机、账号、密码、端口或超时时间，再追加：

```bash
--ssh-host <IP> --ssh-user <用户名> --ssh-password <密码> --ssh-port <端口> --ssh-timeout <秒>
```

## 别名提醒

- 这里命令行参数名叫 `--id`
- 这个 `id` 实际上就是 `subWorkflowId`
- 不是父工作流 `workflowId`

## 返回说明

```json
{
  "code": 1,
  "message": "Ok",
  "data": "101",
  "error": null,
  "timestamp": 1775636268002
}
```

`data` 是一个三位字符串：
- 第 1 位表示样品是否需要
- 第 2 位表示试剂是否需要
- 第 3 位表示耗材是否需要

一般约定为：`1` 表示需要，`0` 表示不需要。

