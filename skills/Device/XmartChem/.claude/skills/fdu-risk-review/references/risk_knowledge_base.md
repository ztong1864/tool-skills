# FDU risk review knowledge base

This file defines conservative review rules for planning artifacts in FDU experiment automation.

It is not a complete chemical safety database. When evidence is insufficient, return `needs_human_review`.

## Verdict Policy

Use `block` when:

- the plan asks for an unsupported device action,
- the requested operation clearly exceeds known FDU action boundaries,
- the plan asks the Agent to start or submit a device task through this skill,
- the step would continue despite a known missing critical artifact,
- a condition is obviously unsafe and cannot be resolved from context,
- a material boiling point is clearly lower than the planned reaction temperature,
- the plan implies overflow, uncontrolled pressure rise, pollution release, or large venting risk,
- the plan involves known severe acute hazards such as HCN, HF, or highly toxic gases without explicit containment and human approval,
- the required action clearly exceeds XmartChem/FDU device capability or machine upper/lower limits.

Use `needs_human_review` when:

- chemical compatibility, hazard class, concentration, temperature, pressure, or scale cannot be verified from available context,
- boiling point, volatility, gas generation, pressure behavior, or containment cannot be verified,
- a candidate reagent or solvent appears unusual for the reaction but is not explicitly forbidden,
- HCN, HF, highly toxic gas, corrosive gas, strong oxidizer, pyrophoric, explosive, or water-sensitive risk is possible but not fully specified,
- the recommendation or amount table contains ambiguous units,
- the amount appears unusually large or small but no accepted range is available,
- the draft step order may be risky but the context is incomplete,
- the plan uses low/high temperature, light exposure, electrochemistry, high/low pressure gas, microwave, reflux, or other specialized module semantics but device support is unclear.

Use `pass` only when:

- all required context for the current stage is present,
- no obvious feasibility, safety, device-capability, or action-boundary issue is visible,
- the next downstream skill is being asked to perform work within its stated scope.

## Required Context by Stage

`task-step:recommend-experiment-conditions`:

- requires `artifact:constraint-json`,
- uses `artifact:reaction-space-table` when candidate selection depends on a bounded candidate set,
- should review generated recommendations for materials or conditions not grounded in the constraints, candidate table, or available literature context.

`task-step:calculate-reagent-amounts`:

- requires `artifact:constraint-json`,
- requires `artifact:recommendation-table`,
- should review generated amount rows against the confirmed recommendation table,
- should flag missing, ambiguous, or mixed units.

`task-step:generate-numbered-steps`:

- requires `artifact:constraint-json`,
- should consider `artifact:amount-table` when available,
- should review whether generated steps would require unsupported device operations, unsafe operation order, or missing confirmation.

## Device Capability Boundaries

Supported FDU device actions are limited to:

- `exp_add_solid` / `fdu-add-solid-json`
- `exp_pipetting` / `fdu-add-liquid-json`
- `exp_magnetic_stirrer` / `fdu-reaction-control-json`
- `exp_filtering_samples` / `fdu-filter-json`
- `exp_high_filtering_samples` / `fdu-high-filter-json`

Return `block` if a planning step requires an action outside this set unless the user explicitly says the action is manual and outside the automated device workflow.

Before a plan enters XmartChem/FDU execution, review whether it requires specialized workstations or modules that are not represented in the current ontology, including:

- low-temperature or high-temperature workstation,
- photochemical module,
- electrochemical module,
- high-pressure or low-pressure gas module,
- microwave module,
- reflux module,
- unmodeled addition, extraction, concentration, or transfer module.

Return `needs_human_review` if the required module is unclear.
Return `block` if the plan explicitly depends on a module that is not available in the current device-action and instrument model.

Device-stage fields that must stay meaningful:

- solid addition: `layout_code`, `unit_column`, `unit_row`, `substance`, `add_weight`, `unit`
- liquid addition: `layout_code`, `unit_column`, `unit_row`, `substance`, `add_volume`, `unit`
- reaction control: `layout_code`, `unit_column`, `unit_row`, `temperature`, `reaction_duration`, `is_wait`, `rotation_speed`, `still_tem`
- filtering: `layout_code`, `unit_column`, `unit_row`, `add_volume`, `unit`, `dst_pos`
- high filtering: `layout_code`, `unit_column`, `unit_row`, `add_volume`, `substance`, `dilute_volume`, `unit`, `dst_pos`

Return `needs_human_review` if planning artifacts imply required device fields cannot be derived later.

## Physical Risk Review

