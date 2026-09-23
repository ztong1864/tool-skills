import os
from threading import Lock
from typing import Any, Dict, Optional

from pipeline_src.utils.hash import hash_dict
from pipeline_src.utils.io import append_jsonl, read_jsonl

_CACHE_WRITE_LOCK = Lock()


def load_cache(cache_path: str) -> Dict[str, Dict[str, Any]]:
    entries = read_jsonl(cache_path)
    return {row["cache_key"]: row for row in entries if "cache_key" in row}


def make_cache_key(payload: Dict[str, Any]) -> str:
    return hash_dict(payload)


def get_cached(cache: Dict[str, Dict[str, Any]], cache_key: str) -> Optional[Dict[str, Any]]:
    row = cache.get(cache_key)
    if not row:
        return None
    return row.get("response")


def save_cache(cache_path: str, payload: Dict[str, Any], response: Dict[str, Any]) -> None:
    record = {
        "cache_key": make_cache_key(payload),
        "payload": payload,
        "response": response,
    }
    with _CACHE_WRITE_LOCK:
        append_jsonl(cache_path, [record])
