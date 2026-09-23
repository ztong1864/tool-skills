---
name: oasis-ontology
description: 只要任务与 Oasis 绿洲实验平台有关，就必须先使用本技能，哪怕这个任务看起来是在直接执行实验流程。尤其是新建实验、选择或修改 workflow、推进 step、推进到耗材入库或样品入库、修改 protocol、查询实验数据、分析实验结果、根据历史结果调整策略，这些都必须先查 Process，再决定后续动作。Agent 不得跳过本技能直接进入执行链。
---

# Oasis-ontology

这是 Oasis 图谱技能。

这个技能是所有 Oasis 相关任务的强制前置入口，不是可选参考。

如果用户请求属于下面任一类型，Agent 必须先使用本技能，而不是直接进入执行链：

- 在 Oasis / 绿洲平台新建实验
- 选择、读取或修改 workflow
- 推进实验 step
- 推进到耗材入库、样品入库、试剂入库等执行步骤
- 修改 step 参数
- 修改 step 调用的 protocol
- 查询或使用材料、样品、试剂、耗材、细胞
- 查询实验数据、实验报告、历史结果
- 执行数据分析
- 根据历史实验结果调整当前实验策略
- 导入新的 workflow JSON
- 创建、编辑、删除图谱中的实体和关系

换句话说，只要任务里出现“新建实验 / workflow / step / protocol / 入库 / 材料 / 数据分析 / 历史结果 / 绿洲平台”这些信号词，就要先触发 `Oasis-ontology`。

它的职责不是直接调用绿洲平台执行接口，而是先帮助 Agent 搞清楚：

- 当前任务属于什么工作情景
- 该查哪类对象
- 哪些对象之间应该建立什么关系
- 什么时候该改图谱，什么时候只该读图谱

## 零、平台环境前提

在进入任何 Oasis 相关任务前，Agent 必须先带着下面这些平台前提来理解请求：

- 绿洲平台首先是一个设备动作编排系统，不是一个自动理解全部现实实验上下文的全自动实验员
- 平台的核心动作通常由机械臂搬运、小车传递、移液站执行协议、高内涵成像仪执行协议组成
- `locationId` 表示平台上的物理位置，不表示药物名、样品名或 workflow 步骤
- 入库首先表示“位置分配与系统登记”，不等于现实世界里物料已经自动放置完成
- `调度-等待` 通常表示机械臂运输、小车传递或设备间调度等待，不应直接理解为实验处理本身
- 新建实验流程的本质是组织后续可执行的动作链，而不是立刻开始现实实验
- `oasis-start` 的本质是把流程提交到实验队列，真正执行仍然需要人工确认

因此，Agent 在 Oasis 任务中的默认关注顺序应是：

1. workflow 是否正确表达实验思路
2. step 和 protocol 是否匹配
3. 当前流程是否已经推进到合适的系统状态
4. 现实物料是否需要由人工在后续阶段补放和确认

Agent 不应因为当前还没有完整物料信息，就误以为无法创建实验流程。  
很多场景下，workflow 选择、step 参数配置、protocol 配置和实验流程创建，可以先于真实物料放置完成。

## 一、触发原则

本技能的触发优先级高于执行型 Oasis skill。

这意味着：

- 如果用户说“新建一个实验流程，推进到耗材入库”，也要先用本技能
- 如果用户说“把某个 workflow 跑起来”，也要先用本技能
- 如果用户说“把这个 step 的 protocol 改掉”，也要先用本技能
- 如果用户说“看一下这个实验结果，帮我调整下一轮策略”，也要先用本技能

原因是这些请求虽然表面上是执行动作，但底层都依赖当前任务属于哪个 `Process`、涉及哪个 `Workflow`、使用哪些 `Material`、参考哪些 `Data`。

## 二、什么时候必须先用本技能

只要任务和下列任一内容有关，就必须先用本技能：

- 绿洲平台新建实验
- 绿洲 workflow / step / protocol / instrument
- 实验数据、实验报告、历史结果、分析结果
- 样品、药物、试剂、耗材、细胞等材料
- 数据分析流程、标准流程、工作方法
- 图谱实体、关系、workflow JSON 导入

