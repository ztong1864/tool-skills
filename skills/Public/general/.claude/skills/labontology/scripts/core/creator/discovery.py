from __future__ import annotations

import ast
import csv
import json
import re
from pathlib import Path
from typing import Any

import yaml

from ..fsutil import iter_dirs, iter_files


MANIFEST_NAMES = ("manifest.yaml", "manifest.yml", "skill.yaml", "skill.yml", "package.yaml")
DOC_NAMES = ("SKILL.md", "README.md", "README.rst", "README.txt", "manifest.md")
KNOWLEDGE_SUFFIXES = {".json", ".yaml", ".yml", ".csv", ".md", ".rst", ".txt"}
KNOWLEDGE_ROOTS = {"kb", "knowledge", "references", "deviceknowledge", "workflow", "workflows", "devices"}
MAX_KNOWLEDGE_BYTES = 4 * 1024 * 1024
# A device's ontology Skill declares the experiment flow of that device in this file: its Skills in order, the
# review Skill after a step, where the user confirms, and named stop points (references/experiment-flows.md).
# `run --flow` builds the mission plan from it.
FLOW_FILE_NAMES = ("experiment_flows.yaml", "experiment_flows.yml")
FLOW_SCHEMA = "labontology.experiment-flow.v1"

# These values are action identifiers, not Skill names. They are strong
# evidence of the capability a Skill needs because they come from the Skill's
# own action schema or structured knowledge file.
ACTION_CAPABILITIES = {
    "exp_pipetting": "capability:liquid-transfer",
    "exp_add_solid": "capability:solid-addition",
    "exp_filtering_samples": "capability:sample-filtration",
    "exp_high_filtering_samples": "capability:high-throughput-filtration",
    "exp_magnetic_stirrer": "capability:reaction-control",
}


class SkillDiscoveryError(ValueError):
    """A Skill's own metadata cannot be read; the Skill is skipped, never guessed."""

    def __init__(self, path: Path, reason: str):
        super().__init__(f"{path}: {reason}")
        self.path = Path(path)
        self.reason = reason


def _yaml_problem(exc: yaml.YAMLError) -> str:
    problem = getattr(exc, "problem", None) or str(exc).splitlines()[0]
    mark = getattr(exc, "problem_mark", None)
    return f"{problem} (line {mark.line + 1})" if mark is not None else str(problem)


def _evidence(source: str, path: Path, detail: str) -> dict[str, str]:
    return {"source": source, "file": str(path), "detail": detail}


def _document_files(skill_dir: Path) -> list[Path]:
    return sorted(
        path for path in iter_files(skill_dir)
        if path.name in DOC_NAMES
    )


