"""Generate the three chained Momentum DSL scripts for the 96-mutant E. coli workflow.

Same shape as dh5a-plasmid-construction's generator: intent -> protocol -> step map,
device action bodies copied from device-operation-library, fixed sections copied from
script-assembler. What this one adds is the control structures the reference scripts
actually use -- parallel branches, device locks, wait points, AddWork chaining, and
Acquire/set blocks that sit somewhere other than the top of the process.
"""

import argparse
import csv
import json
import re
from datetime import datetime
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
ROOT = SKILL_DIR.parents[2]
DEVICE_DIR = ROOT / ".agents" / "skills" / "device-operation-library" / "references" / "devices"
ASSEMBLER_DIR = ROOT / ".agents" / "skills" / "script-assembler" / "instructions"
CONTROL_FLOW = ASSEMBLER_DIR / "control-flow.md"

# Only the spreading plates scale with the library size: 96 mutants go onto twelve
# eight-well plates, eight compartments each.
SPREADING_ROLE = "spreading plate"
WELLS_PER_SPREADING_PLATE = 8

# The mutant library lives on one 96-well plate, filled column by column (A1, B1, ... H1,
# A2, ...). Column j is the eight wells that go onto 8Well_Plate_j, which is why the twelve
# plates sit in FreedomEVO nests 1-12 in order. Confirm the direction with the iBioFoundry
# team before a primer plate is laid out from this file.
PLATE_ROWS = "ABCDEFGH"
PLATE_COLUMNS = 12


