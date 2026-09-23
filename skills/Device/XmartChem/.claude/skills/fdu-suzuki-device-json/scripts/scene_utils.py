#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
KB_DIR = ROOT / "KB"
OUTPUT_DIR = ROOT / "output"

RESOURCE_FILE = KB_DIR / "resource_info.json"
ACTION_SCHEMA_FILE = KB_DIR / "action_schema.json"
SAMPLE_PROTOCOL_FILE = KB_DIR / "sample_protocol.json"
SCENE_RULES_FILE = KB_DIR / "scene_rules_suzuki.json"

SUPPORTED_UNIT_TYPES = {
    "exp_add_solid",
    "exp_pipetting",
    "exp_magnetic_stirrer",
    "exp_filtering_samples",
}

class SceneGenerationError(Exception):
    pass

def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def write_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def normalize_substance_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip()).lower()

def normalize_token(text: str) -> str:
    return normalize_substance_name(text).replace("₂", "2")

def generate_unit_id() -> str:
    return f"unit-{uuid.uuid4().hex[:8]}"

def load_scene_inputs() -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    resource_info = read_json(RESOURCE_FILE)
    action_schema = read_json(ACTION_SCHEMA_FILE)
    sample_protocol = read_json(SAMPLE_PROTOCOL_FILE)
    scene_rules = read_json(SCENE_RULES_FILE)

    if not isinstance(resource_info, dict):
        raise SceneGenerationError("resource_info.json must be a JSON object.")
    if not isinstance(action_schema, dict):
        raise SceneGenerationError("action_schema.json must be a JSON object.")
    if not isinstance(sample_protocol, list):
        raise SceneGenerationError("sample_protocol.json must be a JSON array.")
    if not isinstance(scene_rules, dict):
        raise SceneGenerationError("scene_rules_suzuki.json must be a JSON object.")

    return resource_info, action_schema, sample_protocol, scene_rules


def round_float(value: float, ndigits: int = 4) -> float:
    return round(float(value), ndigits)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def midpoint(low: float, high: float) -> float:
    return (low + high) / 2.0

def parse_stock_concentration_molar(substance_name: str) -> Optional[float]:
    text = substance_name or ""
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*mol\s*/\s*L", text, flags=re.I)
    if not m:
        return None
    return float(m.group(1))

def extract_numeric_range(text: str, unit_pattern: str) -> Optional[Tuple[float, float]]:
    pattern = rf"([0-9]+(?:\.[0-9]+)?)\s*(?:-|–|—|to)\s*([0-9]+(?:\.[0-9]+)?)\s*{unit_pattern}"
    m = re.search(pattern, text, flags=re.I)
    if not m:
        return None
    low = float(m.group(1))
    high = float(m.group(2))
    if low > high:
        low, high = high, low
    return low, high

def extract_upper_bound(text: str, suffix_pattern: str) -> Optional[float]:
    patterns = [
        rf"(?:not\s+exceed|no\s+more\s+than|at\s+most|should\s+not\s+exceed)\s*([0-9]+(?:\.[0-9]+)?)\s*{suffix_pattern}",
        rf"([0-9]+(?:\.[0-9]+)?)\s*{suffix_pattern}\s*(?:max|maximum|cap)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            return float(m.group(1))
    return None

def extract_explicit_value(text: str, suffix_pattern: str) -> Optional[float]:
    m = re.search(rf"([0-9]+(?:\.[0-9]+)?)\s*{suffix_pattern}", text, flags=re.I)
    return float(m.group(1)) if m else None


def build_resource_index(resource_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    return list(resource_info.get("resources", []))


def find_resources_by_aliases(resource_info: Dict[str, Any], aliases: Iterable[str]) -> List[Dict[str, Any]]:
    alias_tokens = [normalize_token(a) for a in aliases if a]
    matches: List[Dict[str, Any]] = []
    for item in build_resource_index(resource_info):
        substance = item.get("substance", "")
        norm_substance = normalize_token(substance)
        if not norm_substance:
            continue
        if any(alias in norm_substance for alias in alias_tokens):
            matches.append(item)
    return matches

def is_available_resource(item: Dict[str, Any]) -> bool:
    if item.get("status", 0) != 0:
        return False
    vol = item.get("available_volume", 0) or 0
    wt = item.get("available_weight", 0) or 0
    return bool(vol > 0 or wt > 0 or item.get("resource_type") in {"TT2TC_V2", "TTR2T"})

def choose_best_resource(
    resources: List[Dict[str, Any]],
    *,
    prefer_stock: bool = False,
    preferred_keyword: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if not resources:
        return None

    candidates = [r for r in resources if is_available_resource(r)] or list(resources)

    def score(item: Dict[str, Any]) -> Tuple[int, int, float]:
        substance = item.get("substance", "")
        text = normalize_token(substance)
        stock = 1 if "mol/l" in text else 0
        keyword = 1 if preferred_keyword and preferred_keyword.lower() in text else 0
        qty = float(item.get("available_volume", 0) or 0) + float(item.get("available_weight", 0) or 0)
        return (keyword, stock if prefer_stock else 0, qty)

    return sorted(candidates, key=score, reverse=True)[0]

def resolve_resource_or_raise(
    label: str,
    resource_info: Dict[str, Any],
    aliases: Iterable[str],
    *,
    prefer_stock: bool = False,
    preferred_keyword: Optional[str] = None,
    optional: bool = False,
) -> Optional[Dict[str, Any]]:
    matches = find_resources_by_aliases(resource_info, aliases)
    best = choose_best_resource(matches, prefer_stock=prefer_stock, preferred_keyword=preferred_keyword)
    if best is None and not optional:
        raise SceneGenerationError(f"Required resource not found for {label}: aliases={list(aliases)}")
    return best

def mmol_to_mL(mmol: float, molar: Optional[float]) -> float:
    if molar is None or molar <= 0:
        raise SceneGenerationError("Cannot convert mmol to mL because stock concentration is missing.")
    return mmol / molar

def mmol_to_mg(mmol: float, molecular_weight: Optional[float]) -> float:
    if molecular_weight is None or molecular_weight <= 0:
        raise SceneGenerationError("Cannot convert mmol to mg because molecular weight is missing.")
    return mmol * molecular_weight

def safe_get_concentration(resource: Dict[str, Any], label: str) -> float:
    conc = parse_stock_concentration_molar(resource.get("substance", ""))
    if conc is None:
        raise SceneGenerationError(f"Stock concentration missing for {label}: {resource.get('substance')}")
    return conc

def is_stock_solution(resource: Dict[str, Any]) -> bool:
    substance = resource.get("substance", "") or ""
    return parse_stock_concentration_molar(substance) is not None

def is_plain_solvent_resource(resource: Dict[str, Any], solvent_aliases: Iterable[str]) -> bool:
    substance = normalize_token(resource.get("substance", ""))
    aliases = [normalize_token(x) for x in solvent_aliases if x]
    if not substance:
        return False
    if is_stock_solution(resource):
        return False
    return any(alias == substance or alias in substance for alias in aliases)

def summarize_resource(resource: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if resource is None:
        return None
    return {
        "layout_code": resource.get("layout_code"),
        "resource_type": resource.get("resource_type"),
        "substance": resource.get("substance"),
        "chemical_id": resource.get("chemical_id"),
        "available_volume": resource.get("available_volume"),
        "available_weight": resource.get("available_weight"),
    }