## 三、强制使用顺序

所有绿洲相关任务都必须遵循下面顺序：

1. 先查 `Process`
2. 判断是否需要读取 `Process.document` 指向的 markdown 正文
3. 再按任务目标查询 `Workflow`、`Data`、`Material`、`StepType`、`StepVariant`、`Protocol`
4. 最后才进行实体创建、关系创建、workflow 导入或属性编辑

如果用户的请求看起来是直接执行链，例如：

- “新建一个实验流程，推进到耗材入库”
- “把这个实验推进到 only-step”
- “修改这个 step 的 protocol 然后继续执行”

也不能跳过第 1 步。

这些执行动作在本技能里的正确理解方式是：

- 先确定当前任务命中了哪个 `Process`
- 再确定相关 `Workflow`
- 再确定相关 `Material` / `Data`
- 最后才进入外部执行 skill 或平台调用

如果跳过第 1 步，Agent 很容易直接查 workflow 结构，却不知道当前任务属于哪种工作情景，进而选错后续动作。

## 四、为什么 Process 必须先查

`Process` 不是普通图谱节点，它是工作情景入口。

Agent 查 `Process` 的目的不是找一个“知识条目”，而是先回答下面三个问题：

- 当前任务是什么类型的工作
- 这种工作通常应该先做什么，再做什么
- 后续应该重点查哪些 `Workflow`、`Data`、`Material`

因此：

- 绿洲任务一开始先查 `Process`
- 默认只查 `Process` 的摘要字段
- 只有摘要不足以指导后续动作时，才去读 `Process.document` 对应的 markdown 正文

## 五、图谱实体定义

当前图谱分成四层语义：情景层、模板层、资源层、经验层。

### 1. 情景层

#### `Process`

表示一种工作情景或方法集合。

典型例子：

- 在绿洲平台新建实验
- 对某种实验结果做数据分析
- 下载实验文档
- 汇总实验结果并调整策略

`Process` 的用途是：

- 作为所有绿洲任务的入口对象
- 告诉 Agent 当前这类任务该怎么组织动作
- 指向该情景通常会产出的 `Data`

推荐字段：

- `id`
- `entity_type`
- `name`
- `description`
- `document`

字段含义：

- `name`
  - 这是 Process 的人类可读名字，用于搜索和判断当前任务是否命中该 Process
- `description`
  - 这是 Process 的摘要说明，用于让 Agent 在不读全文的情况下先判断是否相关
- `document`
  - 这是 Process 的正文 markdown 路径；当摘要不足时，Agent 才去打开它

### 2. 模板层

#### `Workflow`

表示绿洲平台里的实验流程模板。

它回答的是：

- 这个实验模板叫什么
- 它内部有哪些步骤
- 它依赖哪些材料
- 它关联哪些数据

推荐字段：

- `id`
- `entity_type`
- `workflow_name`
- `subworkflow_name`
- `subworkflow_id`
- `source_file`
- `source_path`
- `steps`

字段含义：

- `workflow_name`
  - workflow 的主名字，用于识别实验模板主题
- `subworkflow_name`
  - 子流程名字，用于区分 workflow 下的具体流程段
- `subworkflow_id`
  - workflow 的稳定主键
- `source_file`
  - 这个 workflow 从哪个原始 JSON 文件导入而来
- `source_path`
  - 原始接口路径或原始来源标识
- `steps`
  - 一个有序列表，列表中的元素是 `WorkflowStepRef.id`
  - Agent 通过 `steps` 知道 workflow 包含哪些步骤位置

#### `WorkflowStepRef`

表示 workflow 中的一个步骤位置引用。

它不是“步骤种类”，也不是“步骤配置”，它只负责表达：

- workflow 的这个位置引用了哪个 `StepVariant`
- 这个位置在 workflow 里的顺序
- 这个位置对应哪个源 step id

推荐字段：

- `id`
- `entity_type`
- `workflow_id`
- `step_variant_id`
- `source_step_id`
- `lane_index`
- `step_index_in_lane`
- `display_step_index`

