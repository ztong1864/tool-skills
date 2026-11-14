# Process 控制结构编写规范

`process { ... }` 里除了设备动作，还有五种控制结构。它们都不是设备动作，所以在
`$device-operation-library` 里找不到模板，写法以本文为准。

本文的写法全部来自 iBioFoundry 机器上在跑的参考脚本（`GYF_1_Plasmid_PCR_DpnI`、
`GYF_2_Ecoli_DNA_transformation`、`GYF_3_Detect`），不是推演出来的。

---

## 1. `parallel` / `branch` 并行块

多条互不依赖的支线同时推进时用 `parallel`。每条支线是一个 `branch`，注释
`// i of n` 里的 `i` 从 1 开始、`n` 是分支总数，两个数字都必须和实际分支数对得上。

```javascript
parallel
{
	branch // 1 of 2
	{
		ALPS3000 [Seal]
			(...)
			02_LYY_PCR_plate in 'ALPS3000:Nest' GetMyOwnContainer;

		Cytomat_2C425 [Load]
			(...)
			02_LYY_PCR_plate GetMyOwnContainer;
	}
	branch // 2 of 2
	{
		XPeel [Remove Seal]
			(...)
			02_LYY_PCR_plate_2 in 'XPeel:Nest' GetMyOwnContainer;
	}
}
```

规则：

- `parallel` 块在 `parallel` 的所有分支都结束后才继续往下走，相当于一个汇合点。
- 分支可以嵌套：`branch` 里面可以再写 `parallel`。参考脚本里出现过两层嵌套、
  以及 2、3、4 个分支的情况。
- 分支数量没有上限，但每多一条分支就多一次设备争用，见下一节。
- 缩进每层加一个制表符：`parallel` 与 `{` 同级，`branch` 与其 `{` 再缩进一级，
  分支内的语句再缩进一级。

### 并行块里的设备争用

两条分支同时要同一台设备时，Momentum 不会替你排队，必须自己用设备锁（见第 2 节）。
参考脚本里 `FreedomEVO`、`CentrifugeLoader`、`Rotanta460`、`Clariostar` 四台都是这么处理的。

单 nest 设备（`ALPS3000:Nest`、`XPeel:Nest`、`KBSWasp_sealer:Nest`）在不同分支里
反复出现是允许的，读
`../../device-operation-library/references/workflow-rules/single-nest-device-occupancy.md`。

---

## 2. 设备锁 `Acquire(变量)` / `Release(变量)`

`variables` 固定模板里已经声明了四个锁变量，**不要新增、不要改名**：

| 变量 | 锁住的设备 |
| --- | --- |
| `Lock_EVO` | `FreedomEVO` |
| `lock_CentrifugeLoader` | `CentrifugeLoader`（注意首字母小写，模板就是这么写的） |
| `Lock_Clariostar` | `Clariostar` + `F7_1_Rotation` 这一组 |
| `Lock_Rotanta` | `Rotanta460` |

模板里另有 `Lock_Echo`、`Lock_Fluent` 两个锁变量，当前参考脚本没用到，需要时照同样写法用。

```javascript
Acquire(Lock_EVO);

FreedomEVO [Load]
	(...)
	02_LYY_PCR_plate in 'FreedomEVO:Nest 1' GetMyOwnContainer;

FreedomEVO [RunScript]
	(...)

Release(Lock_EVO);
```

规则：

- `Acquire(变量);` 和 `Release(变量);` 必须成对，且在同一层（同一个 `branch` 或同一个
  顶层序列）里成对。不要在一条分支里 `Acquire`、在另一条里 `Release`。
- 锁要**包住整段连续占用**，而不是每个动作各锁一次。参考脚本里 `Lock_EVO` 一次包住
  "上板 → 跑脚本 → 下板封板"的整段。
- 走 `Clariostar` 的那三步（旋转 → 读板 → 旋转）必须整段加 `Lock_Clariostar`，因为
  `F7_1_Rotation` 是读板机的进出口，两块板同时进会撞。
- 锁和容器的 `Acquire` 是两件事：`Acquire(Lock_EVO);` 带括号锁设备，
  `Acquire, 容器 ...;` 带逗号取容器。不要混写。
- 只在并行块里会争用时才加锁。纯顺序流程加锁不会出错，但是多余的。

---

## 3. `wait_until` 等待点

```javascript
wait_until
	(WaitType = 'Expression', WaitUntil = '6/11/2026 4:09:16 PM', 
	IgnoreDate = 'Yes', WaitTimeout = '120') ;
```

- `IgnoreDate = 'Yes'` 时只看时刻不看日期，`WaitUntil` 里的日期是占位，留着不用管。
- `WaitTimeout` 单位是分钟。
- 典型用途是在并行分支里卡一个时间点，让这条支线等另一条支线把设备腾出来。
  要等的是"另一条支线做完"时，用设备锁而不是 `wait_until`。

---

## 4. `AddWork` 串联下一份脚本

一个实验拆成多份脚本时，上一份结尾用 `AddWork` 把下一份排进队列：

```javascript
AddWork
	(WorkType = 'Batch', BatchType = 'Experiment', SourceName = 'E_GYF_2_Ecoli_DNA_transformation', 
	ProcessName = 'GYF_2_Ecoli_DNA_transformation', Iterations = '1', 
	AutoVerifyLoad = 'No', AutoUnload = 'No', AutoVerifyUnload = 'No', 
	StartType = 'As soon as possible', FixedStart = '9/18/2026 9:45:58 AM', 
	RelativeStart = '00:00:00') ;
```

规则：

- `ProcessName` 是下一份脚本的 `process[...]` 名字**去掉 `AI\` 这类目录前缀**。
- `SourceName` 是 Momentum 里那个 Experiment 的名字，约定为 `E_` + `ProcessName`。
  这个 Experiment 必须在机器上**事先存在**，`AddWork` 不会创建它。
- 因此被串联的流程名**不能带时间戳**，否则 `SourceName` 指向一个不存在的 Experiment，
  脚本能导入但运行到 `AddWork` 会失败。多脚本串联的命名例外见
  `../SKILL.md` 的"多脚本串联时的命名"。
- `StartType = 'As soon as possible'` 时 `FixedStart` 是占位值，不用管。
- `AddWork` 写在 `process` 的最后一条语句，放在所有设备动作之后。
- 容器状态同样承担串联作用：上一份脚本把交接板 `set` 成一个约定状态，下一份脚本用
  `where '板名.Status=="该状态"'` 取出来。两份脚本里的**容器名必须是同一个**，
  否则下一份取不到板。

---

## 5. `comment` 阶段注释

```javascript
comment ('STEP 1 : pcr') ;
```

- 每个实验阶段开头写一条，内容用实验员在原始方案里的叫法。
- 孵育这类"时长就是方案"的步骤，把时长写进注释，例如 `comment ('incubate 8h') ;`。
- `comment` 是语句，结尾要有 `;`，和设备动作一样参与缩进。

---

## 校验清单

- [ ] 每个 `branch` 的 `// i of n` 与实际分支数一致
- [ ] 每个 `Acquire(变量)` 都有同层的 `Release(变量)`
- [ ] 并行分支里争用的设备都加了锁
- [ ] 走 `Clariostar` 的三步整段加了 `Lock_Clariostar`
- [ ] `AddWork` 的 `ProcessName` 不带目录前缀、不带时间戳
- [ ] `AddWork` 的 `SourceName` 等于 `E_` + `ProcessName`
- [ ] 跨脚本交接的容器名在两份脚本里一致
- [ ] `AddWork` 是 `process` 的最后一条语句
