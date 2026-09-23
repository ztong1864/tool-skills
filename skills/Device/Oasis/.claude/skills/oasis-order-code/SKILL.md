---
name: oasis-order-code
description: 在 Oasis 中新建实验并获取新的 orderCode。当用户要“新建实验、创建新的实验单、开始一条新的实验流程、获取实验编号”时调用本技能；如果实验已经存在，只是要查询流程、入库或保存进度，不要重复调用它，会覆盖掉先前创建完成的实验。
when: 当任务需要创建一个全新的实验记录并生成唯一 orderCode 时调用；已有 orderCode 的后续操作应使用其他 Oasis 子技能。
---
# 新建实验：获取实验编号

## 说明

通过 `scripts/call.py` 获取一个唯一的新实验编号（orderCode），格式为 `BSO + 年月日 + 序号`，例如 `BSO2026041500001`。
**获取到的 `orderCode` 是后续所有步骤的必要参数，必须保存好。**

---

## 直接调用（推荐）

技能内置了 Python 脚本，直接调用即可：

```bash
# 获取实验编号（默认输出）
python skills/oasis-order-code/scripts/call.py

# 只输出 orderCode 字符串（方便赋值给变量）
python skills/oasis-order-code/scripts/call.py --only-data

# 输出完整 JSON 响应
python skills/oasis-order-code/scripts/call.py --json-output
```

通常只需要传递本技能自己的业务参数；本技能默认会直接访问 API。只有在明确需要改回“通过 SSH 在远端执行 curl”时，才追加 `--use-ssh`；如果还需要切换 SSH 主机、账号、密码、端口或超时时间，再追加：

```bash
--ssh-host <IP> --ssh-user <用户名> --ssh-password <密码> --ssh-port <端口> --ssh-timeout <秒>
```

**依赖安装（首次使用）**
```bash
pip install paramiko
```

**输出示例**
```text
[OK] 实验编号: BSO2026041500001
```

---

## 返回参数

| 字段名 | 类型 | 描述 |
|--------|------|------|
| code | int | 1=成功，0=失败 |
| message | string | 失败时的错误信息 |
| data | string | 实验编号，例如 `BSO2026041500001` |
| timestamp | long | 时间戳 |

**返回示例**
```json
{
  "code": 1,
  "message": "Ok",
  "data": "BSO2026041500001",
  "error": null,
  "timestamp": 1775635894878,
  "path": "/api/order/order/order-code"
}
```
---

## 强制前置规则补充

- 在调用本技能之前，必须先执行一次 `oasis-reset-location`。
- 这是“新建实验”的固定前置步骤，不是可选建议。
- 即使在同一段对话里刚刚新建过别的实验、刚刚做过一次位置重置，只要现在要再新建一个实验，也必须重新执行一次 `oasis-reset-location`。
- 如果还没做位置重置，不要直接获取 `orderCode`，应先切到 `oasis-reset-location`。

