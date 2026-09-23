# Process: 绿洲平台药物推荐流程
id: process-drug-recommendation-on-oasis
description: 用于在绿洲平台场景下执行药物推荐的标准流程，药物推荐能力由 primekg-drug-recommendation skill 提供。

## Objective

- 在绿洲平台相关实验设计前，为指定疾病或表型目标生成候选药物集合
- 将药物推荐作为实验候选集生成环节，供后续 workflow 执行、物料准备和数据分析使用

## Skill Binding

- recommendation skill:
  - `primekg-drug-recommendation`
- purpose:
  - 基于疾病、适应症或目标表型生成候选药物列表
  - 为 Oasis 新建实验或筛选实验提供候选小分子输入

## When To Use

- 用户要求在绿洲平台场景中先做药物推荐
- 用户要求为某个疾病（如肥胖症）推荐候选小分子，再进入实验验证
- 用户需要把推荐结果作为后续 BODIPY 或其它表型实验的候选样品集合

## Inputs

- 疾病名称、适应症或目标表型
- 候选数量要求
- 可选的筛选偏好或约束条件

## Outputs

- 候选药物名单
- 可供 Oasis 实验流程使用的候选集
- 供后续样品映射与入库使用的药物名称列表

## Downstream Usage

- 可作为 `process-bodipy-screening-experiment` 的候选药物输入阶段
- 推荐结果应在进入实验执行链前由用户确认

## Notes

- 该 Process 负责定义绿洲平台中的药物推荐工作情景，不直接执行 workflow
- 真正的推荐能力来自 `primekg-drug-recommendation` skill
- 若推荐结果要进入 Oasis 执行链，后续仍需查询相关 Workflow、Material 和 Step 约束