def _markdown_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _parse_markdown_document(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    sections: list[dict[str, str]] = []
    current_heading = ""
    current_lines: list[str] = []

    def flush() -> None:
        if current_heading or current_lines:
            sections.append({"heading": current_heading, "text": "\n".join(current_lines), "source": str(path)})

    for line in text.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if match:
            flush()
            current_heading = match.group(1).strip()
            current_lines = []
        elif line.strip():
            current_lines.append(line.strip())
    flush()

    input_hints: list[str] = []
    output_hints: list[str] = []
    execution_order_hints: list[str] = []
    precondition_hints: list[str] = []
    constraint_hints: list[str] = []
    for section in sections:
        heading = section["heading"].lower()
        lines = _markdown_lines(section["text"])
        has_input_heading = bool(re.search(r"输入|input|参数|argument", heading))
        has_output_heading = bool(re.search(r"输出|output|结果", heading))
        if has_input_heading and has_output_heading:
            for line in lines:
                if re.search(r"(?:^[-*]\s*)?输入\s*[:：]", line, re.I):
                    input_hints.append(line)
                elif re.search(r"(?:^[-*]\s*)?输出\s*[:：]", line, re.I):
                    output_hints.append(line)
                else:
                    input_hints.append(line)
                    output_hints.append(line)
        elif has_input_heading:
            input_hints.extend(lines)
        elif has_output_heading:
            output_hints.extend(lines)
        if re.search(r"执行顺序|流程|workflow|sequence|步骤", heading):
            execution_order_hints.extend(lines)
        if re.search(r"前提|条件|precondition|requirement", heading):
            precondition_hints.extend(lines)
        if re.search(r"约束|限制|禁止|注意|constraint|restriction", heading):
            constraint_hints.extend(lines)

    related_files = sorted(set(re.findall(
        r"(?:\.\./|\./)?(?:KB|kb|references|scripts|devices|workflows?)/[A-Za-z0-9_.\-/]+",
        text,
    )))
    related_skill_refs = sorted(set(re.findall(
        r"(?:\.\./)?([A-Za-z0-9][A-Za-z0-9_-]*)/SKILL\.md",
        text,
    )))
    device_evidence = [
        line for line in _markdown_lines(text)
        if re.search(r"设备|设备接口|device\s+api|AddTask|StartTask|GetTaskInfo|Notice|resource", line, re.I)
    ]
    return {
        "path": str(path),
        "sections": sections,
        "input_hints": sorted(set(input_hints)),
        "output_hints": sorted(set(output_hints)),
        "execution_order_hints": sorted(set(execution_order_hints)),
        "precondition_hints": sorted(set(precondition_hints)),
        "constraint_hints": sorted(set(constraint_hints)),
        "related_files": related_files,
        "related_skill_refs": related_skill_refs,
        "device_evidence": sorted(set(device_evidence)),
    }


def _merge_documentation(documents: list[dict[str, Any]]) -> dict[str, Any]:
    fields = (
        "input_hints", "output_hints", "execution_order_hints", "precondition_hints",
        "constraint_hints", "related_files", "related_skill_refs", "device_evidence",
    )
    merged: dict[str, Any] = {
        "files": [item["path"] for item in documents],
        "sections": [section for item in documents for section in item["sections"]],
    }
    for field in fields:
        merged[field] = sorted({value for item in documents for value in item[field]})
    return merged


def _top_level_keys(data: Any) -> list[str]:
    if isinstance(data, dict):
        return sorted(str(key) for key in data)
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return sorted({str(key) for item in data[:100] for key in item})
    return []


def _semantic_values(data: Any) -> list[str]:
    values: set[str] = set()
    if isinstance(data, dict):
        for key, value in data.items():
            key_text = str(key).lower()
            if key_text in {"schema", "schema_version", "version", "unit_type", "action", "action_type"}:
                if isinstance(value, (str, int, float)):
                    values.add(str(value))
            values.update(_semantic_values(value))
    elif isinstance(data, list):
        for item in data[:100]:
            values.update(_semantic_values(item))
    return sorted(values)


def _knowledge_file_record(path: Path, skill_dir: Path) -> dict[str, Any]:
    relative = path.relative_to(skill_dir).as_posix()
    record: dict[str, Any] = {
        "path": relative,
        "source": str(path),
        "format": path.suffix.lower().lstrip(".") or "text",
        "size_bytes": path.stat().st_size,
        "parse_status": "indexed",
        "top_level_keys": [],
        "semantic_values": [],
        "facts": {},
    }
    if path.stat().st_size > MAX_KNOWLEDGE_BYTES:
        record["parse_status"] = "too_large"
        record["unresolved"] = [f"file exceeds {MAX_KNOWLEDGE_BYTES} byte inspection limit"]
        return record
    try:
        if path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            record["top_level_keys"] = _top_level_keys(data)
            record["semantic_values"] = _semantic_values(data)
            record["facts"] = {
                "kind": "array" if isinstance(data, list) else "object" if isinstance(data, dict) else "scalar",
                "item_count": len(data) if isinstance(data, (list, dict)) else 1,
            }
        elif path.suffix.lower() in {".yaml", ".yml"}:
            data = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
            record["top_level_keys"] = _top_level_keys(data)
            record["semantic_values"] = _semantic_values(data)
            record["facts"] = {
                "kind": "array" if isinstance(data, list) else "object" if isinstance(data, dict) else "scalar",
                "item_count": len(data) if isinstance(data, (list, dict)) else 1,
            }
        elif path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.reader(handle))
            record["columns"] = rows[0] if rows else []
            record["facts"] = {"row_count": max(len(rows) - 1, 0)}
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
            record["headings"] = [match.group(1).strip() for match in re.finditer(r"^#{1,6}\s+(.+)$", text, re.M)]
            record["facts"] = {"line_count": len(text.splitlines())}
    except (OSError, UnicodeError, ValueError, yaml.YAMLError, csv.Error) as exc:
        record["parse_status"] = "parse_error"
        record["unresolved"] = [f"{type(exc).__name__}: {exc}"]
    if path.name.lower() == "aliases.json" and isinstance(record.get("facts"), dict):
        record["facts"]["alias_count"] = record["facts"].get("item_count", 0)
    return record