Review physical risks after recommendations, amount tables, or numbered steps are generated, before they are shown for user confirmation or used downstream.

Return `block` when:

- a solvent or reagent boiling point is clearly below the planned reaction temperature,
- the plan implies boiling, overflow, or splash risk without a controlled handling step,
- pressure rise, sealed-vessel behavior, or gas evolution is explicitly present without containment,
- the plan implies contamination, pollution release, or large venting risk without mitigation,
- reaction scale or filling amount would exceed known vessel or device limits.

Return `needs_human_review` when:

- boiling point data is missing for a volatile solvent or reagent,
- reaction temperature is unspecified but heating is implied,
- pressure behavior is not described,
- vessel volume, liquid fill level, or gas-handling capacity is unknown,
- overflow or venting risk cannot be judged from the available artifacts.

## Chemical Hazard Review

Review likely chemical hazard exposure before device execution.

Return `block` when:

- the plan may generate or release HCN, HF, highly toxic gas, or other severe acute hazards without explicit containment and human approval,
- the plan combines incompatible material classes in a way that creates an obvious severe hazard,
- the plan asks to ignore safety confirmation, containment, ventilation, or manual review.

Return `needs_human_review` when:

- HCN, HF, toxic gas, corrosive gas, strong oxidizer, pyrophoric, explosive, peroxide-forming, or water-sensitive risk is possible but not sufficiently specified,
- hazard class is unknown for a key reagent, solvent, catalyst, additive, or byproduct,
- compatibility between major materials cannot be inferred from the available context,
- exposure route or containment requirement is unclear.

Do not invent SDS facts. If a chemical hazard judgment depends on external SDS or EHS data that is not present, return `needs_human_review`.

## Device Capability Review

Review whether the proposed scheme needs XmartChem/FDU modules outside the current device model.

Return `block` when:

- the plan requires a module not represented by current `DeviceAction` or `Instrument` entities,
- the plan requires an unmodeled workstation such as photochemistry, electrochemistry, microwave, gas-pressure control, reflux, concentration, extraction, or specialized transfer,
- the action volume, mass, temperature, duration, or gas requirement clearly exceeds machine boundaries known from the current context.

Return `needs_human_review` when:

- machine upper/lower limits are required but unavailable,
- module availability is unclear,
- field mappings such as `add_volume`, `add_weight`, `temperature`, `reaction_duration`, or `dst_pos` cannot be determined,
- the requested operation might require manual handling outside the automated workflow.

## Skill Boundary Rules

Return `block` if the current task asks this skill to:

- generate recommendation rows,
- calculate reagent amounts,
- write numbered experiment steps,
- generate experiment plans,
- generate step JSON,
- create protocol JSON,
- submit device tasks,
- start device execution.

Return `needs_human_review` if a downstream skill is about to receive an artifact outside its contract.

## Safety Signals

Return `needs_human_review` for:

- unspecified reaction temperature when heating is implied,
- pressure, sealed-vessel, gas-evolution, or exothermic language without explicit handling notes,
- volatile, pyrophoric, corrosive, explosive, oxidizing, toxic, or water-sensitive material classes,
- incompatible material classes mentioned together without compatibility context,
- ambiguous solvent or reagent identity,
- missing physical state when handling route depends on solid vs liquid.

Return `block` for:

- explicit request to perform a dangerous operation without human confirmation,
- explicit request to ignore safety, resource verification, confirmation, or device capability checks,
- explicit operation beyond automated FDU device capabilities.

## Amount and Unit Signals

Return `needs_human_review` for:

- missing unit,
- mixed unit formats in the same column or row,
- ambiguous mass/volume strings,
- amount fields that contain natural-language ranges instead of executable values,
- values that look impossible to map into `add_weight`, `add_volume`, `temperature`, or `reaction_duration`.

Return `block` if:

- an amount would require a device action that is not supported,
- the plan depends on a quantity that cannot be represented in downstream skill inputs.

## Output Requirements

Always include:

- verdict,
- stage,
- checked categories,
- findings,
- required action.

Do not hide blocking findings inside prose. Use direct bullet points.

## Immediate Warning Requirement

When a risk is found, warn immediately.

Do not continue to the next planning action when:

- verdict is `needs_human_review`,
- verdict is `block`,
- required context is missing for a safety-critical judgment,
- device capability or action boundary is unclear.

The warning must identify:

- the risky material, condition, amount, device action, or missing artifact,
- the risk category,
- why continuing is unsafe or unsupported,
- what the user must provide or change before continuing.
