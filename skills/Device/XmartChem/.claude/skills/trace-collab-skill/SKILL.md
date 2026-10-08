---
name: trace-collab-skill
description: Use when Codex needs to operate TRACE-COLLAB / TRACE Lab chemical experiment recommendation workflows (TRACE 项目、贝叶斯优化、闭环推荐、推荐下一轮、提交实验结果、导入已有 TRACE 项目、证据卡), generate candidate recommendations, show recommendation tables, submit completed experiment results, continue next-round recommendations, or troubleshoot agentic/bo_only, .env, model/API key, project.yaml, design_space.csv, observations.csv, recommendations, and trace files. Use it directly -- TRACE requests do not go through LabOntology.
---

# TRACE-COLLAB Skill

本 skill 是 TRACE Lab 的操作技能，用于协助实验人员完成闭环候选推荐。

所有面向用户的文字（说明、表格表头、rationale 摘要、错误提示等）必须用中文输出。
`trace-collab` 工具描述和 TRACE Lab API 返回的原始内容（如 `rationale`、报错信息）都是英文，
看到英文内容时要翻译成中文再呈现给用户，不要直接原样贴出英文。`recommendation_id`/
`project_id`/`round_id` 这类标识符，以及 `completed`/`failed`/`skipped`/`agentic`/
`bo_only` 这类固定取值保留原文，不用翻译。

**执行方式：调用 `trace-collab` 工具**（sdk_python，进程内 MCP server，位于
`tools/Device/XmartChem/.claude/tools/trace-collab/`，通过 HTTP 调用 TRACE Lab API）。
不要再运行 `trace-collab-skill/scripts/trace_lab_api.py` 或
`save_recommendations.py`/`save_experiment_results.py`——每次工具调用直接把结构化
JSON 返回到上下文里，不再需要本地 CSV/JSON 文件落盘中转。

**上传的文件一律传路径，不要抄写内容**：用户上传的设计空间、历史数据、结果表、描述符表、证据卡，
把上传说明里的绝对路径交给对应的 `*_file` 参数（`create_project` 的 `design_records_file` /
`observations_file` / `evidence_file` / `descriptor_tables[].file`，`import_observations` 的 `rows_file`，
`tell_results` 的 `results_file`，`add_descriptor_table` 和 `import_evidence` 的 `file`），由工具自己读取。
不要先 Read 文件再把内容复制进 `*_csv`、`jsonl`、`cards` 参数——抄写会改动内容（测试中出现过读了
证据卡文件却导入了自己编的卡）。`*_csv` / `cards` 只用于用户在对话里直接打出的少量数据。
用户另给的描述符表（每个变量一张、一行一个选项）交给 `create_project` 的 `descriptor_tables` 或
`add_descriptor_table` 由服务端合并，不要自己合并进设计空间 CSV。`project_id` 就是项目的 handle
（`list_projects` 里每个项目的 `handle`），所有工具都用它。

TRACE 请求直接用本 skill，不经过 LabOntology：不要为 TRACE 请求运行 labontology 的 bootstrap 或创建 mission。
需要向用户提问时直接写成文字并结束本轮（网页对话没有 AskUserQuestion）。

工作流闭环：

1. 实验人员提供 CSV 输入或自然语言描述。
2. agent 调用 `trace-collab` 工具生成候选推荐（`ask_recommendations`）。
3. agent 把返回 JSON 整理成 Markdown 表格展示给用户。
4. 用户要求第二轮及以上推荐时，agent 先引导实验人员补充上一轮实验结果。
5. agent 把用户回复解析为结果 JSON，调用 `tell_results` 提交。
6. agent 继续调用 `ask_recommendations` 生成下一轮推荐。

不要把"推荐已生成"作为最终回复；每轮推荐必须展示表格，并说明 `project_id`/`round_id`。

各工具调用自身的守卫规则（如"仍有 pending 推荐时拒绝 `ask_recommendations`"、"`tell_results`
缺少任一 pending 结果时拒绝提交"）已经写在工具描述里，调用时会直接提示，不在此重复参数细节。

## 输入类型判断

根据用户给出的内容判断当前阶段：

