#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any, Dict, List, Optional

from scene_utils import (
    SUPPORTED_UNIT_TYPES,
    SceneGenerationError,
    build_resource_index,
    choose_best_resource,
    clamp,
    extract_explicit_value,
    extract_numeric_range,
    extract_upper_bound,
    find_resources_by_aliases,
    generate_unit_id,
    is_available_resource,
    is_plain_solvent_resource,
    load_scene_inputs,
    midpoint,
    mmol_to_mL,
    mmol_to_mg,
    normalize_substance_name,
    resolve_resource_or_raise,
    round_float,
    safe_get_concentration,
    summarize_resource,
)


def detect_scene(goal_text: str, scene_rules: Dict[str, Any]) -> str:
    text = (goal_text or "").lower()
    keywords = [str(k).lower() for k in scene_rules.get("keywords", [])]
    if any(k in text for k in keywords):
        return scene_rules.get("supported_reaction_type", "suzuki")
    if "4-bromoacetophenone" in text or "phenylboronic acid" in text or "4-溴苯乙酮" in text or "苯硼酸" in text:
        return scene_rules.get("supported_reaction_type", "suzuki")
    raise SceneGenerationError("Current scene skill supports Suzuki coupling only.")


def validate_scene_supported(goal_text: str, scene_rules: Dict[str, Any]) -> None:
    detect_scene(goal_text, scene_rules)


def compute_scene_parameters(goal_text: str, scene_rules: Dict[str, Any]) -> Dict[str, Any]:
    defaults = scene_rules.get("defaults", {})
    text = goal_text or ""

    aryl_range = extract_numeric_range(text, r"mmol") or tuple(defaults.get("aryl_halide_mmol_range", [0.08, 0.12]))
    aryl_halide_mmol = clamp(
        midpoint(*aryl_range),
        float(aryl_range[0]),
        float(aryl_range[1]),
    )

    boronic_range = extract_numeric_range(text, r"(?:equiv(?:alents?)?|eq)") or tuple(defaults.get("boronic_acid_equiv_range", [1.0, 1.2]))
    boronic_acid_equiv = clamp(
        midpoint(*boronic_range),
        float(boronic_range[0]),
        float(boronic_range[1]),
    )

    base_range = extract_numeric_range(text, r"(?:equiv(?:alents?)?|eq)") or tuple(defaults.get("base_equiv_range", [1.5, 3.0]))
    base_equiv = defaults.get("base_equiv", 2.0)
    if base_range != boronic_range:
        base_equiv = clamp(midpoint(*base_range), float(base_range[0]), float(base_range[1]))

    catalyst_cap = extract_upper_bound(text, r"mol\s*%") or float(defaults.get("catalyst_mol_percent_cap", 10.0))
    catalyst_mol_percent = min(float(defaults.get("catalyst_mol_percent", 5.0)), catalyst_cap)

    total_range = extract_numeric_range(text, r"mL") or tuple(defaults.get("reaction_total_volume_range_mL", [0.67, 1.0]))
    reaction_total_volume_mL = clamp(
        float(defaults.get("reaction_total_volume_mL", 0.8)),
        float(total_range[0]),
        float(total_range[1]),
    )

    explicit_filter = extract_explicit_value(text, r"mL")
    filtered_aliquot_mL = float(defaults.get("filtered_aliquot_mL", 0.05))
    if explicit_filter and explicit_filter <= 0.2:
        filtered_aliquot_mL = explicit_filter

    return {
        "aryl_halide_mmol": round_float(aryl_halide_mmol, 4),
        "boronic_acid_equiv": round_float(float(boronic_acid_equiv), 4),
        "base_equiv": round_float(float(base_equiv), 4),
        "catalyst_mol_percent": round_float(float(catalyst_mol_percent), 4),
        "reaction_total_volume_mL": round_float(float(reaction_total_volume_mL), 4),
        "reaction_temperature_C": int(defaults.get("reaction_temperature_C", 25)),
        "reaction_duration_s": int(defaults.get("reaction_duration_s", 28800)),
        "rotation_speed_rpm": int(defaults.get("rotation_speed_rpm", 650)),
        "post_homogenize_duration_s": int(defaults.get("post_homogenize_duration_s", 300)),
        "internal_standard_volume_mL": float(defaults.get("internal_standard_volume_mL", 0.1)),
        "filtered_aliquot_mL": round_float(filtered_aliquot_mL, 4),
        "solvent_minimum_step_mL": float(defaults.get("solvent_minimum_step_mL", 0.01)),
    }


