# Process: BODIPY 药物筛选实验全流程
id: process-bodipy-screening-experiment
description: 用于执行一轮完整的 BODIPY 药物筛选实验，包括候选药物确认、DAY1 加药孵育、细胞孵化等待、DAY2 固定染色成像，以及后续图像分析。

## Experiment Objective

- 在候选药物集合中筛选能够显著降低脂滴相关 BODIPY 信号的药物
- 用两段式自动化实验流程将“加药孵育”和“固定染色成像”分开执行
- 基于图像分析结果比较不同候选药物对细胞脂质积累表型的影响
- 为后续复筛和机制验证提供优先候选药物名单

## Purpose

该 Process 描述的是一轮完整的 BODIPY 药物筛选实验工作情景，而不是单个 workflow 模板。

它回答的是：

- 候选药物是如何进入实验的
- 两段实验 workflow 应如何前后衔接
- 实验中需要准备哪些材料
- 图像分析应接到哪一个分析流程

## Workflow References

- DAY1 workflow:
  - `workflow:3a202bba-f1fc-6af4-738d-10afee900175`
  - `workflow_name: BODIPY---DAY1`
  - `subworkflow_name: 加药孵育`
- DAY2 workflow:
  - `workflow:3a203bb9-0e5f-dbf0-9734-b56883c4cbe1`
  - `workflow_name: BODIPY---DAY2`
  - `subworkflow_name: 固定染色成像`
- analysis process:
  - `process-bodipy-image-analysis`

## Materials

### Drug Materials

- 候选药物列表
  - 来源通常是药物推荐结果或人工确认后的候选药物集合
- `BM / BSA` 对照组对应药物或处理条件
- `FM` 对照组对应药物或处理条件
- 药物母液、工作液和药板布局信息

### Biological Samples

- 待处理细胞样品
- 已完成接种的细胞板
- 细胞培养状态信息
  - 接种时间
  - 细胞密度
  - 是否达到可加药状态

### Reagents

- 细胞培养基及相关换液试剂
- DAY2 固定与染色所需试剂
- 绿色脂滴信号相关 BODIPY 染色试剂
- 蓝色核计数通道对应试剂或染色信号来源

### Consumables

- 细胞培养板
- 药板
- 枪头、储液槽等移液耗材
- 固定、染色、成像过程中需要的辅助耗材

## Stage 1: Candidate Drug Confirmation

- type: candidate_selection
- purpose: 确认本轮进入 BODIPY 筛选实验的候选药物集合。
- input:
  - 药物推荐结果
  - 用户确认后的候选药物名单
  - 对照组定义
- output:
  - 可执行的药物清单
  - 药物与孔位或分组的映射方案

## Stage 2: Create And Execute DAY1 Workflow

- type: workflow_execution
- purpose: 新建 `BODIPY---DAY1 / 加药孵育` 实验流程，完成加药刺激和第一段自动化执行。
- workflow:
  - `workflow:3a202bba-f1fc-6af4-738d-10afee900175`
- key editable protocols:
  - `BODIPY_D1_MoveInMedPlateToP10`
  - `BODIPY_D1_MoveOutMedPlateToP8`
  - `BODIPY_D1_AddMedicineToCellPlate_Demo`
- required actions:
  - 新建一条 DAY1 实验记录
  - 载入 DAY1 workflow 参数
  - 根据流程要求完成样品、药物、耗材准备
  - 执行 DAY1 加药孵育流程
- output:
  - DAY1 实验执行记录
  - 已接受药物处理的细胞板

## Stage 3: Incubation Waiting

- type: incubation_waiting
- purpose: 在 DAY1 加药后保留足够孵化时间，让细胞产生可在 DAY2 观测到的脂滴表型变化。
- input:
  - DAY1 执行完成后的细胞板
- required conditions:
  - 细胞持续处于合适培养条件
  - 等待时间符合本轮实验设定
- output:
  - 可进入固定染色成像阶段的细胞板

## Stage 4: Create And Execute DAY2 Workflow

- type: workflow_execution
- purpose: 新建 `BODIPY---DAY2 / 固定染色成像` 实验流程，对 DAY1 处理后的细胞板执行固定、染色和高内涵成像。
- workflow:
  - `workflow:3a203bb9-0e5f-dbf0-9734-b56883c4cbe1`
- key editable protocols:
  - `BODIPY_DAY2`
  - `C:\\Protocols\\BODIPY.HTS`
- required actions:
  - 新建一条 DAY2 实验记录
  - 载入 DAY2 workflow 参数
  - 准备固定、染色和成像相关试剂与耗材
  - 执行 DAY2 固定染色成像流程
- output:
  - 多孔、多视野、双通道图像数据

## Stage 5: Image Analysis

- type: downstream_analysis
- purpose: 对 DAY2 输出图像进行核计数、绿光强度计算、单孔平均、BSA 归一化与 FM 阈值筛选。
- referenced_process:
  - `process-bodipy-image-analysis`
- input:
  - DAY2 图像目录
  - 板图文件
  - 对照组定义
- output:
  - `data-bodipy-0513-analysis-result`
  - 结构化分析报告

## Stage 6: Interpretation

- type: result_interpretation
- purpose: 结合图像分析结果判断哪些候选药物优先进入下一轮验证。
- decision rule:
  - 若本轮实验目标是 “BODIPY 值越低越好”，则优先关注低于 `FM` 组均值的候选药物
- output:
  - 候选药物优先级列表
  - 下一轮验证建议
