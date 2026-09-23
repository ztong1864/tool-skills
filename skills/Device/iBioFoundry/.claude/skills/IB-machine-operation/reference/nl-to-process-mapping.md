# Natural Language To Process Mapping

Use this file when the user request clearly matches one of the known fixed experiment types below.

Purpose:
- Stabilize `process { ... }` generation for repeated natural-language requests.
- Provide a fixed process skeleton in natural language instead of copying full DSL blocks.
- Keep `process[...]` names and output filenames out of scope. Only the `process { ... }` content matters here.

Rules:
- This mapping constrains only the core `process` device-step skeleton.
- `Acquire` and `set ... Status` should still be added through the current skills, even if a historical example omitted them.
- In every mapping, place `set ... Status` immediately after `Acquire` and before the first device action.
- Device action syntax must still come from `$device-operation-library`.
- Container names, `Acquire`, and `set` rules must still come from `$container-and-status-rules`.
- If a known workflow allows a device-family variant, keep the mapped skeleton fixed and use the currently approved template family.

---

## 1. 单板酶检测

Recognize requests such as:
- 生成单板酶检测的实验脚本
- 单板酶检测
- 单板酶活检测

Standard process skeleton:
1. `Acquire` the BMG plate.
2. Immediately use `set` to mark the plate result state.
3. Run `F7_1_Rotation [Rotate]` before reader entry.
4. Run `Clariostar [Run Protocol]`.
5. Run `F7_1_Rotation [Rotate]` again after reader exit.
6. Move the plate to `Staging_Nests [Load]`.

Special notes:
- This is a BMG plate special-case flow.
- Apply `container-and-status-rules/references/lid-management.md` to `Acquire`.
- Follow `device-operation-library/references/workflow-rules/clariostar-rotation.md` for device-action lid handling.

---

## 2. 微孔板离心

Recognize requests such as:
- 生成微孔板离心的实验脚本
- 微孔板离心

Standard process skeleton:
1. `Acquire` the sample plate and the balancing plate.
2. Immediately use `set` to update the sample plate workflow state; omit `Balance_PCR` unless explicitly required.
3. Run `CentrifugeLoader [Spin]`.
4. Place `PCR_Plate1` in `Bucket 1`.
5. Place `Balance_PCR` in `Bucket 2`.
6. After centrifugation, run `Cytomat_24H [Load]` with both `PCR_Plate1 GetMyOwnContainer` and `Balance_PCR GetMyOwnContainer`.

Special notes:
- The balancing plate is required.
- Preserve the bucket assignment pattern from the device template.
- Default container choice for this fixed workflow is `PCR_Plate1` as the sample plate and `Balance_PCR` as the balancing plate.

---

## 3. 微孔板液体转移

Recognize requests such as:
- 生成微孔板液体转移的实验脚本
- 微孔板液体转移
- 液体处理

Standard process skeleton:
1. `Acquire` the transfer plate.
2. Immediately use `set` to update the workflow state of `Cell_Plate1`.
3. Run `FreedomEVO [Load]` with `Cell_Plate1` in `FreedomEVO:Nest 1`.
4. Run `FreedomEVO [RunScript]` with `Cell_Plate1` in `FreedomEVO:Nest 1`.
5. Seal `Cell_Plate1` with `ALPS3000 [Seal]`.
6. Move `Cell_Plate1` to `Cytomat_10H [Load]`.

Special notes:
- For this known request, prefer the `FreedomEVO` transfer flow.
- Default container choice for this fixed workflow is `Cell_Plate1`.
- The default step-level container mapping is:
  - `FreedomEVO [Load]` -> `Cell_Plate1 in 'FreedomEVO:Nest 1'`
  - `FreedomEVO [RunScript]` -> `Cell_Plate1 in 'FreedomEVO:Nest 1'`
  - `ALPS3000 [Seal]` -> `Cell_Plate1 in 'ALPS3000:Nest'`
  - `Cytomat_10H [Load]` -> `Cell_Plate1 GetMyOwnContainer`
- `Cell_Plate1` is not a reagent plate, so do not add first-appearance unsealing.
- Keep the sealing step after transfer.

---

## 4. PCR扩增

Recognize requests such as:
- 生成PCR扩增的实验脚本
- PCR扩增

Standard process skeleton:
1. `Acquire` the PCR plate.
2. Immediately use `set` to update workflow state.
3. Load the PCR plate onto an `ATC` family thermocycler with `ATC_x [Load]`.
4. Run the PCR program with `ATC_x [Run Protocol]`.
5. Move the amplified plate to `Cytomat_10H [Load]`.

Special notes:
- Any currently approved `ATC` family variant is acceptable.
- Keep the skeleton fixed as `ATC family Load -> ATC family Run Protocol`.
- Do not change this mapping to another PCR device family unless the templates change.

---

## 5. 微孔板震荡孵育

Recognize requests such as:
- 生成微孔板震荡孵育的实验脚本
- 微孔板震荡孵育
- 震荡孵育

Standard process skeleton:
1. `Acquire` the incubation plate.
2. Immediately use `set` to update workflow state.
3. Run `CYTOMAT_2_Tos2 [Set Shake Speeds]`.
4. Run `CYTOMAT_2_Tos2 [Load]`.
5. Run `CYTOMAT_2_Tos2 [Incubate]`.
6. Move the plate to `Staging_Nests [Load]`.

Special notes:
- Prefer `CYTOMAT_2_Tos2` for this known shaking-incubation request.
- Keep the shake-speed step before `Load` and `Incubate`.
