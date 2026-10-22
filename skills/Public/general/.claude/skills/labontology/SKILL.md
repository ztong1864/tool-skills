---
name: labontology
description: >
  Use when a request involves laboratory, chemistry, molecular, experiment,
  protocol, sample, reagent, instrument, device, analysis, readiness,
  paused-task, workflow-library, Skill-selection, workflow-improvement,
  self-evolution, self-improvement, or feedback-driven workflow maintenance
  work. LabOntology MUST be used first as the unified entrypoint and
  supervisor. Do not invoke another laboratory Skill before LabOntology.
  Do not use it for ordinary writing, spreadsheets, images, presentations,
  or general file-generation tasks unless they are part of a laboratory task.
  Not for TRACE Lab / Bayesian-optimization recommendation projects (TRACE,
  贝叶斯优化, 闭环推荐, 推荐下一轮): trace-collab-skill handles those directly.
  Not for lookups with a connected tool (SciGraph, chemistry / protein /
  literature databases) or in a skill's data table (a reagent's CAS or
  density): call the tool or read the table.
  Load it once per turn; once loaded, continue with its Runtime commands and do
  not call this Skill again in the same turn.
---

# LabOntology

LabOntology 是实验任务和实验流程库维护的统一入口，也是任务的监督者：先用它，再由它选择实验 Skill。普通写作、表格、图片、PPT 和一般文件处理不属于它。TRACE Lab（贝叶斯优化闭环推荐：建项目、推荐下一轮、提交结果、证据卡）也不经过它，直接用 trace-collab-skill 和 `trace-collab` 工具，不要为此创建 mission。用已接入的工具查数据（SciGraph 知识图谱、化学 / 蛋白 / 文献数据库等）也不经过它：直接调用工具，同样不创建 mission。在技能自带的数据表里查值（如试剂的 CAS 号、密度、分子式，在 chemical-amount-calculator 的 `KB/chemical_space.csv` 中）也一样：以该技能目录为路径找到表格直接读取，不创建 mission。用户点名的工具不在可用工具里时，不要另找办法替代，告诉用户在 设置 → 密钥管理 配好它的密钥，或在对话的“工具目录”里为本对话开启它，然后再发一次消息。用户不需要知道内部流程，也不需要手动调用其他 Skill。

## 怎么运行

- 在对话的工作目录运行，不要 `cd` 进 Skill 目录（它是多个用户共享的链接）：`python .claude/skills/labontology/scripts/labontology.py <命令>`。
- 缓存目录一律写相对路径 `--cache-dir labontology_workspace_cache`。
- 不需要先运行 `bootstrap`：`run` 和 `inspect` 会自己准备流程库。`bootstrap` 只在用户要求初始化 LabOntology 时运行。

## 核心规则：照着 `do_next` 做

`run`、`act`、`resume`、`context` 的输出都带 `plan_progress`（计划里每一步的进度）和 `do_next`（下一步要运行的完整命令，路径和 id 已经填好）。**照做**，不要额外“再确认一下”：

- 不要重复运行 `context`，不要重新加载本 Skill，不要手敲或改写路径和 id（从输出、`do_next`、附件说明里原样复制）。
- 不要用 Glob / Grep 找 `.claude/skills` 下的文件（它们看不到隐藏目录和链接）；要读实验 Skill 的文档就 Read `do_next` 给出的路径。
- **用户的回复不用你转交**：LabOntology 向用户提问后（确认计划、步骤暂停、`act --ask`），用户的下一条消息就是回答。那一轮直接运行 `do_next` 给出的下一条命令（通常是 `act ... --skill <下一步>`），LabOntology 会把这条消息记为回答；不要运行 `resume --answer`。提问的同一轮里不能开始下一步（会被拒绝）：展示结果、转述问题，结束本轮。命令被拒绝时不要再试同一条命令：按报错或 `do_next` 写回复，然后结束本轮。

## 流程

