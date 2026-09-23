---
name: oasis-reset-location
description: 在 Oasis 中执行位置重置。当用户明确要求“重置位置、重置库位、执行 reset-location、把 location 状态恢复”这类动作时调用本技能；它会直接调用 `/api/storage/location/reset-location`，不负责查询空位、不负责入库，也不负责保存实验步骤。
when: 当目标是执行位置重置本身时调用；如果用户还在查库位、查物料、查预分样结果或做实验步骤保存，不要误用本技能。
---
# 执行位置重置

## 直接调用（推荐）

```bash
python skills/oasis-reset-location/scripts/call.py

# 输出完整 JSON
python skills/oasis-reset-location/scripts/call.py --json-output
```

通常只需要直接运行脚本即可。脚本默认会直接访问 API；只有在明确需要改回“通过 SSH 在远端执行 curl”时，才追加 `--use-ssh`。如还需要切换 SSH 主机、账号、密码、端口或超时时间，再追加：

```bash
--use-ssh --ssh-host <IP> --ssh-user <用户名> --ssh-password <密码> --ssh-port <端口> --ssh-timeout <秒>
```

## 请求说明

- 请求方法：`POST`
- 接口路径：`/api/storage/location/reset-location`
- 当前技能不要求额外业务参数

## 使用提醒

- 本技能会直接执行位置重置动作。
- 不要把它误当成查询接口或入库接口。
- 如果用户只是想确认某个库位状态，先用查询类技能，不要直接重置。
---

## 新建实验前置规则补充

- 本技能除了用于用户显式要求“重置位置”外，还是所有新建实验流程的强制前置步骤。
- 只要接下来要走“新建实验”链路，就应先执行本技能，再去 `oasis-order-code`。
- 这个规则对同一段对话里的重复新建同样生效；每新建一个新的实验，都要重新执行一次本技能。
