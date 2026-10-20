"""Create and maintain the compact LabOntology graph cache.

The cache is an evidence index for an agent. Workflow records are descriptive
references only; this module never turns them into a runtime schedule. An
experiment flow a device's ontology Skill declares is recorded the same way; it
becomes a mission plan only when the Agent creates a mission with `run --flow`
and the user confirms that plan.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..fsutil import iter_files
from .backup import publish_graph

import yaml

BUNDLE_SCHEMA = "labontology.skill-bundle.v1"
CACHE_SCHEMA = "labontology.workspace-cache.v1"
# Bump when discovery or intake output changes so existing caches re-import once.
DISCOVERY_VERSION = 6  # 5: experiment flows (experiment_flows.yaml); output file names only inside code spans;
                       # 6: a flow step names its Skill under `skill` (was `worker`)
MAINTAINABLE_KINDS = frozenset({"knowledge", "device", "workflow"})

def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")

def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower() or "imported"

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _as_list(value: Any) -> list[Any]:
    return [] if value is None else value if isinstance(value, list) else [value]

def _skill_id(skill: dict[str, Any]) -> str:
    return str(skill.get("id") or skill.get("name") or "unknown")

def _artifact_id(value: Any) -> str:
    text = str((value.get("id") or value.get("name")) if isinstance(value, dict) else value)
    return text if text.startswith("artifact:") else f"artifact:{_safe_name(text)}"


def _named(value: Any) -> bool:
    return not isinstance(value, dict) or bool(value.get("id") or value.get("name"))

def _normalise_outputs(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {_artifact_id(key): item for key, item in value.items()}
    result: dict[str, Any] = {}
    for item in _as_list(value):
        if isinstance(item, dict):
            name = item.get("id") or item.get("name")
            if name:
                result[_artifact_id(name)] = item.get("path") or item.get("value")
        elif item:
            result[_artifact_id(item)] = None
    return result

def _skill_outputs(skill: dict[str, Any]) -> dict[str, Any]:
    """Keep named outputs; discard a generic fallback when a concrete output exists."""
    outputs = _normalise_outputs(skill.get("outputs"))
    if len(outputs) > 1:
        outputs.pop("artifact:result", None)
    return outputs

def _explicit_output_bindings(value: Any) -> dict[str, dict[str, Any]]:
    """Read per-output invocation bindings without guessing parameter names."""
    items = value.items() if isinstance(value, dict) else enumerate(_as_list(value))
    bindings: dict[str, dict[str, Any]] = {}
    for key, item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("id") or key
        binding = item.get("binding")
        if not name or not isinstance(binding, dict) or not binding.get("parameter"):
            continue
        normalized = {field: binding[field] for field in ("parameter", "flag", "positional", "additional_flags", "value") if field in binding}
        bindings[_artifact_id(name)] = normalized
    return bindings

def _declared_capabilities(root: Path) -> list[str]:
    values: set[str] = set()
    def collect(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values():
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, str) and value.startswith("capability:"):
            values.add(value)
    for path in iter_files(root):
        if path.suffix.lower() not in {".json", ".yaml", ".yml"}:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path.suffix.lower() == ".json" else yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, yaml.YAMLError):
            continue
        collect(data)
    return sorted(values)

def _source_record(path: Path, roles: list[str], skill_id: str | None = None, note: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"path": str(path.resolve()), "roles": sorted(set(roles)), "sha256": _sha256(path)}
    if skill_id:
        result["skill_id"] = skill_id
    if note:
        result["note"] = note
    return result

INSTRUCTION_DOCUMENTS = ("SKILL.md", "README.md", "manifest.md", "README.rst", "README.txt")


def _instruction_metadata(source_dir: Path) -> dict[str, Any]:
    """The document the host must read before acting: SKILL.md, else the Skill's own README."""
    for name in INSTRUCTION_DOCUMENTS:
        document = source_dir / name
        if document.is_file():
            return {"instruction_source": {"path": str(document.resolve()), "sha256": _sha256(document)}}
    return {}


def _policy_records(skill_id: str, policy: Any) -> list[dict[str, Any]]:
    """Skill-declared execution policy as an ExecutionPolicy entity applied to the Skill."""
    if not isinstance(policy, dict) or not any(policy.get(key) is True for key in ("requires_confirmation", "blocked")):
        return []
    policy_id = f"policy:compact-{_safe_name(skill_id)}"
    return [
        _entity(policy_id, "ExecutionPolicy", {
            "skill_id": skill_id, "source": "manifest",
            "requires_confirmation": policy.get("requires_confirmation") is True,
            "blocked": policy.get("blocked") is True,
        }),
        _relation("appliesTo", policy_id, f"skill:{skill_id}"),
    ]

