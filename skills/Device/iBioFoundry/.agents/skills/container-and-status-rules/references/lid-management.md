# Lid Management Rules

Use this file as the single source of truth for consumable and plate lid annotations.

## Default Lid Policy

- All approved `8Well_Plate_*` containers and BMG assay plates are lidded by default.
- When acquiring one of these plates, write `'Lidded' HasLid` after the container name.
- If the user explicitly requires an eight-well plate or BMG assay plate without a lid, manage it like other labware: do not add lid annotations unless the selected device action explicitly requires them.
- Other containers do not receive lid annotations by default.

## Acquire Syntax

For a default-lidded eight-well plate or BMG assay plate:

```javascript
Acquire,
8Well_Plate_1 'Lidded' HasLid GetMyOwnContainer where '8Well_Plate_1.Status=="New"',
BMG_Plate1 'Lidded' HasLid GetMyOwnContainer where 'BMG_Plate1.Status=="New"';
```

`'Lidded'` describes the plate state and `HasLid` declares that Momentum must manage the lid as part of the acquired container.

## Status Syntax

`Status` and lid state are independent. Never encode lid state in `set ... Status`, and do not add lid annotations to a `set` statement.

```javascript
set 8Well_Plate_1.Status = '"Completed"', BMG_Plate1.Status = '"Completed"';
```

## Device Action Syntax

For device actions, use the lid syntax defined by that exact device action template or workflow rule. Do not copy the `Acquire` syntax into every device action.

- If the action handles the plate with its lid on, use `'Lidded'`.
- If the action temporarily removes and retains the lid, use `'Unlidded'` together with `HoldLid`.
- If the action template has no lid annotation, do not add one.

Examples:

```javascript
8Well_Plate_1 'Lidded' in 'Fluent:Nest 5' GetMyOwnContainer;

BMG_Plate1 'Lidded' in 'F7_1_Rotation:Nest' GetMyOwnContainer;

BMG_Plate1 'Unlidded' in 'Clariostar:Nest' HoldLid GetMyOwnContainer;

BMG_Plate1 GetMyOwnContainer;
```

## Validation

- Every default-lidded eight-well plate or BMG assay plate in `Acquire` uses `'Lidded' HasLid`.
- An explicit user request for a lidless plate suppresses the default `Acquire` lid annotations.
- Every device-action lid annotation matches the selected device template or workflow rule.
- `set ... Status` contains no lid annotation and does not represent lid state.
