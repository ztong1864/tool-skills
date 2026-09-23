TRIAGE_SCHEMA = {
    "required": ["doc_type", "usefulness_score", "keep", "keep_reason", "drop_reason", "suspected_system_tag"],
    "properties": {
        "doc_type": {"type": "str"},
        "usefulness_score": {"type": "float"},
        "keep": {"type": "bool"},
        "keep_reason": {"type": "str"},
        "drop_reason": {"type": "str"},
        "suspected_system_tag": {"type": "bool"},
    },
}

CANDIDATE_SCHEMA = {
    "required": ["candidates"],
    "properties": {
        "candidates": {"type": "list"},
    },
}

FACT_SCHEMA = {
    "required": ["record", "evidence", "missing_fields", "confidence"],
    "properties": {
        "record": {"type": "dict"},
        "evidence": {"type": "dict"},
        "missing_fields": {"type": "list"},
        "confidence": {"type": "float"},
    },
}

DEFAULT_SCHEMA = {
    "required": ["defaults"],
    "properties": {
        "defaults": {"type": "list"},
    },
}

MERGE_SCHEMA = {
    "required": ["merge_groups"],
    "properties": {
        "merge_groups": {"type": "list"},
    },
}

NORMALIZE_SCHEMA = {
    "required": ["normalized", "notes"],
    "properties": {
        "normalized": {"type": "dict"},
        "notes": {"type": "str"},
    },
}
