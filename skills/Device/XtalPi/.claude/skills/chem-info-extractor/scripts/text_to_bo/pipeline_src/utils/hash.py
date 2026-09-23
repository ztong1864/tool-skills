import hashlib
import json
from typing import Any, Dict


def hash_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def hash_dict(obj: Dict[str, Any]) -> str:
    normalized = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return hash_text(normalized)