- **已有的 TRACE 项目**（带 `project.yaml` 的项目文件夹、它的 .zip，或从另一台 TRACE 拿来的一组项目文件：`project.yaml`、`design_space.csv`、`observations.csv`、`evidence_cards.jsonl`、`recommendations_round_*`、`trace_round_*`……）：用 `import_project` 导入，不要用 `create_project` 手工转写（见第 2 步“导入已有项目”）。
- `design_space.csv` 或等价 JSON：用于 `create_project`（新建项目，仅第一次）。
- 单独的描述符表 CSV（如 `additive_descriptors.csv`）：用于 `create_project` 的 `descriptor_tables`，
  或给已有项目用 `add_descriptor_table`。
- 证据卡（JSONL/CSV）：用于 `import_evidence(file=…)`，或建项目时用 `evidence_file` 一起传。
- 历史实验 CSV/JSON：用于 `import_observations`，在第一次 `ask_recommendations` 之前导入。
- 用户自然语言实验结果：用于第二轮及以上推荐前，由 agent 解析为结果 JSON，交给 `tell_results`。
- 实验结果字段至少包含 `recommendation_id`、`status`；`completed` 必须附带目标值（如 `yield`），
  `failed`/`skipped` 附带 `failure_reason`。

## 主工作流

**执行原则**：完成第 1 步检查后，直接依据项目状态继续调用对应的 `trace-collab` 工具，不要
停下来把检查结果整理成状态汇报等用户回应。整个工作流中任何情况都不要调用 `AskUserQuestion`
——不只是"首次使用/已有数据/继续推荐"这类工作流分支选择，设计空间或历史数据里出现占位符/
待确认信息时（例如 `design_space.csv` 里的"replace before experiment"、`observations.csv`
里的"confirm before experiment"）同样不要用它。这类信息缺口该说的话直接写成普通文字追问
用户（和你本来就会写的说明文字放在一起即可），不要额外再调用 `AskUserQuestion` 把同一件事
重复问一遍。

占位符/待确认信息不是延后建项目的理由：项目不存在时默认直接建项目（见下方判断规则），
占位符缺口留到项目建成功之后再用文字追问，不要因为数据不完整就先问用户、把建项目这一步
拖到用户回复之后——一旦这一步被跳过或者建项目本身失败，之后 `ask_recommendations` 会因为
项目根本不存在而报错。判断规则：

- 项目不存在 → 第 2 步：有设计空间就 `create_project`，只有历史数据就 `import_observations`；
  调用后必须确认真的建成功了（见第 2 步），确认成功之前不要问用户任何问题、也不要调用
  `ask_recommendations`。
- 项目已存在 → 不要调用 `create_project` 覆盖，也不要因为用户又贴了一遍 `design_space.csv`
  或重复描述了一次设计空间就询问是要新建还是沿用；直接判定为沿用该项目，继续往下走。
- 存在 pending 推荐（上一批由 `ask_recommendations` 生成、还没 `tell_results` 提交）→
  第 5 步，引导用户补齐上一轮结果。
- 没有 pending 推荐 → 第 3 步 `ask_recommendations`。

**这一条只看第 1 步查到的 pending 状态，不看用户的措辞**：用户说"第二轮""下一轮""继续推荐"
不代表一定存在需要回填的上一轮推荐表——如果上一轮数据是通过 `import_observations` 导入的
历史记录（本来就没有 `ask_recommendations` 生成过、也没有 `recommendation_id` 待回填），
第 1 步查到的 pending 推荐数就是 0，这时不要因为用户提到"第二轮"就跳到第 5 步去找一份不
存在的推荐表——直接第 3 步 `ask_recommendations`。如果 `project_summary`/`get_recommendations`
反复查询都显示没有 pending、也找不到任何推荐表，不要继续重复查询，直接执行第 3 步。

只有 `reset_project` 这种破坏性、不可逆操作才需要先用文字和用户确认；其余情况一律按上面的
规则直接执行。

### 1. 检查服务和项目

先调用 `health` 确认 TRACE Lab API 可达。

再调用 `project_summary`（或 `list_projects` 查看所有项目）检查：

