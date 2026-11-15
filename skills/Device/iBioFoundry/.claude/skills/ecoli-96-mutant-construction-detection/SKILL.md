---
name: ecoli-96-mutant-construction-detection
description: 'Generate the three chained Momentum DSL txt scripts for the 96-mutant E. coli plasmid workflow: whole-plasmid PCR plus DpnI digestion, chemical transformation with recovery and plating onto twelve eight-well plates, then seed culture, IPTG induction, harvest, TBS wash and BCA/fluorescence reading. Trigger on requests such as "96突变体全流程", "质粒构建与检测", "转化与涂布", "IPTG诱导检测", "BCA检测", "第一份脚本"/"第二份脚本"/"第三份脚本".'
---

# 96 突变体大肠杆菌质粒构建与检测

用这个技能生成三份互相串联的 Momentum `.txt` 脚本。三份脚本对应机器上在跑的
`GYF_1_Plasmid_PCR_DpnI`、`GYF_2_Ecoli_DNA_transformation`、`GYF_3_Detect`，原件留在
`references/source-scripts/`。

**不是这个实验的话看另一个技能。** DH5α 宿主、四块八孔板（32 格）、Fluent 涂布与挑克隆、
单块 BMG 板 Bradford 检测的那一套在
[$dh5a-plasmid-construction](../dh5a-plasmid-construction/SKILL.md)，产出两份独立脚本。
两边的 EVO/Fluent 方法、ATC 协议、容器名没有一个是共用的，不要混用。

## 支持的协议

- `gyf_plasmid_pcr_dpni`：全质粒 PCR 与 DpnI 酶切（第一份）。
- `gyf_ecoli_dna_transformation`：化学转化、复苏与涂布十二块八孔板（第二份）。
- `gyf_detect`：种子培养、转接、IPTG 诱导、离心收菌、TBS 洗涤、BCA 与荧光检测（第三份）。
- `gyf_full_96_mutant_workflow`：一次生成以上三份。

## 规模

原生规模是**一块 96 孔板的 96 个突变体**，涂到**十二块八孔板共 96 格——一个突变体一格**。
这和 `dh5a-plasmid-construction` 的四块板 32 格不同：那里 96 孔怎么归并到 32 格写在 Tecan
方法内部，技能看不到；这里是 1:1，没有归并。

- 板数用 `--spreading-plates K` 显式指定，默认十二块。少于十二块时脚本自己的 `comment`
  里会写明缩减了多少、以及设备方法没跟着变，终端也会打印同一句话。
- `--mutants D2A,D2S,...`（或 `--mutants-file`）会在脚本旁边多写一份
  `foundry_<时间戳>_platemap.csv`，四列 `pcr_well,mutant,spreading_plate,compartment`。
  96 孔板**按列填**（A1、B1…H1、A2…），第 j 列的 8 个孔对应 `8Well_Plate_j`——这也是
  十二块板按顺序放在 EVO 第 1 到第 12 位的原因。**填充方向待 iBioFoundry 团队确认。**
- `--mutant-count N` 只和名字个数对账，不影响脚本。
- **设备端的方法不随板数改变**（`AI_GYF_Plating.esc` 等）。缩减规模前必须与 iBioFoundry
  团队确认这些方法能否配合，否则脚本能生成但设备上未必能跑。

向用户确认方案时就要把规模说清楚（几个突变体、几块板、设备方法这条限制）。

## 三份脚本是串起来的

第一份结尾用 `AddWork` 排第二份，第二份排第三份。由此有两条约束，生成和导入时都要照办：

1. **流程名固定、不带时间戳**：`process [AI\\\\GYF_1_Plasmid_PCR_DpnI]`。`AddWork` 的
   `SourceName` 指向机器上事先建好的 Experiment（`E_` + 流程名），名字一带时间戳就对不上。
   输出**文件名**照旧带时间戳。这是 `script-assembler/SKILL.md`"多脚本串联时的命名"里
   写明的例外。
2. **三份都要先导入，再启动第一份**。只导入第一份的话，它跑到 `AddWork` 会找不到下一个流程。

## 参考脚本保真与板子交接

用户确认 `references/source-scripts/` 三份原件为可运行的权威模板。默认生成必须保留每处
容器标识、板号、状态值、大小写、设备绑定位置和控制流程，不能自动改名、重编号、统一
拼写或推断修正。即使跨脚本标识不同也原样保留；只有用户明确要求修改时才能调整，并说明差异。
用户明确指定其他参考版本时，先比对并记录差异，不能静默替换模板。