def _knowledge_files(skill_dir: Path) -> list[dict[str, Any]]:
    result = []
    for path in sorted(iter_files(skill_dir)):
        if path.suffix.lower() not in KNOWLEDGE_SUFFIXES:
            continue
        relative_parts = path.relative_to(skill_dir).parts
        if not relative_parts or relative_parts[0].lower() not in KNOWLEDGE_ROOTS:
            continue
        if path.name in DOC_NAMES:
            continue
        result.append(_knowledge_file_record(path, skill_dir))
    return result


def _markdown_metadata(path: Path, *, strict: bool = False) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Read frontmatter and a description; only SKILL.md frontmatter errors are fatal."""
    text = path.read_text(encoding="utf-8", errors="replace")
    metadata: dict[str, Any] = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            body = parts[2]
            try:
                loaded = yaml.safe_load(parts[1])
            except yaml.YAMLError as exc:
                if strict:
                    raise SkillDiscoveryError(path, f"invalid YAML frontmatter: {_yaml_problem(exc)}") from exc
                loaded = None
            if isinstance(loaded, dict):
                metadata = loaded
            elif loaded is not None and strict:
                raise SkillDiscoveryError(path, "frontmatter is not a key/value mapping")
    description = metadata.get("description")
    if not description:
        paragraphs = [line.strip() for line in body.splitlines() if line.strip() and not line.lstrip().startswith("#")]
        if paragraphs:
            description = paragraphs[0]
    if description:
        metadata["description"] = description
    return metadata, [_evidence("markdown", path, "description and frontmatter")]


def _python_parameters(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError, RecursionError):
        return [], [_evidence("python_ast", path, "syntax error; skipped")]
    parameters: list[dict[str, Any]] = []
    subparser_destinations: dict[str, tuple[str, bool]] = {}
    subparser_choices: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if not isinstance(call.func, ast.Attribute) or call.func.attr != "add_subparsers":
            continue
        destination = next((keyword.value.value for keyword in call.keywords
                            if keyword.arg == "dest" and isinstance(keyword.value, ast.Constant)
                            and isinstance(keyword.value.value, str)), None)
        if not destination:
            continue
        required = next((keyword.value.value for keyword in call.keywords
                         if keyword.arg == "required" and isinstance(keyword.value, ast.Constant)), False)
        for target in node.targets:
            if isinstance(target, ast.Name):
                subparser_destinations[target.id] = (destination, required is True)
                subparser_choices.setdefault(target.id, [])
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != "add_parser":
            continue
        if not isinstance(node.func.value, ast.Name) or node.func.value.id not in subparser_destinations:
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            subparser_choices[node.func.value.id].append(node.args[0].value)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != "add_argument":
            continue
        names = [arg.value for arg in node.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)]
        option_name = next((item for item in names if item.startswith("-")), None)
        positional_name = next((item for item in names if not item.startswith("-")), None)
        raw_name = option_name or positional_name
        name = raw_name.lstrip("-").replace("-", "_") if raw_name else None
        if not name:
            continue
        values = {keyword.arg: keyword.value for keyword in node.keywords}
        required = values.get("required")
        default = values.get("default")
        parameter = {
            "name": name,
            "required": required.value if isinstance(required, ast.Constant) else None,
            "default": default.value if isinstance(default, ast.Constant) else None,
        }
        if option_name is None and positional_name is not None:
            parameter["positional"] = True
        parameters.append(parameter)
    for variable, (destination, required) in subparser_destinations.items():
        parameters.append({"name": destination, "required": required, "default": None,
                           "positional": True, "choices": sorted(set(subparser_choices[variable]))})
    return parameters, [_evidence("python_ast", path, "argparse.add_argument")]


def _manifest_data(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    for name in MANIFEST_NAMES:
        candidate = path / name
        if candidate.exists():
            try:
                data = yaml.safe_load(candidate.read_text(encoding="utf-8-sig"))
            except UnicodeDecodeError as exc:
                raise SkillDiscoveryError(candidate, "manifest is not UTF-8 text") from exc
            except yaml.YAMLError as exc:
                raise SkillDiscoveryError(candidate, f"invalid manifest YAML: {_yaml_problem(exc)}") from exc
            if data is not None and not isinstance(data, dict):
                raise SkillDiscoveryError(candidate, "manifest is not a key/value mapping")
            return data or {}, [_evidence("manifest", candidate, "structured metadata")]
    return {}, []


def _flow_text(value: Any) -> str:
    return " ".join(str(value).split()) if isinstance(value, (str, int, float)) else ""


def _experiment_flow(raw: Any, number: int) -> tuple[dict[str, Any] | None, str | None]:
    """One declared flow, normalised; or why it cannot be used."""
    if not isinstance(raw, dict) or not _flow_text(raw.get("id")):
        return None, f"flow {number} has no id"
    flow_id = _flow_text(raw["id"])
    stops_raw = raw.get("stops") or {}
    if not isinstance(stops_raw, dict):
        return None, f"flow {flow_id}: stops must map each stop name to its description"
    stops = {_flow_text(name): _flow_text(text) for name, text in stops_raw.items() if _flow_text(name)}
    steps: list[dict[str, Any]] = []
    for index, item in enumerate(raw.get("steps") or [], 1):
        # `worker` is the step key's earlier name; flow files that still use it keep working.
        name = _flow_text(item.get("skill") or item.get("worker")) if isinstance(item, dict) else ""
        if not name:
            return None, f"flow {flow_id}: step {index} has no skill"
        step: dict[str, Any] = {"skill": name}
        for key in ("review", "pause", "stop"):
            if _flow_text(item.get(key)):
                step[key] = _flow_text(item[key])
        if item.get("optional") is True:
            step["optional"] = True
        if step.get("stop"):
            stops.setdefault(step["stop"], "")
        steps.append(step)
    if not steps:
        return None, f"flow {flow_id}: no steps"
    declared_stops = {step["stop"] for step in steps if step.get("stop")}
    unknown = sorted(set(stops) - declared_stops)
    if unknown:
        return None, f"flow {flow_id}: stops {unknown} are not set on any step (add `stop: <name>` to that step)"
    default_stop = _flow_text(raw.get("default_stop")) or None
    if default_stop and default_stop not in stops:
        return None, f"flow {flow_id}: default_stop {default_stop!r} is not one of its stops {sorted(stops)}"
    return {"id": flow_id, "name": _flow_text(raw.get("name")) or flow_id,
            "description": _flow_text(raw.get("description")), "default_stop": default_stop,
            "stops": stops, "steps": steps}, None


def _experiment_flows(skill_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """The experiment flows a Skill declares, and the problems that made any of them unusable. A bad flow file
    never hides the Skill itself: the problems are reported (inspect) and the flow is left out."""
    candidate = next((skill_dir / name for name in FLOW_FILE_NAMES if (skill_dir / name).is_file()), None)
    if candidate is None:
        return [], []
    try:
        data = yaml.safe_load(candidate.read_text(encoding="utf-8-sig"))
    except UnicodeDecodeError:
        return [], [f"{candidate}: not UTF-8 text"]
    except yaml.YAMLError as exc:
        return [], [f"{candidate}: invalid YAML: {_yaml_problem(exc)}"]
    if not isinstance(data, dict) or data.get("schema") != FLOW_SCHEMA:
        return [], [f"{candidate}: expected a mapping with `schema: {FLOW_SCHEMA}`"]
    raw_flows = data.get("flows")
    if not isinstance(raw_flows, list) or not raw_flows:
        return [], [f"{candidate}: `flows` must be a non-empty list"]
    flows, problems = [], []
    for number, raw in enumerate(raw_flows, 1):
        flow, problem = _experiment_flow(raw, number)
        if problem:
            problems.append(f"{candidate}: {problem}")
        elif any(item["id"] == flow["id"] for item in flows):
            problems.append(f"{candidate}: flow id {flow['id']!r} is declared twice")
        else:
            flows.append({**flow, "source": str(candidate)})
    return flows, problems


def _merge_parameters(manifest: dict[str, Any], discovered: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw = manifest.get("inputs", manifest.get("parameters", [])) or []
    if not isinstance(raw, (list, dict)):
        raw = [raw]
    parameters: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            parameters.append({"name": item, "required": None, "default": None})
        elif isinstance(item, dict) and item.get("name"):
            parameters.append({**item, "name": item["name"], "required": item.get("required"), "default": item.get("default")})
    seen = {item["name"] for item in parameters}
    parameters.extend(item for item in discovered if item["name"] not in seen)
    return parameters


def _normalise_outputs(raw: Any) -> list[dict[str, Any]]:
    """Normalize common output declarations without inferring missing outputs."""
    if not raw:
        return []
    if isinstance(raw, dict):
        normalized: list[dict[str, Any]] = []
        for name, value in raw.items():
            if isinstance(value, dict):
                item = dict(value)
                item.setdefault("name", str(name))
            else:
                item = {"name": str(name)}
                if isinstance(value, str):
                    item["path"] = value
                elif value is not None:
                    item["value"] = value
            normalized.append(item)
        return normalized
    if isinstance(raw, str):
        return [{"name": raw}]
    if isinstance(raw, list):
        normalized = []
        for item in raw:
            if isinstance(item, str):
                normalized.append({"name": item})
            elif isinstance(item, dict) and item.get("name"):
                normalized.append(dict(item))
        return normalized
    return []


def _normalise_references(raw: Any) -> list[str]:
    """Normalize capability/dependency references while preserving only explicit values."""
    if not raw:
        return []
    values = [raw] if isinstance(raw, str) else raw if isinstance(raw, list) else []
    references: list[str] = []
    for item in values:
        if isinstance(item, str):
            references.append(item)
        elif isinstance(item, dict):
            value = item.get("id") or item.get("name")
            if value:
                references.append(str(value))
    return references


def _artifact_id_from_path(path: str) -> str:
    filename = path.replace("\\", "/").rsplit("/", 1)[-1]
    stem = filename.rsplit(".", 1)[0]
    stem = re.sub(r"[_-]<[^>]+>", "", stem)
    stem = re.sub(r"<[^>]+>", "", stem)
    stem = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()
    return f"artifact:{stem or 'result'}"


def _output_path_candidates(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    span = re.compile(r"`([^`\r\n]+)`")
    file_name = re.compile(
        r"output[\\/][^`\r\n]+\.(?:json|csv|md|yaml|yml|txt)|[A-Za-z0-9_.-]+\.(?:json|csv|md|yaml|yml|txt)", re.I)
    for document in documents:
        for hint in document.get("output_hints", []):
            # Code spans are paired left to right first: searching for a file name between any two backticks read
            # the prose between `scripts/write_recommendations.py` and `--rows -` (which names the rows JSON) as a
            # second output, and with two outputs for one --output parameter neither was bound.
            for match in span.finditer(hint):
                if not file_name.search(match.group(1)):
                    continue
                path = match.group(1).strip().rstrip("。，；,;")
                suffix = Path(path.replace("\\", "/")).suffix.lower().lstrip(".")
                candidates.append({
                    "name": _artifact_id_from_path(path),
                    "format": suffix or None,
                    "path": path,
                    "source": "documentation",
                    "confidence": 0.75,
                    "evidence": [hint],
                })
    return candidates


def _python_output_parameters(path: Path) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError, RecursionError):
        return []
    parameters: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != "add_argument":
            continue
        names = [arg.value for arg in node.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)]
        name = next((item.lstrip("-").replace("-", "_") for item in names if item.startswith("-")), None)
        if not name or not re.search(r"(?:^|_)(?:output|result)(?:_|$)", name, re.I):
            continue
        # A store_true/store_false switch (for example --json-output, "print the full JSON")
        # selects an output style; it is not a file the script writes.
        if any(keyword.arg == "action" and isinstance(keyword.value, ast.Constant)
               and keyword.value.value in {"store_true", "store_false"} for keyword in node.keywords):
            continue
        required = next((keyword.value.value for keyword in node.keywords if keyword.arg == "required" and isinstance(keyword.value, ast.Constant)), None)
        parameter_format = None
        lowered = name.lower()
        if "json" in lowered:
            parameter_format = "json"
        elif "csv" in lowered:
            parameter_format = "csv"
        parameters.append({"parameter": name, "required": required is True, "format": parameter_format})

    source_text = path.read_text(encoding="utf-8", errors="replace").lower()
    if ".mmd" in source_text:
        detected_format = "mmd"
    elif "json.dump" in source_text or "json.dumps" in source_text:
        detected_format = "json"
    elif "to_csv" in source_text or "csv.writer" in source_text:
        detected_format = "csv"
    else:
        detected_format = None
    for item in parameters:
        item["format"] = item["format"] or detected_format
        item["file"] = str(path)
    return parameters


def _output_contract_data(
    manifest: dict[str, Any],
    documents: list[dict[str, Any]],
    skill_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    explicit_outputs = _normalise_outputs(manifest.get("outputs", manifest.get("output", [])))
    if explicit_outputs:
        return explicit_outputs, [{
            "field": "outputs",
            "source": "manifest",
            "detail": "explicit output declaration",
            "confidence": 1.0,
        }]

    documented = _output_path_candidates(documents)
    scripted = [item for path in sorted(iter_files(skill_dir, "*.py")) for item in _python_output_parameters(path)]
    outputs: dict[str, dict[str, Any]] = {}
    evidence: list[dict[str, Any]] = []

    for candidate in documented:
        existing = outputs.get(candidate["name"])
        if existing is None or len(candidate["path"]) < len(existing["path"]):
            outputs[candidate["name"]] = {
                key: value for key, value in candidate.items() if key != "evidence"
            }

    for item in scripted:
        matching = next((candidate for candidate in outputs.values() if candidate.get("format") == item.get("format")), None)
        if matching:
            matching["required"] = item["required"]
            matching["source"] = "script_and_documentation"
            matching["confidence"] = 0.9
            matching["binding"] = {
                "parameter": item["parameter"],
                "flag": "--" + item["parameter"].replace("_", "-"),
            }
            evidence.append({
                "field": "outputs",
                "source": "script_and_documentation",
                "file": item["file"],
                "detail": f"output parameter {item['parameter']!r} matches documented output",
                "confidence": 0.9,
            })
            continue
        name = "artifact:result" if item["parameter"] == "output" else _artifact_id_from_path(item["parameter"])
        suffix = item.get("format") or "json"
        is_directory = bool(re.search(r"(?:^|_)(?:output|result)?_?dir(?:ectory)?$", item["parameter"], re.I))
        outputs.setdefault(name, {
            "name": name,
            "format": item.get("format"),
            "path": (
                f"output/{name.removeprefix('artifact:')}_<timestamp>"
                if is_directory
                else f"output/{name.removeprefix('artifact:')}_<timestamp>.{suffix}"
            ),
            "required": item["required"],
            "source": "script",
            "confidence": 0.7,
        })
        evidence.append({
            "field": "outputs",
            "source": "script",
            "file": item["file"],
            "detail": f"output parameter {item['parameter']!r} detected by Python AST",
            "confidence": 0.7,
        })

    if documented and not scripted:
        evidence.append({
            "field": "outputs",
            "source": "documentation",
            "detail": "output path and format extracted from documentation",
            "confidence": 0.75,
        })
    return list(outputs.values()), evidence


def _capability_data(
    manifest: dict[str, Any],
    knowledge_files: list[dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    """Collect explicit and strong Skill-owned capability evidence.

    Explicit manifest declarations are authoritative. Structured action
    identifiers in the Skill's own knowledge files are high-confidence
    evidence, but still remain reviewable data in the imported bundle.
    Skill names and free-form wording are intentionally not used here.
    """
    capabilities: list[str] = []
    evidence: list[dict[str, Any]] = []

    for capability in _normalise_references(
        manifest.get("required_capabilities", manifest.get("requires_capability", []))
    ):
        if capability in capabilities:
            continue
        capabilities.append(capability)
        evidence.append({
            "capability": capability,
            "source": "manifest",
            "file": "<skill-manifest>",
            "detail": "explicit required_capabilities declaration",
            "confidence": 1.0,
        })

    for record in knowledge_files:
        for value in record.get("semantic_values", []):
            capability = ACTION_CAPABILITIES.get(str(value).lower())
            if not capability or capability in capabilities:
                continue
            capabilities.append(capability)
            evidence.append({
                "capability": capability,
                "source": "knowledge",
                "file": record["path"],
                "detail": f"action identifier {value!r} in structured Skill knowledge",
                "confidence": 0.9,
            })

    return capabilities, evidence


def _execution_policy(manifest: dict[str, Any]) -> dict[str, bool]:
    """Skill-declared execution policy: requires_confirmation and/or blocked."""
    declared = manifest.get("execution_policy")
    source = declared if isinstance(declared, dict) else manifest
    return {key: True for key in ("requires_confirmation", "blocked") if source.get(key) is True}


def _skill_metadata(skill_dir: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Identity comes from the Skill's own top-level document; SKILL.md wins.

    Nested documents (KB/README.md, examples/README.md, ...) still contribute
    documentation hints but never rename or re-describe the Skill.
    """
    for name in DOC_NAMES:
        candidate = skill_dir / name
        if candidate.is_file():
            metadata, evidence = _markdown_metadata(candidate, strict=name == "SKILL.md")
            if metadata:
                return metadata, evidence
    return {}, []


