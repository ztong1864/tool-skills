# Reagent Plate First-Use Unsealing

Apply this rule when arranging the first device operation for containers classified as reagent plates in `container-and-status-rules/references/container-catalog.md`.

## Rule

- After the required adjacent `Acquire` and `set ... Status` statements, treat a container's first appearance as its first occurrence in the device-operation sequence.
- Before each reagent plate's first appearance, run `XPeel [Remove Seal]` for that reagent plate.
- This is a one-time first-appearance requirement for each reagent plate. Do not add another `XPeel [Remove Seal]` when the same plate appears again later in the process.
- Do not run `XPeel [Remove Seal]` for containers outside the reagent-plate category.
- When more than one reagent plate is present, apply the rule separately to each plate and follow `single-nest-device-occupancy.md` between XPeel operations.

## Pattern

```javascript
XPeel [Remove Seal]
	(...)
	Primer1 in 'XPeel:Nest' GetMyOwnContainer;

Device [Action]
	(...)
	Primer1 GetMyOwnContainer;
```

The `XPeel` action must precede the reagent plate's first non-XPeel device action. Later uses of `Primer1` do not receive another automatic unsealing step.
