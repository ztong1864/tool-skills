#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import urllib.error
import urllib.request
from functools import lru_cache

import pandas as pd
import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
AGENTS_ROOT = ROOT.parents[1]
KB_DIR = ROOT / "KB"
OUTPUT_DIR = ROOT / "output"

SCHEMA_FILE = KB_DIR / "constraint_schema.md"
EXAMPLE_FILE = KB_DIR / "example_constraints.json"

DEFAULT_TEST_TEXT = (
    "试剂：金属盐（1种或2种，0.05 当量，固体），手性胺（1.2 当量，固体），"
    "分子筛（不加入或20 mg，固体），溶剂（1 mL，液体）\n"
    "底物：苯乙炔（0.1 mmol，1 当量，液体）、正壬醛（1.2 当量，液体）\n"
    "室温条件下做ATA优化反应"
)

REQUIRED_TOP_LEVEL_FIELDS = {
    "schema_version",
    "created_at",
    "items",
    "ambiguities",
    "source_text",
}


class ConstraintParserError(Exception):
    pass


def load_env() -> None:
    env_path = AGENTS_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)


load_env()

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def read_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text[1:] if text.startswith("\ufeff") else text


def read_json(path: Path) -> Any:
    return json.loads(read_text(path))


def write_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def convert_table_to_csv(table_file: str, output: str = "") -> Path:
    source_path = Path(table_file)
    if not source_path.exists():
        raise ConstraintParserError(f"Table file does not exist: {source_path}")
    if not source_path.is_file():
        raise ConstraintParserError(f"Table path is not a file: {source_path}")

    suffix = source_path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        dataframe = pd.read_excel(source_path, sheet_name=0, header=None, dtype=str, keep_default_na=False)
    elif suffix == ".csv":
        dataframe = pd.read_csv(source_path, header=None, dtype=str, keep_default_na=False)
    else:
        raise ConstraintParserError(f"Unsupported table file type: {suffix}. Use .xlsx, .xls, or .csv.")

    if output:
        output_path = Path(output)
    else:
        output_path = OUTPUT_DIR / f"{source_path.stem}_{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(output_path, index=False, header=False, encoding="utf-8-sig")
    return output_path