- 项目是否已存在。
- active variables 是否正确。
- 是否已有 observations。
- 是否存在 pending recommendations（上一批还没提交结果）。
- `controller_mode`、`planner_name`、`batch_size` 是否符合本轮需求。

这一步只是内部判断依据，检查完立刻按上面的判断规则进入第 2 步或第 3/5 步，不要在这里停下。

### 2. 根据输入建立或补充项目

**导入已有项目**：用户带来的是已有项目（有 `project.yaml`、历史轮次或证据卡文件）时，调用 `import_project`：`project_id` 取一个新名字（加用户名前缀，例如 `bbb_lactonization`），`source` 传上传说明里该项目文件夹或 .zip 的绝对路径；零散上传的文件用 `files`（路径列表），同名上传被改名的（如 `design_space（1）.csv`）用 `named_files`（`{项目里的文件名: 路径}`）说明对应关系；没有 `project.yaml` 时传 `settings`，至少包含 `objective_name`（观测表里放结果的那一列，例如 `lactone_yield`，不要默认成 `yield`）。拿不准能不能导入时先 `dry_run: true`。

- 工具把文件复制到用户工作区的 `trace_projects/<project_id>/` 再登记，原文件不会被改动；旧服务器留下的 `agent_config_path`、本版本不认识的设置会被自动修正并在 `repairs` 里列出，要转告用户。
- 返回的 `warnings`（例如证据卡的 mapping_status 不在允许列表内、被当作 background；Atlas 面对几十万种以上组合）逐条翻译成中文告诉用户；`next` 里建议改 `chunked_gp` 时，用 `update_project_config` 改完再 ask。检查结果里的 `mapping_status_aliases`（例如组里写卡指南用的 `same_redox_manifold`，TRACE 读作 `same_reaction_family`）不是错误，用一句话说明即可。
- 导入的项目如果带着未回填的推荐批次（`pending_recommendation_count` 大于 0），按第 5 步先向用户要这批的结果，或问用户这批是否根本没做。
- 一个文件夹里有多个项目时工具会报错并列出子项目，问用户要导入哪一个。
- `import_project` 报检查错误时什么都不会导入：把错误逐条告诉用户，不要改用 `create_project` 手工转写来绕过。
- 撤销导入用 `unregister_project`（`delete_files: true` 会删掉工作区里的副本，先和用户确认）。

如果用户上传了真实的设计空间 CSV 文件，必须用 `design_records_file` 传这个文件的路径，由工具原样读取
——不要读完 CSV 之后凭理解手动重新敲一份 `design_records` JSON，也不要把内容抄进 `design_records_csv`。
手动转写极容易漏数据：CSV 里一个分类变量（如 Additive、Solvent、TEMPO 衍生物）通常是
"同一个 variable 名字重复多行、每行一个可选值"的长表格式，手动转写时很容易只保留一行
（变成"只有这一个选项"），后续 `import_observations`/`ask_recommendations` 校验历史记录或
生成推荐时，只要用到没被转写进去的那些选项就会全部失败。只有在真的没有 CSV、用户只是用
自然语言描述设计空间时，才需要自己整理成 `design_records` JSON。

如果 CSV 里还带有 `descriptor__<name>` 列（每个候选选项的数值化描述符，配合
`planner_use_descriptors: true` 使用，例如 `descriptor__HOMO_energy`），同样必须通过
`design_records_file` 原样传入，一列都不要省略——这些列不影响行数/选项数，很容易被误认为
"非必要的额外信息"而在转发前被精简掉，但一旦丢失，`planner_use_descriptors: true` 就会
变成空转：planner 会退化成对原始分类值做穷举式搜索，而不是基于描述符做紧凑搜索，遇到
选项数较多的分类变量（几十个以上）时会导致 `ask_recommendations` 极慢甚至卡死。凡是设计
空间 CSV 含有 `descriptor__` 列，一律用 `design_records_file`，不要用 `design_records`
JSON——逐行手工转写几十个数值描述符既不现实也极易出错。

