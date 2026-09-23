from __future__ import annotations

import argparse
import json

from .constants import ENTITY_TYPES, RELATION_TYPES, SCHEMA_DIR
from .entities import EntityService
from .relations import RelationService, relation_id
from .store import GraphStore
from .utils import parse_key_value_pairs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FDU graph CLI")
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

    return parser


def services() -> tuple[GraphStore, EntityService, RelationService]:
    store = GraphStore()
    store.ensure_layout()
    entities = EntityService(store)
    relations = RelationService(store, entities)
    return store, entities, relations


def cmd_init(_: argparse.Namespace) -> int:
    store, _, _ = services()
    write_schema_files(store)
    print(json.dumps({"initialized": True}, ensure_ascii=False, indent=2))
    return 0


def cmd_entity_create(args: argparse.Namespace) -> int:
    _, entities, _ = services()
    payload = {"id": args.id, "entity_type": args.type}
    payload.update(parse_key_value_pairs(args.prop))
    entity = entities.create(payload)
    if args.document_name and args.document_content is not None:
        entity = entities.write_document(args.type, args.id, args.document_name, args.document_content)
    print(json.dumps(entity, ensure_ascii=False, indent=2))
    return 0


def cmd_entity_get(args: argparse.Namespace) -> int:
    _, entities, _ = services()
    entity = entities.get(args.type, args.id)
    print(json.dumps(entity, ensure_ascii=False, indent=2))
    return 0


def cmd_entity_list(args: argparse.Namespace) -> int:
    _, entities, _ = services()
    results = entities.list(args.type, args.text)
    print(json.dumps({"entities": results}, ensure_ascii=False, indent=2))
    return 0


def cmd_entity_update(args: argparse.Namespace) -> int:
    _, entities, _ = services()
    changes = parse_key_value_pairs(args.set)
    entity = entities.update_properties(args.type, args.id, changes)
    if args.document_name and args.document_content is not None:
        entity = entities.write_document(args.type, args.id, args.document_name, args.document_content)
    print(json.dumps(entity, ensure_ascii=False, indent=2))
    return 0


def cmd_entity_delete(args: argparse.Namespace) -> int:
    _, entities, relations = services()
    deleted_relations = relations.delete_touching_entity(args.id)
    entity = entities.delete(args.type, args.id)
    print(json.dumps({"deleted_entity": entity, "deleted_relations": deleted_relations}, ensure_ascii=False, indent=2))
    return 0


def cmd_relation_create(args: argparse.Namespace) -> int:
    _, _, relations = services()
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
    _, _, relations = services()
    results = relations.list(args.type, args.entity_id)
    print(json.dumps({"relations": results}, ensure_ascii=False, indent=2))
    return 0


def cmd_relation_delete(args: argparse.Namespace) -> int:
    _, _, relations = services()
    deleted = relations.delete(args.type, args.id)
    print(json.dumps(deleted, ensure_ascii=False, indent=2))
    return 0


def write_schema_files(store: GraphStore) -> None:
    entity_schema = {
        "entity_types": sorted(ENTITY_TYPES),
    }
    relation_schema = {
        "relation_types": sorted(RELATION_TYPES),
    }
    store.save_json(SCHEMA_DIR / "entity_types.json", entity_schema)
    store.save_json(SCHEMA_DIR / "relation_types.json", relation_schema)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
