---
name: oasis-workflow-category-label
description: 查询 Oasis 中可用的实验流程或工作流列表。当用户还处在“有哪些流程可选、先列出流程、按名称找流程、先选 workflow”阶段时调用本技能；确定了具体流程后，再继续查询子工作流、物料需求或后续执行动作。
when: 当需要先获取流程列表、查找某个实验流程的候选项或确定 workflow 身份时调用；不要把它用于读取单个步骤参数或执行实验动作。
---
# 获取实验流程列表

## 直接调用（推荐）

```bash
# 列出所有工作流（友好摘要）
python skills/oasis-workflow-category-label/scripts/call.py

# 只输出 data 字段 JSON
python skills/oasis-workflow-category-label/scripts/call.py --only-data

# 输出完整 JSON
python skills/oasis-workflow-category-label/scripts/call.py --json-output
```

通常只需要传递本技能自己的业务参数；本技能默认会直接访问 API。只有在明确需要改回“通过 SSH 在远端执行 curl”时，才追加 `--use-ssh`；如果还需要切换 SSH 主机、账号、密码、端口或超时时间，再追加：

```bash
--ssh-host <IP> --ssh-user <用户名> --ssh-password <密码> --ssh-port <端口> --ssh-timeout <秒>
```

**重要输出字段**
- `workflowId`
- `subWorkflowId`

## 别名提醒

- `workflowId`：这里是父工作流 ID
- `subWorkflowId`：这里才是后续大多数执行类接口真正要用的子工作流 ID
- 后续如果进入 `oasis-order-progess`，请求体字段名虽然叫 `workflowId`，但应填这里的 `subWorkflowId`

---

## 返回结构

`data.items[].workflows[]` 每个工作流包含：
- `id` -> `workflowId`
- `name` -> 工作流名称
- `subWorkflows[].id` -> `subWorkflowId`，后续所有步骤使用这个 ID
- `subWorkflows[].name` -> 子工作流名称