def load_json_yaml(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def extract_first_fence(path):
    text = Path(path).read_text(encoding="utf-8")
    # The line break is matched explicitly: a \s* here would also swallow the first
    # line's leading tab and the copied section would come out flush left.
    match = re.search(r"```(?:javascript|txt)?[ \t]*\r?\n(.*?)```", text, re.S)
    if not match:
        raise ValueError(f"No fenced code block found in {path}")
    return match.group(1).strip("\n")


def extract_fence_under(path, heading_contains):
    """The first fenced block under the heading whose text contains `heading_contains`.

    Used for the control structures: control-flow.md is the single source of truth for
    `AddWork` and `wait_until`, exactly as the device files are for device actions.
    """
    text = Path(path).read_text(encoding="utf-8")
    for match in re.finditer(r"^#{2,3} (.+?)\s*$", text, re.M):
        if heading_contains not in match.group(1):
            continue
        section = text[match.end():]
        following = re.search(r"^#{2,3} ", section, re.M)
        if following:
            section = section[: following.start()]
        fence = re.search(r"```(?:javascript)?\s*(.*?)```", section, re.S)
        if fence:
            return fence.group(1).strip("\n")
    raise ValueError(f"No fenced block under a heading containing {heading_contains!r} in {path}")


def extract_action_template(reference_device, action, variant=None):
    path = DEVICE_DIR / f"{reference_device}.md"
    text = path.read_text(encoding="utf-8")
    action_match = re.search(rf"^## Action: {re.escape(action)}\s*$", text, re.M)
    if not action_match:
        raise ValueError(f"Action {action!r} not found in {path}")
    section = text[action_match.end():]
    next_action = re.search(r"^## Action: ", section, re.M)
    if next_action:
        section = section[: next_action.start()]
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
    """Set `key` to `value` in a copied template block.

    The replacement is a function rather than a template string: a path value in this
    DSL carries doubled backslashes, and re.subn would eat one level of them if the
    value went through a replacement template.
    """
    pattern = rf"(?<![A-Za-z0-9_])({re.escape(key)}\s*=\s*)'[^']*'"
    new_block, count = re.subn(pattern, lambda match: f"{match.group(1)}'{value}'", block)
    if count == 0:
        raise ValueError(f"Parameter {key!r} not present in template:\n{block}")
    return new_block


def split_header_and_containers(block):
    lines = block.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.endswith(");") or stripped.endswith(")"):
            return lines[: i + 1], lines[i + 1:]
    raise ValueError(f"Could not find parameter block end:\n{block}")


def apply_containers(block, containers):
    header, _ = split_header_and_containers(block)
    if containers is None:
        return block
    if not containers:
        if header[-1].strip().endswith(")") and not header[-1].strip().endswith(");"):
            header[-1] = header[-1] + ";"
        return "\n".join(header)
    if header[-1].strip().endswith(");"):
        header[-1] = header[-1].rstrip()[:-1]
    rendered = [f"\t{item}{';' if i == len(containers) - 1 else ','}"
                for i, item in enumerate(containers)]
    return "\n".join(header + rendered)


def indent(text, levels=2):
    prefix = "\t" * levels
    return "\n".join(prefix + line if line else "" for line in text.splitlines())


def binding_name(binding):
    return binding.split()[0]


# --------------------------------------------------------------------------- scale


def spreading_plates(protocol):
    return [c["name"] for c in protocol["containers"] if c.get("role") == SPREADING_ROLE]


def scale_protocol(protocol, plates):
    """Keep only the first `plates` spreading plates. Protocols without any are untouched,
    so one --spreading-plates value can be passed for a run that generates all three."""
    available = spreading_plates(protocol)
    if plates is None or not available:
        return protocol, frozenset()
    if plates > len(available):
        raise ValueError(
            f"--spreading-plates {plates} is more than the {len(available)} eight-well plates "
            f"{protocol['standard_name']} defines, and FreedomEVO only has nests 1-{len(available)} for them"
        )
    dropped = frozenset(available[plates:])
    kept = [c for c in protocol["containers"] if c["name"] not in dropped]
    return dict(protocol, containers=kept), dropped


def scale_comment(kept, dropped):
    return (
        f"scale: this script acquires {kept} of the {kept + len(dropped)} eight-well spreading "
        f"plates, so it plates {kept * WELLS_PER_SPREADING_PLATE} of the 96 mutants. The device "
        f"method it calls (AI_GYF_Plating.esc) is unchanged and may still expect all twelve "
        f"plates on nests 1-12 - confirm with the iBioFoundry team before running it"
    )


# ------------------------------------------------------------------------- mutants


def plate_wells(count):
    wells = [f"{row}{column}" for column in range(1, PLATE_COLUMNS + 1) for row in PLATE_ROWS]
    if count > len(wells):
        raise ValueError(f"{count} mutants do not fit on one {len(wells)}-well plate")
    return wells[:count]


def write_plate_map(path, mutants):
    """well -> mutant -> spreading plate and compartment. The DSL is positional and cannot
    carry a mutation label, so this file is how the operator knows which primer goes where.
    The plate/compartment columns assume column-major filling; see PLATE_ROWS above."""
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["pcr_well", "mutant", "spreading_plate", "compartment"])
        for index, (well, mutant) in enumerate(zip(plate_wells(len(mutants)), mutants)):
            plate = index // WELLS_PER_SPREADING_PLATE + 1
            writer.writerow([well, mutant, f"8Well_Plate_{plate}",
                             index % WELLS_PER_SPREADING_PLATE + 1])


def load_mutants(args):
    if args.mutants and args.mutants_file:
        raise ValueError("give --mutants or --mutants-file, not both")
    if args.mutants:
        names = args.mutants.split(",")
    elif args.mutants_file:
        names = Path(args.mutants_file).read_text(encoding="utf-8").splitlines()
    else:
        return None
    names = [name.strip() for name in names if name.strip()]
    if not names:
        raise ValueError("no mutant names were given")
    quoted = [name for name in names if "'" in name]
    if quoted:
        raise ValueError(f"mutant names must not contain a single quote: {', '.join(quoted)}")
    return names


# ------------------------------------------------------------------------ renderers


def render_action(step, dropped=frozenset()):
    reference_device = step.get("reference_device", step["device"])
    block = extract_action_template(reference_device, step["action"], step.get("variant"))
    for key, value in step.get("params", {}).items():
        block = replace_param(block, key, value)
    containers = step.get("containers")
    if containers is not None and dropped:
        containers = [item for item in containers if binding_name(item) not in dropped]
    return apply_containers(block, containers)


