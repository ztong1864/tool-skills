---
name: process-flow-planner
description: Momentum DSL 脚本中 process 部分的流程安排规范，指导如何合理规划实验步骤顺序。
---

# Process 流程安排规范

## 📋 核心原则

1. **顺序执行** - process 中的步骤按从上到下顺序执行，`parallel` 块内的分支并发执行
2. **先获取再设状态** - 先 Acquire 获取耗材，紧接着执行 set
3. **随后设备操作** - 用到某组容器的设备动作必须位于该组的 set 之后
4. **必要约束** - 某些设备操作有固定前后置要求（如酶标仪需旋转）
5. **并发要加锁** - 并行分支里争用同一台设备时必须用设备锁，见
   `../script-assembler/instructions/control-flow.md`

---

## 🔄 标准流程结构

```javascript
process [foundry_standard_experiment_name_YYYYMMDD_HHMMSS]
{
    // 1. 获取所有需要的耗材
    Acquire,
    Plate1 GetMyOwnContainer where 'Plate1.Status=="New"',
    Plate2 GetMyOwnContainer where 'Plate2.Status=="New"',
    Tips_1 GetMyOwnContainer where 'Tips_1.Status=="New"';

    // 2. 紧接 Acquire 设置状态
    set Plate1.Status = '"Completed"', Plate2.Status = '"Completed"', Tips_1.Status = '"used"';

    // 3. 实验操作步骤（按顺序）
    // 3.1 前处理
    Device [Action]
        (...)
        Plate1 GetMyOwnContainer;
    
    // 3.2 移液操作
    FreedomEVO [RunScript]
        (...)
        Plate1 in 'FreedomEVO:Nest 9' GetMyOwnContainer;
    
    // 3.3 培养/孵育
    CYTOMAT_2_Tos2 [Incubate]
        (...)
        Plate1 GetMyOwnContainer;
    
    // 3.4 检测
    Device [Action]
        (...)
        Plate1 GetMyOwnContainer;
}
```

---

## 📝 流程规划要点

### 0. process 命名
- `process[...]` 名称由最终脚本文件名决定，必须等于输出 `.txt` 文件名去掉 `.txt` 后缀。
- 文件名由脚本组装阶段生成，格式为 `foundry_<standard_name>_<YYYYMMDD_HHMMSS>.txt`。

### 1. Acquire 阶段
- 列出所有需要的耗材（板子、枪头等）
- 为每个耗材指定初始状态标记
- 状态标记前后要一致

### 2. set 阶段
- `set ... Status` 必须紧接在其对应 `Acquire` 块的结束分号之后
- 在 `Acquire` 与 `set` 之间不得插入设备动作
- 同一个 `Acquire` 块的容器状态集中写入该 `set` 语句
- 容器分组在 `parallel` 分支里起步、状态在中段真实变化、或容器是配平板时，按
  `../container-and-status-rules/references/acquire-and-status.md` 的"允许的三种例外"写

### 3. 设备操作阶段
- 按实验逻辑顺序安排设备
- 注意设备依赖关系（如酶标仪前后需旋转）
- 每个设备动作前加注释说明来源
- 盖子管理统一读取 `../container-and-status-rules/references/lid-management.md`；设备动作中的盖子写法读取对应设备模板或 workflow rule
- 试剂板首次进入设备操作前必须按 `../device-operation-library/references/workflow-rules/reagent-plate-first-use-unsealing.md` 撕膜一次；同一试剂板后续再次出现不重复撕膜，其他板子不撕膜

---

## ⚠️ 特殊设备流程要求

### 酶标仪（Clariostar）

- 三步顺序和设备动作盖子写法统一读取 `../device-operation-library/references/workflow-rules/clariostar-rotation.md`。

### 离心机（CentrifugeLoader）- 需要平衡
```javascript
CentrifugeLoader [Spin]
    (...)
    PCR_Plate1 in 'CentrifugeLoader:Bucket 1' GetMyOwnContainer,
    Balance_PCR in 'CentrifugeLoader:Bucket 2' GetMyOwnContainer;  // 平衡板

Cytomat_24H [Load]
    (...)
    PCR_Plate1 GetMyOwnContainer,
    Balance_PCR GetMyOwnContainer;
```

说明：
- 默认将样品板写为 `PCR_Plate1`，将平衡板写为 `Balance_PCR`
- `Bucket 1` 默认放 `PCR_Plate1`，`Bucket 2` 默认放 `Balance_PCR`
- 离心后的下一步 `Cytomat_24H [Load]` 默认继续加载这两个容器，不要漏掉 `Balance_PCR`
- `Balance_PCR` 仅用于物理配平，无需写入紧接 `Acquire` 的 `set ... Status`，除非实验流程明确改变其工作流状态

---

## 🎯 流程设计检查清单

- [ ] 所有需要的耗材都在 Acquire 中列出，配平板也要列
- [ ] `set ... Status` 紧接其对应 `Acquire`，且位于用到这些容器的设备动作之前
- [ ] 并行分支里争用的设备都加了设备锁，且 `Acquire`/`Release` 成对同层
- [ ] `process[...]` 名称等于最终脚本文件名去掉 `.txt`
- [ ] 设备操作顺序符合实验逻辑
- [ ] 酶标仪操作包含前后旋转步骤
- [ ] 离心操作有平衡板
- [ ] 离心后的下游设备是否保留了样品板和平衡板的成对传递
- [ ] `set ... Status` 不包含仅用于配平的 `Balance_PCR`
- [ ] 每个设备动作都添加了来源注释

---
