# Acquire And Status Rules

Use these rules only inside Momentum DSL `process [] {}` blocks.

## Status Value Source

- Prefer the status values explicitly specified by the current structured experiment mapping.
- If an `Acquire` status is not specified for a container, default to `"New"`.
- If a `set ... Status` value is not specified for a container, default to `"used"` for consumed tips/consumables and `"Completed"` for output plates or completed experiment containers.

Keep experiment-specific statuses such as reagent states, sample states, intermediate states, or workflow states in the experiment-specific mapping that introduced them. Do not add those experiment-specific values to this shared rule file.

Do not infer extra Status values from device templates or free text when no structured experiment mapping specifies them.

## Required Order

The default shape, and the only one to use unless the experiment forces otherwise:

1. `Acquire` all required containers.
2. Write one complete `set ... Status` statement immediately after `Acquire`.
3. Begin device actions only after the `set` statement.

Never place a device action between an `Acquire` block and the `set ... Status` that belongs to it.

### 允许的三种例外

这三种写法都来自机器上在跑的参考脚本，不是放宽尺度，而是补齐规则：

**一、分支内的 `Acquire`。** 容器分成互不相干的几组、各组在 `parallel` 的不同分支里起步时，
可以在每个 `branch` 里各写一个 `Acquire` 块。这些容器的 `set ... Status` 写在整个
`parallel` 块**结束之后**的第一条语句——写在分支内会让两条支线同时改状态。

```javascript
parallel
{
	branch // 1 of 2
	{
		Acquire,
		03_48DWP_1 GetMyOwnContainer where '03_48DWP_1.Status=="48DWP_1"',
		Cell_Plate1 GetMyOwnContainer where 'Cell_Plate1.Status=="LB_1"';
	}
	branch // 2 of 2
	{
		Acquire,
		03_AX_Buffer GetMyOwnContainer,
		Tips_MCA200_1 GetMyOwnContainer where 'Tips_MCA200_1.Status=="New"';
	}
}

set Cell_Plate1.Status = '"Completed"', Tips_MCA200_1.Status = '"Used"';
```

**二、流程中段的 `set ... Status`。** 只在两种情形下允许：容器的工作流状态确实在流程中间
发生变化（例如 PCR 产物经 DpnI 酶切后从 `"PCR_plate"` 变成 `"PCR_Plate_DpnI"`），
或者需要把交接状态留给下一份脚本去 `where`。这两种都是流程语义，不是补写漏掉的 `set`。

**三、不带 `where` 的 `Acquire`。** 只用于不参与实验状态流转的容器：配平板
（`Balance_PCR`、`Balance_DWP*`）和整板一次性取用的缓冲液板。这类容器不写状态过滤，
也不写进 `set`。

配平板**必须** `Acquire`。只在设备动作里写 `Balance_PCR in 'CentrifugeLoader:Bucket 2'`
而不 `Acquire` 它，是一个会让脚本在机器上取不到板的缺陷。

## Acquire And Status Pattern

Every acquired container must use the approved container name and either an experiment-specified status filter or the default `"New"` status filter.

```javascript
Acquire,
Cell_Plate1 GetMyOwnContainer where 'Cell_Plate1.Status=="New"',
Primer1 GetMyOwnContainer where 'Primer1.Status=="PrimerMix"',
Tips_Liha200_1 GetMyOwnContainer where 'Tips_Liha200_1.Status=="New"',
BMG_Plate1 'Lidded' HasLid GetMyOwnContainer where 'BMG_Plate1.Status=="New"';

set Cell_Plate1.Status = '"Completed"', Primer1.Status = '"Completed"', Tips_Liha200_1.Status = '"used"', BMG_Plate1.Status = '"Completed"';

Device [Action]
	(...)
	Cell_Plate1 GetMyOwnContainer;
```

Rules:

- Replace only the container identifiers.
- Use only container identifiers from `container-catalog.md`.
- Use an experiment-specified `Acquire` status when the protocol mapping provides one.
- Otherwise keep the default `Acquire` status as `"New"`.
- Apply [lid-management.md](lid-management.md) to the container binding.
- Default-lidded `8Well_Plate_*` and BMG assay plates use `'Lidded' HasLid` between the container name and `GetMyOwnContainer`.

## Status Setting Rules

Use the immediately following `set ... Status` statement to assign acquired containers the experiment-specified status. If no status is specified, use the default `"used"` or `"Completed"` convention.

Rules:

- Use `"used"` for consumed tips and other consumables that should not be reused.
- Use `"Completed"` for experiment plates or containers that represent completed output.
- Use experiment-specific final states only when they come from the structured experiment mapping.
- Do not assign `"New"` in `set ... Status` unless the experiment mapping explicitly requires it.
- Do not use `set ... Status` to represent lid-open or lid-closed state.
- Keep all required status assignments in the `set` statement that belongs to their own `Acquire` block.
- A mid-process `set` is allowed only for a real workflow-state change or a handoff to the next script; see the exceptions above.

## Validation Checklist

- [ ] Every acquired container uses an approved container name.
- [ ] Every `Acquire` status comes from the structured experiment mapping or defaults to `"New"`.
- [ ] Each `set ... Status` statement immediately follows its own `Acquire` block, before every device action that uses those containers.
- [ ] 分支内 `Acquire` 的 `set` 写在 `parallel` 块之后，而不是分支里。
- [ ] 流程中段的每一条 `set` 都对应一次真实的状态变化或跨脚本交接。
- [ ] 流程里用到的配平板都出现在某个 `Acquire` 块里。
- [ ] Every `set ... Status` value comes from the structured experiment mapping or defaults to `"used"` / `"Completed"`.
- [ ] Every `Acquire` lid annotation follows `lid-management.md`.
- [ ] No inferred status value is introduced without support from the structured experiment mapping.
