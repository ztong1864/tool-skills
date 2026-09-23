import argparse
import json
import re
from datetime import datetime
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
ROOT = SKILL_DIR.parents[2]
DEVICE_DIR = ROOT / ".agents" / "skills" / "device-operation-library" / "references" / "devices"
ASSEMBLER_DIR = ROOT / ".agents" / "skills" / "script-assembler" / "instructions"


def load_json_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_first_fence(path):
    text = Path(path).read_text(encoding="utf-8")
    match = re.search(r"```(?:javascript|txt)?\s*(.*?)```", text, re.S)
    if not match:
        raise ValueError(f"No fenced code block found in {path}")
    return match.group(1).strip("\n")


def extract_action_template(reference_device, action, variant=None):
    path = DEVICE_DIR / f"{reference_device}.md"
    text = path.read_text(encoding="utf-8")
    action_match = re.search(rf"^## Action: {re.escape(action)}\s*$", text, re.M)
    if not action_match:
        raise ValueError(f"Action {action!r} not found in {path}")
    section = text[action_match.end():]
    next_action = re.search(r"^## Action: ", section, re.M)
    if next_action:
        section = section[:next_action.start()]
    if variant:
        variant_match = re.search(rf"^### {re.escape(variant)}\s*$", section, re.M)
        if not variant_match:
            raise ValueError(f"Variant {variant!r} not found for {action!r} in {path}")
        section = section[variant_match.end():]
    fence = re.search(r"```(?:javascript)?\s*(.*?)```", section, re.S)
    if not fence:
        raise ValueError(f"No template block for {reference_device} {action}")
    return fence.group(1).strip("\n")


def replace_param(block, key, value):
    pattern = rf"(?<![A-Za-z0-9_])({re.escape(key)}\s*=\s*)'[^']*'"
    new_block, count = re.subn(pattern, rf"\1'{value}'", block)
    if count == 0:
        raise ValueError(f"Parameter {key!r} not present in template:\n{block}")
    return new_block


def split_header_and_containers(block):
    lines = block.splitlines()
    last_param = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.endswith(");") or stripped.endswith(")"):
            last_param = i
            break
    if last_param is None:
        raise ValueError(f"Could not find parameter block end:\n{block}")
    return lines[: last_param + 1], lines[last_param + 1 :]


def apply_containers(block, containers):
    header, old_containers = split_header_and_containers(block)
    if containers is None:
        return block
    if not containers:
        if header[-1].strip().endswith(")") and not header[-1].strip().endswith(");"):
            header[-1] = header[-1] + ";"
        return "\n".join(header)
    rendered = []
    for i, container in enumerate(containers):
        suffix = ";" if i == len(containers) - 1 else ","
        rendered.append(f"\t{container}{suffix}")
    return "\n".join(header + rendered)


def render_action(step):
    reference_device = step.get("reference_device", step["device"])
    block = extract_action_template(reference_device, step["action"], step.get("variant"))
    for key, value in step.get("params", {}).items():
        block = replace_param(block, key, value)
    return apply_containers(block, step.get("containers"))


def indent(text, levels=2):
    prefix = "\t" * levels
    return "\n".join(prefix + line if line else "" for line in text.splitlines())


def render_step(step_id, step_map, levels=2):
    step = step_map[step_id]
    if step["type"] == "action":
        return indent(render_action(step), levels)
    raise ValueError(f"Unsupported step type: {step['type']}")


def render_parallel(branches, step_map, levels=2):
    lines = ["\t" * levels + "parallel", "\t" * levels + "{"]
    for idx, branch in enumerate(branches, start=1):
        lines.append("\t" * (levels + 1) + f"branch // {idx} of {len(branches)}")
        lines.append("\t" * (levels + 1) + "{")
        for child in branch:
            lines.append(render_step(child, step_map, levels + 2))
            lines.append("")
        if lines[-1] == "":
            lines.pop()
        lines.append("\t" * (levels + 1) + "}")
    lines.append("\t" * levels + "}")
    return "\n".join(lines)


def render_flow_entry(entry, step_map, levels=2):
    if isinstance(entry, str):
        return render_step(entry, step_map, levels)
    if isinstance(entry, dict) and "parallel" in entry:
        return render_parallel(entry["parallel"], step_map, levels)
    raise ValueError(f"Unsupported protocol flow entry: {entry!r}")


