# Process: 新建实验标准流程
id: process-new-experiment-standard
description: 用于在 Oasis 平台中创建一个新实验并推进到可启动状态的标准流程实例。本流程进参与实验流程在绿洲系统的创建，通过板子，仪器，或者位置的 id 来创建实验流程，不涉及具体的实验物料的配置，比如对照组，浓度等等。仅仅按照以下流程完成实验流程创建即可。**注意，用户并不知道任何 id，包括耗材id，样本id，materialId 等等，不要询问用户任何关于 id 的问题。只要用户要求在绿洲实验平台新建实验，你只需要按照流程，通过 API 接口，在新建实验的过程中，一步一步了解到各个 id。然后向用户展示相应的关键信息，让用户决策即可。** 物料目前由人工放置，你不用询问实验细节，直接在平台中新建实验就可以了。

用户通常会以“新建实验”，“执行实验”，“新建实验流程”等方式要求你来新建实验流程。并且通过技能执行实验仅仅只是把实验推流到系统上去，还需要人工进一步审核，当然这一步也可能跳过，系统会默认通过所有上传的实验流程。所以这一步具体是如何的你不用考虑，只需要在使用技能 `oasis-start` 后会把实验推到系统中，如果成功上传实验，那么告诉用户“实验执行成功”即可。

**新建实验时每次只能新建一个实验，如果新建一个实验后没有执行，然后新建另一个实验，会把之前的实验流程覆盖掉。**

# 新建实验标准流程

该流程主要是统一通过各技能目录下的 `scripts/call.py` 调用。对你来说，重点是命令格式、关键参数和请求体结构，不需要关心底层端口、SSH 或具体接口转发方式。

相关技能字符串变量的编译均为 `utf-8`。
---

## 技能列表（名称以实际目录为准）

| 技能目录名 | 说明 |
|-----------|------|
| `Oasis-order-code` | 获取新实验编号 |
| `Oasis-experiment-plan` | 生成给用户看的实验方案、物料清单与结果分析设计 |
| `Oasis-workflow-category-label` | 获取工作流列表 |
| `Oasis-sub-workflow` | 获取子工作流步骤参数 |
| `Oasis-work-flow-need-material-type-mode` | 获取工作流所需物料类型 |
| `Oasis-order-progess` | 保存实验步骤（覆盖更新） |
| `Oasis-order-progess-only-step` | 绑定库位后仅同步当前步骤 |
| `Oasis-empty-location-by-type` | 获取物料可绑定的库位 |
| `Oasis-material-and-in-by-location` | 物料绑定库位 |
| `Oasis-pre-distribute-sample` | 获取已分配的样品信息，并可输出 `{"materialId":"holdMName"}` 映射 |
| `Oasis-reset-location` | 在新建实验前重置位置，保证后续空库位查询可用 |
| `Oasis-start` | 使用样品 `materialIds` 开始实验（会触发真实实验执行或仪器运行） |

---

## 调用方式

**每个技能都内置了 `scripts/call.py`，直接运行即可。**

```bash
# 格式示例
python skills/<技能目录名>/scripts/call.py [参数]

# 查看帮助
python skills/<技能目录名>/scripts/call.py --help
```

默认情况下，Agent 只需要传递该技能对应的业务/API 参数，脚本会直接访问 API，不需要额外关心 SSH 连接参数。只有在明确需要改回“通过 SSH 在远端执行 curl”时，才追加 `--use-ssh`；如果目标 SSH 主机、账号、密码、端口或超时时间也需要切换，再额外追加：

```bash
--ssh-host <IP> --ssh-user <用户名> --ssh-password <密码> --ssh-port <端口> --ssh-timeout <秒>
```

## 执行节奏

只要进入真实执行链，就必须遵守下面这些规则：

- 如果某一步失败、返回异常，或返回内容不足以支持下一步，立即向用户汇报。
- 尤其在“分配库位”这一步，如果没有分配到可用库位，必须立即停止；不要继续绑定库位、不要继续保存步骤、不要继续启动实验。
- 如果分配库位结果为空（这一步往往在创建实验过程中出现，不要在创建实验前向用户索要 id）、数量不足，或缺少后续必需的 `locationId` / `materialTypeId`，必须先把问题告诉用户，等待用户决定是否继续或改方案。
- 不要跳过步骤，因为跳过步骤会导致之后的步骤返回结果为空。
- `Oasis-start` 仍然要求单独确认；即使前面每一步都确认过，真正启动实验前也必须再确认一次。