def normalize_model_output(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def build_prompt(user_text: str, schema_text: str, example_json: Any, previous_error: str = "") -> str:
    retry_note = ""
    if previous_error:
        retry_note = f"""
The previous output failed validation. Fix the JSON according to this error:
{previous_error}
""".strip()

    return f"""
You are a chemistry constraint parser.

Convert the user's natural-language experimental instruction into strict JSON.

Hard requirements:
1. Use the provided schema exactly.
2. Output JSON only. Do not output Markdown, code fences, comments, or explanations.
3. Preserve the original Chinese chemical names and category names exactly.
4. Extract only component name/category, group, equivalent, quantity, physical_state, raw_text, and a short note.
5. Do not invent candidate identities, reagent names, reaction time, temperature values, or solvent names.
6. `equivalent` must contain only 当量/equiv values. Do not put mmol, mg, or mL values into `equivalent`.
7. `quantity` must contain only mass or volume, as `{{
   "value": number,
   "unit": "mg" | "g" | "mL" | "uL" | "L"
}}`, or null when no mass/volume exists.
8. Do not put mmol values into `quantity`; keep mmol in `note` if useful.
9. `physical_state` must be "solid", "liquid", or null.
10. Put simple details such as "1种或2种", "不加入或20 mg", "1 mL", or "0.1 mmol" into `note`.
11. Do not output optimization domains, nested components, device steps, or reaction conditions.
12. Put unresolved missing details in `ambiguities` instead of guessing.

Current local timestamp:
{datetime.now().replace(microsecond=0).isoformat()}

Schema:
{schema_text}

Example JSON:
{json.dumps(example_json, ensure_ascii=False, indent=2)}

User instruction:
{user_text}

{retry_note}
""".strip()


def require_llm_config(value: str | None, label: str) -> str:
    if not value:
        raise ConstraintParserError(f"{label} is not set.")
    return value


# --- FounDryClaw 密钥管理 key (same block in every FounDryClaw device skill script) ---
PLATFORM_MODEL = "gpt-6-luna"
PLATFORM_KEY_MISSING = (
    "未在 FounDryClaw“密钥管理”中找到 OPENAI-API-KEY：请在 设置 → 密钥管理 中添加 "
    "OPENAI-API-KEY（接口地址和 API Key）后重试。"
)


class PlatformKeyError(RuntimeError):
    """Inside FounDryClaw the 密钥管理 OPENAI-API-KEY is required; raised when it is
    missing or cannot be read. There is deliberately no fallback to .env there."""


def _trust_system_ca_store() -> None:
    """Windows only: also trust the OS certificate store. Antivirus HTTPS scanning (e.g. Avast Web/Mail
    Shield) re-signs traffic with a root that only the OS store knows, so certifi alone fails with
    CERTIFICATE_VERIFY_FAILED. Verification stays on; the OS roots are merged into a CA bundle."""
    if sys.platform != "win32" or os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE"):
        return
    try:
        import ssl
        import tempfile

        import certifi

        pems = [Path(certifi.where()).read_text(encoding="utf-8")]
        for store in ("ROOT", "CA"):
            for cert, encoding, _trust in ssl.enum_certificates(store):
                if encoding == "x509_asn":
                    pems.append(ssl.DER_cert_to_PEM_cert(cert))
        bundle = Path(tempfile.gettempdir()) / "foundryclaw_ca_bundle.pem"
        bundle.write_text("\n".join(pems), encoding="utf-8")
        os.environ["REQUESTS_CA_BUNDLE"] = os.environ["SSL_CERT_FILE"] = str(bundle)
    except Exception:
        pass  # keep the default bundle



@lru_cache(maxsize=None)
def platform_llm_config(model_env: str) -> "tuple[str, str, str] | None":
    """(base_url, api_key, model) from the invoking user's OPENAI-API-KEY in 密钥管理,
    model gpt-6-luna unless the model_env variable overrides it. Returns None outside
    FounDryClaw (FOUNDRYCLAW_MODEL_ROUTER_* unset), where the .env settings apply."""
    base = str(os.environ.get("FOUNDRYCLAW_MODEL_ROUTER_BASE_URL") or "").strip()
    token = str(os.environ.get("FOUNDRYCLAW_MODEL_ROUTER_TOKEN") or "").strip()
    if not base or not token:
        return None
    _trust_system_ca_store()
    request = urllib.request.Request(
        base.rstrip("/") + "/api/model-router/internal/openai-key",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, OSError) as exc:
        raise PlatformKeyError(f"无法从 FounDryClaw 读取“密钥管理”中的 OPENAI-API-KEY：{exc}") from exc
    if not isinstance(payload, dict) or not payload.get("configured"):
        raise PlatformKeyError(PLATFORM_KEY_MISSING)
    base_url = str(payload.get("base_url") or "").strip()
    api_key = str(payload.get("api_key") or "").strip()
    if not base_url or not api_key:
        raise PlatformKeyError(PLATFORM_KEY_MISSING)
    return base_url, api_key, os.getenv(model_env) or PLATFORM_MODEL
# --- end FounDryClaw 密钥管理 key ---


def resolve_llm_config() -> tuple[str, str, str]:
    """(base_url, api_key, model): the user's 密钥管理 key inside FounDryClaw (never .env),
    otherwise OPENAI_BASE_URL / OPENAI_API_KEY / OPENAI_MODEL from .env."""
    try:
        platform = platform_llm_config("CONSTRAINT_PARSER_MODEL")
    except PlatformKeyError as exc:
        raise ConstraintParserError(str(exc)) from exc
    if platform:
        return platform
    return (
        require_llm_config(OPENAI_BASE_URL, "OPENAI_BASE_URL"),
        require_llm_config(OPENAI_API_KEY, "OPENAI_API_KEY"),
        require_llm_config(OPENAI_MODEL, "OPENAI_MODEL"),
    )


_RETRY_STATUS = {502, 503, 504}
_ATTEMPTS = 3


def post_to_model(url: str, headers: dict[str, str], payload: dict[str, Any]) -> requests.Response:
    """POST to the model service. A dropped connection or a gateway error is tried again (one reset used to fail
    the whole step); a read timeout is not, so a slow answer is not waited for twice."""
    for attempt in range(1, _ATTEMPTS + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120)
        except requests.ConnectionError as exc:
            if attempt == _ATTEMPTS:
                raise ConstraintParserError(f"LLM request failed after {_ATTEMPTS} attempts: {exc}") from exc
        else:
            if response.status_code not in _RETRY_STATUS or attempt == _ATTEMPTS:
                return response
        time.sleep(2 * attempt)


def call_llm(prompt: str) -> str:
    base_url, api_key, model = resolve_llm_config()

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You output valid JSON only. No Markdown. No explanations.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        **({} if platform_llm_config("CONSTRAINT_PARSER_MODEL") else {"temperature": 0.1}),  # gpt-6-luna on the 密钥管理 key rejects `temperature`
    }

    response = post_to_model(url, headers, payload)
    if response.status_code != 200:
        raise ConstraintParserError(
            f"LLM request failed: HTTP {response.status_code}; body={response.text[:1000]}"
        )
    data = response.json()
    try:
        return data["choices"][0]["message"]["content"] or ""
    except Exception as exc:
        raise ConstraintParserError(f"Invalid LLM response format: {exc}; raw={data}") from exc


def parse_json_output(text: str) -> dict[str, Any]:
    cleaned = normalize_model_output(text)
    try:
        data = json.loads(cleaned)
    except Exception as exc:
        raise ConstraintParserError(f"Model output is not valid JSON: {exc}; output={cleaned[:1000]}") from exc
    if not isinstance(data, dict):
        raise ConstraintParserError("Top-level output must be a JSON object.")
    return data