def render_acquire(names, containers_by_name, levels=2):
    tab = "\t" * levels
    lines = [tab + "Acquire, "]
    for i, name in enumerate(names):
        item = containers_by_name[name]
        suffix = ";" if i == len(names) - 1 else ","
        modifier = item.get("acquire_modifier", "")
        modifier_text = f" {modifier}" if modifier else ""
        status = item.get("acquire_status")
        # Balancing plates and single-use buffer plates carry no workflow state, so they are
        # acquired without a filter. See acquire-and-status.md, exception three.
        where = f" where '{name}.Status==\"{status}\"'" if status else ""
        lines.append(f"{tab}{name}{modifier_text} GetMyOwnContainer{where}{suffix}")
    return "\n".join(lines)


def render_set(assignments, levels=2):
    body = ", ".join(f"{name}.Status = '\"{status}\"'" for name, status in assignments)
    return "\t" * levels + f"set {body};"


def render_comment(text, levels=2):
    return "\t" * levels + f"comment ('{text}') ;"


def render_lock(variable, release, levels=2):
    keyword = "Release" if release else "Acquire"
    return "\t" * levels + f"{keyword}({variable});"


def render_from_control_flow(heading, params, levels=2):
    block = extract_fence_under(CONTROL_FLOW, heading)
    for key, value in params.items():
        block = replace_param(block, key, value)
    return indent(block, levels)


