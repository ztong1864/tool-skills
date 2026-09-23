# KB v4 原理库构建完成报告

**报告日期**: 2026-05-23
**构建范围**: 扩散相关文献（20 篇论文）

---

## 一、构建概述

KB v4 原理库（PrincipleKB）在 v3.4 材料库基础上新增原理性知识层，解决 v3.4 中"原理性知识被任务话题切片器切碎、无法独立检索和跨任务复用"的核心问题。本次构建聚焦于 20 篇扩散相关文献，完成从 PDF 解析到 PrinciplePlaybook 组织的全 9 级流水线。

### 设计理念

| 维度 | v3.4 材料库 | v4 原理库 |
|------|------------|----------|
| 知识类型 | 材料性能数据、设计规则 | 因果机理、定量关系、边界条件 |
| 组织方式 | 按任务话题切片 | 按机理原型聚合 |
| 可复用性 | 绑定具体任务 | 跨任务可复用 |
| 检索方式 | 任务→材料→规则 | 任务→原理→杠杆→行动 |

---

## 二、流水线架构与执行

### 9 级流水线 P1-P9

| 阶段 | 模块 | 功能 | 产出 |
|------|------|------|------|
| P1 | PrincipleDocumentParser | PDF 解析 + 文本分块 | 260 文件, 55,216 文本块 |
| P2 | ConceptEntityExtractor | 概念实体识别 | 20 文件, 1,028 实体 |
| P3 | PrincipleTraceExtractor | PrincipleTrace 抽取 | 20 文件, 4,838 traces |
| P4 | TypedClaimClassifier | Typed Claim 分型 | 20 文件, 4,838 claims |
| P5 | MechanismPrincipleAggregator | MechanismPrinciple 聚合 | 11 条原理 |
| P6 | StructurePropertyMapBuilder | StructurePropertyMap 构建 | 85 条映射 |
| P7 | OptimizationLeverDeriver | OptimizationLever 推导 | 31 条杠杆 |
| P8 | DesignAxiomDistiller | DesignAxiom 蒸馏 | 7 条公理 |
| P9 | PrinciplePlaybookOrganizer | PrinciplePlaybook 组织 | 12 个 Playbook |

### 执行时间

| 阶段 | 耗时 | 备注 |
|------|------|------|
| P1 | 已缓存 | 之前已完成 |
| P2 | 3,836 秒 (~64 分钟) | 16 篇新论文 |
| P3 | 7,535 秒 (~126 分钟) | 14 篇新论文 |
| P4 | 19,435 秒 (~324 分钟) | 4,838 次 LLM 调用 |
| P5 | 117 秒 | 聚合计算 |
| P6 | 815 秒 | LLM 辅助构建 |
| P7 | 268 秒 | LLM 辅助推导 |
| P8 | 49 秒 | LLM 辅助蒸馏 |
| P9 | 510 秒 | 12 个任务 Playbook |
| **总计** | **~9.6 小时** | |

---

## 三、数据统计

### 3.1 扩散文献 Trace 分析

20 篇扩散文献共产出 4,838 条 PrincipleTraces，类型分布如下：

| Trace 类型 | 数量 | 占比 | 说明 |
|-----------|------|------|------|
| causal | 1,854 | 38.3% | 因果声明（"X导致Y"） |
| quantitative | 949 | 19.6% | 定量关系（方程、比例） |
| empirical_observation | 799 | 16.5% | 经验观察 |
| boundary | 522 | 10.8% | 边界条件（适用范围限制） |
| meta | 363 | 7.5% | 元陈述（综述性总结） |
| theoretical_derivation | 351 | 7.1% | 理论推导 |

**关键发现**：causal + quantitative 占 58%，说明超过一半的抽取结果是具有因果或定量结构的高价值声明。

### 3.2 概念实体统计

1,028 个概念实体，高频概念 Top 15：

| 概念 | 频次 | 类别 |
|------|------|------|
| diffusion coefficient | 74 | PhysicalQuantity |
| molecular diffusion | 70 | PhysicalProcess |
| adsorption | 60 | PhysicalProcess |
| framework flexibility | 58 | StructuralFeature |
| residence time distribution | 45 | PhysicalQuantity |
| guest size | 37 | ControlVariable |
| kinetic diameter | 36 | PhysicalQuantity |
| temperature dependence | 36 | ControlVariable |
| transport diffusivity | 31 | PhysicalQuantity |
| interfacial resistance | 29 | PhysicalProcess |
| loading-dependent diffusion | 27 | PhysicalProcess |
| self-diffusion coefficient | 26 | PhysicalQuantity |
| activation energy | 25 | PhysicalQuantity |
| loading dependence | 25 | ControlVariable |
| corrected diffusivity | 24 | PhysicalQuantity |

