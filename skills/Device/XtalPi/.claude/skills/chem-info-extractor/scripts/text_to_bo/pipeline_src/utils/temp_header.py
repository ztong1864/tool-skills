import json
from pathlib import Path
from typing import Iterable


def resolve_temp_path() -> Path:
    return Path(__file__).resolve().parents[4] / "KB" / "temp.json"


def load_reaction_columns(temp_path: Path | None = None) -> list[str]:
    path = temp_path or resolve_temp_path()
    if not path.exists():
        raise FileNotFoundError(f"Reaction header temp file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if isinstance(payload, list):
        cols = payload
    elif isinstance(payload, dict):
        cols = payload.get("reaction_columns") or payload.get("columns") or payload.get("headers") or []
    else:
        cols = []
    cleaned = [str(col).strip() for col in cols if str(col).strip()]
    if not cleaned:
        raise ValueError(f"No reaction columns found in temp file: {path}")
    return cleaned
