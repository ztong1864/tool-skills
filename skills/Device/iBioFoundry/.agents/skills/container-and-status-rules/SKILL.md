---
name: container-and-status-rules
description: Momentum container, consumable, lid, Acquire, and Status rule library. Use when selecting approved container names, managing plate lids, or writing/checking Acquire and set Status statements inside a process block.
---

# Container And Status Rules

Use this skill as the single entry point for container names, consumable selection, lid management, `Acquire` statements, and `set ... Status` updates.

## Responsibilities

- This skill owns the approved container name inventory.
- This skill owns the default lid policy and `Acquire` lid syntax.
- This skill owns `Acquire` and immediately following `set ... Status` writing patterns inside `process [] {}` blocks.
- [$device-operation-library](../device-operation-library/SKILL.md) owns device action templates and workflow rules.
- [IB-machine-operation](../IB-machine-operation/SKILL.md) orchestrates the full script and should read this skill before selecting device templates.

## What To Read

- Approved container list: [references/container-catalog.md](references/container-catalog.md)
- Lid management rules: [references/lid-management.md](references/lid-management.md)
- Acquire and status rules: [references/acquire-and-status.md](references/acquire-and-status.md)
- Device-dependent labware routing, tip waste syntax, and post-operation staging are owned by `../device-operation-library/references/workflow-rules/default-labware-destinations.md`.

## Rules

- Use only approved container names from `container-catalog.md`.
- Treat `references/container-catalog.md` as the single source of truth for container identifiers.
- Do not invent new container identifiers.
- Keep container names consistent across `Acquire`, device actions, and `set Status`.
- If a structured experiment mapping explicitly specifies an `Acquire` status, use that status for the matching container.
- If no experiment-specific `Acquire` status is specified, default the filter to `"New"`.
- If a structured experiment mapping explicitly specifies a `set ... Status` value, use that status for the matching container.
- If no experiment-specific set status is specified, default to `"used"` for consumed tips/consumables and `"Completed"` for output plates or completed experiment containers.
- Keep experiment-specific statuses in the experiment-specific mapping or protocol reference that introduced them, not in this shared skill.
- Do not infer statuses from device templates or free text when a structured experiment mapping is unavailable.
- In this skill, `Status` means only workflow states used by `Acquire` and `set ... Status`.
- Place the complete `set ... Status` statement immediately after the terminating semicolon of the `Acquire` block and before every device action.
- Apply `references/lid-management.md` to every `Acquire` and every device-action container binding.
- Device-specific routing syntax such as `ends 'FreedomEVO:Waste'` is not managed by this skill; read `device-operation-library` workflow rules for those cases.
- If a needed container is missing from the catalog, stop and report the missing container name.

## Working Order

1. Identify what containers and consumables the experiment requires.
2. Read `container-catalog.md` and select only approved names.
3. Read `lid-management.md` to determine default lid handling.
4. Read `acquire-and-status.md` to write or validate the adjacent `Acquire` and `set Status` statements.
5. Then move to `$device-operation-library` for device actions and device-dependent labware routing.
