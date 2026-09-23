# FDU 中文实验方案 Schema

输出必须严格参考 `KB/example_plan.md` 的 Markdown 结构。

## 顶层标题

```markdown
# 实验方案 T-3:<index>
```

## 固定章节

必须且只使用以下章节：

```markdown
## 实验概述
## 试剂作用与用量
## 实验步骤
## 反应位置与过滤信息
```

## 内容规则

- 每个推荐条件输出一个独立 Markdown 文件。
- `## 试剂作用与用量` 使用项目符号列表。
- `## 实验步骤` 使用连续编号列表。
- 反应位使用 `T-3:<index>`。
- 过滤目标位使用 `W3-5:<index>`。
- 不输出设备 JSON。
- 不输出 `layout_code`、`chemical_id`、`tray_QR_code`、`QR_code`。

## 输入参数

- 步骤模板：`--steps-file`，必填
- 推荐用量 CSV：`--amounts-csv`，必填
- 输出目录：`--output-dir`，可选，默认 `output/experiment_plan_<timestamp>/`
- 反应位前缀：`--tray`，可选，默认 `T-3`