def _runtime(skill: dict[str, Any], inferred_inputs: list[str] | None = None) -> dict[str, Any]:
    skill_id = _skill_id(skill)
    entrypoints = [Path(str(item)) for item in _as_list(skill.get("entrypoints"))]
    entrypoint = next((item for item in entrypoints if item.exists()), entrypoints[0] if entrypoints else None)
    source_dir = Path(str(skill.get("source_dir") or (entrypoint.parent if entrypoint else "."))).resolve()
    declared_command = [str(item) for item in _as_list(skill.get("optional_command", skill.get("command"))) if str(item)]
    if declared_command:
        command = declared_command
    elif entrypoint and entrypoint.is_relative_to(source_dir):
        command = ["python", entrypoint.relative_to(source_dir).as_posix()]
    else:
        command = ["python", str(entrypoint)] if entrypoint else []
    declared_working_dir = skill.get("working_dir")
    if declared_working_dir:
        working_dir = Path(str(declared_working_dir))
        source_dir = (working_dir if working_dir.is_absolute() else source_dir / working_dir).resolve()
    inputs = list(dict.fromkeys([_artifact_id(item) for item in _as_list(skill.get("inputs")) if _named(item)]
                                + list(inferred_inputs or [])))
    outputs = _skill_outputs(skill)
    bindings: dict[str, dict[str, Any]] = {"inputs": {}, "parameters": {}, "outputs": {
        artifact: binding for artifact, binding in _explicit_output_bindings(skill.get("outputs")).items()
        if artifact in outputs
    }}
    output_parameters = [item for item in _as_list(skill.get("parameters"))
                         if isinstance(item, dict) and item.get("name")
                         and re.search(r"(?:^|_)(?:output|result)(?:_|$)", str(item["name"]), re.I)]
    output_parameter_names = {str(item["name"]) for item in output_parameters}
    for parameter in _as_list(skill.get("parameters")):
        if not isinstance(parameter, dict) or not parameter.get("name"):
            continue
        name = str(parameter["name"])
        binding = {"parameter": name, "positional": True} if parameter.get("positional") else {"parameter": name, "flag": "--" + name.replace("_", "-")}
        normalized = _safe_name(name)
        if name not in output_parameter_names:
            bindings["parameters"][name] = binding
        for artifact in inputs:
            if artifact not in bindings["inputs"] and _safe_name(artifact.removeprefix("artifact:")) == normalized:
                bindings["inputs"][artifact] = binding
        for artifact in outputs:
            if artifact not in bindings["outputs"] and _safe_name(artifact.removeprefix("artifact:")) == normalized:
                bindings["outputs"][artifact] = binding
    for parameter in output_parameters:
        name = str(parameter["name"])
        formats = [value for value in ("csv", "json", "yaml", "yml", "md", "txt") if value in name.lower()]
        if not formats:
            continue
        for artifact, location in outputs.items():
            if artifact in bindings["outputs"] or not any(value in str(location).lower() for value in formats):
                continue
            bindings["outputs"][artifact] = (
                {"parameter": name, "positional": True} if parameter.get("positional")
                else {"parameter": name, "flag": "--" + name.replace("_", "-")}
            )
            break
    unbound_outputs = [artifact for artifact in outputs if artifact not in bindings["outputs"]]
    if len(unbound_outputs) == 1 and len(output_parameters) == 1:
        parameter = output_parameters[0]
        name = str(parameter["name"])
        bindings["outputs"][unbound_outputs[0]] = (
            {"parameter": name, "positional": True} if parameter.get("positional")
            else {"parameter": name, "flag": "--" + name.replace("_", "-")}
        )
    bound_output_parameters = {
        str(binding.get("parameter")) for binding in bindings["outputs"].values()
        if isinstance(binding, dict) and binding.get("parameter")
    }
    for parameter in output_parameters:
        name = str(parameter["name"])
        if name not in bound_output_parameters:
            bindings["parameters"][name] = (
                {"parameter": name, "positional": True} if parameter.get("positional")
                else {"parameter": name, "flag": "--" + name.replace("_", "-")}
            )
    explicit_bindings = skill.get("argument_bindings")
    if isinstance(explicit_bindings, dict):
        for binding_type in ("inputs", "parameters", "outputs"):
            declared = explicit_bindings.get(binding_type)
            if isinstance(declared, dict):
                bindings.setdefault(binding_type, {}).update(declared)
    runtime_outputs = outputs if not output_parameters else {artifact: outputs[artifact] for artifact in bindings["outputs"]}
    return {"id": skill_id, "name": str(skill.get("name") or skill_id),
            "optional_command": command,
            "optional_entrypoints": [str(item) for item in entrypoints if item.exists()],
            "fixed_arguments": _as_list(skill.get("fixed_arguments")), "inputs": inputs, "outputs": runtime_outputs,
            "parameters": [item for item in _as_list(skill.get("parameters")) if isinstance(item, dict)],
            "argument_bindings": {key: value for key, value in bindings.items() if value},
            "required_capabilities": [str(item) for item in _as_list(skill.get("required_capabilities"))],
            "side_effect_level": str(skill.get("side_effect_level") or "read_only"),
            "working_dir": str(source_dir), "timeout_seconds": _timeout_seconds(skill.get("timeout_seconds"))}


