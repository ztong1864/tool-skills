---
name: fdu-risk-review
description: FDU 实验规划阶段的危险化合物审查 skill。用于候选条件推荐、投料量计算、编号实验步骤生成之后、对应用户确认之前，只检查规划产物里的物料（以及它们混合或反应时明显会生成的物质）是否属于危险化合物；不审查步骤顺序、后处理、用量写法、设备能力等实验细节，不生成推荐、不计算用量、不编写实验步骤、不生成协议 JSON，也不提交设备任务。
---

# fdu-risk-review

本 skill 是 FDU 实验自动化流程中规划阶段的危险化合物审查。

它由 ontology 规则 `rule:risk-review-after-planning-output` 在以下规划产物生成后、对应用户确认前触发：

- `task-step:recommend-experiment-conditions`
- `task-step:calculate-reagent-amounts`
- `task-step:generate-numbered-steps`

## 审查范围

只审查一件事：规划产物里出现的物料——底物、试剂、催化剂、添加剂、溶剂、内标和后处理用的液体——以及它们混合或反应时
明显会生成的物质，是否属于 `references/risk_knowledge_base.md` 列出的危险化合物。

以下是实验细节，不在审查范围内：不写进 findings，不作为 `block` 或 `needs_human_review` 的理由，也不拿来问用户。

- 步骤顺序、是否写了冷却、搅拌转速和时长、后处理和内标的写法，以及这些内容来自模板还是用户；
- 步骤里多出或缺少的文字、某组比其他组少一步或少一项物料；
- 用量大小、单位写法、加样精度、反应瓶和装液量；
- 设备动作、模块、资源和协议字段（后面的步骤会校验）；
- 条件有没有文献依据、推荐是否合理、预期产率；
- 溶剂沸点（只作提示，见审查流程第 4 步）。

用户在每一步的确认点自己判断这些细节；本 skill 不因为它们中断流程。

## 输入

- 当前阶段的规划产物：推荐表、投料量表或编号步骤（每组一份）
- 用户实验请求或 `artifact:constraint-json`（看物料清单）
- `references/risk_knowledge_base.md`：危险化合物分级
- `KB/solvent_boiling_points.csv`：常用溶剂沸点（沸点检查脚本读取）

## 审查流程

1. 读取 `references/risk_knowledge_base.md`。
2. 列出当前产物里全部组用到的物料，加上它们组合时明显会生成的物质（例如氰化物遇酸生成 HCN）。
3. 逐一对照知识库的分级（用化学常识判断一种物质是否属于某一类，例如叠氮化钠属于叠氮化物）：
   - 第一级（严重急性危害）：用户在本任务里还没有明确确认密闭、防护措施并批准时给 `block`；已经确认的给 `pass`，findings 写“用户已确认”。
   - 第二级（高危，需要确认防护）：用户在本任务里还没有确认过这种物质的防护和处理时给 `needs_human_review`，只问这一次；已经确认的给 `pass`。
   - 不属于这两级的物质：`pass`。不要因为“无法核实 SDS”“危害等级未知”给 `needs_human_review`。
4. 审查条件推荐或投料量时运行沸点检查（只读，输出 JSON）：`python <本技能目录>/scripts/check_boiling_points.py --table <推荐 CSV 或投料量 CSV> --constraints <约束 JSON>`。它的 `result` 为 `block` 时，把 `message` 原样作为一行“提示（不影响结论）：……”写进 findings；verdict 仍只按危险化合物判断。`result` 为 `pass` 或 `needs_human_review` 时什么都不写。
5. 输出简短结论。

## 不再拿来问用户的内容

- 用户在这项任务里已经确认过的事实（例如“已按 SDS 或实验室 SOP 审核相容性和防护要求”）：findings 写“用户已确认”，不作为 `needs_human_review` 的理由。
- 重新审查（用户已经回答上一轮的问题或修改了条件）时，上一轮的问题已经有了答案：只有出现新的危险化合物时才给 `needs_human_review` 或 `block`，否则给 `pass`。

## 在 LabOntology 中登记审查结果

- `pass`：`resume --agent-completed --summary "<审查结果>"`。
- `needs_human_review`：同样用 `resume --agent-completed --summary "<审查结果>"`，required_action 写 `ask_user：<要用户确认的防护或处理>`。Runtime 在这次审查后的确认点把问题和“是否继续”一起交给用户，用户回复一次即可；不要用 `--agent-failed` 登记。
- `block`：`resume --agent-failed --summary "<审查结果>"`。Runtime 请用户修改，用户回复后先按修改重跑被审查的 skill，再审查一次；再审查通过时直接进入下一步，不再为同一步确认。

## 输出格式

```text
verdict: pass | needs_human_review | block
stage: <当前 TaskStep id 或简短阶段名>
checked: hazardous_compounds
findings:
- <危险化合物、所属级别和涉及的组号，或 none>
required_action:
- <continue | ask_user | revise_input>：<用户下一步应该做什么>
```

`verdict:` 和它的取值保持英文（Runtime 按它判断审查是否通过）；findings 和 required_action 的内容用中文写：审查结果会作为问题的一部分直接给用户看（在 LabOntology 中它就是 `--summary`）。

审查之后向用户汇报时（不论 `pass`、`needs_human_review` 还是 `block`），先完整列出被审查的结果，再写结论：条件推荐列出全部推荐组（带组号的表格，见 literature-experiment-recommender 的“在回复里列出推荐表”），投料量列出投料量表，编号步骤按组列出步骤；有危险化合物时标出是哪几组。结论是 `pass` 时只写“未发现危险化合物”，不要再附加对实验细节的意见或问题。

判定规则：

- `pass`：没有知识库所列的危险化合物，或其防护已由用户确认。绝大多数规划产物应是这个结论。
- `needs_human_review`：出现第二级物质，且用户还没有确认它的防护和处理。
- `block`：出现第一级物质（或物料组合明显会生成第一级物质），且用户没有明确确认密闭、防护措施并批准。
