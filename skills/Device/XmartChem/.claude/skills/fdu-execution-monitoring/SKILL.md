---
name: fdu-execution-monitoring
description: 这是 FDU 设备任务提交后的只读持续监控 skill。用于在设备任务已经创建后持续读取任务状态、进度、通知、故障和告警；发现异常时通过 sci_agent 会话推送提醒。本 skill 只做观察和提醒，不得启动、暂停、取消、恢复、重试、跳过、提交或修改任何设备任务。
---

# fdu-execution-monitoring

`fdu-execution-monitoring` 用于监控已经创建的 FDU 设备任务。

它的职责是：

- 持续读取设备任务状态；
- 持续读取设备通知、故障和告警；
- 在任务完成、失败、急停、终止、故障或告警时停止轮询；
- 写出监控结果；
- 在异常情况下向 sci_agent 对应会话推送提醒。

它不是设备控制 skill，不处理恢复动作。

## 使用前提

只有在以下条件都满足时，才允许启动 `monitor_task.py`：

1. 已经有设备任务 ID：
   - 通过 `--task-id` 显式提供；
   - 或从 `fdu-device-run/output/submit_<timestamp>.json` 中解析。
2. Agent 已经解析出 sci_agent 的 `conversation-id`。
3. 设备 API 连接配置可用。

启动后，`task_id` 和 `conversation-id` 会作为启动上下文固定下来。进入轮询后，不再重新解析、不再重新扫描会话文件，也不会改变推送目标。

## Agent 前置工作

`monitor_task.py` 不负责查找当前 sci_agent 会话。Agent 必须在调用脚本前完成会话 ID 解析。

Agent 解析 `conversation-id` 的推荐流程：

1. 读取 `.agents/.env`。
2. 获取：

```text
SCI_AGENT_CHAT_SESSIONS_DIR
```

3. 进入该目录查找 sci_agent 会话 JSON 文件。
4. 每个会话文件名格式为：

```text
<conversation-id>.json
```

5. 结合当前对话内容，找到与当前会话匹配的 JSON 文件。
6. 取文件名去掉 `.json` 后的部分作为 `conversation-id`。
7. 调用 `monitor_task.py` 时通过 `--conversation-id` 显式传入。

示例：

```text
D:\Work\ZJU\sci_agent\backend\data\chat_sessions\65645bc4-962f-4f7f-ba93-a8f85f9a1244.json
```

对应：

```text
conversation-id = 65645bc4-962f-4f7f-ba93-a8f85f9a1244
```

## 启动命令

通过设备任务 ID 启动：

```bash
python .agents/skills/fdu-execution-monitoring/scripts/monitor_task.py --task-id 494 --conversation-id <conversation-id>
```

通过 `fdu-device-run` 提交结果启动：

```bash
python .agents/skills/fdu-execution-monitoring/scripts/monitor_task.py --submit-result-file .agents/skills/fdu-device-run/output/submit_xxx.json --conversation-id <conversation-id>
```

常用参数：

- `--task-id`: 设备任务 ID。
- `--submit-result-file`: `fdu-device-run` 生成的提交结果 JSON。
- `--conversation-id`: sci_agent 会话 ID，必填。
- `--poll-interval`: 轮询间隔，默认 10 秒。
- `--max-duration`: 最大监控时长，默认 172800 秒，即 48 小时；设为 `0` 表示不按时长退出。
- `--sci-agent-api-base`: sci_agent 后端地址，默认 `http://127.0.0.1:8000`。
- `--output`: 监控结果输出路径；未提供时写入 `output/task_monitor_<timestamp>.json`。

## 环境变量

设备 API 配置：

- `FDU_DEVICE_BASE_URL`
- `FDU_DEVICE_USERNAME`
- `FDU_DEVICE_PASSWORD`
- `FDU_DEVICE_TIMEOUT`

sci_agent 会话目录：

- `SCI_AGENT_CHAT_SESSIONS_DIR`

注意：`SCI_AGENT_CHAT_SESSIONS_DIR` 供 Agent 查找当前会话文件使用；`monitor_task.py` 不读取该目录来解析会话。

## 监控行为

`monitor_task.py` 启动后会：

1. 解析并固定 `task_id` 和 `conversation-id`。
2. 登录设备 API。
3. 按 `--poll-interval` 周期调用：

```text
POST /api/GetTaskInfo
POST /api/Notice
```

4. 每轮生成一条任务快照，记录到 `timeline` 和 `observations`。
5. 遇到停止条件后退出轮询。
6. 写出监控结果 JSON。
7. 如果属于异常停止，则调用 sci_agent `/api/chat/push` 推送提醒。

## 停止条件

遇到以下任一情况时停止轮询：

- 任务完成；
- 任务失败；
- 任务急停；
- 任务被用户终止；
- 检测到故障；
- 检测到告警；
- 达到 `--max-duration`。

## 推送逻辑

只有异常情况会推送到 sci_agent：

- `FAILED`
- `USER_TERMINATED`
- `EMERGENCY_STOP`
- 检测到故障；
- 检测到告警。

推送接口：

```text
POST http://127.0.0.1:8000/api/chat/push
```

推送目标使用启动时固定的 `conversation-id`。

## 输出

默认输出：

```text
output/task_monitor_<timestamp>.json
```

输出字段包括：

- `task_id`
- `conversation_id`
- `started_at`
- `ended_at`
- `stop_reason`
- `final_status`
- `timeline`
- `notices_seen`
- `faults_seen`
- `alarms_seen`
- `user_alerts`
- `observations`
- `alert_push`

## 状态映射

任务状态码：

- `0`: `UNSTARTED`
- `1`: `RUNNING`
- `2`: `COMPLETED`
- `3`: `PAUSED`
- `4`: `FAILED`
- `5`: `USER_TERMINATED`
- `6`: `PAUSING`
- `7`: `USER_TERMINATING`
- `8`: `EMERGENCY_STOP`

通知类型：

- `0`: 普通通知
- `1`: 故障
- `2`: 告警

## 禁止事项

本 skill 严格只读。不得调用：

- `AddTask`
- `StartTask`
- `StopTask`
- `CancelTask`
- `FaultRecovery`

不得执行：

- 创建设备任务；
- 启动设备任务；
- 暂停设备任务；
- 取消设备任务；
- 故障恢复；
- 重试、跳过或人工接管动作；
- 修改 protocol JSON；
- 修改 step JSON。