def _timeout_seconds(value: Any) -> int:
    """A malformed optional-script timeout must not block the whole import."""
    try:
        return max(1, int(value or 300))
    except (TypeError, ValueError):
        return 300

def _entity(identifier: str, entity_type: str, properties: dict[str, Any]) -> dict[str, Any]:
    return {"entity": {"id": identifier, "type": entity_type, "properties": properties}}

def _relation(relation_type: str, source: str, target: str) -> dict[str, Any]:
    key = hashlib.sha256(f"{relation_type}|{source}|{target}".encode()).hexdigest()[:12]
    return {"relation": {"id": f"rel:{relation_type}:{key}", "relation": relation_type, "source": source, "target": target}}

def _workflow_records(skills: list[dict[str, Any]], workflows: list[dict[str, Any]], suite_id: str,
                      dependencies: dict[str, list[str]] | None = None) -> list[dict[str, Any]]:
    """Store workflow knowledge as a reference, never as a scheduler instruction."""
    known = {_skill_id(skill) for skill in skills}
    if not workflows:
        dependencies = dependencies or {}
        # Do not turn an arbitrary Suite into one giant pseudo-workflow. Only
        # infer a Flow when there is at least one explicit dependency edge;
        # otherwise the Skills remain an un-ordered catalog for Agent search.
        if not any(dependencies.get(_skill_id(skill)) for skill in skills):
            return []
        workflows = [{"id": f"flow:{_safe_name(suite_id)}", "nodes": [
            {"id": _skill_id(skill), "skill": _skill_id(skill), "depends_on": dependencies.get(_skill_id(skill), [])}
            for skill in sorted(skills, key=_skill_id)
            if dependencies.get(_skill_id(skill)) or any(_skill_id(skill) in values for values in dependencies.values())
        ], "inferred": True}]
    records: list[dict[str, Any]] = []
    for workflow in workflows:
        flow_id = str(workflow.get("id") or f"flow:{_safe_name(suite_id)}")
        if not flow_id.startswith("flow:"):
            flow_id = f"flow:{_safe_name(flow_id)}"
        inferred = bool(workflow.get("inferred", not workflow.get("nodes")))
        records.append(_entity(flow_id, "SkillFlow", {
            "name": str(workflow.get("name") or f"{suite_id} workflow reference"),
            "status": "reference_only", "inferred": inferred,
            "confidence": 0.6 if inferred else 1.0,
            "user_confirmed": bool(workflow.get("user_confirmed", not inferred)),
            "inference_basis": _as_list(workflow.get("inference_basis")) or ["declared workflow" if not inferred else "Skill dependency metadata"],
        }))
        nodes = [node for node in _as_list(workflow.get("nodes")) if isinstance(node, dict)]
        for node in nodes:
            skill_id = str(node.get("skill") or node.get("skill_id") or "")
            if skill_id not in known:
                continue
            node_id = f"flow-node:{_safe_name(flow_id.removeprefix('flow:'))}:{_safe_name(str(node.get('id') or skill_id))}"
            records.extend([_entity(node_id, "FlowNode", {"skill_id": skill_id}), _relation("hasNode", flow_id, node_id), _relation("calls", node_id, f"skill:{skill_id}")])
            for dependency in _as_list(node.get("depends_on")):
                predecessor = f"flow-node:{_safe_name(flow_id.removeprefix('flow:'))}:{_safe_name(str(dependency))}"
                records.append(_relation("precedes", predecessor, node_id))
    return records