def select_scene_resources(resource_info: Dict[str, Any], scene_rules: Dict[str, Any]) -> Dict[str, Optional[Dict[str, Any]]]:
    aliases = scene_rules.get("aliases", {})
    policy = scene_rules.get("selection_policy", {})

    aryl_halide = resolve_resource_or_raise(
        "aryl_halide",
        resource_info,
        aliases.get("aryl_halide", []),
        prefer_stock=bool(policy.get("prefer_stock_solution", True)),
        preferred_keyword="dmf",
    )
    boronic_acid = resolve_resource_or_raise(
        "boronic_acid",
        resource_info,
        aliases.get("boronic_acid", []),
        prefer_stock=bool(policy.get("prefer_stock_solution", True)),
        preferred_keyword="dmf",
    )
    base = resolve_resource_or_raise(
        "base",
        resource_info,
        aliases.get("base", []),
        prefer_stock=bool(policy.get("prefer_stock_solution", True)),
    )
    catalyst = resolve_resource_or_raise(
        "catalyst",
        resource_info,
        aliases.get("catalyst", []),
        prefer_stock=False,
    )
    solvent_candidates = find_resources_by_aliases(resource_info, aliases.get("solvent", []))
    solvent_candidates = [
        r for r in solvent_candidates
        if is_available_resource(r) and is_plain_solvent_resource(r, aliases.get("solvent", []))
    ]
    solvent = choose_best_resource(
        solvent_candidates,
        prefer_stock=False,
        preferred_keyword="dmf",
    )
    internal_standard = resolve_resource_or_raise(
        "internal_standard",
        resource_info,
        aliases.get("internal_standard", []),
        prefer_stock=True,
        optional=True,
    )

    return {
        "aryl_halide": aryl_halide,
        "boronic_acid": boronic_acid,
        "base": base,
        "catalyst": catalyst,
        "solvent": solvent,
        "internal_standard": internal_standard,
    }


def build_scene_plan(goal_text: str, resource_info: Dict[str, Any], scene_rules: Dict[str, Any]) -> Dict[str, Any]:
    validate_scene_supported(goal_text, scene_rules)
    resources = select_scene_resources(resource_info, scene_rules)
    params = compute_scene_parameters(goal_text, scene_rules)

    aryl_halide_mmol = params["aryl_halide_mmol"]
    boronic_acid_mmol = round_float(aryl_halide_mmol * params["boronic_acid_equiv"], 4)
    base_mmol = round_float(aryl_halide_mmol * params["base_equiv"], 4)
    catalyst_mmol = round_float(aryl_halide_mmol * params["catalyst_mol_percent"] / 100.0, 5)

    aryl_halide_conc = safe_get_concentration(resources["aryl_halide"], "aryl_halide")
    boronic_acid_conc = safe_get_concentration(resources["boronic_acid"], "boronic_acid")
    base_conc = safe_get_concentration(resources["base"], "base")

    aryl_halide_volume_mL = round_float(mmol_to_mL(aryl_halide_mmol, aryl_halide_conc), 4)
    boronic_acid_volume_mL = round_float(mmol_to_mL(boronic_acid_mmol, boronic_acid_conc), 4)
    base_volume_mL = round_float(mmol_to_mL(base_mmol, base_conc), 4)

    catalyst_resource = resources["catalyst"]
    catalyst_substance = catalyst_resource.get("substance", "")
    catalyst_conc = None
    catalyst_weight_mg = None
    catalyst_volume_mL = None
    if "mol/l" in catalyst_substance.lower():
        catalyst_conc = safe_get_concentration(catalyst_resource, "catalyst")
        catalyst_volume_mL = round_float(mmol_to_mL(catalyst_mmol, catalyst_conc), 4)
    else:
        mw = scene_rules.get("molecular_weights", {}).get("PdCl2")
        catalyst_weight_mg = round_float(mmol_to_mg(catalyst_mmol, mw), 4)

    reaction_liquid_so_far = sum(
        x for x in [aryl_halide_volume_mL, boronic_acid_volume_mL, base_volume_mL, catalyst_volume_mL or 0.0] if x
    )
    solvent_fill_mL = max(0.0, round_float(params["reaction_total_volume_mL"] - reaction_liquid_so_far, 4))
    if solvent_fill_mL < params["solvent_minimum_step_mL"]:
        solvent_fill_mL = 0.0

    return {
        "scene": scene_rules.get("scene_name", "suzuki_coupling"),
        "reaction_type": scene_rules.get("supported_reaction_type", "suzuki"),
        "goal_text": goal_text,
        "product": scene_rules.get("aliases", {}).get("product", ["4-phenylacetophenone"])[0],
        "resources": {k: summarize_resource(v) for k, v in resources.items()},
        "parameters": {
            **params,
            "boronic_acid_mmol": boronic_acid_mmol,
            "base_mmol": base_mmol,
            "catalyst_mmol": catalyst_mmol,
            "aryl_halide_volume_mL": aryl_halide_volume_mL,
            "boronic_acid_volume_mL": boronic_acid_volume_mL,
            "base_volume_mL": base_volume_mL,
            "catalyst_volume_mL": catalyst_volume_mL,
            "catalyst_weight_mg": catalyst_weight_mg,
            "solvent_fill_mL": solvent_fill_mL,
        },
    }


