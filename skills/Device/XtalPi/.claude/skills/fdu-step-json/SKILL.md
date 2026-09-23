---
name: fdu-step-json
description: 这是化学实验流程的一部分，用于将结构化实验方案拆解为与五类下游技能对齐的 step JSON；只负责步骤拆分与类型归类，不负责协议编排、设备提交或实验方案生成。
---

# fdu-step-json

## 功能

将结构化实验方案拆解为原子步骤，生成可直接交给下游单步 skill 处理的 step JSON。

## 强制执行顺序

1. 使用 `python scripts/generate_step_json.py --plan-file "<方案文件>"` 或 `--plan "<方案内容>"`。
2. 如需运行内置示例，使用 `python scripts/generate_step_json.py --test`。
3. 脚本调用 `scripts/step_json_core.py` 完成解析、映射和校验。
4. 生成结果按照 `KB/unit_skill_map.json` 映射到对应下游 skill。

## 输入输出

- 输入：结构化实验方案文件、结构化实验方案文本、测试模式输入。
- 输出：`output/generated_step_json_<timestamp>.json`。
- 约束：输出顶层只保留 `timestamp` 和 `steps`，每个步骤都应具备对应的 `skill_input`。

## 注意事项

- 每个步骤都应映射到五个下游 skill 中的一个。
- `step_index` 必须连续递增。
- 不输出设备运行时字段和资源绑定字段。
- 只有实验方案明确出现高滤语义时，才使用高滤步骤类型。
- 对 `intern-s1-pro`、`intern-s1`、`intern-s1-mini` 这类模型，会自动关闭 `thinking_mode`。
- 生成过程会先读取仓库根目录 `.env`，再使用当前环境变量覆盖。
- 生成过程依赖 OpenAI 兼容接口，`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL` 和 `OPENAI_TEMPERATURE` 都必须可用。
