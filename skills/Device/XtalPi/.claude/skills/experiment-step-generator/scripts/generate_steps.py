#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import urllib.error
import urllib.request
from functools import lru_cache

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[2]
KB_DIR = ROOT / "KB"
OUTPUT_DIR = ROOT / "output"

DEFAULT_CONSTRAINTS = WORKSPACE / ".claude" / "skills" / "constraint-parser" / "output" / "parsed_constraints_2026-04-27-13-31-19.json"
DEFAULT_REFERENCE_DIR = WORKSPACE / "experiment_plans"
ATA_STEP_FILE = KB_DIR / "ata_step.md"
REFERENCE_PLAN_FILE = KB_DIR / "reference_experiment_plan.md"


class StepGenerationError(Exception):
    pass


def load_env() -> None:
    workspace_env = WORKSPACE / ".env"
    if workspace_env.exists():
        load_dotenv(workspace_env)


load_env()

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def read_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text[1:] if text.startswith("\ufeff") else text


def read_json(path: Path) -> Any:
    return json.loads(read_text(path))


def write_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_reference_markdown(reference_dir: Path, max_files: int = 3) -> str:
    chunks: list[str] = []
    if REFERENCE_PLAN_FILE.exists():
        chunks.append(read_text(REFERENCE_PLAN_FILE).strip())

    if reference_dir.exists():
        for path in sorted(reference_dir.glob("*.md"))[:max_files]:
            text = read_text(path).strip()
            if text and text not in chunks:
                chunks.append(f"<!-- {path.name} -->\n{text}")

    return "\n\n---\n\n".join(chunks)


def normalize_model_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except Exception as exc:
        raise StepGenerationError(f"LLM detection output is not valid JSON: {exc}; output={cleaned[:500]}") from exc
    if not isinstance(data, dict):
        raise StepGenerationError("LLM detection output must be a JSON object.")
    return data


def build_detection_prompt(source_text: str) -> str:
    return f"""
请判断用户输入的实验指令属于哪一种反应类型。

只输出 JSON，不要输出 Markdown 或解释。

输出格式：
{{
  "reaction_type": "ATA" | "unknown",
  "confidence": 0.0,
  "reason": "一句中文理由"
}}

判断规则：
- 如果文本出现 ATA、炔丙基化、苯乙炔/醛底物组合、金属盐/手性胺优化体系等明显 ATA 线索，输出 "ATA"。
- 如果无法判断，输出 "unknown"。

用户输入：
{source_text}
""".strip()


def build_steps_prompt(source_text: str, ata_steps: str, reference_text: str,
                       selected: list[str] | None = None) -> str:
    if selected:
        material_rule = (
            "4. 下面给出了用户选定的条件：步骤中写这些条件里的具体物料名称和用量，不要再写“从……中选 1 种”这类候选描述；"
            "标为“不加入”的物料不写进步骤。"
            + ("每个条件单独写一组编号步骤，每组前面单独一行写 `### 条件 N`（N 为下面给出的条件编号）。" if len(selected) > 1 else "")
        )
        selected_block = "\n\n## 选定条件（来自投料量表）\n" + "\n".join(selected)
        heading_note = "（每组前的 `### 条件 N` 除外）" if len(selected) > 1 else ""
    else:
        material_rule = "4. 如果用户只给出类别，如“金属盐”“手性胺”“溶剂”，步骤中也保留类别，不要编造具体名称。"
        selected_block = heading_note = ""
    return f"""
你是自动化化学实验步骤编写助手。

输入已被判定为 ATA 反应。
请根据用户原始实验指令和 ATA 步骤模板，输出可执行的实验步骤。

严格要求：
1. 只输出编号步骤列表，不要输出标题、实验概述、试剂作用与用量、过滤信息或其他章节{heading_note}。
2. 直接参考 `ATA 步骤模板` 的步骤顺序和表达方式。
3. 根据 `source_text` 替换或保留试剂/底物/用量信息。
{material_rule}
5. 不输出反应位、过滤位、layout_code、chemical_id、QR_code、托盘信息。
6. 反应条件以 `source_text` 为准：预搅拌、反应温度、反应时间和转速按用户写的来；`source_text` 里有后加的修改（例如“修改：只能室温反应”）时以修改为准；用户没写的条件才沿用 ATA 模板。模板中的后处理照常保留：加入 0.2 mL 联苯内标溶液和 0.6 mL 乙腈；室温搅拌 5 分钟、静置 20 分钟；移取 0.02 mL 上层清液，用 0.8 mL 乙腈稀释。
7. 步骤编号应连续，每步只表达一个主要操作。
8. 不写长篇解释。

## source_text
{source_text}{selected_block}

## ATA 步骤模板
{ata_steps}

## 参考实验方案 Markdown
{reference_text}

请只输出最终编号步骤列表。
""".strip()


