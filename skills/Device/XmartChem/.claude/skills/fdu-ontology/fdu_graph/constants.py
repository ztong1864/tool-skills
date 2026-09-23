from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
GRAPH_DIR = ROOT_DIR / "graph"
CANONICAL_DIR = GRAPH_DIR / "canonical"
ENTITIES_DIR = CANONICAL_DIR / "entities"
RELATIONS_DIR = CANONICAL_DIR / "relations"
SCHEMA_DIR = GRAPH_DIR / "schema"

ENTITY_DIR_NAMES = {
    "AgentFlow": "agent_flows",
    "TaskStep": "task_steps",
    "DataArtifact": "data_artifacts",
    "Checkpoint": "checkpoints",
    "ExecutionRule": "execution_rules",
    "DeviceAction": "device_actions",
    "Resource": "resources",
    "Condition": "conditions",
    "Property": "properties",
    "Instrument": "instruments",
    "Process": "processes",
}

DOC_BACKED_ENTITY_TYPES = {"Process", "DataArtifact", "ExecutionRule"}

ENTITY_FILE_NAMES = {}
for entity_type, dirname in ENTITY_DIR_NAMES.items():
    if entity_type in DOC_BACKED_ENTITY_TYPES:
        ENTITY_FILE_NAMES[entity_type] = f"{dirname}/json/{dirname}.json"
    else:
        ENTITY_FILE_NAMES[entity_type] = f"{dirname}.json"

ENTITY_TYPES = set(ENTITY_DIR_NAMES)

RELATION_TYPES = {
    "startsWith",
    "nextStep",
    "requiresInput",
    "createsOutput",
    "pausesAt",
    "routesTo",
    "appliesTo",
    "requiresResource",
    "containsAction",
    "requiresCondition",
    "hasCondition",
    "hasProperty",
    "usesInstrument",
    "supportsAction",
}

RELATION_FILE_NAMES = {
    "startsWith": "starts_with.json",
    "nextStep": "next_step.json",
    "requiresInput": "requires_input.json",
    "createsOutput": "creates_output.json",
    "pausesAt": "pauses_at.json",
    "routesTo": "routes_to.json",
    "appliesTo": "applies_to.json",
    "requiresResource": "requires_resource.json",
    "containsAction": "contains_action.json",
    "requiresCondition": "requires_condition.json",
    "hasCondition": "has_condition.json",
    "hasProperty": "has_property.json",
    "usesInstrument": "uses_instrument.json",
    "supportsAction": "supports_action.json",
}
