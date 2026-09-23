# CYTOMAT Tos Shaking Incubation

Use this rule when a process incubates a plate in `CYTOMAT_2_Tos1` or `CYTOMAT_2_Tos2`.

## Rule

- Run `CYTOMAT_2_TosX [Set Shake Speeds]` before `CYTOMAT_2_TosX [Incubate]` unless the active protocol proves the speed was already set earlier in the same process.
- Use the same device variant for speed setup, load, and incubation.
- Choose the speed and incubation duration from the active experiment mapping. Do not infer them from the container type alone.

## Validated Reference Pattern

In the DH5a plasmid construction reference script, `Cell_Plate1` is loaded into `CYTOMAT_2_Tos1`, then `CYTOMAT_2_Tos1 [Set Shake Speeds]` sets both towers to `900`, then `CYTOMAT_2_Tos1 [Incubate]` runs for `01:00:00`.