def validate_item(item: Any, path: str) -> None:
    if not isinstance(item, dict):
        raise ConstraintParserError(f"{path} must be an object.")
    for field in ("name", "group", "equivalent", "quantity", "physical_state", "raw_text"):
        if field not in item:
            raise ConstraintParserError(f"{path}.{field} is required.")
    if item["group"] not in {"reagent", "substrate", "solvent", "condition"}:
        raise ConstraintParserError(f"{path}.group has invalid value: {item['group']!r}")
    if item["physical_state"] not in {"solid", "liquid", None}:
        raise ConstraintParserError(f"{path}.physical_state must be 'solid', 'liquid', or null.")
    if item["equivalent"] is not None and not isinstance(item["equivalent"], (int, float)):
        raise ConstraintParserError(f"{path}.equivalent must be a number or null.")
    quantity = item["quantity"]
    if quantity is not None:
        if not isinstance(quantity, dict):
            raise ConstraintParserError(f"{path}.quantity must be an object or null.")
        for field in ("value", "unit"):
            if field not in quantity:
                raise ConstraintParserError(f"{path}.quantity.{field} is required.")
        if not isinstance(quantity["value"], (int, float)):
            raise ConstraintParserError(f"{path}.quantity.value must be a number.")
        if not isinstance(quantity["unit"], str):
            raise ConstraintParserError(f"{path}.quantity.unit must be a string.")


def validate_constraints(data: dict[str, Any], source_text: str) -> None:
    missing = REQUIRED_TOP_LEVEL_FIELDS - set(data)
    if missing:
        raise ConstraintParserError(f"Missing top-level fields: {sorted(missing)}")

    if data["schema_version"] != "constraint-parser/simple-v1":
        raise ConstraintParserError("schema_version must be 'constraint-parser/simple-v1'.")

    if not isinstance(data["items"], list):
        raise ConstraintParserError("items must be an array.")
    if not isinstance(data["ambiguities"], list):
        raise ConstraintParserError("ambiguities must be an array.")

    for index, item in enumerate(data["items"]):
        validate_item(item, f"items[{index}]")

    if data.get("source_text") != source_text:
        data["source_text"] = source_text


def generate_constraints(user_text: str, attempts: int = 3) -> dict[str, Any]:
    if not SCHEMA_FILE.exists():
        raise ConstraintParserError(f"Missing schema file: {SCHEMA_FILE}")
    if not EXAMPLE_FILE.exists():
        raise ConstraintParserError(f"Missing example file: {EXAMPLE_FILE}")

    schema_text = read_text(SCHEMA_FILE)
    example_json = read_json(EXAMPLE_FILE)
    previous_error = ""

    for attempt in range(1, attempts + 1):
        prompt = build_prompt(user_text, schema_text, example_json, previous_error)
        raw_output = call_llm(prompt)
        try:
            data = parse_json_output(raw_output)
            validate_constraints(data, user_text)
            return data
        except ConstraintParserError as exc:
            previous_error = str(exc)
            if attempt == attempts:
                raise

    raise ConstraintParserError("Generation failed after all attempts.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse experimental constraints into JSON using an LLM.")
    parser.add_argument("--text", default="", help="Natural-language experimental instruction.")
    parser.add_argument("--input-file", default="", help="UTF-8 text file containing the instruction.")
    parser.add_argument("--table-file", default="", help="Input table file to normalize to CSV, usually chemical_space.xlsx.")
    parser.add_argument("--output", default="", help="Optional output JSON path.")
    parser.add_argument("--csv-output", default="", help="Optional output CSV path for --table-file.")
    parser.add_argument("--test", action="store_true", help="Run the built-in ATA example.")
    return parser


def resolve_input(text: str, input_file: str, use_test: bool) -> str:
    if use_test:
        return DEFAULT_TEST_TEXT
    if input_file:
        return read_text(Path(input_file)).strip()
    return text.strip()


def main() -> int:
    args = build_parser().parse_args()
    user_text = resolve_input(args.text, args.input_file, args.test)
    if not user_text:
        print("Input text must not be empty. Use --text, --input-file, or --test.", file=sys.stderr)
        return 1
    if not args.table_file and not args.test:
        print("Table file must not be empty. Use --table-file with a .xlsx, .xls, or .csv file.", file=sys.stderr)
        return 1

    try:
        csv_path = convert_table_to_csv(args.table_file, args.csv_output) if args.table_file else None
        data = generate_constraints(user_text)
        output_path = Path(args.output) if args.output else OUTPUT_DIR / f"parsed_constraints_{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.json"
        write_json(data, output_path)
        print(f"Constraint JSON generated: {output_path}")
        if csv_path:
            print(f"Candidate CSV generated: {csv_path}")
        print(f"Items: {len(data['items'])}; ambiguities: {len(data['ambiguities'])}")
        return 0
    except Exception as exc:
        print(f"Generation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