def discover_skill(skill_dir: Path) -> dict[str, Any]:
    skill_dir = skill_dir.resolve()
    manifest_data, evidence = _manifest_data(skill_dir)
    metadata, metadata_evidence = _skill_metadata(skill_dir)
    evidence.extend(metadata_evidence)
    documents = [_parse_markdown_document(candidate) for candidate in _document_files(skill_dir)]
    evidence.append(_evidence("manifest", skill_dir / "<directory>", "skill directory scanned"))
    for name in MANIFEST_NAMES:
        if (skill_dir / name).exists():
            break
    python_parameters: list[dict[str, Any]] = []
    for path in sorted(iter_files(skill_dir, "*.py")):
        found, python_evidence = _python_parameters(path)
        python_parameters.extend(found)
        evidence.extend(python_evidence)
    skill_id = manifest_data.get("id") or manifest_data.get("skill_id") or metadata.get("name") or skill_dir.name
    description = manifest_data.get("description") or metadata.get("description")
    parameters = _merge_parameters(manifest_data, python_parameters)
    outputs, contract_evidence = _output_contract_data(manifest_data, documents, skill_dir)
    knowledge_files = _knowledge_files(skill_dir)
    required_capabilities, capability_evidence = _capability_data(manifest_data, knowledge_files)
    dependencies = _normalise_references(
        manifest_data.get("dependencies", manifest_data.get("runtime_dependencies", []))
    )
    side_effect_level = manifest_data.get("side_effect_level")
    experiment_flows, flow_problems = _experiment_flows(skill_dir)
    unresolved: list[str] = []
    if not description:
        unresolved.append("description")
    if not parameters:
        unresolved.append("parameters")
    if not outputs:
        unresolved.append("outputs")
    if side_effect_level is None:
        unresolved.append("side_effect_level")
    return {
        "id": str(skill_id),
        "name": str(manifest_data.get("name") or metadata.get("name") or skill_id),
        "description": description,
        "source_dir": str(skill_dir),
        "parameters": parameters,
        "inputs": manifest_data.get("inputs", []),
        "outputs": outputs,
        "contract_evidence": contract_evidence,
        "required_capabilities": required_capabilities,
        "capability_evidence": capability_evidence,
        "dependencies": dependencies,
        "side_effect_level": side_effect_level,
        "execution_policy": _execution_policy(manifest_data),
        "optional_command": manifest_data.get("optional_command", manifest_data.get("command", [])),
        "working_dir": manifest_data.get("working_dir"),
        "fixed_arguments": manifest_data.get("fixed_arguments", []),
        "argument_bindings": manifest_data.get("argument_bindings", {}),
        "timeout_seconds": manifest_data.get("timeout_seconds"),
        "entrypoints": [str(path) for path in sorted(iter_files(skill_dir, "*.py"))],
        "status": "discovered",
        "confidence": round(0.5 + (0.2 if description else 0) + (0.2 if parameters else 0) + (0.1 if manifest_data else 0), 2),
        "unresolved": unresolved,
        "evidence": evidence,
        "documentation": _merge_documentation(documents),
        "knowledge_files": knowledge_files,
        "experiment_flows": experiment_flows,
        "experiment_flow_problems": flow_problems,
    }


