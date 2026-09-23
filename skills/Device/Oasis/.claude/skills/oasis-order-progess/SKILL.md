---
name: oasis-order-progess
description: 在 Oasis 中覆盖保存当前实验流程或步骤状态。它适合“用完整最新状态重写当前实验进度”的场景；这是覆盖更新，不是追加更新，所以只有在你确定要用当前内容整体替换已有步骤时才调用。若只是入库后顺手同步到某一步，优先考虑更轻量的 only-step 技能。
when: 当用户明确要求保存或覆盖更新当前实验步骤，且你持有完整、应被视为最新真值的步骤数据时调用；不要把它当成追加写入接口使用。
---
# 保存实验步骤（覆盖更新）

注意：**这个接口是覆盖更新，会重写整个实验流程，必须谨慎使用。**

## 直接调用（推荐）

```bash
# 新建实验（commonlyOrderId 不传，currentStep 默认 2）
python skills/oasis-order-progess/scripts/call.py \
  --order-code BSO2026041500001 \
  --order-name "AI测试2" \
  --workflow-id 3a1e2d7a-6587-4baf-af10-1f20a3ab5885 \
  --workflow-name "展示20251214-细胞板从固定堆栈" \
  --parameters '{"stepId":[...]}'

# 从文件读取 parameters（推荐，避免引号转义）
python skills/oasis-order-progess/scripts/call.py \
  --order-code BSO2026041500001 \
  --order-name "AI测试2" \
  --workflow-id 3a1e2d7a-... \
  --workflow-name "展示20251214" \
  --parameters-file params.json

# 更新已有实验（需要传 commonlyOrderId）
python skills/oasis-order-progess/scripts/call.py \
  --order-code BSO2026041500001 \
  --order-name "AI测试2" \
  --workflow-id 3a1e2d7a-... \
  --workflow-name "展示20251214" \
  --parameters-file params.json \
  --commonly-order-id 3a207e5b-03c2-5f96-744f-5a21d054fb1f

# 输出完整 JSON
python skills/oasis-order-progess/scripts/call.py ... --json-output
```

通常只需要传递本技能自己的业务参数，例如 `--order-code`、`--workflow-id`、`--workflow-name`、`--parameters-file`。脚本默认会直接访问 API；只有在明确需要改回“通过 SSH 在远端执行 curl”时，才追加 `--use-ssh`。如还需要切换 SSH 主机、账号、密码、端口或超时时间，再追加：

```bash
--ssh-host <IP> --ssh-user <用户名> --ssh-password <密码> --ssh-port <端口> --ssh-timeout <秒>
```

**成功后务必保存返回的 `commonlyOrderId`（即 `data.id`），后续入库步骤必需。**

## 编辑工作流程前先参考结构化文档

如果用户要“编辑工作流程”“调整某个现有模板的参数”“按实验语义改流程”，不要直接盯着 `parameters` 改。先参考：

- `../oasis-ontology/references/workflow-docs/`
- `../oasis-ontology/references/Oasis-结构化MD实体规范.md`

推荐顺序：

1. 在结构化 MD 中确认目标流程每一步的实验语义、设备关系、物料条件和数据产物
2. 用 `oasis-sub-workflow --only-data` 获取原始 `parameters`
3. 只改需要变更的 `Editable` 参数
4. 用本技能整体覆盖保存

结构化 MD 里的 `Step / Condition / Instrument / Data / Relation` 是解释层，不是 Oasis API 请求体字段；不要把这些节点直接拼回 `parameters`。

## 别名提醒

- 请求体里的 `workflowId`：这里虽然字段名叫 `workflowId`，但**必须填写子工作流 ID**，也就是别处的 `subWorkflowId`
- 请求体里的 `workflowName`：这里要填的是子工作流名称，不是父工作流名称
- 返回里的 `data.id`：这就是后续接口要用的 `commonlyOrderId`
- 同一个 ID 在别的接口中可能会改名叫 `associateId` 或命令行参数 `--order-id`

---

## 请求参数

| 字段名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| commonlyOrderId | guid / null | 新建时可为 null，更新时必填 | 临时实验 ID |
| concurrencyStamp | string | 是 | 新建时传 `""` |
| currentStep | int | 是 | 新建时传 `2` |
| orderCode | string | 是 | 实验编号 |
| orderName | string | 是 | 实验名称 |
| parameters | string | 是 | 步骤参数 JSON 字符串，注意引号转义问题 |
| stepMaterialRecords | string | 是 | 物料记录 JSON 字符串，无物料时传 `"{}"` |
| workflowId | guid | 是 | **这里实际填写的是子工作流 ID**，也就是别处的 `subWorkflowId` |
| workflowName | string | 是 | 这里填写的是子工作流名称 |

## parameters 修改规则

`parameters` 来自 `oasis-sub-workflow --id <subWorkflowId> --only-data` 的 `data` 对象。需要改实验流程参数时，推荐先把这个对象保存为本地 JSON 文件，修改后再用 `--parameters-file` 传入。

- `--parameters-file` 指向的文件应保存原始 JSON 对象，不要提前转成带转义的 JSON 字符串；`call.py` 会在请求体里自动序列化成 `parameters` 字符串。
- 只修改 `parameterList` 中 `type` 为 `"Editable"` 的参数，通常改它的 `value` 字段。
- 不要修改 `type` 为 `"Hidden"` 的参数，不要删除 `stepId`、步骤数组、`parameterList` 或其它原始字段。
- 如果只是调整流程参数，不要顺手改 `stepMaterialRecords`；物料记录仍按当前实验实际入库状态处理。
- 这是覆盖保存接口，传入的 `parameters` 会被视为当前完整最新状态，而不是局部补丁。

## 保存前检查

在调用本技能前，至少确认下面几点：

- 目标 `workflowId` 实际上传的是 `subWorkflowId`
- `workflowName` 实际上传的是子工作流名称
- `parameters` 仍然是原始 Oasis JSON 结构
- 被修改的字段确实来自 `Editable`
- 解释性结构化文档内容没有混入请求体

## 返回说明

成功后 `data.id` 即为 `commonlyOrderId`（临时实验 ID）。在其它接口中，这个 ID 也可能叫 `associateId` 或 `order-id`。

```json
{
  "data": {
    "orderCode": "BSO2026041500001",
    "id": "3a207e5b-03c2-5f96-744f-5a21d054fb1f",
    "currentStep": 2
  },
  "code": 1
}
```