如果用户给的是**单独的描述符表**（例如 `additive_descriptors.csv`、`solvent_descriptors.csv`，
每张表一行一个选项）而不是已经合并好的 `descriptor__` 列，不要自己把它们合并进设计空间
CSV：设计空间 CSV 用 `design_records_file` 传入，每张描述符表作为 `descriptor_tables` 的一项
（`variable`、`value_column`、`file`），并设 `planner_use_descriptors: true`（每个活跃的分类变量都要有描述符表；温度、用量这类数值变量没有表时直接用它自己的数值，不用补表）。服务端按选项名
**完全一致**匹配；某个选项在表里找不到行、两个选项的描述符完全相同、或表里没有数值列时，整个
请求失败，不会建出半个项目，报错会逐条列出问题。只有表里把某个选项写成了不同拼写（例如设计里
是 `CeCl3·7H2O`、表里是 `CeCl3`）时才用 `aliases`（`{设计选项: 表中名称}`），而且**必须是用户
确认过的同一种物质**——不要为了让请求通过而猜别名，也不要把缺行的选项映射到别的物质上（例如把
`Co(OAc)2` 映射成 `CoSO4` 会让它带上硫酸根的描述符）。缺行时把报错里列出的选项原样（翻译说明
后）告诉用户，问他们是补一行数据还是确认别名。

**优化器**：`create_project` 不指定时用 `chunked_gp`（几秒内给百万级组合打分）。只有用户明确要求且组合数
不到约 10 万时才用 `atlas`：Atlas 在大空间上可能要十几分钟甚至跑不完（真实案例：内酯化项目有 1,096,875 种
组合）。导入的旧项目如果还是 Atlas，按 `check_project` 的警告用 `update_project_config` 改成 `chunked_gp`。
项目设置是 Atlas 而组合数超过 10 万时，TRACE 会在这一轮自动改用 `chunked_gp`，ask 的返回里带 `planner_switched`：
用一句话告诉用户，并建议用 `update_project_config` 把 `planner_name` 改成 `chunked_gp`。

设计空间里含有占位符（如"replace before experiment"、"confirm before experiment"）
也要照常建项目，不要等用户先把占位符填成真实值才建——占位符问题留到确认建项目成功之后、
第 3 步之前再用文字追问即可。等用户回复了占位符的真实值之后，如果原本是用
上传文件建的项目，请用户上传改好的文件（或说明要改的值后在工作区里改好这一个值再保存成文件），
再用 `design_records_file` 整份传给 `create_project`——不要借着"填一个值"的机会把整份 CSV 重新
手动转写成 JSON 或文本。这只在项目第一次创建时调用，不要每轮都重新创建；已有项目时不要调用
`create_project` 覆盖（判断规则见上方"执行原则"）。

调用后必须确认真的建成功：工具返回不是报错，且能在 `project_summary`（传对应
`project_id`）里查到刚建的这个项目。然后调用 `check_project`：有 error 必须先解决；有 warning
（例如大设计空间用了 Atlas、有证据卡永远不会被展示）要用中文告诉用户，并按上面的规则处理。
建失败就把具体报错（翻译成中文，逐条列出的问题不要省略）告诉用户并停在这里——不要假装项目已经
建好就去问占位符问题或调用 `ask_recommendations`，对一个不存在的项目调用 `ask_recommendations`
必然报错。一次创建是"全有或全无"：设计空间、描述符表、历史观测、证据卡里任何一部分有问题，
都不会建出项目，改好后整体重新提交即可。

如果用户提供的是历史实验记录，在第一次 `ask_recommendations` 之前调用
`import_observations` 导入（上传的文件用 `rows_file`，对话里打出的少量数据才用 `rows`/`rows_csv`）；
也可以在建项目时用 `observations_file` 一并提交。

