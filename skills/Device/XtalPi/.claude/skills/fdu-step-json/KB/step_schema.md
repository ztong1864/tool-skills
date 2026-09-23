# 单步 JSON Schema

请生成一个 JSON object，把实验方案拆解为原子化操作步骤。

## 顶层结构

输出必须是如下结构：

```json
{
  "timestamp": "2026-04-10-10-30-00",
  "steps": [
    {
      "step_index": 1,
      "unit_type": "exp_add_solid",
      "downstream_skill": "fdu-add-solid-json",
      "instruction": "向 T-3:0 加入 5 mg PdCl2",
      "skill_input": {
        "layout_code": "T-3:0",
        "unit_column": 0,
        "unit_row": 0,
        "substance": "PdCl2",
        "add_weight": 5,
        "unit": "mg"
      }
    }
  ]
}
```

## steps 中每一步的必需字段

每个步骤对象都必须包含：

- `step_index`
- `unit_type`
- `downstream_skill`
- `instruction`
- `skill_input`

## 顶层字段

顶层对象必须包含：

- `timestamp`
- `steps`

说明：
- `timestamp` 格式固定为 `YYYY-MM-DD-HH-MM-SS`
- 不再输出 `format`
- 不再输出 `version`

## layout 相关规则

- `skill_input` 统一使用 `layout_code`
- 不再使用 `target_layout_code`
- 不再使用 `source_layout_code`
- `unit_column` 必须从 `layout_code` 末尾的 `:<数字>` 解析得到
- `unit_row` 必须按每个 `layout_code` 内部步骤从 `0` 开始递增

## unit_type 与 skill_input 的字段对应关系

### `exp_add_solid`

- `layout_code`
- `unit_column`
- `unit_row`
- `substance`
- `add_weight`
- `unit`

### `exp_pipetting`

- `layout_code`
- `unit_column`
- `unit_row`
- `substance`
- `add_volume`
- `unit`

### `exp_magnetic_stirrer`

- `layout_code`
- `unit_column`
- `unit_row`
- `temperature`
- `reaction_duration`
- `rotation_speed`
- `is_wait`
- `still_tem`

### `exp_filtering_samples`

- `layout_code`
- `unit_column`
- `unit_row`
- `add_volume`
- `unit`
- `dst_pos`

说明：如果下游允许自动推断过滤目标位，`dst_pos` 可以为 `null`。

### `exp_high_filtering_samples`

- `layout_code`
- `unit_column`
- `unit_row`
- `add_volume`
- `substance`
- `dilute_volume`
- `unit`
- `dst_pos`

说明：如果下游允许自动推断高滤目标位，`dst_pos` 可以为 `null`。

## 过滤类步骤判别规则

- 只有实验方案明确出现“高滤”“高过滤”“高滤取样”“高滤样品”等表达时，才使用 `exp_high_filtering_samples`
- 普通“过滤”“过滤取样”“过滤样品”“HPLC 过滤样品”默认使用 `exp_filtering_samples`
- 不允许把“高滤”错误映射成普通过滤，也不允许把普通过滤错误映射成高滤
- `instruction` 文案必须与 `unit_type` 一致
- `exp_filtering_samples` 使用“过滤”
- `exp_high_filtering_samples` 使用“高滤”

## 允许的取值

### `unit_type`

- `exp_add_solid`
- `exp_pipetting`
- `exp_magnetic_stirrer`
- `exp_filtering_samples`
- `exp_high_filtering_samples`

### `downstream_skill`

必须与 `unit_type` 精确对应。

## instruction 写法规则

- 每一步都使用一条中文单句
- 加料使用 `向 T-3:0 加入 ...`
- 反应控制使用 `T-3:0 在 ... 下搅拌 ...`
- 过滤使用 `从 T-3:0 取 ... 过滤`
- 高滤使用 `从 T-3:0 取 ... 高滤`
- 化学物名称应与 `skill_input.substance` 保持一致

## 不要输出的内容

- Markdown
- `chemical_id`
- `tray_QR_code`
- `QR_code`
- 与当前 schema 无关的设备绑定字段
- 一个 step 中包含多个物理动作
