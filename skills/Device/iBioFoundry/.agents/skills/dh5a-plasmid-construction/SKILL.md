---
name: dh5a-plasmid-construction
description: Generate complete Momentum DSL txt scripts for the DH5a plasmid-construction workflow. Use for full plasmid construction, the front-stage mutant construction/transformation script, or the separate downstream clone-picking, expression, lysis, and Bradford detection script. Trigger on requests such as "质粒构建", "质粒构建前段", "挑克隆表达Bradford", or "Bradford检测".
---

# DH5a Experiment Protocols

**不是这个实验的话看另一个技能。** 这个技能做的是 DH5α 宿主、四块八孔板（32 格）、
Fluent 涂布与挑克隆、单块 BMG 板 Bradford 检测的那一套，产出两份各自独立的脚本。
96 个突变体涂十二块八孔板（一格一个）、BL21 感受态、48 深孔板种子培养、IPTG 诱导 12 h、
BCA 与 340/530 荧光检测的那一套，是
[$ecoli-96-mutant-construction-detection](../ecoli-96-mutant-construction-detection/SKILL.md)，
三份脚本用 `AddWork` 串联。两边的设备程序没有一个是共用的。

Use this skill to generate the complete DH5a plasmid-construction workflow as two independent Momentum `.txt` scripts:

1. Mutant construction and transformation: PCR through kanamycin-plate spreading.
2. Clone picking, expression, lysis, and Bradford detection: STEP6 through STEP11.

## Supported Protocols

- `dh5a_mutant_construction_transformation`: 质粒构建前段。
- `dh5a_clone_expression_bradford`: 挑克隆、表达、裂解和 Bradford 检测后段。
- `dh5a_full_plasmid_construction`: 一次生成以上两个独立脚本。

## Scale

原生规模是**一块 96 孔板的 96 个突变体**，复苏后涂布到**四块八孔板共 32 个格**。96 个孔怎么归并到 32 个格，写在 Tecan 方法内部，本技能看不到。

- 板数用 `--spreading-plates K` **显式指定**，不会按突变体数量自动换算（换算需要上面那个归并比例，本技能无权假设它）。不给这个参数就是四块板，与以前一样。
- 突变体名字用 `--mutants D2A,D2S,...`（或 `--mutants-file`），会在脚本旁边多写一份 `<脚本名>_platemap.csv`，两列 `pcr_well,mutant`，96 孔板**按列填**（A1、B1…H1、A2…）。填充方向待 iBioFoundry 团队确认。对照表不分配涂布格，原因同上。
- `--mutant-count N` 只用来和名字个数对账，不影响脚本。
- **设备端的 Tecan 方法不随板数改变**（`ZFL_ZZW_Tubu_afterTranform_8well_plate`、`ZFL_AI_pickolo8well_1plate`）。缩减板数的脚本会在自身的 `comment` 里写明这一点，生成时也打印到终端。**缩减规模前必须与 iBioFoundry 团队确认这些方法能否配合**，否则脚本能生成但设备上未必能跑。

向用户确认方案时就要把规模说清楚（几个突变体、几块板、设备方法这条限制），不要等脚本生成完再发现对不上。

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

```bash
python .claude/skills/dh5a-plasmid-construction/scripts/generate_script.py --request "生成质粒构建实验脚本"
python .claude/skills/dh5a-plasmid-construction/scripts/generate_script.py --request "生成质粒构建前段实验脚本"
python .claude/skills/dh5a-plasmid-construction/scripts/generate_script.py --request "生成挑克隆表达Bradford实验脚本"
```

缩减规模并带突变体名字（见 Scale）：

```bash
python .claude/skills/dh5a-plasmid-construction/scripts/generate_script.py \
  --request "生成质粒构建前段实验脚本" --spreading-plates 1 \
  --mutant-count 9 --mutants "D2A,D2S,D2P,R61L,R61A,R61K,H62K,H62R,H62L" \
  --output-dir <artifact 目录>
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
- With `--spreading-plates K`, the `Acquire` block holds exactly K `8Well_Plate_*` entries, and no `set ... Status` line or device step mentions a plate beyond K.
- With `--mutants`, the `_platemap.csv` beside the script has one row per name, in the order given.