**历史记录里带轮次编号**：历史表的 `round_id`/`recommendation_id` 列里可能已有 `round_001_rec_001`
这类编号（例如从旧项目导出的表）。新版 TRACE Lab 会把新一轮接在历史编号之后（历史到 `round_003`，
第一次 ask 就是 `round_004`），可以直接导入，不用改数据。旧版 TRACE Lab 的第一轮仍叫 `round_001`，
编号相撞，之后 `tell_results` 会报 "Recommendation `round_001_rec_001` already has a completed
observation"，`check_project` 也会把这些待回填推荐列为 error。遇到这种情况先告诉用户服务是旧版本；
临时办法是导入前把这些行的 `round_id`、`source`、`stage` 改成 `historical` 并清空
`recommendation_id`（已验证可以走完 ask → tell → 第二轮），代价是丢掉旧批次的编号对应关系。
不要在没有告知用户的情况下自己改他们的数据。

### 3. 生成候选推荐

调用 `ask_recommendations`。第一轮和之后每一轮都用同一个工具，没有单独的"下一轮"工具。

- 默认在项目最新批次仍有 pending 推荐时会被拒绝——这时不要传 `allow_pending=true` 强行跳过，
  而是回到第 5 步，引导用户补齐上一轮结果并 `tell_results` 提交后再重试。
- `controller_mode` 不要主动传：留空时沿用项目自己的设置（`project_summary` 里能看到），项目设为
  `agentic` 才会调用 LLM（需要 TRACE Lab 服务已配置可用的 `OPENAI_API_KEY`）。只有用户明确要求
  这一次跳过 LLM 时才传 `bo_only`。不要把 `agentic` 当默认值硬塞进去，否则会覆盖项目里设置的
  `bo_only`。
- 大设计空间上 ask 很慢时不要连续重复调用；先用 `check_project` 看是不是 Atlas 遇上了几十万种以上的
  组合，是的话改成 `chunked_gp`（见上）。同一个项目已有 ask 在运行时会返回 HTTP 409，等它跑完。

如果用户只是说"继续下一轮""做第二轮推荐"之类，先看第 1 步查到的 pending 推荐状态，不要
只凭这句话本身判断：确实存在 pending 推荐（上一批是 `ask_recommendations` 生成、还没
`tell_results` 提交）时，不能直接调用 `ask_recommendations`，必须先执行第 5 步；如果没有
pending 推荐（例如上一轮只是 `import_observations` 导入的历史数据，本来就不存在待回填的
`recommendation_id`），不要因为用户说了"第二轮""下一轮"就去找一份不存在的上一轮推荐表——
直接执行本步 `ask_recommendations`。

### 4. 展示推荐表格

`ask_recommendations` 返回的 JSON 里包含本批次每条推荐（`recommendation_id`、`rank`、候选
变量取值、`rationale` 等）。agent 必须把它整理成 Markdown 表格展示给用户，包含：

- `rank`
- candidate 关键变量和值（每个变量单独成列，例如 `Additive`、`Solvent`、`Temperature`）
- rationale 摘要
- 有 `model_estimate` 时加一列“模型预测”（`predicted` ± `uncertainty`，单位同目标值）

用户问“为什么推荐第 N 条”时，按这条的 `model_estimate`（模型预测的目标值和不确定度，1 个标准差）和
`proposed_by`（`ei`：期望改进最大；`ucb`：预测值加不确定度的上界最高；`ei+ucb`：两者都选中）回答：
例如“模型预测收率约 62%（±8%），由 EI 选出，属于预测高、仍有把握提升的条件”。bo_only 模式除此之外没有
别的理由，不要编造化学解释；agentic 模式再用 `get_trace` 看智能体的推理。没有 `model_estimate` 的
（随机初始设计、Atlas）如实说明没有逐条预测。

用户可见表格不要展示 `recommendation_id` 和 `batch_role`；这两个字段仍需要 agent 在上下文里
记住，用于后续结果回填和 `tell_results` 提交（不再有本地 CSV 帮你保管这些字段）。

同时在回复中说明：

- `round_id`
- `project_id`
- 是否引用了证据（可用 `get_evidence` 查看）

### 5. 第二轮及以上推荐前引导用户补充结果

当用户要求第二轮及以上推荐、且第 1 步确认确实存在 pending 推荐（上一批是 `ask_recommendations`
生成、还没 `tell_results` 提交）时，不能直接调用 `ask_recommendations`。