字段含义：

- `workflow_id`
  - 说明这个步骤位置属于哪个 workflow
- `step_variant_id`
  - 说明这个位置实际使用的是哪个步骤变体
- `source_step_id`
  - 说明它在原始 JSON 里的 step id 是什么
- `lane_index` / `step_index_in_lane`
  - 用于恢复 workflow 内部顺序
- `display_step_index`
  - 用于保留界面展示层的步骤编号

#### `StepType`

表示稳定的步骤种类。

典型例子：

- `移液站-移液`
- `洗板机-洗板`
- `调度-等待`
- `高内涵仪-成像`

`StepType` 的主要用途不是保存“当前值”，而是保存：

- 这类步骤有哪些参数可以改
- 每个参数大概是什么类型
- 每个参数是干什么的

推荐字段：

- `id`
- `entity_type`
- `canonical_name`
- `normalized_name`
- `editable_parameters`

字段含义：

- `canonical_name`
  - 这是步骤种类的标准名字，Agent 查步骤类型时主要靠它识别
- `normalized_name`
  - 这是做归一化后的名字，用于减少名称差异造成的重复
- `editable_parameters`
  - 这是最重要的字段
  - Agent 在判断“这一步允许改哪些参数”时，必须看它

`editable_parameters` 中每个参数对象建议包含：

- `key`
- `value_type`
- `display_name`
- `description`

参数对象的字段含义：

- `key`
  - 程序里实际使用的参数名
- `value_type`
  - 这个参数接受什么类型的值
- `display_name`
  - 这个参数在界面或文档中的人类可读名字
- `description`
  - 这个参数改了会影响什么

#### `StepVariant`

表示某个 `StepType` 的一种具体配置。

它回答的是：

- 这一步当前具体用了什么参数
- 它调用了什么 protocol
- 它在展示层叫什么

推荐字段：

- `id`
- `entity_type`
- `step_type_id`
- `variant_signature`
- `display_step_name`
- `display_step_dev_type_name`

字段含义：

- `step_type_id`
  - 说明这个变体属于哪个步骤种类
- `variant_signature`
  - 这是这个变体的核心
  - Agent 在比较两个步骤配置是否相同时，应比较这里
- `display_step_name`
  - 这是这个变体在 workflow 展示中的名字
- `display_step_dev_type_name`
  - 这是这个变体在展示层对应的设备类型名字

#### `Protocol`

表示步骤变体引用的协议。

Agent 查 `Protocol` 的目标是判断：

- workflow 中某一步调用的是哪个协议
- 如果用户要改协议，应该改成哪个名字
- 这个协议具体是干什么的

推荐字段：

- `id`
- `entity_type`
- `protocol_key`
- `reference_name`
- `description`

字段含义：

- `protocol_key`
  - 程序内部用于稳定匹配协议的键
- `reference_name`
  - 非常重要
  - 它是在 workflow 中修改 step 调用 protocol 时所使用的名字
  - 当用户说“把这一步换成某个 protocol”时，Agent 最终要写入或匹配的就是这个名字
- `description`
  - 用于解释这个 protocol 的功能
  - 当多个 protocol 名字相近时，Agent 应依靠 `description` 区分用途

#### `Instrument`

表示步骤变体涉及的设备类型。

推荐字段：

- `id`
- `entity_type`
- `name`

字段含义：

- `name`
  - 表示这个步骤变体在设备层面对应什么设备类型
  - 当用户问“这一步是在哪个设备上做的”时，Agent 应看它

### 3. 资源层

#### `Material`

表示样品、药物、试剂、耗材、细胞等资源对象。

Agent 查 `Material` 的目标是判断：

- 有哪些资源可用
- 某个 workflow 依赖哪些资源
- 某个材料的用途是什么

当前 `material_type` 只允许三类：

- `sample`
  - 样品 / 药物
- `reagent`
  - 试剂
- `consumable`
  - 耗材 / 细胞

推荐字段：

