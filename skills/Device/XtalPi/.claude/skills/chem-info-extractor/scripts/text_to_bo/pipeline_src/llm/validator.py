from typing import Any, Dict, List, Tuple


class ValidationError(Exception):
    pass


def _is_type(value: Any, expected: str) -> bool:
    if expected == "str":
        return isinstance(value, str)
    if expected == "float":
        return isinstance(value, (int, float))
    if expected == "int":
        return isinstance(value, int)
    if expected == "bool":
        return isinstance(value, bool)
    if expected == "list":
        return isinstance(value, list)
    if expected == "dict":
        return isinstance(value, dict)
    return False


def validate_schema(obj: Dict[str, Any], schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors = []
    required = schema.get("required", [])
    for key in required:
        if key not in obj:
            errors.append(f"missing_required:{key}")
    props = schema.get("properties", {})
    for key, spec in props.items():
        if key not in obj:
            continue
        expected = spec.get("type")
        if expected and not _is_type(obj[key], expected):
            errors.append(f"type_mismatch:{key}:{expected}")
    return len(errors) == 0, errors
