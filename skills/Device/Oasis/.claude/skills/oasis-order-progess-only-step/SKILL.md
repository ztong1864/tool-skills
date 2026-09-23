---
name: oasis-order-progess-only-step
description: 在样品、试剂或耗材入库完成后，仅同步实验当前所处的步骤号。适合“入库结束，把实验推进到某一步”这类轻量更新；如果需要重写整条实验流程或完整步骤内容，不要用它，应改用覆盖保存的 oasis-order-progess。
when: 当用户只需要在入库后把实验步骤更新到指定 step，而不是整体覆盖实验流程时调用。
---
## 直接调用（推荐）

```bash
python skills/oasis-order-progess-only-step/scripts/call.py \
  --order-code <orderCode> \
  --order-name "实验名称" \
  --step <step>

# 输出完整 JSON
python skills/oasis-order-progess-only-step/scripts/call.py ... --json-output
```

通常只需要传递本技能自己的业务参数，例如 `--order-code`、`--order-name`、`--step`。脚本默认会直接访问 API；只有在明确需要改回“通过 SSH 在远端执行 curl”时，才追加 `--use-ssh`。如还需要切换 SSH 主机、账号、密码、端口或超时时间，再追加：

```bash
--ssh-host <IP> --ssh-user <用户名> --ssh-password <密码> --ssh-port <端口> --ssh-timeout <秒>
```

## 请求参数

| 字段名 | 类型 | 描述 |
|--------|------|------|
| step | int | 3/4/5 等步骤号，3 表⽰样品放置完成， 4 表示试剂已放置完成， 5 表示耗材已放置完成 |
| orderCode | string | 实验编号 |
| orderName | string | 实验名称 |
| materialParameter | null | 固定传 `null` |

## 返回说明

```json
{
  "data": {"orderCode": "BSO2026041500001", "currentStep": 3},
  "code": 1
}
```