class Renderer:
    def __init__(self, protocol, step_map, dropped=frozenset()):
        self.protocol = protocol
        self.step_map = step_map
        self.dropped = dropped
        self.containers_by_name = {c["name"]: c for c in protocol["containers"]}
        self.acquired = []
        self.set_names = []
        self.used_steps = set()
        self.bound_names = set()
        self.locks = []

    # -- flow entries ------------------------------------------------------
    def entry(self, entry, levels):
        if isinstance(entry, str):
            return self.step(entry, levels)
        if "parallel" in entry:
            return self.parallel(entry["parallel"], levels)
        if "acquire" in entry:
            names = [n for n in entry["acquire"] if n not in self.dropped]
            missing = [n for n in names if n not in self.containers_by_name]
            if missing:
                raise ValueError(f"acquire names not declared in containers: {', '.join(missing)}")
            self.acquired.extend(names)
            return render_acquire(names, self.containers_by_name, levels)
        if "set" in entry:
            assignments = []
            for name in entry["set"]:
                if name in self.dropped:
                    continue
                item = self.containers_by_name[name]
                status = item.get("final_status")
                if not status:
                    raise ValueError(f"{name} is in a set entry but has no final_status")
                assignments.append((name, status))
                self.set_names.append(name)
            return render_set(assignments, levels)
        if "set_status" in entry:
            pairs = [(a["name"], a["status"]) for a in entry["set_status"]
                     if a["name"] not in self.dropped]
            return render_set(pairs, levels)
        if "comment" in entry:
            return render_comment(entry["comment"], levels)
        if "lock" in entry:
            self.locks.append((levels, entry["lock"], "acquire"))
            return render_lock(entry["lock"], False, levels)
        if "unlock" in entry:
            self.locks.append((levels, entry["unlock"], "release"))
            return render_lock(entry["unlock"], True, levels)
        if "wait_until" in entry:
            return render_from_control_flow("wait_until", entry["wait_until"], levels)
        if "add_work" in entry:
            process_name = entry["add_work"]["ProcessName"]
            params = dict(entry["add_work"])
            params.setdefault("SourceName", f"E_{process_name}")
            return render_from_control_flow("AddWork", params, levels)
        raise ValueError(f"Unsupported flow entry: {entry!r}")

    def step(self, step_id, levels):
        if step_id not in self.step_map:
            raise ValueError(f"No step named {step_id!r} in the step map")
        step = self.step_map[step_id]
        if step["type"] != "action":
            raise ValueError(f"Unsupported step type: {step['type']}")
        self.used_steps.add(step_id)
        for binding in step.get("containers") or []:
            name = binding_name(binding)
            if name not in self.dropped:
                self.bound_names.add(name)
        return indent(render_action(step, self.dropped), levels)

    def parallel(self, branches, levels):
        tab = "\t" * levels
        lines = [tab + "parallel", tab + "{"]
        for index, branch in enumerate(branches, start=1):
            lines.append("\t" * (levels + 1) + f"branch // {index} of {len(branches)}")
            lines.append("\t" * (levels + 1) + "{")
            for child in branch:
                lines.append(self.entry(child, levels + 2))
                lines.append("")
            if lines[-1] == "":
                lines.pop()
            lines.append("\t" * (levels + 1) + "}")
        lines.append(tab + "}")
        return "\n".join(lines)

    # -- whole process -----------------------------------------------------
    def process(self, note_extra=""):
        lines = [f"\tprocess [{self.protocol['process_name']}]", "\t{", "\t\t// Process steps"]
        if note_extra:
            lines.append(render_comment(note_extra))
            lines.append("")
        for stage in self.protocol["stages"]:
            if stage.get("comment"):
                lines.append(render_comment(stage["comment"]))
                lines.append("")
            for entry in stage["flow"]:
                lines.append(self.entry(entry, 2))
                lines.append("")
        if lines[-1] == "":
            lines.pop()
        lines.append("\t}")
        self.validate()
        return "\n".join(lines)

    def validate(self):
        name = self.protocol["standard_name"]
        declared = [c["name"] for c in self.protocol["containers"]]
        duplicates = {n for n in self.acquired if self.acquired.count(n) > 1}
        if duplicates:
            raise ValueError(f"{name}: acquired more than once: {', '.join(sorted(duplicates))}")
        never = [n for n in declared if n not in self.acquired]
        if never:
            raise ValueError(f"{name}: declared but never acquired: {', '.join(never)}")
        unacquired = sorted(self.bound_names - set(self.acquired))
        if unacquired:
            raise ValueError(
                f"{name}: used by a device action but never acquired: {', '.join(unacquired)}"
            )
        expected = [c["name"] for c in self.protocol["containers"] if c.get("final_status")]
        missing_set = [n for n in expected if n not in self.set_names]
        if missing_set:
            raise ValueError(f"{name}: has a final_status but no set entry: {', '.join(missing_set)}")
        extra_set = {n for n in self.set_names if self.set_names.count(n) > 1}
        if extra_set:
            raise ValueError(f"{name}: set more than once: {', '.join(sorted(extra_set))}")
        held = {}
        for level, variable, kind in self.locks:
            if kind == "acquire":
                if variable in held:
                    raise ValueError(f"{name}: {variable} acquired twice without a release")
                held[variable] = level
            else:
                if variable not in held:
                    raise ValueError(f"{name}: {variable} released without being acquired")
                if held.pop(variable) != level:
                    raise ValueError(
                        f"{name}: {variable} is acquired and released at different nesting levels"
                    )
        if held:
            raise ValueError(f"{name}: never released: {', '.join(sorted(held))}")
        unused = sorted(set(self.step_map) - self.used_steps)
        if unused:
            print(f"  note: {len(unused)} step(s) in the step map are unused: {', '.join(unused)}")


def render_full_script(process_text):
    sections = [
        extract_first_fence(ASSEMBLER_DIR / "runtime.md"),
        extract_first_fence(ASSEMBLER_DIR / "devices.md"),
        extract_first_fence(ASSEMBLER_DIR / "pools.md"),
        extract_first_fence(ASSEMBLER_DIR / "variables.md"),
        process_text,
    ]
    return "profile [My System]\n{\n" + "\n\n".join(sections) + "\n}\n"


# ------------------------------------------------------------------------- intents