1. **新的实验请求**：创建 mission，上传的文件用 `--input-artifact 名称=绝对路径`（路径从附件说明原样复制）：
   - **设备有实验流程时，从设备本体的流程开始**：每台设备的本体 Skill（例如 XmartChem 的 fdu-ontology）可以声明这台设备的实验流程：实验 Skill 的顺序、每步之后的审查 Skill、需要用户确认的位置和几个终点。`inspect --cache-dir labontology_workspace_cache --skills` 的 `experiment_flows` 列出它们（`steps` 是流程，⏸ 是确认点，`stops` 是终点及说明）。用户要在这台设备上做实验（准备、方案、协议、提交……）时，用 `run --cache-dir labontology_workspace_cache --goal "<用户目标>" --flow <流程 id> --until <终点> --input-artifact ...` 创建 mission：Runtime 按流程生成计划，带上审查步骤，只在 ⏸ 处暂停。终点按 `stops` 的说明选：用户没说做到哪一步时用 `default_stop`；用户要求提交或创建设备任务才选包含设备提交的终点。不要自己用 `--plan` 拼这类流程，也不要省略审查步骤（`--plan` 列的全是流程里的步骤时，Runtime 也会按流程补上审查和 ⏸ 暂停）。然后 `act ... --ask-plan`，把 `pending_ticket.question` 转告用户，**结束本轮**。
   - 用户按顺序列了多个步骤（“先…再…然后…最后…”），而设备没有对应的实验流程：先用 `inspect --cache-dir labontology_workspace_cache --skills` 看有哪些实验 Skill，再 `run --cache-dir labontology_workspace_cache --goal "<用户目标>" --plan id1,id2,... --input-artifact ...`（`--plan` 按用户的顺序列 Skill id，不要加用户没要求的步骤，例如设备提交）。用户要求在关键步骤暂停或确认（“在关键步骤暂停等我确认”）时也这样建计划，每一步完成后都会停下。然后 `act ... --ask-plan`，把 `pending_ticket.question` 转告用户，**结束本轮**。
   - 确认点可以选定条件（例如只用第 1、2 组），后面的步骤只处理选定的条件。
   - 单个目标：直接 `run ... --goal "<用户目标>"`（不用先 `inspect`），再照 `do_next`。
