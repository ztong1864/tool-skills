from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
GRAPH_DIR = ROOT_DIR / "graph"
SOURCE_DIR = GRAPH_DIR / "source" / "workflows"
CANONICAL_DIR = GRAPH_DIR / "canonical"
ENTITIES_DIR = CANONICAL_DIR / "entities"
RELATIONS_DIR = CANONICAL_DIR / "relations"
SCHEMA_DIR = GRAPH_DIR / "schema"
SYNC_DIR = GRAPH_DIR / "sync"

ENTITY_DIR_NAMES = {
    "Workflow": "workflows",
    "WorkflowStepRef": "workflow_step_refs",
    "StepType": "step_types",
    "StepVariant": "step_variants",
    "Process": "processes",
    "Data": "data",
    "Material": "materials",
    "Protocol": "protocols",
    "Instrument": "instruments",
    "Knowledge": "knowledge",
}

DOC_BACKED_ENTITY_TYPES = {"Process", "Knowledge", "Data", "Material"}

ENTITY_FILE_NAMES = {}
for entity_type, dirname in ENTITY_DIR_NAMES.items():
    if entity_type in DOC_BACKED_ENTITY_TYPES:
        ENTITY_FILE_NAMES[entity_type] = f"{dirname}/json/{dirname}.json"
    else:
        ENTITY_FILE_NAMES[entity_type] = f"{dirname}.json"

ENTITY_TYPES = set(ENTITY_DIR_NAMES)

RELATION_TYPES = {
    "hasStep",
    "refersToVariant",
    "instanceOf",
    "produce",
    "withData",
    "useMaterial",
    "usesProtocol",
    "usesInstrument",
    "precedes",
    "guides",
}

RELATION_FILE_NAMES = {
    "hasStep": "has_step.json",
    "refersToVariant": "refers_to_variant.json",
    "instanceOf": "instance_of.json",
    "produce": "process_produce_data.json",
    "withData": "workflow_with_data.json",
    "useMaterial": "workflow_use_material.json",
    "usesProtocol": "uses_protocol.json",
    "usesInstrument": "uses_instrument.json",
    "precedes": "precedes.json",
    "guides": "guides.json",
}

MATERIAL_TYPES = {"sample", "reagent", "consumable"}