def validate_resource_capacity(plan: Dict[str, Any], resource_info: Dict[str, Any]) -> None:
    by_layout = {item.get("layout_code"): item for item in build_resource_index(resource_info)}
    params = plan.get("parameters", {})
    resources = plan.get("resources", {})

    checks = [
        (resources["aryl_halide"], params.get("aryl_halide_volume_mL"), "available_volume"),
        (resources["boronic_acid"], params.get("boronic_acid_volume_mL"), "available_volume"),
        (resources["base"], params.get("base_volume_mL"), "available_volume"),
    ]
    if resources.get("solvent") and params.get("solvent_fill_mL", 0) > 0:
        checks.append((resources["solvent"], params.get("solvent_fill_mL"), "available_volume"))
    if resources.get("internal_standard"):
        checks.append((resources["internal_standard"], params.get("internal_standard_volume_mL"), "available_volume"))

    catalyst = resources.get("catalyst")
    if catalyst:
        if params.get("catalyst_volume_mL"):
            checks.append((catalyst, params.get("catalyst_volume_mL"), "available_volume"))
        elif params.get("catalyst_weight_mg"):
            checks.append((catalyst, params.get("catalyst_weight_mg"), "available_weight"))

    for resource, required, field in checks:
        if not resource or required is None:
            continue
        layout = resource.get("layout_code")
        actual = by_layout.get(layout, {})
        available = float(actual.get(field, 0) or 0)
        if float(required) > available:
            raise SceneGenerationError(
                f"Insufficient {field} at {layout}: required {required}, available {available}"
            )


