---
name: dh5a-plasmid-construction
description: Generate complete Momentum DSL txt scripts for the DH5a plasmid-construction workflow. Use for full plasmid construction, the front-stage mutant construction/transformation script, or the separate downstream clone-picking, expression, lysis, and Bradford detection script. Trigger on requests such as "质粒构建", "质粒构建前段", "挑克隆表达Bradford", or "Bradford检测".
---

# DH5a Experiment Protocols

Use this skill to generate the complete DH5a plasmid-construction workflow as two independent Momentum `.txt` scripts:

1. Mutant construction and transformation: PCR through kanamycin-plate spreading.
2. Clone picking, expression, lysis, and Bradford detection: STEP6 through STEP11.

## Supported Protocols

- `dh5a_mutant_construction_transformation`: 质粒构建前段。
- `dh5a_clone_expression_bradford`: 挑克隆、表达、裂解和 Bradford 检测后段。
- `dh5a_full_plasmid_construction`: 一次生成以上两个独立脚本。

## Workflow

1. Match the user request against `references/intent-map.yaml`.
2. Read the matched procedure map to understand the natural-language hierarchy: experiment name -> major stages -> fine-grained experimental substeps -> code step IDs.
3. Read the matched protocol file for the executable stage order and container list.
4. Read the matched step-map file for step IDs and parameterized device actions.
5. Use `../device-operation-library/SKILL.md` as the source of truth for device action templates.
6. Use `../container-and-status-rules/SKILL.md` for container validity, `Acquire`, and final `set ... Status` rules.
7. Use `../script-assembler/SKILL.md` and its `instructions/` files for fixed `runtime/devices/pools/variables`.
8. Generate the script with `scripts/generate_script.py`.

## Command

```powershell
python .agents\skills\dh5a-plasmid-construction\scripts\generate_script.py --request "生成质粒构建实验脚本"
python .agents\skills\dh5a-plasmid-construction\scripts\generate_script.py --request "生成质粒构建前段实验脚本"
python .agents\skills\dh5a-plasmid-construction\scripts\generate_script.py --request "生成挑克隆表达Bradford实验脚本"
```

The generator writes a timestamped file under `outputs/` by default. Use `--output-dir <path>` to choose another directory.

## Design Boundary

- Keep experiment semantics in this skill: intent phrases, natural-language procedure maps, executable protocol flow, and per-protocol step maps.
- Keep device DSL templates in `device-operation-library`; do not duplicate device template bodies in this skill.
- Keep fixed script sections in `script-assembler`; do not copy `runtime/devices/pools/variables` into this skill.
- Keep container approval and status defaults in `container-and-status-rules`.

## Validation

After generation, check that:

- The filename matches `foundry_<standard_name>_<YYYYMMDD_HHMMSS>.txt`.
- `process[...]` matches the filename without `.txt`.
- The generated protocol contains the expected method names for the matched request.
- The script uses only approved containers listed in the matched protocol.
