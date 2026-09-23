from __future__ import annotations

import hashlib
import json
import re
from typing import Any


def stable_hash(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()[:8]


def ascii_slug(text: str) -> str:
    lowered = text.strip().lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    lowered = lowered.strip("-")
    return lowered or "item"


def make_hashed_id(prefix: str, name: str) -> str:
    slug = ascii_slug(name)
    return f"{prefix}:{slug}--{stable_hash(name)}"


def safe_file_stem(entity_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", entity_id).strip("._")
    if not cleaned:
        cleaned = "item"
    return f"{cleaned}__{stable_hash(entity_id)}"


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def parse_scalar(value: str) -> Any:
    text = value.strip()
    if text.lower() in {"true", "false"}:
        return text.lower() == "true"
    if text.lower() == "null":
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def parse_key_value_pairs(items: list[str]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid key=value item: {item}")
        key, raw_value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid empty key in item: {item}")
        data[key] = parse_scalar(raw_value)
    return data


def set_dotted(mapping: dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    current = mapping
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = value


def get_dotted(mapping: dict[str, Any], dotted_key: str) -> Any:
    current: Any = mapping
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current