如果第 1 步查到没有 pending 推荐（例如上一轮是 `import_observations` 导入的历史数据，没有
`ask_recommendations` 生成过、也没有 `recommendation_id` 待回填），不要执行本步——跳到第 3
步直接调用 `ask_recommendations`，不要反复调用 `project_summary`/`get_recommendations`
去找一份根本不存在的推荐表。

确认存在 pending 推荐后，先把上一轮推荐表（第 4 步展示过的那份）重新贴出来，并要求用户逐条
回复实验结果。引导问题使用这个格式：

```text
请补充上一轮每条推荐的实验结果：
- rank 1 / round_001_rec_001：状态 completed/failed/skipped？如果 completed，请给 yield；如果 failed/skipped，请给原因（failed 时如果测了产率，例如没有产物就是 0，也请给出）。
- rank 2 / round_001_rec_002：...
- rank 3 / round_001_rec_003：...
```

有效状态：

- `completed`：需要数值型目标值，例如 `yield`。
- `failed`：记录失败原因。如果做了测量（例如没有产物，yield 0），同时填上数值，模型会从中学习这个区域不好；
  没有测量（设备故障、操作失误）就不填数值。
- `skipped`：记录跳过原因，不需要目标值。
- failed 和 skipped 的条件之后不会再被推荐。确实要重做没测量的失败条件或跳过的条件时，用
  `update_project_config` 设 `repeat_failed_conditions: true`；带测量值的 failed 和 completed 一样不会重复推荐。
- `pending`：允许保留，但不是终态；仍有 pending 时默认不能进入下一轮。

收到用户自然语言回复后，agent 必须自动解析为结果 JSON（供 `tell_results` 的 `results`
参数使用）。允许用户用 rank 或 `recommendation_id` 表达，例如"1号 72.5，2号失败沉淀，3号跳过
原料不足"。解析后的 JSON 示例：

```json
[
  {"recommendation_id": "round_001_rec_001", "status": "completed", "yield": 72.5, "notes": "clean run"},
  {"recommendation_id": "round_001_rec_002", "status": "failed", "yield": 0, "failure_reason": "precipitation, no product"},
  {"recommendation_id": "round_001_rec_003", "status": "skipped", "failure_reason": "not enough material"}
]
```

如果缺少某条推荐结果、`completed` 缺少目标值、或状态不明确，先追问用户，不要调用
`tell_results`（该工具本身也会在遗漏任一 pending 推荐时拒绝提交）。

### 6. 提交结果并继续下一轮

把上一步整理好的结果 JSON 传给 `tell_results` 的 `results`；用户上传的是结果表文件时用 `results_file` 传路径。

汇报结果时说明：

- `appended` 数量。
- 各状态数量。
- `observation_count`。
- `completed_observation_count`。
- `best_so_far`。
- `reflection_status`。
- 是否还有 pending recommendation。

如果没有 pending，继续执行第 3 步的 `ask_recommendations`，再执行第 4 步展示新一轮推荐表格。

### 7. 按需：改设置、补描述符、导入证据卡

- **改设置**：用 `update_project_config`，传 `settings` 对象，例如 `{"planner_name": "chunked_gp"}`。
  可改：`reaction_name`、`reaction_scope`、`planner_name`、`acquisition_function`、`planner_options`、
  `controller_mode`、`agent_config_path`、`batch_size`、`seed`、`planner_use_descriptors`、
  `allow_random_fallback`、`repeat_failed_conditions`、`evidence_selection`。`project_id`、`objective_name`、`goal` 不能改（已有观测依赖它们），要改就
  只能新建项目。已有观测和推荐批次不受影响。**已经有观测的项目不能用 `overwrite` 重建，想换优化器
  就用它，不要重新创建。**
- **补描述符表**：对已存在的项目用 `add_descriptor_table`（`variable`、`value_column`、上传的表用 `file`，必要时
  `aliases`、`replace`）。规则同第 2 步：名称完全一致才匹配，别名必须由用户确认，失败时不会改动
  任何东西。变量已经有同名描述符列时默认报错，确实要覆盖才传 `replace: true`。