def match_intent(request, intents):
    folded = request.lower()
    best = None
    for intent in intents["intents"]:
        for keyword in intent["keywords"]:
            if keyword.lower() in folded and (best is None or len(keyword) > len(best[0])):
                best = (keyword, intent)
    if best:
        return best[1]
    known = [
        f"  {intent['display_name']}: " + "、".join(intent["keywords"][:4])
        for intent in intents["intents"]
    ]
    raise SystemExit(
        "\n".join([f"没有匹配到实验意图：{request}",
                   "这个技能认得下面这几类请求（每类列出前几个关键词）："] + known)
    )


def load_protocol_bundle(item):
    references = SKILL_DIR / "references"
    protocol = load_json_yaml(references / item["protocol_file"])
    step_map = load_json_yaml(references / item["step_map_file"])["steps"]
    return protocol, step_map


def load_intent_protocols(intent):
    if "protocols" in intent:
        return [load_protocol_bundle(item) for item in intent["protocols"]]
    return [load_protocol_bundle(intent)]


def main():
    parser = argparse.ArgumentParser(
        description="Generate the 96-mutant E. coli Momentum DSL scripts."
    )
    parser.add_argument("--request", default="生成96突变体大肠杆菌质粒构建与检测实验脚本")
    parser.add_argument("--output-dir", default=str(ROOT / "outputs"))
    parser.add_argument("--timestamp", default=None,
                        help="Override timestamp as YYYYMMDD_HHMMSS for deterministic tests.")
    parser.add_argument("--spreading-plates", type=int, default=None,
                        help="How many eight-well plates to acquire in the transformation script. "
                             "Default: all twelve, which is one compartment per mutant. Protocols "
                             "without spreading plates ignore this.")
    parser.add_argument("--mutant-count", type=int, default=None,
                        help="How many mutants this round builds. Only cross-checks --mutants.")
    parser.add_argument("--mutants", default=None,
                        help="Mutant names, comma separated, e.g. D2A,D2S,R61L. Writes a "
                             "well-to-mutant CSV beside the scripts.")
    parser.add_argument("--mutants-file", default=None,
                        help="Mutant names, one per line (instead of --mutants).")
    arguments = parser.parse_args()

    if arguments.spreading_plates is not None and arguments.spreading_plates < 1:
        raise ValueError("--spreading-plates must be at least 1")
    if arguments.mutant_count is not None and arguments.mutant_count < 1:
        raise ValueError("--mutant-count must be at least 1")
    mutants = load_mutants(arguments)
    if arguments.mutant_count is not None and mutants is not None \
            and len(mutants) != arguments.mutant_count:
        raise ValueError(
            f"--mutant-count {arguments.mutant_count} does not match the {len(mutants)} names given"
        )

    intents = load_json_yaml(SKILL_DIR / "references" / "intent-map.yaml")
    intent = match_intent(arguments.request, intents)
    timestamp = arguments.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(arguments.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for protocol, step_map in load_intent_protocols(intent):
        scaled, dropped = scale_protocol(protocol, arguments.spreading_plates)
        note = scale_comment(arguments.spreading_plates, dropped) if dropped else ""
        renderer = Renderer(scaled, step_map, dropped)
        script = render_full_script(renderer.process(note))
        path = output_dir / f"foundry_{scaled['standard_name']}_{timestamp}.txt"
        path.write_text(script, encoding="utf-8", newline="")
        written.append(path)
        print(path)
        if note:
            print(f"  {note}")

    if mutants:
        map_path = output_dir / f"foundry_{timestamp}_platemap.csv"
        write_plate_map(map_path, mutants)
        print(map_path)
        print("  pcr_well -> mutant -> spreading plate/compartment, assuming the 96-well plate "
              "is filled column by column; confirm that direction with the iBioFoundry team")

    if len(written) > 1:
        print(f"{len(written)} scripts written. Import them all before starting the first one: "
              f"each ends with AddWork, which queues the next by its fixed process name.")


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        # A protocol or step-map defect, a bad flag, or a template that no longer carries
        # a parameter this skill overrides. The message says which; a traceback would not.
        raise SystemExit(str(error)) from None
