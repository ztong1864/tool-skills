---
name: trace-collab-skill
description: Use when Codex needs to operate TRACE-COLLAB / TRACE Lab chemical experiment recommendation workflows, generate candidate recommendations, show recommendation tables, submit completed experiment results, continue next-round recommendations, or troubleshoot agentic/bo_only, .env, model/API key, project.yaml, design_space.csv, observations.csv, recommendations, and trace files.
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
JSON 返回到上下文里，不再需要本地 CSV/JSON 文件落盘中转。上传的 CSV 原文可以直接透传给
`create_project`/`import_observations`/`tell_results` 的 `*_csv` 参数（服务端解析），
不必手工转成 JSON。

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

- `design_space.csv` 或等价 JSON：用于 `create_project`（新建项目，仅第一次）。
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

如果用户上传了真实的设计空间 CSV 文件，必须用 `design_records_csv` 把这份 CSV 原文原样
透传给 `create_project`——不要读完 CSV 之后凭理解手动重新敲一份 `design_records` JSON。
手动转写极容易漏数据：CSV 里一个分类变量（如 Additive、Solvent、TEMPO 衍生物）通常是
"同一个 variable 名字重复多行、每行一个可选值"的长表格式，手动转写时很容易只保留一行
（变成"只有这一个选项"），后续 `import_observations`/`ask_recommendations` 校验历史记录或
生成推荐时，只要用到没被转写进去的那些选项就会全部失败。只有在真的没有 CSV、用户只是用
自然语言描述设计空间时，才需要自己整理成 `design_records` JSON。

如果 CSV 里还带有 `descriptor__<name>` 列（每个候选选项的数值化描述符，配合
`planner_use_descriptors: true` 使用，例如 `descriptor__HOMO_energy`），同样必须通过
`design_records_csv` 原样透传，一列都不要省略——这些列不影响行数/选项数，很容易被误认为
"非必要的额外信息"而在转发前被精简掉，但一旦丢失，`planner_use_descriptors: true` 就会
变成空转：planner 会退化成对原始分类值做穷举式搜索，而不是基于描述符做紧凑搜索，遇到
选项数较多的分类变量（几十个以上）时会导致 `ask_recommendations` 极慢甚至卡死。凡是设计
空间 CSV 含有 `descriptor__` 列，一律用 `design_records_csv`，不要用 `design_records`
JSON——逐行手工转写几十个数值描述符既不现实也极易出错。

设计空间里含有占位符（如"replace before experiment"、"confirm before experiment"）
也要照常建项目，不要等用户先把占位符填成真实值才建——占位符问题留到确认建项目成功之后、
第 3 步之前再用文字追问即可。等用户回复了占位符的真实值之后，如果原本是用
`design_records_csv` 建的项目，更新时也要在原始 CSV 文本里只改那一个占位符对应的值、
其余行原样保留，再整份传给 `create_project`——不要借着"填一个值"的机会把整份 CSV 重新
手动转写成 JSON。这只在项目第一次创建时调用，不要每轮都重新创建；已有项目时不要调用
`create_project` 覆盖（判断规则见上方"执行原则"）。

调用后必须确认真的建成功：工具返回不是报错，且能在 `project_summary`（传对应
`project_id`）里查到刚建的这个项目。建失败就把具体报错原文（翻译成中文）告诉用户并停在
这里——不要假装项目已经建好就去问占位符问题或调用 `ask_recommendations`，对一个不存在的
项目调用 `ask_recommendations` 必然报错。

如果用户提供的是历史实验记录，在第一次 `ask_recommendations` 之前调用
`import_observations`（`rows` 或 `rows_csv` 二选一）导入。

### 3. 生成候选推荐

调用 `ask_recommendations`。第一轮和之后每一轮都用同一个工具，没有单独的"下一轮"工具。

- 默认在项目最新批次仍有 pending 推荐时会被拒绝——这时不要传 `allow_pending=true` 强行跳过，
  而是回到第 5 步，引导用户补齐上一轮结果并 `tell_results` 提交后再重试。
- `controller_mode` 默认 `agentic`（需要 TRACE Lab 服务已配置可用的 `OPENAI_API_KEY`），无 LLM
  或调试时可用 `bo_only`。

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
- rank 1 / round_001_rec_001：状态 completed/failed/skipped？如果 completed，请给 yield；如果 failed/skipped，请给原因。
- rank 2 / round_001_rec_002：...
- rank 3 / round_001_rec_003：...
```

有效状态：

- `completed`：需要数值型目标值，例如 `yield`。
- `failed`：记录失败原因，不需要目标值。
- `skipped`：记录跳过原因，不需要目标值。
- `pending`：允许保留，但不是终态；仍有 pending 时默认不能进入下一轮。

收到用户自然语言回复后，agent 必须自动解析为结果 JSON（供 `tell_results` 的 `results`
参数使用）。允许用户用 rank 或 `recommendation_id` 表达，例如"1号 72.5，2号失败沉淀，3号跳过
原料不足"。解析后的 JSON 示例：

```json
[
  {"recommendation_id": "round_001_rec_001", "status": "completed", "yield": 72.5, "notes": "clean run"},
  {"recommendation_id": "round_001_rec_002", "status": "failed", "failure_reason": "precipitation"},
  {"recommendation_id": "round_001_rec_003", "status": "skipped", "failure_reason": "not enough material"}
]
```

如果缺少某条推荐结果、`completed` 缺少目标值、或状态不明确，先追问用户，不要调用
`tell_results`（该工具本身也会在遗漏任一 pending 推荐时拒绝提交）。

### 6. 提交结果并继续下一轮

把上一步整理好的结果 JSON 传给 `tell_results`（`results` 或 `results_csv` 二选一）。

汇报结果时说明：

- `appended` 数量。
- 各状态数量。
- `observation_count`。
- `completed_observation_count`。
- `best_so_far`。
- `reflection_status`。
- 是否还有 pending recommendation。

如果没有 pending，继续执行第 3 步的 `ask_recommendations`，再执行第 4 步展示新一轮推荐表格。

## 工具速查

- `health`：检查 API 是否可达。
- `list_projects`：列出所有项目及摘要。
- `project_summary`：单个项目的完整状态摘要。
- `create_project`：根据设计空间创建新项目（仅首次）。
- `import_observations`：导入历史实验记录。
- `ask_recommendations`：生成候选推荐（首轮和后续轮次通用）。
- `tell_results`：提交实验结果。
- `get_recommendations`：读取所有推荐批次及状态。
- `get_observations`：读取所有观测结果。
- `get_evidence`：读取用于生成推荐的证据卡。
- `get_trace`：读取某一轮的决策 trace。
- `reset_project`：清空项目运行状态（保留配置/设计空间），破坏性操作，调用前先和用户确认。

## Trace 查看

当用户问"为什么推荐这个候选"或需要解释推荐依据时，调用 `get_trace`（传 `project_id` 和
`round_id`）。解释时优先对应到推荐表格中的 `recommendation_id`，说明候选条件、rationale、
证据引用和决策路径。

## 常见问题处理

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
