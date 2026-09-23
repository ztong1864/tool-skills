from __future__ import annotations

from typing import Any

from .constants import RELATION_TYPES
from .entities import EntityService
from .schema import require_relation_type, validate_relation
from .store import GraphStore
from .utils import stable_hash


def relation_id(source: str, relation_type: str, target: str) -> str:
    return f"rel:{relation_type}:{stable_hash(source + '|' + relation_type + '|' + target)}"


class RelationService:
    def __init__(self, store: GraphStore, entities: EntityService) -> None:
        self.store = store
        self.entities = entities

    def create(self, relation: dict[str, Any], *, allow_existing: bool = True) -> list[dict[str, Any]]:
        validate_relation(relation)
        self._ensure_relation_endpoints(relation)
        created: list[dict[str, Any]] = []
        if self._upsert_relation(relation, allow_existing=allow_existing):
            created.append(relation)
        created.extend(self._derive_relations(relation))
        return created

    def delete(self, relation_type: str, relation_id_value: str) -> dict[str, Any]:
        require_relation_type(relation_type)
        relation_map = self.store.load_relation_map(relation_type)
        if relation_id_value not in relation_map:
            raise FileNotFoundError(f"Relation not found: {relation_id_value}")
        relation = relation_map.pop(relation_id_value)
        self.store.save_relation_map(relation_type, relation_map)
        return relation

    def list(self, relation_type: str | None = None, entity_id: str | None = None) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        relation_types = [relation_type] if relation_type else sorted(RELATION_TYPES)
        for current_type in relation_types:
            for relation in self.store.load_relation_map(current_type).values():
                if entity_id and relation["from"] != entity_id and relation["to"] != entity_id:
                    continue
                results.append(relation)
        return results

    def delete_touching_entity(self, entity_id: str) -> list[dict[str, Any]]:
        deleted: list[dict[str, Any]] = []
        for relation_type in sorted(RELATION_TYPES):
            relation_map = self.store.load_relation_map(relation_type)
            remove_ids = [
                relation_id_value
                for relation_id_value, relation in relation_map.items()
                if relation["from"] == entity_id or relation["to"] == entity_id
            ]
            for relation_id_value in remove_ids:
                deleted.append(relation_map.pop(relation_id_value))
            if remove_ids:
                self.store.save_relation_map(relation_type, relation_map)
        return deleted

    def _ensure_relation_endpoints(self, relation: dict[str, Any]) -> None:
        source_exists = any(entity["id"] == relation["from"] for entity in self.entities.list())
        target_exists = any(entity["id"] == relation["to"] for entity in self.entities.list())
        if not source_exists:
            raise ValueError(f"Relation source does not exist: {relation['from']}")
        if not target_exists:
            raise ValueError(f"Relation target does not exist: {relation['to']}")

    def _upsert_relation(self, relation: dict[str, Any], *, allow_existing: bool) -> bool:
        relation_map = self.store.load_relation_map(relation["relation_type"])
        if relation["id"] in relation_map and not allow_existing:
            raise ValueError(f"Relation already exists: {relation['id']}")
        if relation["id"] in relation_map:
            return False
        relation_map[relation["id"]] = relation
        self.store.save_relation_map(relation["relation_type"], relation_map)
        return True

    def _derive_relations(self, relation: dict[str, Any]) -> list[dict[str, Any]]:
        _ = relation
        return []

    def _find_entity_by_id(self, entity_id: str) -> dict[str, Any] | None:
        for entity in self.entities.list():
            if entity["id"] == entity_id:
                return entity
        return None