def require_llm_config(value: str | None, label: str) -> str:
    if not value:
        raise StepGenerationError(f"{label} is not set.")
    return value


def sanitize_markdown(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:markdown|md)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def validate_markdown(text: str) -> None:
    if not re.search(r"^\s*1[.、]", text, flags=re.MULTILINE):
        raise StepGenerationError("Generated steps must start with a numbered step list.")
    forbidden_sections = ["# 实验步骤方案", "## 实验概述", "## 实验步骤", "## 试剂作用与用量", "## 反应位置与过滤信息"]
    for marker in forbidden_sections:
        if marker in text:
            raise StepGenerationError(f"Generated output must not contain section heading: {marker}")
    if any(token in text for token in ["layout_code", "chemical_id", "QR_code", "tray_QR_code"]):
        raise StepGenerationError("Generated Markdown contains forbidden device binding fields.")


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
        platform = platform_llm_config("EXPERIMENT_STEP_MODEL")
    except PlatformKeyError as exc:
        raise StepGenerationError(str(exc)) from exc
    if platform:
        return platform
    return (
        require_llm_config(OPENAI_BASE_URL, "OPENAI_BASE_URL"),
        require_llm_config(OPENAI_API_KEY, "OPENAI_API_KEY"),
        require_llm_config(OPENAI_MODEL, "OPENAI_MODEL"),
    )


def call_llm(prompt: str, system_content: str = "你只输出干净内容，不输出解释。") -> str:
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
                "content": system_content,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        **({} if platform_llm_config("EXPERIMENT_STEP_MODEL") else {"temperature": 0.2}),  # gpt-6-luna on the 密钥管理 key rejects `temperature`
    }

    response = requests.post(url, headers=headers, json=payload, timeout=120)
    if response.status_code != 200:
        raise StepGenerationError(f"LLM request failed: HTTP {response.status_code}; body={response.text[:1000]}")
    data = response.json()
    try:
        return data["choices"][0]["message"]["content"] or ""
    except Exception as exc:
        raise StepGenerationError(f"Invalid LLM response format: {exc}; raw={data}") from exc


_NOT_ADDED = {"none", "null", "无", "不加入"}


def parse_rows(text: str, count: int) -> list[int]:
    """1-based condition numbers such as "1", "1,3" or "2-4"; empty means every row."""
    if not text.strip():
        return list(range(1, count + 1))
    numbers: list[int] = []
    for part in re.split(r"[,，\s]+", text.strip()):
        if not part:
            continue
        match = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        if not match:
            raise StepGenerationError(f"--rows takes condition numbers such as 1, 1,3 or 2-4, not {part!r}")
        start, end = int(match.group(1)), int(match.group(2) or match.group(1))
        numbers.extend(range(start, end + 1))
    bad = [number for number in numbers if not 1 <= number <= count]
    if bad:
        raise StepGenerationError(f"--rows {bad}: the amounts table has conditions 1-{count}")
    return list(dict.fromkeys(numbers))