- **导入证据卡**：上传的证据卡文件用 `import_evidence(file=<路径>)`（`mode` 为 `append` 或
  `replace`）；`cards`/`jsonl`/`csv` 只用于对话里现写的卡。校验很严格：`card_id` 重复、`summary` 为空、
  `mapping_status` 不在 `direct`、`same_start_end`、`same_reaction_family`、`variable_level`、`background`、
  `out_of_scope` 之内都会报错，并一次列出全部有问题的卡，什么都不导入，不会悄悄改成 `background`
  （别名 `same_redox_manifold`、`same_reaction` 会存成 `same_reaction_family`，返回的 `status_notes` 列出改了哪几张，转告用户）；
  报错时把问题逐条告诉用户，不要自己改卡再导入。导入后用 `get_evidence` 查看。
  每次导入前工具都会把当前的卡存成 `snapshot_file`，返回里的 `undo` 就是撤销命令
  （`import_evidence(file=<snapshot_file>, mode="replace")`）：导错了用它恢复，不要手工重写卡片。
- **从 PDF 起草证据卡**：这是 TRACE 服务器上的命令行流程（`evidence-prepare` → `evidence-verify` →
  `evidence-sheet` → 研究者审阅 → `evidence-accept`），需要管理员在服务器上运行，对话里做不了。
  告诉用户这个流程；拿到审阅通过的卡片文件后，用 `import_evidence(file=…)` 导入。
  注意：智能体每次 ask 只读得分最高的少数几张卡（默认 5 张，每张只保留前 400 字符），新导入的卡
  不一定会被读到；导入后调用 `evidence_preview`，它列出智能体实际会读到的卡（含截断后的原文）、每张没被读到的卡的原因，
  以及 `warnings`（例如两张卡 summary 相同占两个名额），把 `warnings` 转告用户，不要凭猜测回答。
- **证据选择方式**：项目设置 `evidence_selection` 默认 `score`（按得分排）；改成 `per_variable`
  会先给每个被优化的变量选一张最专门的卡，会改变决策智能体读到的证据，只在用户明确要求时才改，
  并告诉用户它还需要 TRACE Lab 智能体配置里的 `knowledge_top_k` 和 `decision_engine_knowledge_max_items`
  不小于变量数才有意义。
- 这几个操作在项目有 ask 正在运行时会返回 HTTP 409（"An ask is running"）：等它跑完再试，不要在
  循环里反复重试。

### 别人的项目

TRACE Lab 服务是所有用户共用的：`list_projects` 能看到所有项目，每个项目带 `owner`（创建或导入它的用户），
`yours` 为 true 表示是当前用户自己的。读取（摘要、推荐、观测、证据、trace）不受限制；会改动项目的工具
（`ask_recommendations`、`tell_results`、`import_observations`、`update_project_config`、`add_descriptor_table`、
`import_evidence`、`reset_project`、`unregister_project`、带 `overwrite` 的 `create_project`）遇到别人的项目会拒绝并
说明属于谁。这时把项目属于谁告诉用户，问是否仍要修改；只有用户明确同意后，才带 `others_project_ok: true`
再调用一次。`owner` 为 `unknown` 的是记录所有者之前建的旧项目，不受限制，但重置、覆盖前同样要先和用户确认。

### 用哪把 key

agentic 模式的 LLM 步骤（推荐、反思）用用户自己在“设置 → 密钥管理”里配置的 OPENAI-API-KEY；没有配置时用
TRACE 服务器自带的共享 key。`ask_recommendations`、`tell_results` 的返回里 `llm_key` 说明这次用的是哪一把；
用户问起或用的是共享 key 时，用一句话告诉用户。

## 工具速查