def match_intent(request, intents):
    folded = request.lower()
    best_match = None
    for intent in intents["intents"]:
        for keyword in intent["keywords"]:
            if keyword.lower() in folded:
                if best_match is None or len(keyword) > len(best_match[0]):
                    best_match = (keyword, intent)
    if best_match:
        return best_match[1]
    raise ValueError(f"No DH5a experiment intent matched request: {request}")


def load_protocol_bundle(intent):
    references = SKILL_DIR / "references"
    protocol_file = intent.get("protocol_file", "protocol.yaml")
    step_map_file = intent.get("step_map_file", "step-map.yaml")
    protocol = load_json_yaml(references / protocol_file)
    step_map = load_json_yaml(references / step_map_file)["steps"]
    return protocol, step_map


def load_intent_protocols(intent):
    if "protocols" not in intent:
        return [load_protocol_bundle(intent)]
    return [load_protocol_bundle(item) for item in intent["protocols"]]


def render_acquire(containers):
    lines = ["\t\t// Process steps", "\t\tAcquire, "]
    for i, item in enumerate(containers):
        suffix = ";" if i == len(containers) - 1 else ","
        name = item["name"]
        status = item.get("acquire_status", "New")
        modifier = item.get("acquire_modifier", "")
        modifier_text = f" {modifier}" if modifier else ""
        lines.append(f"\t\t{name}{modifier_text} GetMyOwnContainer where '{name}.Status==\"{status}\"'{suffix}")
    return "\n".join(lines)


def render_status(containers, selected_names=None):
    assignments = []
    for item in containers:
        if selected_names is not None and item["name"] not in selected_names:
            continue
        if item.get("initial_set") is False:
            continue
        name = item["name"]
        final_status = item.get("final_status")
        if final_status is None:
            role = item.get("role", "")
            final_status = "used" if "tips" in role or "consumable" in role else "Completed"
        assignments.append(f"{name}.Status = '\"{final_status}\"'")
    return "\t\tset " + ", ".join(assignments) + ";"


def render_status_blocks(protocol):
    groups = protocol.get("status_groups")
    if not groups:
        return [render_status(protocol["containers"])]
    return [render_status(protocol["containers"], set(group)) for group in groups]


def render_process(process_name, protocol, step_map):
    lines = [f"\tprocess [{process_name}]", "\t{"]
    lines.append(render_acquire(protocol["containers"]))
    lines.append("")
    for status_block in render_status_blocks(protocol):
        lines.append(status_block)
        lines.append("")
    note = protocol.get("process_note", "")
    if note:
        lines.append(f"\t\tcomment ('{note}') ;")
        lines.append("")
    for stage in protocol["stages"]:
        lines.append(f"\t\tcomment ('{stage['comment']}') ;")
        lines.append("")
        for entry in stage.get("flow", stage.get("steps", [])):
            lines.append(render_flow_entry(entry, step_map, 2))
            lines.append("")
    if lines[-1] == "":
        lines.pop()
    lines.append("\t}")
    return "\n".join(lines)


def render_full_script(process_text):
    sections = [
        extract_first_fence(ASSEMBLER_DIR / "runtime.md"),
        extract_first_fence(ASSEMBLER_DIR / "devices.md"),
        extract_first_fence(ASSEMBLER_DIR / "pools.md"),
        extract_first_fence(ASSEMBLER_DIR / "variables.md"),
        process_text,
    ]
    body = "\n\n".join(sections)
    return "profile [My System]\n{\n" + body + "\n}\n"


def main():
    parser = argparse.ArgumentParser(description="Generate DH5a Momentum DSL experiment scripts.")
    parser.add_argument("--request", default="生成质粒构建实验脚本")
    parser.add_argument("--output-dir", default=str(ROOT / "outputs"))
    parser.add_argument("--timestamp", default=None, help="Override timestamp as YYYYMMDD_HHMMSS for deterministic tests.")
    args = parser.parse_args()

    intents = load_json_yaml(SKILL_DIR / "references" / "intent-map.yaml")
    intent = match_intent(args.request, intents)
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for protocol, step_map in load_intent_protocols(intent):
        process_name = f"foundry_{protocol['standard_name']}_{timestamp}"
        script = render_full_script(render_process(process_name, protocol, step_map))
        output_path = output_dir / f"{process_name}.txt"
        output_path.write_text(script, encoding="utf-8")
        print(output_path)


if __name__ == "__main__":
    main()