- `id`
- `entity_type`
- `name`
- `material_type`
- `description`
- `document`（可选）

字段含义：

- `material_type`
  - 表示这是样品、试剂还是耗材
  - Agent 在判断资源类别时必须依靠它，不要自行猜测
- `description`
  - 用于解释这个材料的功能
  - 当用户问“这个材料是干什么的”时，Agent 应先看这里
- `document`
  - 如果材料有更长的说明文档，再按需读取

### 4. 经验层

#### `Data`

表示实验数据、实验报告、分析结果、结果文件等信息对象。

Agent 查 `Data` 的目标是判断：

- 过去有哪些结果
- 哪些结果能支持当前判断
- 哪些报告需要被打开阅读

推荐字段：

- `id`
- `entity_type`
- `name`
- `data_type`
- `description`
- `document`（可选）

字段含义：

- `data_type`
  - 表示这是报告、原始数据、分析结果还是其他类型的数据对象
- `description`
  - 用于说明这个数据对象记录了什么
- `document`
  - 指向更详细的正文文档或结果文件说明

## 五、图谱关系定义

### 核心业务关系

#### `Process -produce-> Data`

语义：

- 某个工作情景或方法流程会产出某类数据、报告或分析结果

Agent 什么时候用它：

- 用户问“这个 Process 会产出什么”
- 用户要找某类分析流程对应的结果对象

#### `Workflow -withData-> Data`

语义：

- 某个实验模板关联某些数据对象

Agent 什么时候用它：

- 用户问“这个 workflow 对应哪些结果、报告、数据”
- 用户要从实验模板追到历史数据

#### `Workflow -useMaterial-> Material`

语义：

- 某个实验模板依赖某些材料

Agent 什么时候用它：

- 用户问“这个 workflow 需要哪些材料”
- 用户要判断当前材料是否足够执行某个 workflow

### Workflow 内部结构关系

#### `Workflow -hasStep-> WorkflowStepRef`

语义：

- 这个 workflow 包含一个步骤位置引用

Agent 什么时候用它：

- 用户要看 workflow 里有哪些步骤
- 用户要重建 workflow 结构

#### `WorkflowStepRef -refersToVariant-> StepVariant`

语义：

- workflow 中这个位置引用了哪个步骤变体

Agent 什么时候用它：

- 用户要看 workflow 某一步当前到底用了什么配置

#### `StepVariant -instanceOf-> StepType`

语义：

- 这个具体配置属于哪个步骤种类

Agent 什么时候用它：

- 用户要从“当前配置”回溯到“这类步骤能改什么参数”

### 辅助关系

#### `StepType -usesProtocol-> Protocol`

语义：

- 这一类步骤可以填写哪些协议
- 它表达的是 StepType 的可选 protocol 集合，不是某一次具体配置当前已经绑定了哪个 protocol

Agent 什么时候用它：

- 用户要判断某一类步骤允许填写哪些 protocol
- 用户要根据步骤种类推断 protocol 候选集合
- 如果要看某个具体步骤当前已经绑定了什么 protocol，应读取 `StepVariant.variant_signature`

#### `StepVariant -usesInstrument-> Instrument`

语义：

- 这个步骤变体对应哪个设备类型

Agent 什么时候用它：

- 用户问某一步在哪种设备上执行

#### `WorkflowStepRef -precedes-> WorkflowStepRef`

语义：

- workflow 中步骤顺序关系

Agent 什么时候用它：

- 用户要恢复 workflow 的执行顺序

## 六、存储分层

### 1. source 层

表示原始输入数据，不作为图谱主数据直接编辑。

位置：

- `graph/source/workflows/`
  - 原始 workflow JSON
- `graph/source/materials/`
  - 原始 material 配置或外部材料源
- `graph/source/manifests/`
  - 导入清单、映射清单或原始同步辅助文件

规则：

- `source/` 只放原始输入
- 不要把规范化结果写回 `source/`

### 2. canonical 层

表示图谱主数据层。

位置：

- `graph/canonical/entities/`
- `graph/canonical/relations/`

规则：

- CLI 默认读写这里
- Agent 默认查询这里

