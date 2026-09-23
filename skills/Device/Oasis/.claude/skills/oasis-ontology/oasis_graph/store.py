from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .constants import (
    DOC_BACKED_ENTITY_TYPES,
    ENTITIES_DIR,
    ENTITY_DIR_NAMES,
    ENTITY_FILE_NAMES,
    RELATIONS_DIR,
    RELATION_FILE_NAMES,
    ROOT_DIR,
    SCHEMA_DIR,
    SOURCE_DIR,
    SYNC_DIR,
)
from .utils import json_dumps


class GraphStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or ROOT_DIR

    def ensure_layout(self) -> None:
        SOURCE_DIR.mkdir(parents=True, exist_ok=True)
        ENTITIES_DIR.mkdir(parents=True, exist_ok=True)
        RELATIONS_DIR.mkdir(parents=True, exist_ok=True)
        SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
        SYNC_DIR.mkdir(parents=True, exist_ok=True)
        for filename in ENTITY_FILE_NAMES.values():
            path = ENTITIES_DIR / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                self.save_json(path, {})
        for filename in RELATION_FILE_NAMES.values():
            path = RELATIONS_DIR / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                self.save_json(path, {})

    def entity_path(self, entity_type: str, entity_id: str) -> Path:
        _ = entity_id
        return ENTITIES_DIR / ENTITY_FILE_NAMES[entity_type]

    def relation_path(self, relation_type: str, relation_id: str) -> Path:
        _ = relation_id
        return RELATIONS_DIR / RELATION_FILE_NAMES[relation_type]

    def relation_type_dir(self, relation_type: str) -> Path:
        return RELATIONS_DIR / RELATION_FILE_NAMES[relation_type]

    def save_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json_dumps(data), encoding="utf-8")

    def load_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def delete_path(self, path: Path) -> None:
        if path.exists():
            path.unlink()

    def iter_entity_paths(self, entity_type: str | None = None) -> list[Path]:
        if entity_type:
            return [ENTITIES_DIR / ENTITY_FILE_NAMES[entity_type]]
        return [ENTITIES_DIR / filename for filename in ENTITY_FILE_NAMES.values()]

    def iter_relation_paths(self, relation_type: str | None = None) -> list[Path]:
        if relation_type:
            return [RELATIONS_DIR / RELATION_FILE_NAMES[relation_type]]
        return [RELATIONS_DIR / filename for filename in RELATION_FILE_NAMES.values()]

    def load_entity_map(self, entity_type: str) -> dict[str, dict[str, Any]]:
        path = ENTITIES_DIR / ENTITY_FILE_NAMES[entity_type]
        if not path.exists():
            return {}
        data = self.load_json(path)
        return data if isinstance(data, dict) else {}

    def save_entity_map(self, entity_type: str, data: dict[str, dict[str, Any]]) -> None:
        self.save_json(ENTITIES_DIR / ENTITY_FILE_NAMES[entity_type], data)

    def entity_docs_dir(self, entity_type: str) -> Path | None:
        if entity_type not in DOC_BACKED_ENTITY_TYPES:
            return None
        dirname = ENTITY_DIR_NAMES[entity_type]
        return ENTITIES_DIR / dirname

    def load_relation_map(self, relation_type: str) -> dict[str, dict[str, Any]]:
        path = RELATIONS_DIR / RELATION_FILE_NAMES[relation_type]
        if not path.exists():
            return {}
        data = self.load_json(path)
        return data if isinstance(data, dict) else {}

    def save_relation_map(self, relation_type: str, data: dict[str, dict[str, Any]]) -> None:
        self.save_json(RELATIONS_DIR / RELATION_FILE_NAMES[relation_type], data)