- `health`：检查 API 是否可达。
- `list_projects`：列出所有项目及摘要和 `owner`（默认精简，`full: true` 给完整内容）。
- `project_summary`：单个项目的状态摘要和 `owner`（选项很多的变量只列前几个，`full: true` 给全部）。
- `create_project`：根据设计空间创建新项目（仅首次；上传的文件传 `*_file` 路径；不指定时优化器为 `chunked_gp`）。
- `import_project`：导入已有项目（文件夹、.zip 或上传的项目文件），保留历史推荐批次和 trace；`dry_run` 只检查。
- `unregister_project`：撤销导入（`delete_files` 同时删除工作区副本）。
- `import_observations`：导入历史实验记录。
- `ask_recommendations`：生成候选推荐（首轮和后续轮次通用；chunked_gp 的每条推荐带 `model_estimate`）。
- `tell_results`：提交实验结果（failed 测到的数值也一并提交）。
- `get_recommendations`：默认只读最新一批（或 `round_id` 指定的一批），不带决策 trace；`rounds` 列出所有轮次。用户要“所有批次”时按 `rounds` 逐批读取，不要用 `full: true`（完整内容太大时工具只会返回精简结果）。
- `get_observations`：读取观测结果和各状态计数（默认最近 50 条，`offset`/`limit` 翻页）。
- `get_evidence`：读取证据卡，默认每次 12 张的精简列表（`offset`/`limit` 翻页），`card_ids` 取指定卡的完整内容，`full: true` 取全部完整内容。
- `evidence_preview`：看智能体在 ask 时实际读到哪几张证据卡、其余为什么读不到（导入证据卡或改 `evidence_selection` 之后用）。
- `get_trace`：读取某一轮的决策 trace（精简；`recommendation_id` 只看某一条，`full: true` 取完整）。
- `reset_project`：清空项目运行状态（保留配置/设计空间），破坏性操作，调用前先和用户确认。
- `check_project`：检查项目文件是否一致，返回 errors、warnings 和关键数字（组合数、观测数、证据卡数）。
- `update_project_config`：修改项目设置（如改成 `chunked_gp`），不用重建项目。
- `add_descriptor_table`：给已有项目的某个变量补一张描述符表（每个选项一行）。
- `import_evidence`：导入证据卡（上传的文件用 `file`；严格校验；返回 `snapshot_file` 和撤销命令 `undo`）。

## Trace 查看

当用户问"为什么推荐这个候选"或需要解释推荐依据时，调用 `get_trace`（传 `project_id` 和
`round_id`，只想解释某一条时再传 `recommendation_id`）。解释时优先对应到推荐表格中的 `recommendation_id`，说明候选条件、rationale、
证据引用和决策路径。

## 常见问题处理

- 报错里逐条列出的问题（`- design_space.csv: ...`、`card 2 (x1): ...`）是给用户看的原始依据，翻译成
  中文后**全部**转告，不要只挑第一条；也不要为了让请求通过而放宽或改动用户的数据。
- HTTP 409 "An ask is running for project ..."：同一项目已有 ask 在跑（大空间上可能要几分钟），
  等它结束，不要重复提交。
- 建项目时报 "Lab project already exists"：项目 id 已被占用（TRACE Lab 服务是所有用户共用的）。沿用
  已有项目前先用 `project_summary` 确认那确实是用户自己的项目，否则换一个更有辨识度的 id。
- 历史数据导入后 `tell_results` 报 "already has a completed observation"：说明服务是旧版本，见第 2 步
  "历史记录里带轮次编号"。
- `health` 调用报 "Cannot reach TRACE Lab API"：TRACE Lab 服务未启动，或工具所在后端进程的
  `TRACE_LAB_BASE_URL` 环境变量配置不对（默认 `http://127.0.0.1:8788`）。
- `LLM agent unavailable for stagnation_diagnosis`：TRACE Lab 服务没有可用 `OPENAI_API_KEY`，
  或 agent 构建失败。用 `--env-file .env` 重启该服务的 Docker 容器；不使用 LLM 时把
  `controller_mode` 改为 `bo_only`。
- 兼容 OpenAI 的中转接口失败：检查 `OPENAI_BASE_URL` 是否需要 `/v1` 后缀，并确认
  `configs/agent_bo.yaml` 中模型名可被该网关识别。
- Windows 安装 `matter-golem` 失败：使用 Docker/Linux；本机 Windows 可跳过该依赖。
- TRACE Lab 服务本机提示 `ModuleNotFoundError: olympus`：设置 `PYTHONPATH` 包含
  `third_party/atlas/src` 和 `third_party/olympus/src`，或直接使用 Docker 部署该服务。