### 3. schema 层

表示结构约束层。

位置：

- `graph/schema/`

### 4. sync 层

表示同步状态层。

位置：

- `graph/sync/`

## 七、文档型实体规则

`Process`、`Data`、`Material` 可以带 markdown 正文。

当前约定：

- markdown 文件放在各自实体目录下
- JSON 元数据索引放在各自目录下的 `json/` 子目录里

例如：

- `graph/canonical/entities/processes/`
- `graph/canonical/entities/processes/json/processes.json`

规则：

- JSON 记录元数据
- markdown 记录正文
- `document` 字段指向 markdown 文件

### 文档型实体维护要求

`Process`、`Data`、`Material` 这三类实体不是只写 markdown 就结束了。

Agent 在维护它们时，必须同时保证下面两层是一致的：

- 正文 markdown
  - 放在对应实体目录下
- JSON 元数据索引
  - 放在对应目录下的 `json/` 子目录里

对应位置如下：

- `Process`
  - markdown: `graph/canonical/entities/processes/`
  - json: `graph/canonical/entities/processes/json/processes.json`
- `Data`
  - markdown: `graph/canonical/entities/data/`
  - json: `graph/canonical/entities/data/json/data.json`
- `Material`
  - markdown: `graph/canonical/entities/materials/`
  - json: `graph/canonical/entities/materials/json/materials.json`

维护原则：

- 优先使用 CLI 创建或更新文档型实体
  - 这样程序会同时维护 JSON 元数据和 `document` 字段
- 如果先手工补了 markdown 正文，也必须补对应 JSON 索引
  - 否则 Agent 后续无法通过 `entity-list` / `entity-get` 搜到它
- 只写 JSON、不写 markdown 也不完整
  - 因为 `Process`、`Data`、`Material` 的关键解释通常在正文里

简单理解：

- markdown 负责“让人读懂”
- json 负责“让程序检索到”

这两层缺一不可。

## 八、CLI 入口

统一使用：

```bash
python scripts/graph_cli.py <command> [options]
```

## 九、Agent 必会命令

### 1. 初始化

```bash
python scripts/graph_cli.py init
```

### 2. 先查 Process 摘要

```bash
python scripts/graph_cli.py entity-list --type Process --text 新建实验
python scripts/graph_cli.py entity-list --type Process --text 数据分析
python scripts/graph_cli.py entity-list --type Process --text BODIPY
```

如果命中后需要正文，再读取 `document` 指向的 markdown。

### 3. 查 Workflow / Step / Data / Material

```bash
python scripts/graph_cli.py entity-list --type Workflow --text BODIPY
python scripts/graph_cli.py entity-list --type StepType --text 移液
python scripts/graph_cli.py entity-list --type Data --text 报告
python scripts/graph_cli.py entity-list --type Material --text 染料
```

### 4. 获取单个实体

```bash
python scripts/graph_cli.py entity-get --type StepType --id step-type:item--1195f0ed
python scripts/graph_cli.py entity-get --type Workflow --id workflow:3a202bba-f1fc-6af4-738d-10afee900175
```

### 5. 新建实体

普通实体：

```bash
python scripts/graph_cli.py entity-create \
  --type Protocol \
  --id protocol:openlid--a11c29b0 \
  --prop protocol_key=OpenLid \
  --prop reference_name=OpenLid \
  --prop description="用于移液开盖动作的协议"
```

文档型实体：

```bash
python scripts/graph_cli.py entity-create \
  --type Process \
  --id process:new-experiment-on-oasis \
  --prop name="在绿洲平台新建实验" \
  --prop description="指导 Agent 在绿洲平台中完成实验新建的过程性知识" \
  --document-name new-experiment-on-oasis.md \
  --document-content "# 在绿洲平台新建实验"
```

### 5.1 不同实体的最小创建模板

不要把所有实体都按 `Process` 的例子硬套。不同实体至少要区分成下面几类。

#### `Process`

适用场景：

- 新建实验标准流程
- BODIPY 图像分析流程
- 完整实验流程
- 文档下载流程

