from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .constants import MATERIAL_TYPES, SOURCE_DIR
from .entities import EntityService
from .relations import RelationService, relation_id
from .utils import make_hashed_id, stable_hash


def parse_workflow_filename(path: Path) -> tuple[str, str, str]:
    parts = path.stem.split("__")
    if len(parts) < 3:
        raise ValueError("Workflow file name must look like <workflow>__<subworkflow>__<subworkflow_id>.json")
    return parts[0], parts[1], parts[2]


def load_workflow_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_editable_parameters(step_record: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    editable: dict[str, Any] = {}
    editable_parameters: list[dict[str, Any]] = []
    for parameter in step_record.get("parameterList", []):
        if parameter.get("Type") != "Editable":
            continue
        key = parameter.get("Key")
        if not key:
            continue
        value = parameter.get("Value")
        editable[key] = value
        editable_parameters.append(
            {
                "key": key,
                "value_type": infer_value_type(value),
                "display_name": parameter.get("DisplayParaName") or key,
                "description": "",
            }
        )
    editable_parameters.sort(key=lambda item: item["key"])
    return editable, editable_parameters


def infer_value_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if value is None:
        return "null"
    return "string"


class WorkflowImporter:
    def __init__(self, entities: EntityService, relations: RelationService) -> None:
        self.entities = entities
        self.relations = relations

    def import_file(self, path: Path, *, material_ids: list[str] | None = None, data_ids: list[str] | None = None) -> dict[str, Any]:
        workflow_name, subworkflow_name, subworkflow_id = parse_workflow_filename(path)
        raw = load_workflow_json(path)

        SOURCE_DIR.mkdir(parents=True, exist_ok=True)
        source_copy = SOURCE_DIR / path.name
        source_copy.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

        workflow_id = f"workflow:{subworkflow_id}"
        workflow = {
            "id": workflow_id,
            "entity_type": "Workflow",
            "workflow_name": workflow_name,
            "subworkflow_name": subworkflow_name,
            "subworkflow_id": subworkflow_id,
            "source_file": str(source_copy.relative_to(path.parents[1])).replace("\\", "/") if len(path.parents) > 1 else str(source_copy),
            "source_path": raw.get("path"),
            "steps": [],
        }
        self.entities.create_or_update(workflow)

        created_step_refs: list[str] = []
        created_variants: list[str] = []
        created_step_types: list[str] = []
        created_protocols: list[str] = []
        created_instruments: list[str] = []

        step_items: list[tuple[str, dict[str, Any]]] = []
        for source_step_id, records in raw.get("data", {}).items():
            if not records:
                continue
            step_items.append((source_step_id, records[0]))

        step_items.sort(key=lambda item: (item[1].get("m", 0), item[1].get("n", 0), item[0]))

        previous_ref_id: str | None = None
        for source_step_id, step_record in step_items:
            step_name = step_record.get("name") or "unknown-step"
            step_type_id = make_hashed_id("step-type", step_name)
            editable_params, editable_parameter_defs = normalize_editable_parameters(step_record)
            self._upsert_step_type(step_type_id, step_name, editable_parameter_defs)
            created_step_types.append(step_type_id)

            variant_signature = {"editable_params": editable_params}
            variant_hash = stable_hash(json.dumps(variant_signature, ensure_ascii=False, sort_keys=True))
            step_variant_id = f"step-variant:{step_type_id}:{variant_hash}"
            protocol_value = editable_params.get("protocol")
            instrument_name = self._resolve_instrument_name(step_record)
            self._upsert_step_variant(
                step_variant_id=step_variant_id,
                step_type_id=step_type_id,
                variant_signature=variant_signature,
                display_step_name=self._resolve_display_step_name(step_record),
                display_step_dev_type_name=instrument_name,
            )
            created_variants.append(step_variant_id)

            ref_id = f"workflow-step-ref:{subworkflow_id}:{source_step_id}"
            step_ref = {
                "id": ref_id,
                "entity_type": "WorkflowStepRef",
                "workflow_id": workflow_id,
                "step_variant_id": step_variant_id,
                "source_step_id": source_step_id,
                "lane_index": step_record.get("m"),
                "step_index_in_lane": step_record.get("n"),
                "display_step_index": self._resolve_display_step_index(step_record),
            }
            self.entities.create_or_update(step_ref)
            created_step_refs.append(ref_id)

            self.relations.create(
                {
                    "id": relation_id(workflow_id, "hasStep", ref_id),
                    "relation_type": "hasStep",
                    "from": workflow_id,
                    "to": ref_id,
                }
            )
            self.relations.create(
                {
                    "id": relation_id(ref_id, "refersToVariant", step_variant_id),
                    "relation_type": "refersToVariant",
                    "from": ref_id,
                    "to": step_variant_id,
                }
            )
            self.relations.create(
                {
                    "id": relation_id(step_variant_id, "instanceOf", step_type_id),
                    "relation_type": "instanceOf",
                    "from": step_variant_id,
                    "to": step_type_id,
                }
            )

            if protocol_value:
                protocol_id = self._upsert_protocol(str(protocol_value))
                created_protocols.append(protocol_id)
                self.relations.create(
                    {
                        "id": relation_id(step_type_id, "usesProtocol", protocol_id),
                        "relation_type": "usesProtocol",
                        "from": step_type_id,
                        "to": protocol_id,
                    }
                )

            if instrument_name:
                instrument_id = self._upsert_instrument(instrument_name)
                created_instruments.append(instrument_id)
                self.relations.create(
                    {
                        "id": relation_id(step_variant_id, "usesInstrument", instrument_id),
                        "relation_type": "usesInstrument",
                        "from": step_variant_id,
                        "to": instrument_id,
                    }
                )

            if previous_ref_id:
                self.relations.create(
                    {
                        "id": relation_id(previous_ref_id, "precedes", ref_id),
                        "relation_type": "precedes",
                        "from": previous_ref_id,
                        "to": ref_id,
                    }
                )
            previous_ref_id = ref_id

        workflow["steps"] = created_step_refs
        self.entities.create_or_update(workflow)

        for material_id in material_ids or []:
            material = self._find_existing_entity(material_id, "Material")
            self.relations.create(
                {
                    "id": relation_id(workflow_id, "useMaterial", material["id"]),
                    "relation_type": "useMaterial",
                    "from": workflow_id,
                    "to": material["id"],
                }
            )

        for data_id in data_ids or []:
            data = self._find_existing_entity(data_id, "Data")
            self.relations.create(
                {
                    "id": relation_id(workflow_id, "withData", data["id"]),
                    "relation_type": "withData",
                    "from": workflow_id,
                    "to": data["id"],
                }
            )

        return {
            "workflow_id": workflow_id,
            "step_refs": created_step_refs,
            "step_variants": sorted(set(created_variants)),
            "step_types": sorted(set(created_step_types)),
            "protocols": sorted(set(created_protocols)),
            "instruments": sorted(set(created_instruments)),
        }

    def _upsert_step_type(self, step_type_id: str, name: str, editable_parameters: list[dict[str, Any]]) -> None:
        payload = {
            "id": step_type_id,
            "entity_type": "StepType",
            "canonical_name": name,
            "normalized_name": name,
            "editable_parameters": editable_parameters,
        }
        if self.entities.exists("StepType", step_type_id):
            current = self.entities.get("StepType", step_type_id)
            merged = self._merge_editable_parameters(current.get("editable_parameters", []), editable_parameters)
            current["editable_parameters"] = merged
            self.entities.create_or_update(current)
            return
        self.entities.create(payload)

    def _merge_editable_parameters(self, current: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {item["key"]: item for item in current if "key" in item}
        for item in incoming:
            merged[item["key"]] = {**merged.get(item["key"], {}), **item}
        return [merged[key] for key in sorted(merged)]

    def _upsert_step_variant(
        self,
        *,
        step_variant_id: str,
        step_type_id: str,
        variant_signature: dict[str, Any],
        display_step_name: str | None,
        display_step_dev_type_name: str | None,
    ) -> None:
        payload = {
            "id": step_variant_id,
            "entity_type": "StepVariant",
            "step_type_id": step_type_id,
            "variant_signature": variant_signature,
            "display_step_name": display_step_name,
            "display_step_dev_type_name": display_step_dev_type_name,
        }
        self.entities.create_or_update(payload)

    def _upsert_protocol(self, reference_name: str) -> str:
        protocol_id = make_hashed_id("protocol", reference_name)
        payload = {
            "id": protocol_id,
            "entity_type": "Protocol",
            "protocol_key": reference_name,
            "reference_name": reference_name,
            "description": "",
        }
        self.entities.create_or_update(payload)
        return protocol_id

    def _upsert_instrument(self, name: str) -> str:
        instrument_id = make_hashed_id("instrument", name)
        payload = {
            "id": instrument_id,
            "entity_type": "Instrument",
            "name": name,
        }
        self.entities.create_or_update(payload)
        return instrument_id

    def _resolve_display_step_name(self, step_record: dict[str, Any]) -> str | None:
        for parameter in step_record.get("parameterList", []):
            value = parameter.get("DisplayStepName")
            if value:
                return value
        return step_record.get("name")

    def _resolve_display_step_index(self, step_record: dict[str, Any]) -> int | None:
        for parameter in step_record.get("parameterList", []):
            value = parameter.get("DisplayStepIndex")
            if value is not None:
                return value
        return None

    def _resolve_instrument_name(self, step_record: dict[str, Any]) -> str | None:
        for parameter in step_record.get("parameterList", []):
            value = parameter.get("DisplayStepDevTypeName")
            if value:
                return value
        return None

    def _find_existing_entity(self, entity_id: str, entity_type: str) -> dict[str, Any]:
        entity = self.entities.get(entity_type, entity_id)
        if entity["entity_type"] != entity_type:
            raise ValueError(f"Entity {entity_id} is not of type {entity_type}")
        return entity
