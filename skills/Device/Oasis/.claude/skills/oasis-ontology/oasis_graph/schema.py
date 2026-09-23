from __future__ import annotations

from typing import Any

from .constants import ENTITY_TYPES, MATERIAL_TYPES, RELATION_TYPES


def require_entity_type(entity_type: str) -> None:
    if entity_type not in ENTITY_TYPES:
        allowed = ", ".join(sorted(ENTITY_TYPES))
        raise ValueError(f"Unknown entity type: {entity_type}. Allowed: {allowed}")


def require_relation_type(relation_type: str) -> None:
    if relation_type not in RELATION_TYPES:
        allowed = ", ".join(sorted(RELATION_TYPES))
        raise ValueError(f"Unknown relation type: {relation_type}. Allowed: {allowed}")


def validate_entity(entity: dict[str, Any]) -> None:
    entity_id = entity.get("id")
    entity_type = entity.get("entity_type")
    if not entity_id or not isinstance(entity_id, str):
        raise ValueError("Entity requires a string id")
    if not entity_type or not isinstance(entity_type, str):
        raise ValueError("Entity requires a string entity_type")
    require_entity_type(entity_type)

    if entity_type == "Material":
        material_type = entity.get("material_type")
        if material_type not in MATERIAL_TYPES:
            allowed = ", ".join(sorted(MATERIAL_TYPES))
            raise ValueError(f"Material.material_type must be one of: {allowed}")

    if entity_type == "Workflow":
        steps = entity.get("steps", [])
        if steps is not None and not isinstance(steps, list):
            raise ValueError("Workflow.steps must be a list")

    if entity_type == "StepType":
        editable_parameters = entity.get("editable_parameters", [])
        if editable_parameters is not None and not isinstance(editable_parameters, list):
            raise ValueError("StepType.editable_parameters must be a list")


def validate_relation(relation: dict[str, Any]) -> None:
    relation_id = relation.get("id")
    relation_type = relation.get("relation_type")
    source = relation.get("from")
    target = relation.get("to")

    if not relation_id or not isinstance(relation_id, str):
        raise ValueError("Relation requires a string id")
    if not relation_type or not isinstance(relation_type, str):
        raise ValueError("Relation requires a string relation_type")
    if not source or not isinstance(source, str):
        raise ValueError("Relation requires a string from")
    if not target or not isinstance(target, str):
        raise ValueError("Relation requires a string to")

    require_relation_type(relation_type)
