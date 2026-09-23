---
name: bo-optimizer
description: 这是化学实验流程的一部分，用于基于 chem-info-extractor 产出的 BO 表和描述符空间生成下一轮实验建议；只负责优化决策，不负责 PDF 解析、事实抽取或分子信息整理。
---

# bo-optimizer

## 功能

读取 `chem-info-extractor` 生成的 BO 表和描述符空间，调用 `EDBO+` / `summit` 生成下一轮实验建议。它只负责优化决策，不负责 PDF 解析、文本抽取或事实标准化。

## 强制执行顺序

1. 确认上游 `chem-info-extractor` 已生成 BO 表和描述符目录。
2. 检查 `manual_conditions_round0.csv` 的列名和 `select_tag` 是否可解析。
3. 运行 `run_bo_next_round.py` 生成下一轮建议。
4. 将结果写入 `bo-optimizer/output/`。

## 输入输出

- 输入：BO 表 CSV、描述符目录、可选 round 工作目录。
- 输出：下一轮实验建议 CSV。
- 约束：描述符命名必须与 BO 表一致。

## 注意事项

- 需要 `summit` 及其依赖可正常导入。
- 若缺少必需列或描述符不匹配，优化会失败。
- 只消费上游结果，不回头修正事实抽取。

## 相关文件

- `scripts/bayesian_optimization/condition_opt/run_bo_next_round.py`
- `scripts/bayesian_optimization/condition_opt/utils.py`
- `scripts/bayesian_optimization/condition_opt/EDBOplus/`