def discover_tree(root: Path, exclude_skill_dirs: set[Path] | None = None,
                  errors: list[dict[str, str]] | None = None,
                  require_contract: bool = False) -> list[dict[str, Any]]:
    """Discover Skills below root.

    When ``errors`` is a list, a Skill whose own metadata is unreadable is
    skipped and reported there, so one broken Skill cannot block the others.
    Without it the first such error is raised. With ``require_contract`` only
    folders declaring a SKILL.md or manifest count as Skills; a folder holding
    only a README (documentation, notes) is not a Skill.
    """
    root = root.resolve()
    excluded = {Path(path).resolve() for path in (exclude_skill_dirs or set())}

    def is_excluded(path: Path) -> bool:
        return any(path == excluded_path or excluded_path in path.parents for excluded_path in excluded)

    candidates: set[Path] = set()
    directories = [path for path in iter_dirs(root) if path == root or not is_excluded(path)]
    for directory in directories:
        if any((directory / name).exists() for name in (*MANIFEST_NAMES, *DOC_NAMES)):
            candidates.add(directory)
    # A skill may contain documentation for internal folders (for example
    # graph/, scripts/, or KB/). Once a parent declares the skill, do not
    # rediscover those folders unless they declare their own manifest/entry.
    roots = [path for path in candidates if any((path / name).exists() for name in MANIFEST_NAMES + ("SKILL.md",))]
    candidates = {
        path for path in candidates
        if not is_excluded(path)
        if not any(path != parent and parent in path.parents for parent in roots)
        or any((path / name).exists() for name in MANIFEST_NAMES + ("SKILL.md",))
    }
    if require_contract:
        candidates = {path for path in candidates if path in roots}
    discovered = []
    for path in sorted(candidates):
        try:
            discovered.append(discover_skill(path))
        except SkillDiscoveryError as exc:
            if errors is None:
                raise
            errors.append({"source_dir": str(path), "file": str(exc.path), "reason": exc.reason})
    return discovered
