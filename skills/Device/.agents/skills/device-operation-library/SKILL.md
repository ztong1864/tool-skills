---
name: device-operation-library
description: Unified Momentum device template library for laboratory automation scripts. Use when writing or updating Momentum DSL device actions, selecting device templates, checking editable parameters, merging repeated device families, or applying cross-device workflow rules such as Clariostar plus F7_1_Rotation.
---

# Device Operation Library

Use this skill as the single entry point for device action templates.

## Workflow

1. Identify the devices used by the requested experiment.
2. Read the relevant file in `references/devices/`.
3. If the flow depends on multiple devices, also read the relevant file in `references/workflow-rules/`.
4. Copy the action template exactly unless a field is explicitly marked editable.
5. Keep device-level details in device references and process-level dependencies in workflow rules.
6. When container routing depends on a device, such as tip waste routing, post-operation staging, or single-nest occupancy, read the relevant workflow rule instead of inventing a destination.
7. If the process contains a reagent plate, read `reagent-plate-first-use-unsealing.md` before arranging its first device operation.

## What To Read

- Device index: [references/devices/index.md](references/devices/index.md)
- Workflow rule index: [references/workflow-rules/index.md](references/workflow-rules/index.md)

## Rules

- Treat `references/devices/*.md` as the source of truth for device actions.
- Treat `references/workflow-rules/*.md` as the source of truth for cross-device sequencing constraints.
- Do not invent device names, action names, container names, or parameter names.
- Container identifier validity is owned by [$container-and-status-rules](../container-and-status-rules/SKILL.md), not by this skill.
- Default plate lid policy and `Acquire` lid syntax are owned by `../container-and-status-rules/references/lid-management.md`.
- For device actions, preserve the exact lid annotation from the selected device template or workflow rule; an action may use `'Lidded'`, `'Unlidded'` with `HoldLid`, or no lid annotation.
- If a device template contains a container name that conflicts with `container-and-status-rules/references/container-catalog.md`, use the catalog-approved name and treat the template entry as a reference defect to be fixed.
- Do not change parameters unless the reference explicitly marks them editable.
- In device reference files, concrete example values listed under the editable section are placeholders from the sample block, not a restriction that only those exact literal values may be used.
- When a device family is merged into one file, select the exact variant from that family file instead of creating a new device-specific template.
- If a flow uses both `CentrifugeLoader` and `Cytomat_24H`, read the corresponding workflow rule in addition to the individual device templates.
- If a flow uses FreedomEVO liquid-handling scripts, read `freedomevo-liquid-handling-prerun.md` to decide whether the Inheco preparation script is needed.
- If a flow uses `CYTOMAT_2_Tos1` or `CYTOMAT_2_Tos2` incubation, read `cytomat-tos-shaking-incubation.md`.
- If a flow consumes tips, moves labware after operation, or needs a default staging destination, read `default-labware-destinations.md`.
- If a flow contains any reagent plate, apply `reagent-plate-first-use-unsealing.md` exactly once per reagent plate before its first device-operation appearance.
- If a flow runs multiple labware items through `ALPS3000:Nest` or another single-nest device, read `single-nest-device-occupancy.md`.

## Current Device Families

- `ATC-family.md` covers `ATC_1`, `ATC_2`, and `ATC_3`.
- `CYTOMAT_2_Tos-family.md` covers `CYTOMAT_2_Tos1` and `CYTOMAT_2_Tos2`.

## Output Expectation

Return only the exact action block or blocks needed for the current experiment, and load only the device references that are actually relevant.
