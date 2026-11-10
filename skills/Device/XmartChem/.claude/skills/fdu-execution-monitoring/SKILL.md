---
name: fdu-execution-monitoring
description: 这是 FDU 设备任务提交后的只读持续监控 skill。用于在设备任务已经创建后持续读取任务状态、进度、通知、故障和告警；发现异常时把提醒推送到发起监控的对话。本 skill 只做观察和提醒，不得启动、暂停、取消、恢复、重试、跳过、提交或修改任何设备任务。
---

# fdu-execution-monitoring

`fdu-execution-monitoring` 用于监控已经创建的 FDU 设备任务。

它的职责是：

- 持续读取设备任务状态；
- 持续读取设备通知、故障和告警；
- 在任务完成、失败、急停、终止、故障或告警时停止轮询；
- 写出监控结果；
- 在异常情况下向发起监控的对话推送提醒。

它不是设备控制 skill，不处理恢复动作。

## 使用前提

只有在以下条件都满足时，才允许启动 `monitor_task.py`：

1. 已经有设备任务 ID：
   - 通过 `--task-id` 显式提供；
   - 或从 `fdu-device-run` 的提交记录中解析：在 LabOntology 中是 mission 的 artifacts 目录下的 `submit.json`；单独使用时是 `.claude/skills/fdu-device-run/output/submit_<timestamp>.json`。
2. 有接收提醒的对话 ID（`conversation-id`），见下方“对话 ID”。
3. 设备 API 连接配置可用。

启动后，`task_id` 和 `conversation-id` 会作为启动上下文固定下来。进入轮询后，不再重新解析、不再重新扫描会话文件，也不会改变推送目标。

## 对话 ID

异常提醒推送到发起监控的这个对话。在 FounDryClaw 对话中，当前对话的 ID 在环境变量 `FOUNDRYCLAW_CONVERSATION_ID` 里，`monitor_task.py` 不带 `--conversation-id` 时自动使用它，不需要另外查找会话文件。只有提醒要发到另一个对话，或在 FounDryClaw 之外运行（没有这个环境变量）时，才用 `--conversation-id` 显式传入。

## 启动命令

通过设备任务 ID 启动：

```bash
python .claude/skills/fdu-execution-monitoring/scripts/monitor_task.py --task-id 494
```

通过 `fdu-device-run` 提交结果启动：

```bash
python .claude/skills/fdu-execution-monitoring/scripts/monitor_task.py --submit-result-file <fdu-device-run 的提交记录 JSON>
```

常用参数：

- `--task-id`: 设备任务 ID。
- `--submit-result-file`: `fdu-device-run` 生成的提交结果 JSON。
- `--conversation-id`: 接收提醒的对话 ID；默认取 `FOUNDRYCLAW_CONVERSATION_ID`（当前对话），没有这个环境变量时必填。
- `--poll-interval`: 轮询间隔，默认 10 秒。
- `--max-duration`: 最大监控时长，默认 172800 秒，即 48 小时；设为 `0` 表示不按时长退出。
- `--sci-agent-api-base`: 接收推送的后端地址；默认取 `FOUNDRYCLAW_MODEL_ROUTER_BASE_URL`（FounDryClaw 对话中就是本平台后端），没有这个环境变量时为 `http://127.0.0.1:8000`。
- `--output`: 监控结果输出路径；在 LabOntology 中写 mission 的 artifacts 目录下的文件；未提供时写入本技能目录的 `output/task_monitor_<timestamp>.json`（所有用户共用）。

## 环境变量

设备 API 配置：

- `FDU_DEVICE_BASE_URL`
- `FDU_DEVICE_USERNAME`
- `FDU_DEVICE_PASSWORD`
- `FDU_DEVICE_TIMEOUT`

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
7. 如果属于异常停止，则调用后端的 `/api/chat/push` 把提醒推送到对话。

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

只有异常情况会推送到对话：

- `FAILED`
- `USER_TERMINATED`
- `EMERGENCY_STOP`
- 检测到故障；
- 检测到告警。

推送接口：

```text
POST <--sci-agent-api-base>/api/chat/push
```

推送目标使用启动时固定的 `conversation-id`。

## 输出

默认输出（本技能目录下；LabOntology 中用 `--output` 写进 mission 的 artifacts 目录）：

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