2. **用户的下一条消息回答了你的问题**（确认、选择、补充信息、重新上传文件……）：运行 `do_next` 给出的下一条命令，例如 `act ... --skill <下一步>`；用户要停止就 `act ... --cancel`。LabOntology 把这条消息记为回答，不需要 `resume --answer`。消息说的是别的事时，直接回答，mission 保持等待。mission 正在等待回答时，`run` 会被拒绝并告诉你原 mission 的下一步。新上传的文件不会自动交给 mission：执行需要这个文件的实验 Skill 时，用 `act ... --skill <id> --input <输入 id>=<附件路径>` 交给它。
3. **执行实验 Skill**：`act ... --skill <id>`（Runtime 自己写决策并登记 Skill 文档）。mission 进入 `waiting_agent` 后：Read 输出里给出的 SKILL.md，按文档做；有脚本就运行脚本（脚本、输入文件都用绝对路径；参数不清楚时运行脚本的 `--help`，不要读脚本源码，也不要逐个读 KB 文件，SKILL.md 明确要求读的除外），产出文件全部写进 `artifact_dir`（用户指定了输出路径，例如 `--output outputs/result.csv`，再复制一份到那里）；然后 `resume ... --agent-completed --register-all --summary "<真实结果>"`，一次登记全部产出。
   - 脚本运行完、产出文件写好之后再 `resume`：不要把 `resume` 和脚本（或脚本要读的文件）放在同一批并行的工具调用里，否则脚本还没写出文件，步骤就被登记了。`act` 和它的 `resume` 也不能在同一批里：几秒内跟着 `act` 来的 `resume` 会被拒绝。一次只做一步：不要把后面几步的 `act`、审查结论或 `--ask-plan` 预先写进同一批调用。
   - `--summary` 用中文写（报错原文和审查的 `verdict:` 关键词除外）：步骤暂停和审查未通过时，Runtime 把它放进给用户的问题里。
   - `--summary` 里只写普通文字，不要用反引号（`）或 `$`：命令在 bash 里运行，双引号中的反引号和 `$` 会被当成命令执行，报错原文就丢了（记录成“发生未预期错误 ，…”）。引用报错时直接写原文，例如 name 'sys' is not defined。
   - `act --skill` 只运行一次：输出是 `waiting_agent` 就说明 Skill 已经下达，接着做它的工作，不要再 `act` 同一个 Skill（再发只会得到一条 `notice`，什么也不变）。产出写进 `artifact_dir` 时直接复制输出里给出的路径，不要手打 mission id，也不要自己建 `rev` 文件夹：放错位置的文件 `--register-all` 会拒绝并列出，移到 `artifact_dir` 后再 resume。同一个 Skill 在本轮再做一次时（审查未通过后、暂停时重做），新产物用新文件名写进 `artifact_dir`（例如加 `_v2`）。
   - **审查步骤**（`plan_progress` 里带 `label` 的步骤，例如 fdu-risk-review 审查推荐结果）：按审查 Skill 的文档审查上一步的产物，把结论和发现写进 `--summary`；结论是阻断（例如 block）时用 `--agent-failed --summary "<结论、发现、需要怎么改>"`：Runtime 会向用户提问，转述问题并**结束本轮**；用户回复后照 `do_next` 用用户的修改重新运行被审查的 Skill，再审查一次，不要在原来的结果上重试审查。用户只是回答了审查提出的问题（确认事实、选定口径，没有改条件）时，带着回答重新审查（`act --skill <审查 Skill>`），不用重跑被审查的 Skill。需要人判断的结论照常登记，写进 summary，用户确认时会看到。审查要先读被审查的产物再写结论；登记审查时不要带上被审查步骤的文件（`--provide-artifact`），也不要照抄它的 summary，这两种都会被拒绝。
   - **计划里的步骤一次只做一步**：`--register-all` 之后，如果计划还有后续步骤，mission 会进入 `waiting_human`（步骤确认）；按实验流程建的计划只在 ⏸ 处这样停，其余步骤登记后直接照 `do_next` 做下一步。这时先读 `do_next` 里列出的产物文件，把这一步的关键结果（表格、数值、文件名）展示给用户，再转述 `pending_ticket.question`，**结束本轮**；不要自己开始下一步。Runtime 已登记为成功的步骤就是结果：它报告的局限（例如没有文献依据）用一句话说明即可，不要说结果不可信，也不要让用户重做。用户回复后照 `do_next` 运行下一步。只有用户明确要求“一次跑完、中间不用停”时，创建 mission 才加 `--run-through`。
   - 暂停时用户要求重做已经完成的步骤（例如“补齐两组步骤”“投料量重新算”）：`act ... --revise "<用户要求的改动>" --redo <那一步的 Skill id>`。计划在同一个 mission 里回到那一步，之后已完成的步骤也依次重做（各自带审查和 ⏸ 暂停），旧结果保留到新结果替换为止。不要新建 mission，也不要说需要管理员处理。
   - 用户在步骤确认时对下一步提了要求（例如“只保留第一条，生成实验步骤”）：运行下一步时按它的文档把要求作为参数传入（例如 experiment-step-generator 的 `--amounts <投料量 CSV> --rows 1`）；文档没有对应参数时，用一句话说明结果仍是全部条件的版本。
4. **失败**：只有实际执行后出现真实报错，才 `resume ... --agent-failed --summary "<报错原文>"`；不要凭猜测报失败，也不要用同一个坏输入反复重跑。下游因上游产物有问题而失败时，先记录失败，再用 `act --skill <上游 Skill>` 重做上游，之后按 `do_next` 重试下游。登记失败后，把这一步做不成的原因如实告诉用户并**结束本轮**：mission 的结果只能来自 LabOntology 选定的实验 Skill，不要用 WebSearch、文献、联网工具或自己的知识补出这一步的结果（例如模型跑不起来，就改用检索来的药物清单和属性交差）。
5. **收尾**：`plan_progress` 全部 `done` 后照 `do_next` 做：按实验流程建的计划停在终点时，`do_next` 会给出流程在这里的确认问题（例如是否创建设备任务）和下一步命令，先展示结果、转述问题并结束本轮，用户同意才继续；否则运行 `act ... --complete`，再向用户汇报（关键结果用简短列表或表格，不要整段粘贴 JSON 或文件内容），最后给出一个最有用的下一步。需要用户补充事实时用 `act ... --ask "<一个问题>"`，转告问题并结束本轮；步骤做完之前用户明确放弃时用 `act ... --cancel`；计划的步骤都做完后用户说“结束吧”“先不创建设备任务”，用 `act ... --complete`（结果保留），这时 `--cancel` 会被拒绝。mission 已经 `completed` 时没有可取消的东西：告诉用户任务已经完成、结果保留，不要反复运行 `--cancel`。

## 其他规则

- 需要设备动作的实验 Skill（例如 oasis-start、fdu-device-run）由 Runtime 强制暂停等待用户批准，这是唯一要你转交回复的情况：用户同意就 `resume ... --confirm --answer "<用户原话>"`，拒绝就 `--reject --answer "<用户原话>"`；其他命令都不算批准。
- `coverage_diagnostic.status` 是 `candidate_review`（任务的词没有匹配到任何实验 Skill）时，`skills` 列出全部已登记的实验 Skill 和它们的文档路径：读描述可能相符的那几个文档再决定，不要没读就说没有这个能力。读完仍没有合适的，或状态是 `no_registered_skill`（没有可用的实验 Skill）：先说明任务尚未开始及原因（`coverage_diagnostic.user_message`），不要说成执行失败；只有用户明确同意后，低风险只读任务才可以走 `agent_fallback`（见 references/runtime-protocol.md）。
- 实验 Skill 缺少参考资料（文献 PDF 等）：最多看一次目录，不要反复找，也不要用 WebSearch。文档允许用现有输入完成的，就完成并在回复里如实说明缺少该资料、结果没有它作依据；必须有才能继续的，用 `act --ask`。
- 约束解析结果里的 `ambiguities`（例如“金属盐还没从候选里选定”）只是记录，不是要向用户追问的问题：继续下一步，由推荐步骤选定。
- 不要用 Skill 工具加载实验 Skill（constraint-parser、fdu-*、oasis-* 等）：由 LabOntology 选择，你 Read 它的 SKILL.md。
- 以 “Base directory for this skill:” 开头的文本是系统加载 Skill 时插入的说明，不是用户消息：不要当作用户的回答，也不要复制进 Skill 参数。加载本 Skill 时，参数只用一句话概括用户本轮的请求。
- 后续对话（解释、排序、汇总上一轮结果）：对原 mission 读一次 `context`，再读需要的产物文件（每个最多一次），直接回答。
- **修改已完成的任务**（用户改了这项任务的条件，例如温度、用量、某个物料，并要求不受影响的步骤不要重做）：不要新建 mission，也不要手工改旧产物。对原 mission 运行 `act ... --revise "<用户要求的改动>" --redo <需要重做的 Skill id，逗号分隔>`（`--revise` 只写改动本身，例如“反应温度改为 100 ℃”，不要夹带给自己的指示），只列结果受这项改动影响的 Skill；Runtime 会重新打开原 mission，按原计划顺序一次重做一步（每步之后照样暂停；按实验流程建的 mission 会带上重做步骤的审查，只在 ⏸ 处暂停），新产物写进 `artifacts/rev<N>/`，旧产物保留。
  - **改动要进到 Skill 的输入里**：改的是用户指令里的条件（温度、时间、物料……）时，读指令的 Skill（例如 constraint-parser）也要重做：把原指令里被改的数值直接改掉再解析（例如“80 ℃ 反应 12 小时”改成“100 ℃ 反应 12 小时”），实在无法原位改写时才在末尾加“；修改：<改动>”，下游 Skill 才能拿到新条件。只重做下游 Skill、输入没变，只会得到原来的结果；`do_next` 会列出这种来自保留步骤的输入。
  - 每个重做步骤登记前先读新产物，确认改动确实体现在里面（Skill 没有对应字段的数值，例如只记录物料的解析器里的温度，出现在它保存的指令原文 `source_text` 里就算体现了）；没有体现就 `resume --agent-failed --summary "<还差什么>"`，不要登记成成功，也不要在汇报里说已经改好。这个判断在登记前做完：`--complete` 之后修改就不能再撤销，只能再 `--revise` 改回去。
  - 改动做不到时（Skill 不支持、重做失败、用户放弃），运行 `act ... --cancel --reason "<原因>"`：只撤销这次修改，mission 回到修改前的结果，然后用一句话告诉用户。修改没做完时 `--complete` 会被拒绝。
  - `do_next` 列出的保留步骤如果用到了重新生成的输入，要向用户说明它们为什么仍然有效。只有目标完全不同时才新建 mission。
- **不要修改实验 Skill 或本 Skill 的文件**（SKILL.md、scripts、KB、模板、提示词）：它们是所有用户共用的流程库。实验 Skill 做不到用户要的事时，用一句话说明是哪个 Skill、缺什么，然后停下；不要进入计划模式，也不要自己改脚本。

## 初始化与流程清单

用户只要求初始化 LabOntology，或只询问有哪些实验流程 / 实验 Skill 可用、流程库是否就绪时，这是只读查询：不创建 mission，不选择 Skill。运行一次 `inspect --cache-dir labontology_workspace_cache --skills`（用户要求初始化时先运行一次 `bootstrap`），按用途分组列出可用流程（注明涉及设备操作或需要用户确认的环节），再给出一个最有用的下一步。

## 流程库维护

重复失败、缺少条件或用户纠正时，先只读运行 `suggest-maintenance`，经明确检查后才用 `maintain-graph` 应用低风险修改（保留一个最新备份，可用 `restore-backup` 恢复）；不要修改实验 Skill 的 SKILL.md、设备命令或 mission 历史。命令细节见 references/runtime-protocol.md。

## 回复形式

先给实验结果，再给唯一最有用的下一步：Ready（可继续的流程）、Missing condition（只指出缺少的材料、条件或证据）、Waiting for approval（拟执行的动作、影响、需要的确认）、Paused task（当前状态，不暗示设备动作会自动重做）、Library problem（先说“实验流程库需要更新”）。不要主动展示内部路径、命令、原始异常或大段 JSON；用户明确要求时，只能返回当前任务已登记产物的路径（`mission.artifacts`）。有多个任务或流程匹配时，只问一个聚焦的问题。

## 安全边界

不得自动执行设备相关或高影响动作，不得补造缺失证据，不得绕过安全、审批、授权或输入条件；`complete` 不能用来绕过实验 Skill、审批或输入条件；`agent_fallback` 的结果必须标明是 Agent 直接执行，不能冒充实验 Skill 的结果。
