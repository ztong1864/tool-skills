# TRACE Lab 工作流参考

## 核心逻辑

TRACE Lab 的操作逻辑不是单次 API 调用，而是实验协作闭环。执行方式是调用
`trace-collab` 工具（`tools/Device/XmartChem/.claude/tools/trace-collab/`，进程内
sdk_python MCP server，通过 HTTP 调用 TRACE Lab API），不再运行本地
CLI 脚本或写本地 CSV/JSON 中转文件：

1. 实验人员给出 CSV 输入或自然语言描述。
2. agent 根据输入和项目状态调用 `trace-collab` 工具的对应函数。
3. `ask_recommendations` 生成候选推荐，直接返回结构化 JSON。
4. agent 把返回结果整理成 Markdown 表格展示给用户（不再有脚本代劳）。
5. 用户要求第二轮及以上推荐时，agent 先引导实验人员逐条补充上一轮实验结果。
6. agent 把用户自然语言回复解析为结果 JSON。
7. agent 调用 `tell_results` 提交结果，再调用 `ask_recommendations` 生成下一轮推荐。

每轮推荐都必须在回复中展示 Markdown 推荐表格，表头为 `rank`、candidate 变量列和
`rationale`；不展示 `recommendation_id` 和 `batch_role`，但 agent 需要在上下文里记住
这两个字段，用于后续结果回填和 `tell_results` 提交。

## 输入数据

设计空间、历史实验记录、实验结果三类数据都可以用 JSON 或 CSV 原文传给工具（`design_records`/
`design_records_csv`、`rows`/`rows_csv`、`results`/`results_csv`，每对二选一）。用户上传 CSV
时优先直接透传原文，不必手工转成 JSON。

### 设计空间

用于 `create_project`，常见列：

```text
variable,type,value,low,high,step,unit,stage,active,role,fixed_value
```

支持变量类型：

- `categorical`
- `discrete_numeric`
- `continuous`
- `fixed`

descriptor 列可写成 `descriptor__<name>`。

### 历史实验记录

用于 `import_observations`，在第一次 `ask_recommendations` 之前导入。至少应包含实验变量和
目标值，例如：

```text
Catalyst,Solvent,Temperature,yield,status
cat_a,MeOH,60,55.2,completed
```

### 实验结果

用于 `tell_results`，提交实验人员完成推荐实验后的真实结果。至少包含：

```text
recommendation_id,status,yield,failure_reason,notes
```

有效状态：

- `completed`：需要目标值，例如 `yield`。
- `failed`：记录失败原因，不需要目标值。
- `skipped`：记录跳过原因，不需要目标值。
- `pending`：仍未完成，不是终态。

`tell_results` 会检查最新批次里每条 pending 推荐是否都在提交的结果里，缺任何一条都会直接
拒绝，不需要 agent 自己再核对一遍。

## 项目目录结构（TRACE Lab 服务端）

TRACE Lab 的每个项目都位于服务所在机器的 `runs/lab_projects/{project_id}`，与调用方
（工具或脚本）在哪台机器无关。

核心文件：

- `project.yaml`：项目目标、planner、controller mode、批次大小、证据文件名等配置。
- `design_space.csv`：实验变量、候选值、连续范围、固定条件等设计空间。
- `observations.csv`：历史实验结果和推荐实验完成后的真实观测结果。
- `evidence_cards.jsonl`：文献或领域知识证据卡。
- `recommendations_round_*.json/csv`：TRACE Lab 原始推荐文件。
- `trace_round_*.jsonl`：推荐决策、证据引用、代理动作、实验结果反思等审计轨迹。

## 运行环境（TRACE Lab 服务端）

TRACE Lab 服务项目根目录下的 `.env` 通常包含：

```env
OPENAI_API_KEY=
OPENAI_BASE_URL=
TRACE_LAB_PROJECTS_ROOT=runs/lab_projects
TRACE_LAB_HOST=127.0.0.1
TRACE_LAB_PORT=8788
```

不要打印密钥值。检查环境时只报告这些变量是否已设置。

`agentic` 模式需要 `OPENAI_API_KEY`。如果使用 OpenAI 兼容中转接口，还需要可用的
`OPENAI_BASE_URL`。模型配置主要在 `configs/agent_bo.yaml` 的 `runtime.model_name` 和
`runtime.llm_fallback_model_name`。

`trace-collab` 工具通过 `TRACE_LAB_BASE_URL` 环境变量（在工具所在的后端进程里配置，默认
`http://127.0.0.1:8788`）找到这个服务；工具侧配置和 TRACE Lab 服务自己的 `.env` 是两回事，
排查连不上时两边都要看。

## 启动和检查（TRACE Lab 服务端）

Docker 构建：

```powershell
docker build -t trace-collab-lab .
```

使用 `.env` 启动服务：

```powershell
docker rm -f trace-collab-lab-run
docker run -d --name trace-collab-lab-run -p 8788:8788 --env-file .env trace-collab-lab
```

服务起来之后，调用方（agent）用 `health` 工具检查可达性，用 `project_summary`/
`list_projects` 检查项目状态，不再需要本地 CLI 脚本。

## 第一轮推荐