## 字段别名与同义 ID

Oasis 不同接口里，很多字段实际指向的是同一个业务对象，但名字不完全一样。调用时要按“语义”对齐，不要只按字面名字机械匹配。

| 语义 | 常见字段名 / 参数名 | 说明 |
|------|---------------------|------|
| 工作流 ID | `workflowId` | 在工作流列表接口里，通常指父工作流 ID |
| 子工作流 ID | `subWorkflowId`、`workflowId`（在部分保存类接口里） | **最容易混淆。** 在 `Oasis-order-progess` 这类接口中，请求体里的 `workflowId` 实际上要填子工作流 ID，也就是别处的 `subWorkflowId` |
| 子工作流名称 | `workflowName`、`subWorkflowName` | 在保存类接口里通常叫 `workflowName`，但它对应的是子工作流名称 |
| 临时实验 ID | `commonlyOrderId`、`associateId`、`--order-id`、`data.id` | 这些通常是同一个 ID。`Oasis-order-progess` 返回的 `data.id`，后续在别的接口里可能叫 `commonlyOrderId` 或 `associateId` |
| 样品 / 物料主 ID | `holdMId`、`materialId`、`materialIds` | 语义上都和“物料 ID / 样品 ID”相关。预分样结果里的 `holdMId`，后续启动实验时通常要作为 `materialIds` 传入 |
| 物料名称 | `holdMName`、`materialName` | 在预分样结果里，`holdMName` 是辨识当前药物 / 物料名称的关键字段；如果要把药物名称对回执行时真正要传的 `materialId`，优先使用 `Oasis-pre-distribute-sample --material-name-map` |
| 物料类型 ID | `materialTypeId`、`holdMTypeId` | 前者常用于分配库位、绑定库位；后者常出现在已分配样品或库位结果中，表示当前持有物料的类型 ID |
| 库位 ID | `locations[].id`、`locationId`、`id`（在部分库位对象里） | 空库位查询返回里常见 `locations[].id`；后续入库请求里通常叫 `locationId` |

### 快速记忆

- `workflowId` 不一定总是父工作流 ID；在保存实验步骤时，它往往要填“子工作流 ID”
- `data.id` 经常就是后续接口要用的 `commonlyOrderId` / `associateId`
- `holdMId` 通常可以理解成“这个样品当前真正的 materialId”
- 药物名称和执行用 `materialId` 的对应关系，优先从 `Oasis-pre-distribute-sample --material-name-map` 获取

## 可编辑流程参数

如果用户要调整实验流程里的可变参数，参数源头在 `Oasis-sub-workflow`，保存动作在 `Oasis-order-progess`。

- 先运行 `Oasis-sub-workflow --id <subWorkflowId> --only-data` 获取完整 `parameters` JSON 对象。
- 只修改其中 `parameterList` 里 `type` 为 `"Editable"` 的参数，通常改 `value` 字段。
- 不要修改 `type` 为 `"Hidden"` 的参数，也不要破坏原始 JSON 结构。
- 修改完成后，把完整 JSON 对象保存成本地文件，再用 `Oasis-order-progess --parameters-file <file>` 覆盖保存。

## 关键 ID 传递链

**每完成一个步骤，API 所返回的参数都要记录下来，之后的步骤和后续的调试都要用到**

