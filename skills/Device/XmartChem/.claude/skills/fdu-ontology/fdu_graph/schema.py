from __future__ import annotations

from typing import Any

from .constants import ENTITY_TYPES, RELATION_TYPES


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

    if entity_type == "AgentFlow":
        steps = entity.get("steps", [])
        if steps is not None and not isinstance(steps, list):
            raise ValueError("AgentFlow.steps must be a list")

    if entity_type == "TaskStep":
        for key in ("input_artifact_ids", "output_artifact_ids"):
            values = entity.get(key, [])
            if values is not None and not isinstance(values, list):
                raise ValueError(f"TaskStep.{key} must be a list")

    if entity_type == "DataArtifact":
        for key in ("required_fields", "required_columns", "consumer_step_ids"):
            values = entity.get(key, [])
            if values is not None and not isinstance(values, list):
                raise ValueError(f"DataArtifact.{key} must be a list")

    if entity_type == "Checkpoint":
        shown_artifacts = entity.get("shown_artifact_ids", [])
        if shown_artifacts is not None and not isinstance(shown_artifacts, list):
            raise ValueError("Checkpoint.shown_artifact_ids must be a list")

    if entity_type == "DeviceAction":
        required_fields = entity.get("required_fields", [])
        if required_fields is not None and not isinstance(required_fields, list):
            raise ValueError("DeviceAction.required_fields must be a list")

    if entity_type == "Condition":
        for key in ("required_artifact_ids", "checked_by_step_ids"):
            values = entity.get(key, [])
            if values is not None and not isinstance(values, list):
                raise ValueError(f"Condition.{key} must be a list")

    if entity_type == "Property":
        allowed_values = entity.get("allowed_values", [])
        if allowed_values is not None and not isinstance(allowed_values, list):
            raise ValueError("Property.allowed_values must be a list")

    if entity_type == "Instrument":
        for key in ("supported_action_ids", "required_resource_ids"):
            values = entity.get(key, [])
            if values is not None and not isinstance(values, list):
                raise ValueError(f"Instrument.{key} must be a list")


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
