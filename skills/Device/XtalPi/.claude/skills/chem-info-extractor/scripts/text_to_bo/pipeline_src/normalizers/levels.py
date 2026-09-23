import re
from typing import Dict, Optional


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.3g}"


def _extract_first_number(text: str) -> Optional[float]:
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def normalize_tempo(value: Optional[str], alias: Dict[str, str] | None = None) -> Optional[str]:
    if value is None:
        return None
    text = _clean_text(str(value))
    if alias and text in alias:
        return alias[text]

    lower = text.lower()
    number = _extract_first_number(lower)
    if number is None:
        return None

    if "equiv" in lower or re.search(r"\beq\b", lower):
        return f"{_format_number(number)} equiv"
    if "mol%" in lower or "%" in lower:
        return f"{_format_number(number)} mol%"
    if re.fullmatch(r"\d+(\.\d+)?", lower):
        return f"{_format_number(number)} mol%"
    return None


def normalize_ratio(value: Optional[str], alias: Dict[str, str] | None = None) -> Optional[str]:
    if value is None:
        return None
    text = _clean_text(str(value))
    if alias and text in alias:
        return alias[text]

    lower = text.lower()
    number = _extract_first_number(lower)
    if number is None:
        return None

    if "equiv" in lower or re.search(r"\beq\b", lower):
        return f"{_format_number(number)} eq"
    if "mol%" in lower or "%" in lower:
        # convert mol% to equivalent (e.g., 10 mol% -> 0.1 eq)
        equiv = number / 100.0
        return f"{_format_number(equiv)} eq"
    return None


def normalize_volume(value: Optional[str], alias: Dict[str, str] | None = None) -> Optional[str]:
    if value is None:
        return None
    text = _clean_text(str(value))
    if alias and text in alias:
        return alias[text]

    lower = text.lower()
    if "ml" not in lower:
        return None
    number = _extract_first_number(lower)
    if number is None:
        return None
    return f"{_format_number(number)} mL"


def normalize_solvent(value: Optional[str], alias: Dict[str, str] | None = None) -> Optional[str]:
    if value is None:
        return None
    text = _clean_text(str(value))
    if alias and text in alias:
        return alias[text]

    lower = text.lower()
    replacements = {
        "dce": "DCE",
        "dcm": "DCM",
        "dmf": "DMF",
        "thf": "THF",
        "dme": "DME",
        "ch3cn": "CH3CN",
        "acetonitrile": "CH3CN",
        "ethyl acetate": "ethyl acetate",
        "toluene": "toluene",
        "benzene": "benzene",
    }
    for key, canon in replacements.items():
        if key in lower:
            return canon
    if "ch3cn" in lower and "h2o" in lower:
        return "CH3CN/H2O (9:1)"
    return text


def normalize_additive(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = _clean_text(str(value))
    # Remove parentheses that only contain amounts/units.
    text = re.sub(r"\s*\([^)]*(mol|mmol|equiv|eq|%)\s*[^)]*\)", "", text, flags=re.IGNORECASE)
    parts = [p.strip() for p in re.split(r";", text) if p.strip()]
    if not parts:
        return None
    # de-duplicate while keeping stable order
    seen = set()
    unique = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return "; ".join(unique)


def parse_yield_percent(text: str) -> Optional[float]:
    if not text:
        return None
    lower = text.lower()
    numbers = re.findall(r"(\d+(?:\.\d+)?)\s*%", lower)
    if not numbers:
        return None
    # Prefer isolated yield if explicitly mentioned.
    if "isolated" in lower:
        return float(numbers[-1])
    return float(numbers[0])