```text
Oasis-reset-location
    -> 先重置位置，保证后续空库位查询可用
            -> Oasis-order-code
    -> orderCode（实验编号，全流程必需）
            -> Oasis-workflow-category-label
    -> subWorkflowId（子工作流 ID，注意不是父工作流 ID）
    -> workflowName（这里保存的是子工作流名称）
            -> Oasis-sub-workflow --id <subWorkflowId>
    -> data 字段
    -> 序列化为字符串
    -> 作为 parameters 传入 Oasis-order-progess
            -> Oasis-work-flow-need-material-type-mode --id <subWorkflowId>
    -> materialTypeMode 字符串（例如 "101"）
    -> 决定哪些物料需要绑定库位
            -> Oasis-order-progess（**请求体里的 workflowId 实际要填 subWorkflowId**）
    -> commonlyOrderId（临时实验 ID，即 data.id，后续绑定库位必需）
            -> Oasis-empty-location-by-type --workflow-id <subWorkflowId> --order-id <commonlyOrderId>
    -> locationId（data[].locations[].id）
    -> materialTypeId（data[].materialTypeId）
            -> Oasis-material-and-in-by-location
    -> 绑定库位成功（data=true）
            -> Oasis-order-progess-only-step（step=3/4/5）
    -> 记录绑定库位完成状态
            -> Oasis-pre-distribute-sample --associate-id <commonlyOrderId>
    -> holdMId（已分配样品 ID，语义上可视为 materialId）
    -> 可选：--material-name-map 输出 {"materialId":"holdMName"}，用于把药物名称映射回执行用 materialId
            -> Oasis-start --material-ids <holdMId>
```

---

## 新建实验完整流程

**新建实验需要严格按照以下步骤执行，用户有时会要求到仅仅执行到某一步，但是之前的步骤必须严格执行，非特殊情况可以直接执行到预分配样本**

**前四个阶段非特殊情况可以直接执行，无需向用户确认**

**不要擅自跳过任何一个步骤去执行下一步，因为这回导致之后的步骤返回结果为空**

### 阶段 1：初始化

**步骤 1：重置位置**
在获取 `orderCode` 之前必须先执行一次 `Oasis-reset-location`。

```bash
python skills/Oasis-reset-location/scripts/call.py
```

**步骤 2：获取实验编号**
```bash
python skills/Oasis-order-code/scripts/call.py --only-data
# 输出：BSO2026041500001
# 保存为 orderCode
```

**步骤 3：获取工作流列表，选择目标流程**
```bash
python skills/Oasis-workflow-category-label/scripts/call.py
# 从输出中找到目标工作流，记录：
#   subWorkflowId（后续所有步骤都用这个 ID）
#   workflowName（子工作流名称）
```

**步骤 4：获取工作流步骤参数（作为 parameters）**
```bash
python skills/Oasis-sub-workflow/scripts/call.py --id <subWorkflowId> --only-data > params_data.json
# --only-data 输出的内容就是 Oasis-order-progess 所需的 parameters 值（JSON 对象）
```

**步骤 5：获取物料需求**
```bash
python skills/Oasis-work-flow-need-material-type-mode/scripts/call.py --id <subWorkflowId> --only-data
# 输出例如 "101"：第 1 位=样品，第 2 位=试剂，第 3 位=耗材（1=需要，0=不需要）
```

**步骤 6：保存初始实验步骤**
```bash
python skills/Oasis-order-progess/scripts/call.py \
  --order-code <orderCode> \
  --order-name "实验名称" \
  --workflow-id <subWorkflowId> \
  --workflow-name <workflowName> \
  --parameters-file params_data.json
# workflow-id 必须填子工作流 ID，不是父工作流 ID
# 返回 commonlyOrderId（data.id），后续绑定库位必需，务必保存
```

---

### 阶段 2：需要样品时执行，样品库位绑定

**步骤 7：如果实验需要样品，分配样品库位**
```bash
python skills/Oasis-empty-location-by-type/scripts/call.py \
  --workflow-id <subWorkflowId> \
  --order-id <commonlyOrderId> \
  --type 1 \
  --count <数量>
# 记录：locationId（data[].locations[].id）、materialTypeId（data[].materialTypeId）
```

执行完本步后，必须先检查是否真的分配到了可用库位。

- 如果没有分配到库位、数量不足，或缺少 `locationId` / `materialTypeId`，立即停止并向用户汇报。
- 只有在库位分配结果完整且用户确认继续后，才能执行步骤 8。

**步骤 8：如果实验需要样品，样品库位绑定**
```bash
python skills/Oasis-material-and-in-by-location/scripts/call.py \
  --order-id <commonlyOrderId> \
  --location-ids <locationId> \
  --material-type-id <materialTypeId>
```

**步骤 9：同步样品库位绑定状态**
```bash
python skills/Oasis-order-progess-only-step/scripts/call.py \
  --order-code <orderCode> --order-name "实验名称" --step 3
```

---

### 阶段 3：需要试剂时执行，试剂库位绑定