最小示例：

```bash
python scripts/graph_cli.py entity-create \
  --type Process \
  --id process:bodipy-screening \
  --prop name="BODIPY 药物筛选实验全流程" \
  --prop description="从候选药物确认到 DAY1、DAY2 和图像分析的完整流程" \
  --document-name BODIPYScreeningExperimentProcess.md \
  --document-content "# Process: BODIPY 药物筛选实验全流程"
```

关键属性：

- `id`
- `entity_type`
- `name`
- `description`
- `document`

#### `Data`

适用场景：

- 实验分析结果
- 实验报告
- 原始数据结果

最小示例：

```bash
python scripts/graph_cli.py entity-create \
  --type Data \
  --id data:bodipy-0513-analysis-result \
  --prop name="BODIPY 0513 analysis result" \
  --prop data_type="analysis_result" \
  --prop description="BODIPY 0513 实验的图像分析结果" \
  --document-name BODIPY0513AnalysisResult.md \
  --document-content "# Data: BODIPY 0513 analysis result"
```

关键属性：

- `id`
- `entity_type`
- `name`
- `data_type`
- `description`
- `document`

#### `Material`

适用场景：

- 样品
- 药物
- 试剂
- 耗材

最小示例：

```bash
python scripts/graph_cli.py entity-create \
  --type Material \
  --id material:bodipy-dye \
  --prop name="BODIPY 染料" \
  --prop material_type="reagent" \
  --prop description="用于脂滴相关荧光信号染色的试剂" \
  --document-name BODIPYDye.md \
  --document-content "# Material: BODIPY 染料"
```

关键属性：

- `id`
- `entity_type`
- `name`
- `material_type`
- `description`
- `document`

注意：`material_type` 只允许：

- `sample`
- `reagent`
- `consumable`

#### `Protocol`

适用场景：

- workflow 某一步实际调用的协议
- 要给 step 绑定或替换的协议

最小示例：

```bash
python scripts/graph_cli.py entity-create \
  --type Protocol \
  --id protocol:bodipy-day2 \
  --prop protocol_key=BODIPY_DAY2 \
  --prop reference_name=BODIPY_DAY2 \
  --prop description="BODIPY DAY2 固定染色相关移液协议"
```

关键属性：

- `id`
- `entity_type`
- `protocol_key`
- `reference_name`
- `description`

#### `StepType`

适用场景：

- 需要先补一个新的步骤种类抽象
- 某个 workflow 对应的步骤种类还没有进入图谱
- 需要先定义这类步骤允许修改哪些参数

最小示例：

```bash
python scripts/graph_cli.py entity-create \
  --type StepType \
  --id step-type:liquid-handler-operation \
  --prop canonical_name="移液站-移液" \
  --prop normalized_name="移液站-移液" \
  --prop editable_parameters='[{"key":"protocol","value_type":"string","display_name":"移液协议","description":"该步骤使用的移液协议"}]'
```

关键属性：

- `id`
- `entity_type`
- `canonical_name`
- `normalized_name`
- `editable_parameters`

注意：

- `editable_parameters` 必须是 list
- 如果这个 `StepType` 明确来自某个 workflow JSON，默认仍然优先使用 `workflow-import`
- 手工添加更适合“图谱里暂时还没有，但你已经明确知道要抽象出一个步骤种类”的情况

#### `StepVariant`

适用场景：

- 需要补一个具体步骤配置
- 需要手工表达“某个步骤种类在当前流程里用了哪组 protocol / 展示名 / 设备名”

最小示例：

```bash
python scripts/graph_cli.py entity-create \
  --type StepVariant \
  --id step-variant:bodipy-day2-imaging \
  --prop step_type_id=step-type:high-content-imaging \
  --prop variant_signature='{"protocol":"C:\\\\Protocols\\\\BODIPY.HTS"}' \
  --prop display_step_name="成像" \
  --prop display_step_dev_type_name="高内涵仪A"
```

关键属性：

- `id`
- `entity_type`
- `step_type_id`
- `variant_signature`
- `display_step_name`
- `display_step_dev_type_name`