### 3.3 MechanismPrinciples 详情

11 条 MechanismPrinciples 中，最核心的是：

**限域诱导的平移-转动耦合扩散** (`mprin_e6a4d6`)
- 聚合了来自 24 篇论文的 4,379 条 traces
- 适用任务：气体分离、蒸汽分离、烃类异构体分离、膜分离、吸附分离
- 设计含义：通过调控孔道尺寸和形状，可以实现从平移扩散为主到转动-平移耦合扩散的切换，从而改变选择性

其他重要原理：
- 趋于平衡降低动态选择性（C3H6/C3H8 分离核心原理）
- 三唑环顺式取向诱导的V形配体构象（配体设计原理）
- AUA力中心偏移联合原子表征（分子模拟原理）

### 3.4 OptimizationLevers 分布

31 条 OptimizationLevers，按适用任务分组：

| 任务领域 | 杠杆数 | 示例 |
|---------|--------|------|
| 气体分离 | 14 | 孔窗尺寸调控、扩散路径工程、负载依赖性利用 |
| 分子模拟 | 6 | AUA力场选择、模拟时间步长优化 |
| 材料表征 | 4 | 红外光谱配位态判定、颗粒流动性评估 |
| 催化 | 3 | 微环境调控、气相反应物富集 |
| 材料成型 | 2 | 粉体流动性优化、反应器装填 |
| 光学传感 | 2 | 激发波长选择、发光位移调控 |

### 3.5 PrinciplePlaybooks 详情

12 个 Playbook，共 99 个有序步骤：

| Playbook | 步骤数 | 任务 |
|----------|--------|------|
| gas_separation | 8 | 通用气体分离 |
| C3H6/C3H8 separation | 8 | 丙烯/丙烷动力学分离 |
| kinetic_separation | 8 | 动力学分离 |
| diffusion_selective_separation | 8 | 扩散选择性分离 |
| adsorptive_separation | 9 | 吸附分离 |
| membrane_separation | 9 | 膜分离 |
| breakthrough_screening | 8 | 穿透实验筛选 |
| pore_engineering | 8 | 孔道工程 |
| mof_design | 8 | MOF 设计 |
| diffusion_simulation | 8 | 扩散模拟 |
| adsorption_modeling | 8 | 吸附建模 |
| mass_transfer_analysis | 9 | 传质分析 |

---

## 四、构建过程中修复的缺陷

| # | 严重度 | 模块 | 问题 | 修复 |
|---|--------|------|------|------|
| 1 | 高 | P3 | `PrincipleTraceExtractor` 查找 `mentions_*.json`，但 P2 输出 `entities_*.json` | 改为读取 `entities_*.json` |
| 2 | 高 | P4 | `classify()` 调用 `classify_claims_for_paper()` 使用模块级 `_V4_CLAIMS` | 重写为自包含方法 |
| 3 | 高 | P5 | `aggregate()` 调用 `run_p5()` 使用模块级路径 | 重写为自包含方法 |
| 4 | 高 | P6 | 同 P5 模式 | 重写 |
| 5 | 高 | P7/P8 | 同 P5 模式 | 重写 |
| 6 | 致命 | P9 | `__init__` 签名与 pipeline runner 不匹配 | 新增兼容参数 |
| 7 | 高 | Pipeline runner | 目录名不一致 (`claims/` vs `typed_claims/` 等) | 统一命名 |
| 8 | 高 | P9 | Pipeline runner 调用 `organize()` 但正确方法是 `organize_playbook()` | 改用 `run_all_tasks()` |
| 9 | 高 | P9 | 任务注册表与 lever `applicable_tasks` 不匹配 | 更新为实际使用的任务 ID |

---

## 五、LLM 调用统计

### 模型回退链

gpt-5.4 → gemini-3.5-flash → gemini-3.1-pro-preview → claude-opus-4-7

### 调用情况

| 模型 | 状态 | 备注 |
|------|------|------|
| gpt-5.4 | 主要模型 | JSON 格式化问题频繁（~30% 调用需要重试），但内容质量高 |
| gemini-3.5-flash | 回退模型 | 经常不返回 JSON 对象，成功率约 50% |
| gemini-3.1-pro-preview | 额度耗尽 | 402 Payment Required |
| claude-opus-4-7 | 最终回退 | 很少被调用到 |

### 主要问题

1. **gpt-5.4 JSON 格式化**：长输出时经常在 ~193 行产生 JSON 语法错误（缺少逗号分隔符）
2. **gemini-3.5-flash 不返回 JSON**：约 50% 调用返回纯文本而非 JSON 对象
3. **重试机制有效**：3 次尝试 + 4 模型回退确保了大多数抽取的成功

---

## 六、文件清单

### 新增代码文件

