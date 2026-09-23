from __future__ import annotations

from typing import Any

from .constants import ENTITY_TYPES
from .schema import require_entity_type, validate_entity
from .store import GraphStore
from .utils import get_dotted, set_dotted


class EntityService:
    def __init__(self, store: GraphStore) -> None:
        self.store = store

    def create_or_update(self, entity: dict[str, Any]) -> dict[str, Any]:
        validate_entity(entity)
        entity_map = self.store.load_entity_map(entity["entity_type"])
        entity_map[entity["id"]] = entity
        self.store.save_entity_map(entity["entity_type"], entity_map)
        return entity

    def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        validate_entity(entity)
        entity_map = self.store.load_entity_map(entity["entity_type"])
        if entity["id"] in entity_map:
            raise ValueError(f"Entity already exists: {entity['id']}")
        entity_map[entity["id"]] = entity
        self.store.save_entity_map(entity["entity_type"], entity_map)
        return entity

    def write_document(self, entity_type: str, entity_id: str, filename: str, content: str) -> dict[str, Any]:
        docs_dir = self.store.entity_docs_dir(entity_type)
        if docs_dir is None:
            raise ValueError(f"Entity type {entity_type} does not support markdown documents")
        docs_dir.mkdir(parents=True, exist_ok=True)
        doc_path = docs_dir / filename
        doc_path.write_text(content, encoding="utf-8")
        entity = self.get(entity_type, entity_id)
        entity["document"] = str(doc_path.relative_to(self.store.root)).replace("\\", "/")
        return self.create_or_update(entity)

    def get(self, entity_type: str, entity_id: str) -> dict[str, Any]:
        require_entity_type(entity_type)
        entity_map = self.store.load_entity_map(entity_type)
        if entity_id not in entity_map:
            raise FileNotFoundError(f"Entity not found: {entity_id}")
        return entity_map[entity_id]

    def exists(self, entity_type: str, entity_id: str) -> bool:
        require_entity_type(entity_type)
        return entity_id in self.store.load_entity_map(entity_type)

    def list(self, entity_type: str | None = None, text: str | None = None) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        entity_types = [entity_type] if entity_type else sorted(ENTITY_TYPES)
        for current_type in entity_types:
            for entity in self.store.load_entity_map(current_type).values():
                if text:
                    haystack = str(entity).lower()
                    if text.lower() not in haystack:
                        continue
                results.append(entity)
        return results

    def update_properties(self, entity_type: str, entity_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        entity = self.get(entity_type, entity_id)
        for key, value in changes.items():
            set_dotted(entity, key, value)
        validate_entity(entity)
        entity_map = self.store.load_entity_map(entity_type)
        entity_map[entity_id] = entity
        self.store.save_entity_map(entity_type, entity_map)
        return entity

    def delete(self, entity_type: str, entity_id: str) -> dict[str, Any]:
        entity = self.get(entity_type, entity_id)
        entity_map = self.store.load_entity_map(entity_type)
        entity_map.pop(entity_id, None)
        self.store.save_entity_map(entity_type, entity_map)
        return entity

    def get_property(self, entity_type: str, entity_id: str, key: str) -> Any:
        entity = self.get(entity_type, entity_id)
        return get_dotted(entity, key)