注意：

- `variant_signature` 建议写成 JSON 对象字符串，表达当前配置最关键的差异
- `StepVariant` 本身不会自动连上 `StepType`
- `StepVariant` 中写了 protocol，也不会自动生成 `StepType -usesProtocol-> Protocol`
- 如果是手工补录，后续还要补关系：
  - `StepVariant -instanceOf-> StepType`
  - `StepType -usesProtocol-> Protocol`
  - `StepVariant -usesInstrument-> Instrument`

#### `WorkflowStepRef`

适用场景：

- 需要手工表达 workflow 中某个具体步骤位置
- 需要把 workflow 的步骤顺序和某个 `StepVariant` 接起来

最小示例：

```bash
python scripts/graph_cli.py entity-create \
  --type WorkflowStepRef \
  --id workflow-step-ref:demo-workflow:step-01 \
  --prop workflow_id=workflow:demo-workflow \
  --prop step_variant_id=step-variant:bodipy-day2-imaging \
  --prop source_step_id=step-01 \
  --prop lane_index=0 \
  --prop step_index_in_lane=2 \
  --prop display_step_index=4
```

关键属性：

- `id`
- `entity_type`
- `workflow_id`
- `step_variant_id`
- `source_step_id`
- `lane_index`
- `step_index_in_lane`
- `display_step_index`

注意：

- `WorkflowStepRef` 是“workflow 里的步骤位置”，不是步骤种类本身
- 如果手工创建，后续通常还要补关系：
  - `Workflow -hasStep-> WorkflowStepRef`
  - `WorkflowStepRef -refersToVariant-> StepVariant`
  - 必要时补 `WorkflowStepRef -precedes-> WorkflowStepRef`

#### `Workflow`

通常不要手工新建 `Workflow`。优先用 `workflow-import` 从原始 JSON 导入。

原因：

- `Workflow` 不只是一个名字
- 它还依赖 `WorkflowStepRef`
- 还依赖 `StepVariant`
- 还依赖 `hasStep / refersToVariant / instanceOf / usesProtocol / usesInstrument` 等关系

所以：

- `Workflow / WorkflowStepRef / StepType / StepVariant / Instrument`
  - 默认优先走 `workflow-import`
- `Process / Data / Material`
  - 更适合 Agent 按工作过程持续维护

### 6. 编辑实体属性

```bash
python scripts/graph_cli.py entity-update \
  --type Protocol \
  --id protocol:openlid--a11c29b0 \
  --set description="用于移液开盖动作的协议"
```

编辑文档型实体正文：

```bash
python scripts/graph_cli.py entity-update \
  --type Process \
  --id process:new-experiment-on-oasis \
  --document-name new-experiment-on-oasis.md \
  --document-content "# 更新后的正文"
```

### 7. 删除实体

```bash
python scripts/graph_cli.py entity-delete --type Material --id material:bodipy-dye
```

删除实体时，程序会一并清理关联关系。

### 8. 创建关系

```bash
python scripts/graph_cli.py relation-create \
  --type produce \
  --from process:new-experiment-on-oasis \
  --to data:bodipy-report-2026-01-01
```

```bash
python scripts/graph_cli.py relation-create \
  --type useMaterial \
  --from workflow:3a202bba-f1fc-6af4-738d-10afee900175 \
  --to material:bodipy-dye
```

### 9. 查看关系

```bash
python scripts/graph_cli.py relation-list --type produce
python scripts/graph_cli.py relation-list --entity-id workflow:3a202bba-f1fc-6af4-738d-10afee900175
```

### 10. 导入 workflow JSON

```bash
python scripts/graph_cli.py workflow-import \
  --file sub-workflow-step-parameters/BODIPY---DAY1__加药孵育__3a202bba-f1fc-6af4-738d-10afee900175.json
```

如果已知该 workflow 关联的材料或数据，也可以一起挂接：

```bash
python scripts/graph_cli.py workflow-import \
  --file sub-workflow-step-parameters/BODIPY---DAY1__加药孵育__3a202bba-f1fc-6af4-738d-10afee900175.json \
  --material-id material:bodipy-dye \
  --data-id data:bodipy-report-2026-01-01
```