如果用户提供了新的设计空间，先调用 `create_project`（`design_records` 或
`design_records_csv` 二选一）。只在项目第一次创建时调用一次，之后每轮不要重复创建。

如果用户提供了历史实验记录，先调用 `import_observations`（`rows` 或 `rows_csv` 二选一）。

调用 `ask_recommendations` 生成候选推荐，agent 把返回 JSON 整理成 Markdown 表格展示给用户，
表头为 `rank`、candidate 变量列和 `rationale`；不展示 `recommendation_id` 或 `batch_role`。

## 实验人员回填结果

实验人员根据推荐表格完成实验后，可以直接给自然语言回复；agent 负责自动整理成结果 JSON。
用户可以按 rank 或 `recommendation_id` 回答，例如：

```text
1号 completed，yield 72.5，备注 clean run；
2号 failed，原因 precipitation；
3号 skipped，原因 not enough material。
```

agent 应先把用户回复解析为结果 JSON：

```json
[
  {"recommendation_id": "round_001_rec_001", "status": "completed", "yield": 72.5, "notes": "clean run"},
  {"recommendation_id": "round_001_rec_002", "status": "failed", "failure_reason": "precipitation"},
  {"recommendation_id": "round_001_rec_003", "status": "skipped", "failure_reason": "not enough material"}
]
```

如果用户回复缺少某条推荐、`completed` 缺少 `yield`、或状态不明确，agent 必须继续追问，不能
调用 `tell_results`。

调用 `tell_results` 提交结果，提交后检查返回里的：

- `appended`
- `observation_count`
- `completed_observation_count`
- `best_so_far`
- `reflection_status`
- 是否还有 pending recommendation

## 下一轮推荐

当最新批次没有 pending，且上一轮结果已经通过 `tell_results` 提交后，才能生成下一轮。

如果用户只提出"继续下一轮""第二轮推荐"但没有给出上一轮实验结果，agent 必须先回到"实验人员
回填结果"步骤，引导用户逐条补充状态、yield、失败原因或备注。不能跳过 `tell_results` 直接
调用 `ask_recommendations`（该工具默认也会在仍有 pending 推荐时拒绝）。

生成下一轮和第一轮用的是同一个 `ask_recommendations` 调用，没有单独的"next"接口；agent 回复
同样必须展示 Markdown 推荐表格。

## API 总览

`trace-collab` 工具的每个函数对应下面这个 TRACE Lab REST API 的一个端点（基础地址
`http://127.0.0.1:8788`，可用 `TRACE_LAB_BASE_URL` 覆盖）：

- `GET /api/health` → `health`
- `GET /api/projects` → `list_projects`
- `POST /api/projects` → `create_project`
- `GET /api/projects/{project_id}` → `project_summary`
- `POST /api/projects/{project_id}/ask` → `ask_recommendations`
- `POST /api/projects/{project_id}/tell` → `tell_results`
- `GET /api/projects/{project_id}/recommendations` → `get_recommendations`
- `GET /api/projects/{project_id}/evidence` → `get_evidence`
- `GET /api/projects/{project_id}/observations` → `get_observations`
- `POST /api/projects/{project_id}/observations/import` → `import_observations`
- `GET /api/projects/{project_id}/trace/{round_id}` → `get_trace`
- `POST /api/projects/{project_id}/reset` → `reset_project`

## Trace 查看

当用户问"为什么推荐这个候选"时，调用 `get_trace`（`project_id` + `round_id`）。解释时对应
推荐表格中的 `recommendation_id`，说明候选条件、rationale、证据引用和决策路径。

## 常见失败原因

`health` 报 "Cannot reach TRACE Lab API"

- 原因：TRACE Lab 服务没启动，或工具所在后端进程的 `TRACE_LAB_BASE_URL` 配置不对。
- 处理：确认服务已运行且端口一致；检查 `TRACE_LAB_BASE_URL` 环境变量。

`LLM agent unavailable for stagnation_diagnosis`

- 原因：TRACE Lab 服务没有 `OPENAI_API_KEY`，或者 DecisionEngine 无法构建 LLM agents。
- 处理：用 `--env-file .env` 重启该服务的 Docker 容器；如果不需要 LLM，`ask_recommendations`
  传 `controller_mode=bo_only`。

`Non-retryable LLM failure`

- 原因：模型名错误、结构化输出不被支持、代理/base URL 错误、认证失败、额度问题或 endpoint 不
  兼容。
- 处理：检查服务端 `configs/agent_bo.yaml` 中的模型名，以及 `.env` 中的 `OPENAI_BASE_URL`；
  很多兼容接口要求 URL 以 `/v1` 结尾。

Windows 上 `matter-golem` 安装失败

- 原因：C 扩展编译需要 Windows SDK 头文件。
- 处理：TRACE Lab 服务用 Docker/Linux 部署。Windows 本地安装可以通过 platform marker 跳过。

`ModuleNotFoundError: olympus`

- 原因：TRACE Lab 服务本地第三方源码路径没有放进 `PYTHONPATH`。
- PowerShell 处理方式（在 TRACE Lab 服务所在机器上）：

```powershell
$env:PYTHONPATH = "$PWD\third_party\atlas\src;$PWD\third_party\olympus\src;$env:PYTHONPATH"
```
