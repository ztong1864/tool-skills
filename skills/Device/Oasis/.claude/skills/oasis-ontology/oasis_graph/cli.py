from __future__ import annotations

import argparse
import json
from pathlib import Path

from .constants import ENTITY_TYPES, MATERIAL_TYPES, RELATION_TYPES, SCHEMA_DIR
from .entities import EntityService
from .relations import RelationService, relation_id
from .store import GraphStore
from .utils import parse_key_value_pairs
from .workflow_import import WorkflowImporter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Oasis graph CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_init = subparsers.add_parser("init", help="Initialize graph directory layout")
    parser_init.set_defaults(func=cmd_init)

    parser_entity_create = subparsers.add_parser("entity-create", help="Create an entity")
    parser_entity_create.add_argument("--type", required=True, choices=sorted(ENTITY_TYPES))
    parser_entity_create.add_argument("--id", required=True)
    parser_entity_create.add_argument("--prop", action="append", default=[])
    parser_entity_create.add_argument("--document-name")
    parser_entity_create.add_argument("--document-content")
    parser_entity_create.set_defaults(func=cmd_entity_create)

    parser_entity_get = subparsers.add_parser("entity-get", help="Get an entity")
    parser_entity_get.add_argument("--type", required=True, choices=sorted(ENTITY_TYPES))
    parser_entity_get.add_argument("--id", required=True)
    parser_entity_get.set_defaults(func=cmd_entity_get)

    parser_entity_list = subparsers.add_parser("entity-list", help="List entities")
    parser_entity_list.add_argument("--type", choices=sorted(ENTITY_TYPES))
    parser_entity_list.add_argument("--text")
    parser_entity_list.set_defaults(func=cmd_entity_list)

    parser_entity_update = subparsers.add_parser("entity-update", help="Update entity properties")
    parser_entity_update.add_argument("--type", required=True, choices=sorted(ENTITY_TYPES))
    parser_entity_update.add_argument("--id", required=True)
    parser_entity_update.add_argument("--set", action="append", default=[])
    parser_entity_update.add_argument("--document-name")
    parser_entity_update.add_argument("--document-content")
    parser_entity_update.set_defaults(func=cmd_entity_update)

    parser_entity_delete = subparsers.add_parser("entity-delete", help="Delete an entity and touching relations")
    parser_entity_delete.add_argument("--type", required=True, choices=sorted(ENTITY_TYPES))
    parser_entity_delete.add_argument("--id", required=True)
    parser_entity_delete.set_defaults(func=cmd_entity_delete)

    parser_relation_create = subparsers.add_parser("relation-create", help="Create a relation")
    parser_relation_create.add_argument("--type", required=True, choices=sorted(RELATION_TYPES))
    parser_relation_create.add_argument("--from", dest="source", required=True)
    parser_relation_create.add_argument("--to", dest="target", required=True)
    parser_relation_create.add_argument("--prop", action="append", default=[])
    parser_relation_create.set_defaults(func=cmd_relation_create)

    parser_relation_list = subparsers.add_parser("relation-list", help="List relations")
    parser_relation_list.add_argument("--type", choices=sorted(RELATION_TYPES))
    parser_relation_list.add_argument("--entity-id")
    parser_relation_list.set_defaults(func=cmd_relation_list)

    parser_relation_delete = subparsers.add_parser("relation-delete", help="Delete a relation")
    parser_relation_delete.add_argument("--type", required=True, choices=sorted(RELATION_TYPES))
    parser_relation_delete.add_argument("--id", required=True)
    parser_relation_delete.set_defaults(func=cmd_relation_delete)

    parser_workflow_import = subparsers.add_parser("workflow-import", help="Import one workflow JSON")
    parser_workflow_import.add_argument("--file", required=True)
    parser_workflow_import.add_argument("--material-id", action="append", default=[])
    parser_workflow_import.add_argument("--data-id", action="append", default=[])
    parser_workflow_import.set_defaults(func=cmd_workflow_import)

    return parser


def services() -> tuple[GraphStore, EntityService, RelationService, WorkflowImporter]:
    store = GraphStore()
    store.ensure_layout()
    entities = EntityService(store)
    relations = RelationService(store, entities)
    importer = WorkflowImporter(entities, relations)
    return store, entities, relations, importer