## 十、Agent 默认决策规则

- 用户要找“怎么做某件事”
  - 先查 `Process`
- 用户要找实验模板或平台步骤
  - 查 `Workflow`、`StepType`、`StepVariant`
- 用户要找过去实验结果或报告
  - 查 `Data`
- 用户要判断有哪些试剂、样品、耗材可用
  - 查 `Material`
- 用户要修改 Protocol / Material / Process 的解释性内容
  - 直接编辑对应实体的 `description` 或正文 markdown

## 十一、不要这样做

- 不要在绿洲任务里跳过 `Process` 查询
- 不要默认全量读取所有 `Process` markdown
- 不要手工改 `graph/` 里的 JSON，优先走 CLI
- 不要把 `StepVariant` 当成 `StepType`
- 不要把 `Workflow` 当成 `Process`
- 不要为没有必要的场景臆造关系

## 十二、关键原则

**所有绿洲相关任务，先查 Process 摘要，再按需查 Workflow / Data / Material / Step。**

## Knowledge 维护规则

`Knowledge` 是长期规则知识实体，用于保存可复用的实验或分析规则，例如：

- 命名规则
- 通道语义规则
- 归一化规则
- 结果判读规则
- 固定实验室约定

`Knowledge` 不是 workflow-import 自动生成的对象。  
它需要由 Agent 手工维护，并且应通过关系：

- `Knowledge -guides-> Process`

来表达“这条长期规则指导哪个外围流程”。

`Knowledge` 的维护不只发生在遇到新 workflow JSON、协议文件或新脚本时。  
只要 Agent 在日常 Oasis 相关任务中遇到稳定、可复用、后续大概率还会再次使用的知识，就应评估是否写入 ontology。

默认原则：

- 新 workflow、新 step 结构，优先补 `Workflow / WorkflowStepRef / StepType / StepVariant`
- 日常任务中新发现的长期规则、命名约定、分析口径、材料含义、模型解释，优先补 `Knowledge`
- 如果知识本身已经构成可复用对象，也可以同步补 `Material`、`Data`、`Process`

Agent 不应把这些知识只留在当前对话里。  
如果它们已经足够稳定、不是一次性临时备注，就应沉淀到 ontology，作为后续任务的常备知识层。

### 何时新增 Knowledge

当用户提供的信息不是某一次实验的临时备注，而是后续还会重复使用的稳定规则时，应新增 `Knowledge`，而不是只写进某个 `Process` 文档里。

例如：

- “w1 代表蓝色核计数，w2 代表绿色强度”
- “所有单孔结果都要 normalize 到 BSA 组均值”
- “某类实验默认以 FM 平均值作为筛选阈值”

### Knowledge 的维护位置

- markdown 正文：
  - `graph/canonical/entities/knowledge/`
- JSON 索引：
  - `graph/canonical/entities/knowledge/json/knowledge.json`

和 `Process / Data / Material` 一样，写完 markdown 后，必须同步维护 JSON 索引。

### 创建 Knowledge 实体

```bash
python scripts/graph_cli.py entity-create \
  --type Knowledge \
  --id knowledge:bodipy-image-analysis-rules \
  --prop name="BODIPY image analysis rules" \
  --prop description="Long-term reusable rules for BODIPY image analysis." \
  --document-name BODIPYImageAnalysisKnowledge.md \
  --document-content "# Knowledge: BODIPY image analysis rules"
```

### 创建 guides 关系

```bash
python scripts/graph_cli.py relation-create \
  --type guides \
  --from knowledge:bodipy-image-analysis-rules \
  --to process:bodipy-image-analysis
```

### Knowledge 与 Process 的分工

- `Process`
  - 描述“怎么做一类外围流程”
- `Knowledge`
  - 描述“做这类流程时长期遵循的规则”

不要把长期规则只写进 `Process` 而不沉淀为 `Knowledge`；否则后续其它流程无法复用这些规则。