第一份把 `02_LYY_PCR_plate_2` 标为 `PCR_Plate_DpnI`；第二份按此状态获取并使用
`02_LYY_PCR_plate_1`。两者的现场交接机制无法仅从脚本确定，不要声称它们必然是同一块板。
第二份中 `02_LYY_PCR_Plate_3` 与 `02_LYY_PCR_plate_3` 及 `Status`/`status` 的原始拼写也要逐处保留。
第二份的 `02_LYY_cell_plate1` 状态为 `Revive_plate`，第三份按 `New` 获取同名容器；具体实物交接须由实验员确认。
生成后的参考校验不能放行这些标识或状态拼写变更。

## Workflow

1. 把用户需求对到 `references/intent-map.yaml`。
2. 读 `references/procedure-map.yaml` 看自然语言层级：实验名 → 阶段 → 实验子步骤 →
   代码步骤 ID。注意里面的 `derived_text` 是从脚本反推的中文描述，**不是实验员的原话**；
   与实验员对齐后应替换成他的原文。
3. 读匹配到的 protocol 文件，拿到容器清单与可执行的阶段顺序。
4. 读匹配到的 step-map 文件，拿到步骤 ID 与参数化的设备动作。
5. 设备动作模板以 `../device-operation-library/SKILL.md` 为准。
6. 容器合法性、`Acquire`、`set ... Status` 以 `../container-and-status-rules/SKILL.md` 为准。
7. 并行块、设备锁、`wait_until`、`AddWork` 的写法以
   `../script-assembler/instructions/control-flow.md` 为准。
8. 固定的 `runtime/devices/pools/variables` 以 `../script-assembler/SKILL.md` 为准。
9. 用 `scripts/generate_script.py` 生成脚本。默认规模交付前必须运行下方参考校验；失败时停止交付并报告差异，不得称为模板一致。缩减规模属于用户指定的改动，须单独说明并核查，其结果不等同于原始模板。

## Command

```bash
python .claude/skills/ecoli-96-mutant-construction-detection/scripts/generate_script.py --request "生成96突变体大肠杆菌质粒构建与检测实验脚本"
```

```bash
python .claude/skills/ecoli-96-mutant-construction-detection/scripts/generate_script.py --request "生成第三份脚本"
```

缩减规模并带突变体名字（见"规模"）：

```bash
python .claude/skills/ecoli-96-mutant-construction-detection/scripts/generate_script.py --request "96突变体全流程" --spreading-plates 3 --mutant-count 24 --mutants "M1,M2,M3,M4,M5,M6,M7,M8,M9,M10,M11,M12,M13,M14,M15,M16,M17,M18,M19,M20,M21,M22,M23,M24" --output-dir <artifact 目录>
```

默认写到 `outputs/` 下，用 `--output-dir <path>` 换目录。请求对不上任何意图时会列出本技能
认得的几类请求，而不是抛堆栈。

## 改完必须自检

```bash
python .claude/skills/ecoli-96-mutant-construction-detection/scripts/verify_against_reference.py
```

它重新生成三份脚本，和 `references/source-scripts/` 里的原件逐语句比对（忽略换行位置和
参数顺序），并检查 `procedure-map.yaml` 覆盖了每一个代码步骤。**改了这个技能的 protocol
或 step-map、改了 `device-operation-library` 的设备模板、改了 `script-assembler` 的固定段，
都要跑一次**——共用模板在这个技能底下变了，这里会报不一致，而不是悄悄生成一份与机器不符的脚本。

## Design Boundary

- 实验语义留在本技能：意图短语、自然语言阶段表、可执行流程、每个协议的 step map。
- 设备 DSL 模板留在 `device-operation-library`，不要把模板正文抄进本技能。
- 固定段留在 `script-assembler`，不要把 `runtime/devices/pools/variables` 抄进本技能。
- 控制结构的写法留在 `script-assembler/instructions/control-flow.md`；生成器从那里取
  `AddWork` 和 `wait_until` 的模板，并不自带一份。
- 容器目录与状态默认值留在 `container-and-status-rules`。

## Validation

生成后检查：

- 文件名符合 `foundry_<standard_name>_<YYYYMMDD_HHMMSS>.txt`。
- `process[...]` 是固定流程名（带 `AI\\\\` 前缀、不带时间戳）。
- 三份脚本的 `AddWork` 指向下一份的流程名，`SourceName` 等于 `E_` + 流程名。
- 流程里出现的每个容器都在某个 `Acquire` 块里，配平板也在。
- 每个 `Acquire(锁)` 都有同层的 `Release(锁)`。
- 带 `--spreading-plates K` 时，`Acquire` 里正好 K 块 `8Well_Plate_*`，且没有任何设备步骤
  提到第 K 块之后的板。
- 带 `--mutants` 时，`_platemap.csv` 每个名字一行，顺序与给定顺序一致。

生成器自己会在这几条上报错而不是输出一份坏脚本：容器声明了却没 `Acquire`、设备动作用了
没 `Acquire` 的容器、`final_status` 没有对应的 `set`、`Acquire` 重复、锁不成对或不同层、
step-map 里有没被引用的步骤（这一条只提示，不报错）。