def build_logical_protocol_from_scene_plan(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    params = plan.get("parameters", {})
    resources = plan.get("resources", {})

    def make_liquid_step(resource: Dict[str, Any], volume_mL: float) -> Dict[str, Any]:
        return {
            "unit_type": "exp_pipetting",
            "substance": resource["substance"],
            "src_layout_code": resource["layout_code"],
            "resource_type": resource["resource_type"],
            "chemical_id": resource.get("chemical_id"),
            "add_volume": volume_mL,
        }

    def make_solid_step(resource: Dict[str, Any], weight_mg: float) -> Dict[str, Any]:
        return {
            "unit_type": "exp_add_solid",
            "substance": resource["substance"],
            "src_layout_code": resource["layout_code"],
            "resource_type": resource["resource_type"],
            "chemical_id": resource.get("chemical_id"),
            "add_weight": weight_mg,
        }

    logical: List[Dict[str, Any]] = []

    catalyst = resources.get("catalyst")
    if catalyst and params.get("catalyst_weight_mg"):
        logical.append(make_solid_step(catalyst, params["catalyst_weight_mg"]))
    elif catalyst and params.get("catalyst_volume_mL"):
        logical.append(make_liquid_step(catalyst, params["catalyst_volume_mL"]))

    logical.extend(
        [
            make_liquid_step(resources["aryl_halide"], params["aryl_halide_volume_mL"]),
            make_liquid_step(resources["boronic_acid"], params["boronic_acid_volume_mL"]),
            make_liquid_step(resources["base"], params["base_volume_mL"]),
        ]
    )

    if resources.get("solvent") and params.get("solvent_fill_mL", 0) > 0:
        logical.append(make_liquid_step(resources["solvent"], params["solvent_fill_mL"]))

    logical.append(
        {
            "unit_type": "exp_magnetic_stirrer",
            "temperature": f"{params['reaction_temperature_C']}C",
            "reaction_duration": int(params["reaction_duration_s"]),
            "rotation_speed": int(params["rotation_speed_rpm"]),
            "still_tem": "rt" if params["reaction_temperature_C"] == 25 else f"{params['reaction_temperature_C']}C",
            "is_wait": True,
        }
    )

    if resources.get("internal_standard"):
        logical.append(make_liquid_step(resources["internal_standard"], round_float(float(params["internal_standard_volume_mL"]), 4)))

    logical.append(
        {
            "unit_type": "exp_magnetic_stirrer",
            "temperature": "25C",
            "reaction_duration": int(params["post_homogenize_duration_s"]),
            "rotation_speed": int(params["rotation_speed_rpm"]),
            "still_tem": "rt",
            "is_wait": True,
        }
    )

    logical.append(
        {
            "unit_type": "exp_filtering_samples",
            "add_volume": round_float(float(params["filtered_aliquot_mL"]), 4),
        }
    )

    return logical


def validate_logical_protocol(logical_protocol: List[Dict[str, Any]], action_schema: Dict[str, Any]) -> None:
    if not isinstance(logical_protocol, list) or not logical_protocol:
        raise SceneGenerationError("Logical protocol must be a non-empty JSON array.")

    logical_schema = action_schema.get("logical_schema", {})
    for idx, step in enumerate(logical_protocol):
        if not isinstance(step, dict):
            raise SceneGenerationError(f"Logical step #{idx} is not an object.")

        unit_type = step.get("unit_type")
        if unit_type not in SUPPORTED_UNIT_TYPES:
            raise SceneGenerationError(f"Unsupported logical unit_type at step #{idx}: {unit_type}")

        schema = logical_schema.get(unit_type)
        if not schema:
            raise SceneGenerationError(f"Missing schema for logical unit_type: {unit_type}")

        for field in schema.get("required_fields", []):
            if field not in step:
                raise SceneGenerationError(
                    f"Logical step #{idx} missing required field '{field}' for unit_type '{unit_type}'"
                )


def get_sample_defaults(sample_protocol: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    defaults: Dict[str, Dict[str, Any]] = {}
    for step in sample_protocol:
        unit_type = step.get("unit_type")
        process_json = step.get("process_json", {})
        if unit_type and unit_type not in defaults and isinstance(process_json, dict):
            defaults[unit_type] = process_json
    return defaults


def build_resource_map(resource_info: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    mapping: Dict[str, Dict[str, Any]] = {}
    for item in build_resource_index(resource_info):
        substance = item.get("substance", "")
        if substance:
            mapping[normalize_substance_name(substance)] = item
    return mapping

def build_layout_map(resource_info: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {item.get("layout_code"): item for item in build_resource_index(resource_info)}

def get_main_reaction_stir_defaults(defaults: Dict[str, Dict[str, Any]], logical_step: Dict[str, Any]) -> Dict[str, Any]:
    sample_stir = defaults.get("exp_magnetic_stirrer", {})
    return {
        "temperature": logical_step.get("temperature", sample_stir.get("temperature", "25C")),
        "reaction_duration": logical_step.get("reaction_duration", sample_stir.get("reaction_duration", 7200)),
        "rotation_speed": logical_step.get("rotation_speed", sample_stir.get("rotation_speed", 650)),
        "still_tem": logical_step.get("still_tem", sample_stir.get("still_tem", "rt")),
        "is_wait": logical_step.get("is_wait", sample_stir.get("is_wait", True)),
        "custom": sample_stir.get("custom", {}),
    }


def find_empty_filter_dst(resource_info: Dict[str, Any]) -> Dict[str, Any]:
    resources = build_resource_index(resource_info)
    preferred = [
        item for item in resources
        if item.get("resource_type") == "TT2TC_V2"
        and item.get("status", 0) == 0
        and str(item.get("layout_code", "")).startswith("T-2:")
    ]
    if preferred:
        return preferred[0]

    fallback = [
        item for item in resources
        if item.get("resource_type") == "TT2TC_V2"
        and item.get("status", 0) == 0
    ]
    if fallback:
        return fallback[0]

    raise SceneGenerationError("No available filtering destination found.")



def render_device_protocol(
    logical_protocol: List[Dict[str, Any]],
    resource_info: Dict[str, Any],
    action_schema: Dict[str, Any],
    sample_protocol: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    defaults = get_sample_defaults(sample_protocol)
    layout_map = build_layout_map(resource_info)
    rendering_defaults = action_schema.get("rendering_defaults", {})
    reactor = rendering_defaults.get("reactor")

    if not isinstance(reactor, dict):
        raise SceneGenerationError("action_schema.rendering_defaults.reactor is missing or invalid.")

    final_protocol: List[Dict[str, Any]] = []

    for i, logical_step in enumerate(logical_protocol):
        unit_type = logical_step["unit_type"]
        step = {
            "layout_code": reactor["layout_code"],
            "substance": reactor.get("substance", ""),
            "resource_type": reactor["resource_type"],
            "tray_QR_code": reactor.get("tray_QR_code", ""),
            "QR_code": reactor.get("QR_code", ""),
            "unit_column": reactor.get("unit_column_start", 0),
            "unit_row": reactor.get("unit_row_start", 0) + i,
            "unit_type": unit_type,
            "unit_id": generate_unit_id(),
            "process_json": {},
        }

        if unit_type == "exp_add_solid":
            src_layout_code = logical_step.get("src_layout_code")
            resource = layout_map.get(src_layout_code)
            if not resource:
                raise SceneGenerationError(f"Resource not found for layout_code: {src_layout_code}")
            sample = defaults.get("exp_add_solid", {})
            step["process_json"] = {
                "src_layout_code": resource["layout_code"],
                "resource_type": logical_step.get("resource_type", resource["resource_type"]),
                "substance": logical_step.get("substance", resource["substance"]),
                "chemical_id": logical_step.get("chemical_id", resource.get("chemical_id")),
                "add_weight": logical_step["add_weight"],
                "offset": sample.get("offset", 0.0),
                "custom": sample.get("custom", {}),
            }

        elif unit_type == "exp_pipetting":
            src_layout_code = logical_step.get("src_layout_code")
            resource = layout_map.get(src_layout_code)
            if not resource:
                raise SceneGenerationError(f"Resource not found for layout_code: {src_layout_code}")
            sample = defaults.get("exp_pipetting", {})
            step["process_json"] = {
                "src_layout_code": resource["layout_code"],
                "resource_type": logical_step.get("resource_type", resource["resource_type"]),
                "substance": logical_step.get("substance", resource["substance"]),
                "chemical_id": logical_step.get("chemical_id", resource.get("chemical_id")),
                "add_volume": logical_step["add_volume"],
                "offset": sample.get("offset", 0.0),
                "disable_LLDSensitivity": sample.get("disable_LLDSensitivity", False),
                "custom": sample.get("custom", {}),
            }

        elif unit_type == "exp_magnetic_stirrer":
            step["process_json"] = get_main_reaction_stir_defaults(defaults, logical_step)

        elif unit_type == "exp_filtering_samples":
            dst = find_empty_filter_dst(resource_info)
            sample = defaults.get("exp_filtering_samples", {})
            dst_default = sample.get("dst", {})
            step["process_json"] = {
                "add_volume": logical_step["add_volume"],
                "offset": sample.get("offset", 0.0),
                "custom": sample.get("custom", {}),
                "dst": {
                    "pos": dst["layout_code"],
                    "resource_type": dst_default.get("resource_type", dst.get("resource_type")),
                    "tray_QR_code": dst_default.get("tray_QR_code", dst.get("tray_QR_code", "")),
                },
            }
        else:
            raise SceneGenerationError(f"Unsupported unit_type during rendering: {unit_type}")

        final_protocol.append(step)

    return final_protocol


def validate_final_protocol(protocol: List[Dict[str, Any]], resource_info: Dict[str, Any]) -> None:
    resource_list = build_resource_index(resource_info)
    by_layout = {item.get("layout_code"): item for item in resource_list}
    seen_unit_ids = set()

    for idx, step in enumerate(protocol):
        if not isinstance(step, dict):
            raise SceneGenerationError(f"Final step #{idx} is not an object.")
        unit_id = step.get("unit_id")
        if not unit_id or unit_id in seen_unit_ids:
            raise SceneGenerationError(f"Final step #{idx} has invalid or duplicated unit_id.")
        seen_unit_ids.add(unit_id)

        process_json = step.get("process_json")
        if not isinstance(process_json, dict):
            raise SceneGenerationError(f"Final step #{idx} process_json must be an object.")

        unit_type = step.get("unit_type")
        if unit_type in {"exp_add_solid", "exp_pipetting"}:
            src_layout_code = process_json.get("src_layout_code")
            resource = by_layout.get(src_layout_code)
            if not resource:
                raise SceneGenerationError(f"Source layout_code not found: {src_layout_code}")

            if process_json.get("resource_type") != resource.get("resource_type"):
                raise SceneGenerationError(f"resource_type mismatch at {src_layout_code}")

            if normalize_substance_name(process_json.get("substance", "")) != normalize_substance_name(resource.get("substance", "")):
                raise SceneGenerationError(f"substance mismatch at {src_layout_code}")

            if unit_type == "exp_pipetting":
                add_volume = float(process_json.get("add_volume", 0) or 0)
                available_volume = float(resource.get("available_volume", 0) or 0)
                if add_volume > available_volume:
                    raise SceneGenerationError(
                        f"add_volume exceeds available_volume at {src_layout_code}: {add_volume} > {available_volume}"
                    )
            if unit_type == "exp_add_solid":
                add_weight = float(process_json.get("add_weight", 0) or 0)
                available_weight = float(resource.get("available_weight", 0) or 0)
                if add_weight > available_weight:
                    raise SceneGenerationError(
                        f"add_weight exceeds available_weight at {src_layout_code}: {add_weight} > {available_weight}"
                    )

        elif unit_type == "exp_filtering_samples":
            dst = process_json.get("dst")
            if not isinstance(dst, dict) or not dst.get("pos"):
                raise SceneGenerationError(f"Filtering step #{idx} missing dst.pos.")
            target = by_layout.get(dst["pos"])
            if not target:
                raise SceneGenerationError(f"Filtering destination not found: {dst['pos']}")
            if target.get("status", 0) != 0:
                raise SceneGenerationError(f"Filtering destination not available: {dst['pos']}")


def generate_protocol_from_goal(goal_text: str, allow_fallback_reagents: bool = False) -> List[Dict[str, Any]]:
    resource_info, action_schema, sample_protocol, scene_rules = load_scene_inputs()

    plan = build_scene_plan(goal_text, resource_info, scene_rules)
    if not allow_fallback_reagents:
        validate_resource_capacity(plan, resource_info)

    logical_protocol = build_logical_protocol_from_scene_plan(plan)
    validate_logical_protocol(logical_protocol, action_schema)

    final_protocol = render_device_protocol(
        logical_protocol=logical_protocol,
        resource_info=resource_info,
        action_schema=action_schema,
        sample_protocol=sample_protocol,
    )
    validate_final_protocol(final_protocol, resource_info)
    return final_protocol
