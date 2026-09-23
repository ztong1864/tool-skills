---
name: reference-script-skill-miner
description: Extract reusable skill knowledge from validated Momentum reference scripts and matching experiment descriptions. Use when an assistant is asked to analyze a new reference experiment script, build or improve an experiment-generation skill, identify hidden device/container/workflow rules, or enrich device-operation-library and container-and-status-rules from examples without mixing reference-script analysis into runtime generation skills.
---

# Reference Script Skill Miner

Use this skill only when improving skills from reference materials. Do not use it during ordinary script generation unless the user explicitly provides a reference script or asks to enrich skills.

## Inputs

- A validated Momentum `.txt` reference script.
- Optional natural-language experiment description.
- Existing shared skills:
  - `../device-operation-library/SKILL.md`
  - `../container-and-status-rules/SKILL.md`
  - `../script-assembler/SKILL.md`

## Workflow

1. Identify fixed parts that should not be learned as experiment-specific knowledge: `runtime`, `devices`, `pools`, and `variables`.
2. Extract the `process` block and split it into:
   - `Acquire` and status setup.
   - Stage comments.
   - Atomic device actions.
   - Flow structures such as `parallel` and `branch`.
3. If a natural-language description exists, map:
   - experiment name -> major stages,
   - major stages -> fine-grained experimental substeps,
   - substeps -> atomic device action IDs.
4. Separate reusable knowledge from experiment-specific mappings:
   - Device action syntax and editable parameters belong in `device-operation-library/references/devices/`.
   - Cross-device order, preparation scripts, labware destinations, waste routing, and single-nest constraints belong in `device-operation-library/references/workflow-rules/`.
   - Approved container identifiers and status-writing defaults belong in `container-and-status-rules/`.
   - Experiment names, stage text, substep mappings, method names, and fixed per-experiment flow belong in the new experiment skill.
5. If a device name, device action, or labware/container identifier appears in the reference script but is missing from the shared libraries, extract it into the appropriate shared library before referencing it from an experiment skill:
   - Missing device names or actions go to `device-operation-library/references/devices/`.
   - Missing cross-device behavior goes to `device-operation-library/references/workflow-rules/`.
   - Missing labware/container identifiers go to `container-and-status-rules/references/container-catalog.md`.
6. Prefer adding a small general rule with a validated example over copying a whole experiment script into a shared skill.
7. Mark uncertain generalizations as "consider" rules and keep exact behavior in the experiment-specific mapping.

## Output

For each proposed update, state:

- Target file.
- Rule or template to add.
- Evidence from the reference script.
- Whether the rule is general, device-family-specific, or experiment-specific.