**步骤 10：如果实验需要试剂，分配试剂库位**
```bash
python skills/Oasis-empty-location-by-type/scripts/call.py \
  --workflow-id <subWorkflowId> --order-id <commonlyOrderId> --type 2
```

执行完本步后，同样必须先检查是否真的分配到了可用库位；如果没有分配到，立即停止并向用户汇报。

**步骤 11：如果实验需要试剂，试剂库位绑定**
```bash
python skills/Oasis-material-and-in-by-location/scripts/call.py \
  --order-id <commonlyOrderId> --location-ids <locationId> --material-type-id <materialTypeId>
```

**步骤 12：同步试剂库位绑定状态**
```bash
python skills/Oasis-order-progess-only-step/scripts/call.py \
  --order-code <orderCode> --order-name "实验名称" --step 4
```

---

### 阶段 4：需要耗材时执行，耗材库位绑定

**步骤 13：如果实验需要耗材，分配耗材库位**
```bash
python skills/Oasis-empty-location-by-type/scripts/call.py \
  --workflow-id <subWorkflowId> --order-id <commonlyOrderId> --type 0
```

执行完本步后，同样必须先检查是否真的分配到了可用库位；如果没有分配到，立即停止并向用户汇报。

**步骤 14：如果实验需要耗材，耗材库位绑定**
```bash
python skills/Oasis-material-and-in-by-location/scripts/call.py \
  --order-id <commonlyOrderId> --location-ids <locationId> --material-type-id <materialTypeId>
```

**步骤 15：同步耗材库位绑定状态**
```bash
python skills/Oasis-order-progess-only-step/scripts/call.py \
  --order-code <orderCode> --order-name "实验名称" --step 5
```

启动实验需要传入样品 `materialIds`。如果用户只给了 `orderCode`、`commonlyOrderId` 或 `associateId`，不能直接调用 `Oasis-start`，必须先查询已分配样品。

**步骤 16：查询已分配样品，获取 MaterialId**

需要在**样品绑定库位**后才能查询到。
所以不需要提前查询预分配结果。

```bash
python skills/Oasis-pre-distribute-sample/scripts/call.py \
  --associate-id <commonlyOrderId> --only-data
# 从返回结果中取 holdMId
# holdMId 就是启动实验需要传入的样品 MaterialId
```

执行完本步后，先向用户汇报 `holdMId` 和必要时的药物名称映射，再确认是否继续启动实验。

如果需要确认“这次执行的 materialId 对应哪种药物”，应优先追加：

```bash
python skills/Oasis-pre-distribute-sample/scripts/call.py \
  --associate-id <commonlyOrderId> --material-name-map
# 输出格式：{"materialId":"holdMName"}
# 用于把药物名称映射回执行时真正要传的 materialId
```

---

### 阶段 5：启动实验

**步骤 17：启动实验**
```bash
python skills/Oasis-start/scripts/call.py \
  --material-ids <holdMId> --confirm
```
---

## 新建实验强制规则补充

- 只要目标是“新建实验”或“开始一条新的实验流程”，在获取 `orderCode` 之前必须先执行一次 `Oasis-reset-location`。
- 这个规则对同一段对话里的每一次新建实验都生效。不要因为前面已经新建过一次、已经做过一次位置重置，或者当前上下文里保留了旧的实验信息，就跳过这一步。
- 如果用户在同一段对话里连续新建多个实验，每新建一个实验，都要重新执行一遍：`Oasis-reset-location` -> `Oasis-order-code` -> 后续步骤。
- `Oasis-reset-location` 是新建实验链路的强制前置步骤，不是可选建议。

## 创建实验流程时的参数边界说明

- 创建实验流程时，重点是按 API 已暴露的参数完成流程创建、步骤保存、绑定库位推进与启动实验。
- 如果 API 接口本身没有提供对应参数填写位置，就不要把额外的实验设计细节当作创建实验流程的前置必填项。
- 这类不应在“创建实验流程”阶段强制要求填写的细节包括但不限于：细胞模型、板型、给药设计、对照设置等。
- 上述内容可以属于实验设计、方案说明或线下执行约束，但不是当前新建实验 API 链路中的必填字段。
- 因此，在面向 Oasis 新建实验接口执行时，应避免因为缺少这些字段而阻塞创建流程；只有当具体接口明确要求某个参数时，才将其视为必填。