def cmd_init(_: argparse.Namespace) -> int:
    store, _, _, _ = services()
    write_schema_files(store)
    print(json.dumps({"initialized": True}, ensure_ascii=False, indent=2))
    return 0


def cmd_entity_create(args: argparse.Namespace) -> int:
    _, entities, _, _ = services()
    payload = {"id": args.id, "entity_type": args.type}
    payload.update(parse_key_value_pairs(args.prop))
    if args.type == "Workflow" and "steps" not in payload:
        payload["steps"] = []
    if args.type == "StepType" and "editable_parameters" not in payload:
        payload["editable_parameters"] = []
    if args.type == "Material" and payload.get("material_type") not in MATERIAL_TYPES:
        allowed = ", ".join(sorted(MATERIAL_TYPES))
        raise ValueError(f"Material requires material_type in: {allowed}")
    entity = entities.create(payload)
    if args.document_name and args.document_content is not None:
        entity = entities.write_document(args.type, args.id, args.document_name, args.document_content)
    print(json.dumps(entity, ensure_ascii=False, indent=2))
    return 0


def cmd_entity_get(args: argparse.Namespace) -> int:
    _, entities, _, _ = services()
    entity = entities.get(args.type, args.id)
    print(json.dumps(entity, ensure_ascii=False, indent=2))
    return 0


def cmd_entity_list(args: argparse.Namespace) -> int:
    _, entities, _, _ = services()
    results = entities.list(args.type, args.text)
    print(json.dumps({"entities": results}, ensure_ascii=False, indent=2))
    return 0


def cmd_entity_update(args: argparse.Namespace) -> int:
    _, entities, _, _ = services()
    changes = parse_key_value_pairs(args.set)
    entity = entities.update_properties(args.type, args.id, changes)
    if args.document_name and args.document_content is not None:
        entity = entities.write_document(args.type, args.id, args.document_name, args.document_content)
    print(json.dumps(entity, ensure_ascii=False, indent=2))
    return 0


def cmd_entity_delete(args: argparse.Namespace) -> int:
    _, entities, relations, _ = services()
    deleted_relations = relations.delete_touching_entity(args.id)
    entity = entities.delete(args.type, args.id)
    if entity["entity_type"] == "WorkflowStepRef":
        workflow_id = entity.get("workflow_id")
        if workflow_id:
            workflow = _find_entity_by_id(entities, workflow_id)
            if workflow:
                workflow["steps"] = [item for item in workflow.get("steps", []) if item != entity["id"]]
                entities.create_or_update(workflow)
    print(json.dumps({"deleted_entity": entity, "deleted_relations": deleted_relations}, ensure_ascii=False, indent=2))
    return 0


def cmd_relation_create(args: argparse.Namespace) -> int:
    _, _, relations, _ = services()
    relation = {
        "id": relation_id(args.source, args.type, args.target),
        "relation_type": args.type,
        "from": args.source,
        "to": args.target,
    }
    relation.update(parse_key_value_pairs(args.prop))
    created = relations.create(relation)
    print(json.dumps({"created_relations": created}, ensure_ascii=False, indent=2))
    return 0


def cmd_relation_list(args: argparse.Namespace) -> int:
    _, _, relations, _ = services()
    results = relations.list(args.type, args.entity_id)
    print(json.dumps({"relations": results}, ensure_ascii=False, indent=2))
    return 0


def cmd_relation_delete(args: argparse.Namespace) -> int:
    _, _, relations, _ = services()
    deleted = relations.delete(args.type, args.id)
    print(json.dumps(deleted, ensure_ascii=False, indent=2))
    return 0


def cmd_workflow_import(args: argparse.Namespace) -> int:
    _, _, _, importer = services()
    result = importer.import_file(
        Path(args.file).resolve(),
        material_ids=args.material_id,
        data_ids=args.data_id,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def write_schema_files(store: GraphStore) -> None:
    entity_schema = {
        "entity_types": sorted(ENTITY_TYPES),
        "material_types": sorted(MATERIAL_TYPES),
    }
    relation_schema = {
        "relation_types": sorted(RELATION_TYPES),
    }
    store.save_json(SCHEMA_DIR / "entity_types.json", entity_schema)
    store.save_json(SCHEMA_DIR / "relation_types.json", relation_schema)


def _find_entity_by_id(entities: EntityService, entity_id: str) -> dict | None:
    for entity in entities.list():
        if entity["id"] == entity_id:
            return entity
    return None


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