def _experiment_flow_records(skills: list[dict[str, Any]], flows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A declared experiment flow as a SkillFlow (kind experiment_flow) with its steps, stops and ordered nodes.

    A flow naming a Skill this library does not have is kept with `missing_skills`, so inspect can say why
    `run --flow` refuses it."""
    known = {_skill_id(skill) for skill in skills}
    records: list[dict[str, Any]] = []
    for flow in flows:
        name = str(flow.get("id") or "")
        steps = [step for step in _as_list(flow.get("steps")) if isinstance(step, dict) and step.get("skill")]
        if not name or not steps:
            continue
        flow_entity = f"flow:{_safe_name(name)}"
        named = [skill_id for step in steps for skill_id in (step["skill"], step.get("review")) if skill_id]
        missing = sorted({skill_id for skill_id in named if skill_id not in known})
        records.append(_entity(flow_entity, "SkillFlow", {
            "name": str(flow.get("name") or name), "kind": "experiment_flow", "flow_id": name,
            "description": flow.get("description") or "", "ontology_skill": flow.get("ontology_skill"),
            "default_stop": flow.get("default_stop"), "stops": dict(flow.get("stops") or {}), "steps": steps,
            "missing_skills": missing, "source": flow.get("source"),
            "status": "declared" if not missing else "missing_skills",
            "inferred": False, "confidence": 1.0, "user_confirmed": True,
            "inference_basis": ["declared experiment flow"],
        }))
        order = 0
        for step in steps:
            for node_type, skill_id in (("skill_call", step["skill"]), ("review", step.get("review"))):
                if not skill_id or skill_id not in known:
                    continue
                order += 1
                node_id = f"flow-node:{_safe_name(name)}:{order}_{_safe_name(skill_id)}"
                records.extend([_entity(node_id, "FlowNode", {"skill_id": skill_id, "order": order, "node_type": node_type}),
                                _relation("hasNode", flow_entity, node_id), _relation("calls", node_id, f"skill:{skill_id}")])
    return records

def _graph_records(bundle: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    skills = [item for item in _as_list(bundle.get("skills")) if isinstance(item, dict)]
    suite_id = str(bundle["suite_id"])
    device_root = Path(str(bundle["_bundle_dir"])) / "DeviceKnowledge"
    available_capabilities = set(_declared_capabilities(device_root))
    available_capabilities.update(
        str(capability) for skill in skills for capability in _as_list(skill.get("required_capabilities"))
        if str(capability).startswith("capability:")
    )
    suite_properties = {"name": suite_id, "skill_count": len(skills), "status": "maintained", "available_capabilities": sorted(available_capabilities)}
    flow_problems = [item for item in _as_list(bundle.get("experiment_flow_problems")) if isinstance(item, dict)]
    if flow_problems:
        suite_properties["experiment_flow_problems"] = flow_problems
    records: list[dict[str, Any]] = [_entity(suite_id, "SkillSuite", suite_properties)]
    sources: list[dict[str, Any]] = []
    outputs_by_skill = {_skill_id(skill): _skill_outputs(skill) for skill in skills}
    known_skill_ids = set(outputs_by_skill)
    dependency_map: dict[str, list[str]] = {}
    for skill in skills:
        documentation = skill.get("documentation") if isinstance(skill.get("documentation"), dict) else {}
        references = [str(item) for item in _as_list(skill.get("dependencies"))]
        references.extend(str(item) for item in _as_list(documentation.get("related_skill_refs")))
        input_text = "\n".join(str(item).lower() for item in _as_list(documentation.get("input_hints")))
        for candidate in known_skill_ids:
            forms = {candidate.lower(), candidate.lower().replace("-", " "), candidate.lower().replace("-", "_")}
            # Whole words only: "planning" must not make a Skill depend on "plan".
            if any(re.search(rf"(?<![a-z0-9]){re.escape(form)}(?![a-z0-9])", input_text) for form in forms):
                references.append(candidate)
        dependency_map[_skill_id(skill)] = list(dict.fromkeys(item for item in references if item in known_skill_ids and item != _skill_id(skill)))
    for skill in skills:
        skill_id = _skill_id(skill)
        dependency_inputs = [artifact for dependency in dependency_map[skill_id]
                             for artifact in outputs_by_skill.get(str(dependency), {})]
        runtime = _runtime(skill, dependency_inputs)
        unbound_outputs = sorted(set(_skill_outputs(skill)) - set(runtime["outputs"]))
        unresolved = list(_as_list(skill.get("unresolved"))) + [
            f"runtime output binding missing: {artifact}" for artifact in unbound_outputs
        ]
        properties = {"name": str(skill.get("name") or skill_id), "description": skill.get("description"), "status": str(skill.get("status") or "draft"), "side_effect_level": runtime["side_effect_level"], "required_capabilities": runtime["required_capabilities"], "entrypoints": [str(item) for item in _as_list(skill.get("entrypoints"))], "unresolved": list(dict.fromkeys(unresolved)), "runtime": runtime}
        # Every imported Skill must be read before it can act; a Skill with no
        # instruction document is therefore never selectable at runtime.
        properties["requires_instruction"] = True
        properties.update(_instruction_metadata(Path(str(skill.get("source_dir") or runtime["working_dir"]))))
        properties["preconditions"] = list(_as_list(documentation.get("precondition_hints")))
        for key in ("documentation", "knowledge_files", "capability_evidence", "contract_evidence",
                    "evidence", "recommended_next_skills", "output_mode", "decision_policy"):
            if skill.get(key) not in ({}, [], None):
                properties[key] = skill[key]
        records.extend([_entity(f"skill:{skill_id}", "Skill", properties), _relation("containsSkill", suite_id, f"skill:{skill_id}"), _entity(f"contract:compact-{_safe_name(skill_id)}", "SkillContract", {"skill_id": skill_id, "parameters": runtime["parameters"], "input_artifacts": runtime["inputs"], "outputs": runtime["outputs"]}), _relation("hasContract", f"skill:{skill_id}", f"contract:compact-{_safe_name(skill_id)}")])
        records.extend(_policy_records(skill_id, skill.get("execution_policy")))
        for artifact in runtime["inputs"]:
            artifact_type = f"artifact-type:{_safe_name(artifact.removeprefix('artifact:'))}"
            records.extend([_entity(artifact_type, "ArtifactType", {"name": artifact}), _relation("contractRequires", f"contract:compact-{_safe_name(skill_id)}", artifact_type)])
        for artifact, location in runtime["outputs"].items():
            artifact_type = f"artifact-type:{_safe_name(artifact.removeprefix('artifact:'))}"
            properties = {"name": artifact}
            if location is not None:
                properties["path"] = location
            records.extend([_entity(artifact_type, "ArtifactType", properties), _relation("contractProduces", f"contract:compact-{_safe_name(skill_id)}", artifact_type)])
        source_dir = Path(str(skill.get("source_dir") or runtime["working_dir"]))
        if source_dir.exists():
            for path in sorted(iter_files(source_dir)):
                sources.append(_source_record(path, ["skill_source"], skill_id))
        for raw in _as_list(skill.get("entrypoints")):
            path = Path(str(raw))
            if path.exists():
                sources.append(_source_record(path, ["entrypoint"], skill_id))
        for item in _as_list(skill.get("knowledge_files")):
            if isinstance(item, dict) and item.get("path"):
                path = source_dir / str(item["path"])
                if path.exists():
                    sources.append(_source_record(path, ["knowledge"], skill_id))
    workflow_records = _workflow_records(skills, [item for item in _as_list(bundle.get("workflows")) if isinstance(item, dict)], suite_id, dependency_map)
    workflow_records += _experiment_flow_records(
        skills, [item for item in _as_list(bundle.get("experiment_flows")) if isinstance(item, dict)])
    records.extend(workflow_records)
    for record in workflow_records:
        entity = record.get("entity", {})
        if entity.get("type") == "SkillFlow":
            records.append(_relation("providesSkillFlow", suite_id, entity["id"]))
    for folder, role in (("DeviceKnowledge", "device_knowledge"), ("Workflow", "workflow")):
        root = Path(str(bundle["_bundle_dir"])) / folder
        if root.exists():
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    sources.append(_source_record(path, [role]))
    merged: dict[str, dict[str, Any]] = {}
    for item in sources:
        existing = merged.get(item["path"])
        if existing:
            existing["roles"] = sorted(set(existing["roles"]) | set(item["roles"]))
        else:
            merged[item["path"]] = item
    entities: dict[str, dict[str, Any]] = {}
    relations: dict[str, dict[str, Any]] = {}
    for record in records:
        if "entity" in record:
            entity = record["entity"]
            previous = entities.get(entity["id"])
            if previous is None:
                entities[entity["id"]] = entity
            else:
                previous["properties"].update({key: value for key, value in entity.get("properties", {}).items() if value not in (None, [], {})})
        else:
            relation = record["relation"]
            relations.setdefault(relation["id"], relation)
    return ([{"entity": entity} for entity in entities.values()] + [{"relation": relation} for relation in relations.values()], list(merged.values()))

def portable_root(root: Path, workspace: Path) -> str:
    """Store a Skill root relative to the workspace so the project can be moved."""
    root, workspace = Path(root).resolve(), Path(workspace).resolve()
    try:
        return root.relative_to(workspace).as_posix() or "."
    except ValueError:
        return str(root)


def resolve_suite_root(value: Any, workspace: Path) -> Path:
    path = Path(str(value))
    return (path if path.is_absolute() else Path(workspace) / path).resolve()


def _read_cache_records(cache: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    graph_path, index_path, manifest_path = cache / "ontology.jsonl", cache / "source-index.json", cache / "cache-manifest.json"
    present = [path.is_file() for path in (graph_path, index_path, manifest_path)]
    if not any(present):
        # A missing cache, or a directory holding only runs/, is a new cache.
        return [], [], {}
    if not all(present):
        raise ValueError(f"workspace cache is incomplete: {cache}; run restore-backup to recover the graph")
    records = [json.loads(line) for line in graph_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    index = json.loads(index_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema") != CACHE_SCHEMA:
        schema = manifest.get("schema") if isinstance(manifest, dict) else None
        raise ValueError(f"workspace cache has unsupported schema: {schema!r}")
    return records, list(index.get("sources", [])), manifest


def _suite_owned_ids(records: list[dict[str, Any]], suite_id: str) -> set[str]:
    relations = [record["relation"] for record in records if "relation" in record]
    owned = {suite_id}
    skills = {relation["target"] for relation in relations
              if relation.get("relation") == "containsSkill" and relation.get("source") == suite_id}
    flows = {relation["target"] for relation in relations
             if relation.get("relation") == "providesSkillFlow" and relation.get("source") == suite_id}
    contracts = {relation["target"] for relation in relations
                 if relation.get("relation") == "hasContract" and relation.get("source") in skills}
    nodes = {relation["target"] for relation in relations
             if relation.get("relation") == "hasNode" and relation.get("source") in flows}
    return owned | skills | flows | contracts | nodes


def _replace_suite_records(existing: list[dict[str, Any]], incoming: list[dict[str, Any]], suite_id: str) -> list[dict[str, Any]]:
    relations = [record["relation"] for record in existing if "relation" in record]
    existing_entities = {record["entity"]["id"]: record["entity"] for record in existing if "entity" in record}
    incoming_entities_by_id = {record["entity"]["id"]: record["entity"] for record in incoming if "entity" in record}
    old_skill_ids = {relation["target"] for relation in relations
                     if relation.get("relation") == "containsSkill" and relation.get("source") == suite_id}
    incoming_skill_ids = {record["relation"]["target"] for record in incoming
                          if record.get("relation", {}).get("relation") == "containsSkill"
                          and record["relation"].get("source") == suite_id}
    other_suite_members = {relation["target"] for relation in relations
                           if relation.get("relation") == "containsSkill" and relation.get("source") != suite_id}
    removable_skills = old_skill_ids - incoming_skill_ids - other_suite_members
    removable_contracts = {relation["target"] for relation in relations
                           if relation.get("relation") == "hasContract" and relation.get("source") in removable_skills}
    # Skill-declared policies follow their Skill: re-imported Skills bring the
    # current declaration (or none), removed Skills take theirs with them.
    removable_contracts |= {relation["source"] for relation in relations
                            if relation.get("relation") == "appliesTo"
                            and str(relation.get("source", "")).startswith("policy:compact-")
                            and relation.get("target") in incoming_skill_ids | removable_skills}
    shared_skills = incoming_skill_ids & other_suite_members
    for skill_id in shared_skills:
        existing_properties = existing_entities.get(skill_id, {}).get("properties", {})
        incoming_properties = incoming_entities_by_id.get(skill_id, {}).get("properties", {})
        existing_source = existing_properties.get("instruction_source", {})
        incoming_source = incoming_properties.get("instruction_source", {})
        # A Skill entity is global, so a changed definition is safe to merge
        # only when both memberships point at the same source document. The
        # caller is responsible for refreshing every owning Suite together.
        same_source = (
            isinstance(existing_source, dict) and isinstance(incoming_source, dict)
            and existing_source.get("path") and existing_source.get("path") == incoming_source.get("path")
        )
        if existing_properties != incoming_properties and not same_source:
            raise ValueError(f"conflicting shared Skill definition: {skill_id}")
    retained = [record for record in existing if not (
        ("entity" in record and record["entity"].get("id") in {suite_id} | removable_skills | removable_contracts)
        or ("relation" in record and (
            record["relation"].get("source") == suite_id
            or record["relation"].get("source") in removable_skills
            or record["relation"].get("target") in removable_skills
            or record["relation"].get("source") in removable_contracts
            or record["relation"].get("target") in removable_contracts
        ))
    )]
    old_flows = {relation["target"] for relation in relations
                 if relation.get("relation") == "providesSkillFlow" and relation.get("source") == suite_id}
    old_nodes = {relation["target"] for relation in relations
                 if relation.get("relation") == "hasNode" and relation.get("source") in old_flows}
    retained = [record for record in retained if not (
        ("entity" in record and record["entity"].get("id") in old_flows | old_nodes)
        or ("relation" in record and (
            record["relation"].get("source") in old_flows | old_nodes
            or record["relation"].get("target") in old_flows | old_nodes
        ))
    )]
    retained_entities = {record["entity"]["id"] for record in retained if "entity" in record}
    incoming_entities = {record["entity"]["id"] for record in incoming if "entity" in record}
    conflicts = sorted((retained_entities & incoming_entities) - {
        entity_id for entity_id in retained_entities & incoming_entities
        if entity_id.startswith(("artifact-type:", "skill:", "contract:compact-", "policy:compact-"))
    })
    if conflicts:
        raise ValueError(f"duplicate entity IDs across SkillSuites: {conflicts}")
    entities: dict[str, dict[str, Any]] = {}
    relations: dict[str, dict[str, Any]] = {}
    for record in retained + incoming:
        if "entity" in record:
            entity = record["entity"]
            previous = entities.get(entity["id"])
            if previous is None:
                entities[entity["id"]] = entity
            else:
                previous.setdefault("properties", {}).update(entity.get("properties", {}))
        else:
            relation = record["relation"]
            relations[relation["id"]] = relation
    return ([{"entity": entity} for entity in entities.values()]
            + [{"relation": relation} for relation in relations.values()])


def _merge_sources(existing: list[dict[str, Any]], incoming: list[dict[str, Any]], suite_id: str) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {
        (str(record["path"]), str(record.get("suite_id", ""))): record for record in existing
        if isinstance(record, dict) and record.get("path") and record.get("suite_id") != suite_id
    }
    for record in incoming:
        merged[(str(record["path"]), str(record.get("suite_id", "")))] = record
    return list(merged.values())


def _suite_ids(records: list[dict[str, Any]]) -> list[str]:
    return sorted(record["entity"]["id"] for record in records
                  if record.get("entity", {}).get("type") == "SkillSuite")


def _publish_cache(cache: Path, records: list[dict[str, Any]], sources: list[dict[str, Any]],
                   existing_manifest: dict[str, Any], suite_roots: dict[str, str]) -> list[str]:
    suite_ids = _suite_ids(records)
    timestamp = _now()
    manifest = {"schema": CACHE_SCHEMA, "suite_ids": suite_ids,
                "created_at": existing_manifest.get("created_at", timestamp), "updated_at": timestamp,
                "cache_format": "graph-v1", "discovery_version": DISCOVERY_VERSION,
                "entity_count": sum("entity" in item for item in records),
                "relation_count": sum("relation" in item for item in records),
                "suite_roots": {key: value for key, value in suite_roots.items() if key in suite_ids}}
    publish_graph(cache, records, {"schema": "labontology.source-index.v1", "sources": sources}, manifest,
                  reason="before compact graph replacement")
    return suite_ids


def _write_compact_cache(cache: Path, bundle: dict[str, Any]) -> list[str]:
    existing_records, existing_sources, existing_manifest = _read_cache_records(cache)
    records, sources = _graph_records(bundle)
    suite_id = str(bundle["suite_id"])
    records = _replace_suite_records(existing_records, records, suite_id)
    sources = [{**source, "suite_id": suite_id} for source in sources]
    sources = _merge_sources(existing_sources, sources, suite_id)
    suite_roots = {str(key): str(value) for key, value in dict(existing_manifest.get("suite_roots", {})).items()}
    source_root = bundle.get("_source_root")
    if source_root:
        suite_roots[suite_id] = portable_root(Path(str(source_root)), cache.parent)
    return _publish_cache(cache, records, sources, existing_manifest, suite_roots)


def remove_suites(cache_dir: Path, suite_ids: list[str]) -> list[str]:
    """Drop SkillSuites whose Skill root is gone; mission records are untouched."""
    cache = Path(cache_dir).resolve()
    records, sources, manifest = _read_cache_records(cache)
    present = set(_suite_ids(records))
    removed = [suite_id for suite_id in suite_ids if suite_id in present]
    if not removed:
        return []
    for suite_id in removed:
        records = _replace_suite_records(records, [], suite_id)
    sources = [record for record in sources if record.get("suite_id") not in removed]
    suite_roots = {str(key): str(value) for key, value in dict(manifest.get("suite_roots", {})).items()}
    _publish_cache(cache, records, sources, manifest, suite_roots)
    return removed

def receive_bundle(bundle_dir: Path, workdir: Path | None = None, source_root: Path | None = None) -> dict[str, Any]:
    bundle_dir = Path(bundle_dir).resolve()
    payload_path = bundle_dir / "skills.json"
    if not payload_path.is_file():
        raise FileNotFoundError(f"bundle payload is missing: {payload_path}")
    bundle = json.loads(payload_path.read_text(encoding="utf-8"))
    if bundle.get("schema") != BUNDLE_SCHEMA:
        raise ValueError(f"unsupported bundle schema: {bundle.get('schema')!r}")
    suite_id = bundle.get("suite_id")
    if not isinstance(suite_id, str) or not suite_id:
        raise ValueError("bundle suite_id is required")
    bundle["_bundle_dir"] = str(bundle_dir)
    if source_root is not None:
        bundle["_source_root"] = str(Path(source_root).resolve())
    cache = Path(workdir or Path.cwd()).resolve() / "labontology_workspace_cache"
    suite_ids = _write_compact_cache(cache, bundle)
    return {"output_dir": str(cache), "cache_format": "graph-v1", "suite_id": suite_id, "suite_ids": suite_ids}

def maintain_cache(cache_dir: Path, source: Path, *, kind: str = "knowledge", skill_id: str | None = None,
                   note: str | None = None, suite_id: str | None = None) -> dict[str, Any]:
    if kind not in MAINTAINABLE_KINDS:
        raise ValueError(f"unsupported maintenance kind: {kind}")
    cache, source = Path(cache_dir).resolve(), Path(source).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"source is not a file: {source}")
    index_path, graph_path = cache / "source-index.json", cache / "ontology.jsonl"
    if not index_path.is_file() or not graph_path.is_file():
        raise FileNotFoundError("cache must contain ontology.jsonl and source-index.json")
    role = {"knowledge": "knowledge", "device": "device_knowledge", "workflow": "workflow"}[kind]
    index = json.loads(index_path.read_text(encoding="utf-8"))
    record = _source_record(source, [role], skill_id, note)
    if suite_id:
        record["suite_id"] = suite_id
    index["sources"] = [item for item in index.get("sources", [])
                        if not (item.get("path") == str(source) and item.get("suite_id") == suite_id)] + [record]
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_path = cache / "cache-manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["updated_at"] = _now()
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if skill_id:
        graph = [json.loads(line) for line in graph_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for record in graph:
            entity = record.get("entity", {})
            if entity.get("id") == f"skill:{skill_id}":
                item = {"path": str(source), "kind": kind}
                if note:
                    item["note"] = note
                existing = entity.setdefault("properties", {}).setdefault("maintenance_sources", [])
                existing[:] = [entry for entry in existing if entry.get("path") != str(source)] + [item]
                break
        else:
            raise ValueError(f"unknown skill_id: {skill_id}")
        graph_path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in graph) + "\n", encoding="utf-8")
    return {"cache_dir": str(cache), "source_index": "source-index.json", "path": str(source), "kind": kind}
