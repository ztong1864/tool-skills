---
name: process-visualizer
description: Convert generated Thermo Fisher Momentum `.txt` experiment scripts into concise process flowcharts, including `parallel` / `branch` process blocks. Use when Codex needs to visualize the `process` block of a completed Momentum DSL script, summarize Acquire/set/device-action steps, or output Mermaid `.mmd` code for a lab automation workflow.
---

# Process Visualizer

## Overview

Use this skill after a Momentum script has already been generated. The input is a `.txt` Momentum DSL script; the output is a Mermaid flowchart code file that gives a compact view of the `process` sequence.

Mermaid is the preferred output format because it is plain text, easy to diff, can be embedded in Markdown, and is sufficient for the simple linear workflow summaries usually needed here.

## Workflow

1. Locate the generated Momentum `.txt` script.
2. Run `scripts/visualize_process.py` to extract the selected `process` block and write a Mermaid `.mmd` file.
3. Inspect the `.mmd` file for obvious parsing misses, especially if the script contains conditional or parallel constructs.
4. Return the output path and, when useful, paste the Mermaid code block for quick preview.

## Quick Start

```powershell
python .agents\skills\process-visualizer\scripts\visualize_process.py `
  "D:\path\to\script.txt" `
  --output "D:\path\to\script.mmd"
```

If a script contains multiple process blocks, pass the target name:

```powershell
python .agents\skills\process-visualizer\scripts\visualize_process.py `
  "D:\path\to\script.txt" `
  --process single_plate_enzyme_assay `
  --output "D:\path\to\single_plate_enzyme_assay.mmd"
```

## Output Rules

- Always visualize only the `process` block, not `runtime`, `devices`, `pools`, or `variables`.
- Include Start and End nodes.
- Preserve the process order exactly.
- Render `parallel { branch { ... } branch { ... } }` as a `Parallel` split, one labeled branch lane per branch, and a `Join` node before the workflow continues.
- Summarize these step types:
  - `Acquire`: show acquired container and `where` condition.
  - `set`: show the assignment.
  - `Device [Action]`: show device, action, important parameters such as `ProtocolName` or `Duration`, and container/location lines.
  - `comment`: show a short comment label when comments mark workflow stages.
  - Unknown statements: include a compact first-line summary so no process step silently disappears.
- Keep labels short; prefer key information over full parameter dumps.
- Use Mermaid `flowchart TD` unless the user requests another direction.

## Script Notes

`scripts/visualize_process.py` is intentionally deterministic and dependency-free. Prefer running it instead of reimplementing parsing logic in the response.

The script handles typical Momentum process syntax:

- `process name { ... }` and `process [display name] { ... }`
- top-level statements ending with `;`
- `parallel` blocks containing one or more `branch` blocks
- multiline device parameters in parentheses
- multiline comments beginning with `//`

It produces a concise process diagram with linear steps and parallel branch groups. If a future script uses conditional logic or loops beyond Momentum `parallel/branch`, treat the output as a first-pass summary and revise manually if the user needs exact control-flow semantics.