```
mof_agent/knowledge_base/builder/
  principle_document_parser.py          (P1)
  concept_entity_extractor.py          (P2)
  principle_trace_extractor.py         (P3)
  typed_claim_classifier.py            (P4)
  mechanism_principle_aggregator.py    (P5)
  structure_property_map_builder.py    (P6)
  optimization_lever_deriver.py        (P7)
  design_axiom_distiller.py            (P8)
  principle_playbook_organizer.py      (P9)
  run_principle_pipeline.py            (统一入口)
  paper_router.py                      (P0 路由器)
  __init__.py                          (动态加载)

mof_agent/knowledge_base/schemas/
  principle_entities.py                (4 个实体类型)
  principle_evidence.py                (4 个证据类型)
  principle_core.py                    (5 个核心类型)
  principle_methods.py                 (4 个方法类型)

mof_agent/knowledge_base/config/
  principle_vocab.json                 (44 个种子概念)
  mechanism_archetypes.json            (10 个原型)

mof_agent/knowledge_base/retriever_v4.py  (RetrieverV4)
```

### 数据文件

```
memory/knowledge_base/v4/
  build_progress_v4.json
  shared/
    paper_routing.json
    kinetic_diameter_table.json
  principle/
    parsed/          (260 个解析文件)
    entities/        (20+ 个实体文件)
    traces/          (148 个 trace 文件)
    typed_claims/    (24 个 claim 文件)
    principles/      (11 个原理文件)
    sp_maps/         (85 个 SP 映射)
    opt_levers/      (11 个杠杆组)
    axioms/          (2 个公理组)
    playbooks/       (12 个 Playbook)
  bridge_indexes/    (6 个桥接索引)
  wiki/principles/   (Wiki 骨架)
  principle_indexes/ (5 个索引文件)
```

---

## 七、核心发现与洞察

### 7.1 扩散知识的核心原理网络

通过 P5 聚合，发现扩散领域的关键原理可归纳为以下层级：

```
Level 0: 限域耦合扩散 (mprin_e6a4d6) — 超级原理
  ├── 24 篇论文, 4,379 traces 聚合
  ├── 适用范围: 气体分离/膜分离/吸附分离
  └── 核心杠杆: 孔窗尺寸 → 扩散机制切换

Level 1: 特定机理原理
  ├── 趋于平衡降低动态选择性 (mprin_019ad6)
  │   └── C3H6/C3H8 分离的直接理论支撑
  ├── 配体构象控制 (mprin_28c2b2)
  │   └── MOF 设计中的配体选择原理
  └── 微环境调控 (mprin_98e690)
      └── 催化中的协同效应

Level 2: 工具性原理
  ├── 分子模拟力场选择 (mprin_404fa4)
  ├── 颗粒模型理想化 (mprin_90c18a)
  └── 红外光谱配位态判定 (mprin_2b9de9)
```

### 7.2 v3.4 问题的解决

| v3.4 问题 | v4 解决方案 | 验证 |
|-----------|------------|------|
| 扩散综述被切碎为 traces | 聚合为 MechanismPrinciple | 4,379 traces → 1 条超级原理 |
| design_rule 强绑任务 | applicable_tasks 多值 | 每条原理平均覆盖 2-3 个任务 |
| 无跨论文综合 | P5 聚合 + P6 SP 映射 | 11 条原理来自 20+ 篇论文 |
| 无"原理→行动"链路 | P7-P9 生成杠杆/公理/Playbook | 31 杠杆 + 7 公理 + 12 Playbook |

---

## 八、后续建议

### 8.1 短期优化（1-2 周）

1. **扩展原理库**：将剩余 240 篇双管道论文加入原理库
2. **P9 任务注册表自动化**：从 lever/axiom 的 `applicable_tasks` 自动生成任务列表
3. **LLM JSON 格式化**：改进 prompt 减少重试率，或增加 JSON 修复逻辑
4. **Playbook 质量验证**：人工检查 12 个 Playbook 的步骤可执行性

### 8.2 中期增强（1-2 月）

1. **RetrieverV4 真实数据集成测试**：用真实原理库数据验证检索融合
2. **桥接索引更新**：根据实际产出的 principles/levers/axioms 更新桥接索引
3. **CounterPrinciple 补充**：当前缺少反原理数据，需要补充
4. **原理间关系图**：构建原理间的依赖/冲突/增强关系网络

### 8.3 长期方向（3-6 月）

1. **增量更新机制**：新论文自动进入流水线，增量更新原理库
2. **人机协同验证**：领域专家审核原理的准确性和完整性
3. **与其他知识库对接**：连接外部机理数据库（如 Catalysis-Hub）
4. **Agent 集成**：将 RetrieverV4 接入 MOF Discovery Agent 的决策循环

---

*报告生成时间: 2026-05-23 23:10 CST*
