# Acquire And Status Rules

Use these rules only inside Momentum DSL `process [] {}` blocks.

## Status Value Source

- Prefer the status values explicitly specified by the current structured experiment mapping.
- If an `Acquire` status is not specified for a container, default to `"New"`.
- If a `set ... Status` value is not specified for a container, default to `"used"` for consumed tips/consumables and `"Completed"` for output plates or completed experiment containers.

Keep experiment-specific statuses such as reagent states, sample states, intermediate states, or workflow states in the experiment-specific mapping that introduced them. Do not add those experiment-specific values to this shared rule file.

Do not infer extra Status values from device templates or free text when no structured experiment mapping specifies them.

## Required Order

Inside every `process [] {}` block, use this order:

1. `Acquire` all required containers.
2. Write one complete `set ... Status` statement immediately after `Acquire`.
3. Begin device actions only after the `set` statement.

Do not place device actions between `Acquire` and `set ... Status`, and do not defer the required `set` statement until the end of the process.

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
- Keep all required status assignments in the single `set` statement immediately after `Acquire`.

## Validation Checklist

- [ ] Every acquired container uses an approved container name.
- [ ] Every `Acquire` status comes from the structured experiment mapping or defaults to `"New"`.
- [ ] The `set ... Status` statement immediately follows `Acquire`, before every device action.
- [ ] Every `set ... Status` value comes from the structured experiment mapping or defaults to `"used"` / `"Completed"`.
- [ ] Every `Acquire` lid annotation follows `lid-management.md`.
- [ ] No inferred status value is introduced without support from the structured experiment mapping.