def load_selected_conditions(amounts_path: Path, rows: str) -> list[str]:
    """One line per chosen condition of the amounts CSV (columns in pairs `x` / `x_amount`), e.g.
    '条件 1：metal_salt_1 = FeCl3（0.811 mg）；metal_salt_2 = 不加入；…'."""
    with amounts_path.open(encoding="utf-8-sig", newline="") as handle:
        table = list(csv.DictReader(handle))
    if not table:
        raise StepGenerationError(f"Amounts table has no rows: {amounts_path}")
    columns = list(table[0].keys())
    lines: list[str] = []
    for number in parse_rows(rows, len(table)):
        row = table[number - 1]
        parts: list[str] = []
        for column in columns:
            if column.endswith("_amount") and column[: -len("_amount")] in row:
                continue
            value = str(row.get(column) or "").strip()
            amount = str(row.get(f"{column}_amount") or "").strip()
            if not value:
                continue
            if value.lower() in _NOT_ADDED:
                parts.append(f"{column} = 不加入")
            else:
                parts.append(f"{column} = {value}" + (f"（{amount}）" if amount else ""))
        lines.append(f"条件 {number}：" + "；".join(parts))
    return lines


def detect_reaction_type(source_text: str) -> dict[str, Any]:
    raw = call_llm(build_detection_prompt(source_text), system_content="你只输出 JSON，不输出解释。")
    data = normalize_model_json(raw)
    reaction_type = str(data.get("reaction_type", "")).strip().upper()
    if reaction_type not in {"ATA", "UNKNOWN"}:
        data["reaction_type"] = "unknown"
    return data


def generate_steps(constraints_path: Path, reference_dir: Path,
                   amounts_path: Path | None = None, rows: str = "") -> str:
    selected = load_selected_conditions(amounts_path, rows) if amounts_path else None
    constraints = read_json(constraints_path)
    source_text = constraints.get("source_text")
    if not source_text:
        raise StepGenerationError("Constraint JSON does not contain source_text.")
    detection = detect_reaction_type(source_text)
    if str(detection.get("reaction_type", "")).upper() != "ATA":
        reason = detection.get("reason") or "输入未被识别为 ATA 反应。"
        raise StepGenerationError(f"Unsupported reaction type: {detection.get('reaction_type')}; {reason}")
    ata_steps = read_text(ATA_STEP_FILE)
    reference_text = load_reference_markdown(reference_dir)
    markdown = sanitize_markdown(call_llm(build_steps_prompt(source_text, ata_steps, reference_text, selected), system_content="你只输出编号实验步骤列表，不输出标题或解释。"))
    validate_markdown(markdown)
    return markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Markdown experiment steps using LLM.")
    parser.add_argument("--constraints", default=str(DEFAULT_CONSTRAINTS), help="constraint-parser JSON path.")
    parser.add_argument("--reference-dir", default=str(DEFAULT_REFERENCE_DIR), help="Directory containing reference experiment .md files.")
    parser.add_argument("--output", default="", help="Output Markdown path.")
    parser.add_argument("--amounts", default="", help="Optional amounts CSV (chemical-amount-calculator output): write steps "
                        "for chosen conditions with their real materials and amounts.")
    parser.add_argument("--rows", default="", help="With --amounts: condition numbers to keep, e.g. 1 or 1,3 (default: all).")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.rows and not args.amounts:
            raise StepGenerationError("--rows needs --amounts (the amounts CSV the condition numbers refer to).")
        markdown = generate_steps(Path(args.constraints), Path(args.reference_dir),
                                  Path(args.amounts) if args.amounts else None, args.rows)
        out_path = Path(args.output) if args.output else OUTPUT_DIR / f"generated_experiment_steps_{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.md"
        write_text(markdown + "\n", out_path)
        print(f"Experiment steps generated: {out_path}")
        return 0
    except Exception as exc:
        print(f"Generation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
