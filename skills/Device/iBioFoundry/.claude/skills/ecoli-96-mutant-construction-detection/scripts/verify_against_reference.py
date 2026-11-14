#!/usr/bin/env python3
"""Generate the three scripts and prove they still match the machine's own scripts.

`references/source-scripts/` holds the three scripts exported from the iBioFoundry
Momentum profile on 2026-11-12. This script regenerates from the skill's protocol and
step maps, parses both sides, and compares them statement by statement.

Run it after editing anything this skill reads -- the protocol or step maps here, a
device template in device-operation-library, or a fixed section in script-assembler.
A shared template that changes under this skill will show up here as a mismatch rather
than as a script that quietly no longer matches the instrument.

    python verify_against_reference.py
    python verify_against_reference.py --keep <dir>   # leave the generated scripts behind

Line wrapping is not compared: generated bodies are copied from the template blocks,
the references came out of Momentum's exporter. Statement order, device, action,
parameter key/value pairs, container bindings, locks, comments and chaining are.

Exit status is 0 only when the only differences are the ones listed in EXPECTED below.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SOURCES = SKILL_DIR / "references" / "source-scripts"
PAIRS = [
    ("GYF_1_Plasmid_PCR_DpnI.txt", "gyf_1_plasmid_pcr_dpni"),
    ("GYF_2_Ecoli_DNA_transformation.txt", "gyf_2_ecoli_dna_transformation"),
    ("GYF_3_Detect.txt", "gyf_3_detect"),
]
TIMESTAMP = "20261113_120000"

# The deviations this skill makes on purpose. Both are documented in SKILL.md under
# "两处刻意的改动"; anything else is a regression.
EXPECTED = [
    ("02_LYY_PCR_plate_1", "02_LYY_PCR_plate_2"),
    ("02_LYY_PCR_plate_3", "02_LYY_PCR_Plate_3"),
]


# --------------------------------------------------------------------------- parsing
def process_body(path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = next(i for i, l in enumerate(lines) if l.lstrip().startswith("process ["))
    name = re.match(r"\s*process \[(.*)\]", lines[start]).group(1)
    depth, body = 0, []
    for line in lines[start + 1:]:
        stripped = line.strip()
        if stripped == "{":
            depth += 1
            if depth == 1:
                continue
        if stripped == "}":
            depth -= 1
            if depth == 0:
                break
        body.append(line)
    return name, body


def params_of(text):
    return re.findall(r"([A-Za-z0-9_]+)\s*=\s*'([^']*)'", text)


class Parser:
    def __init__(self, lines):
        self.lines, self.i = lines, 0

    def peek(self):
        while self.i < len(self.lines) and not self.lines[self.i].strip():
            self.i += 1
        return self.lines[self.i].strip() if self.i < len(self.lines) else None

    def take(self):
        value = self.peek()
        self.i += 1
        return value

    def until_semicolon(self, first):
        parts = [first]
        while not parts[-1].rstrip().endswith(";"):
            parts.append(self.lines[self.i].strip())
            self.i += 1
        return " ".join(parts)

    def block(self):
        out = []
        while True:
            nxt = self.peek()
            if nxt is None or nxt == "}" or nxt.startswith("branch //"):
                return out
            if nxt.startswith("//"):
                self.take()
                continue
            out.append(self.statement())

    def statement(self):
        line = self.take()
        if line == "parallel":
            assert self.take() == "{"
            branches = []
            while self.peek() != "}":
                assert self.peek().startswith("branch //")
                self.take()
                assert self.take() == "{"
                branches.append(self.block())
                assert self.take() == "}"
            self.take()
            return {"parallel": branches}
        if line.startswith("Acquire("):
            return {"lock": re.match(r"Acquire\((.+?)\)", line).group(1)}
        if line.startswith("Release("):
            return {"unlock": re.match(r"Release\((.+?)\)", line).group(1)}
        if line.startswith("Acquire"):
            payload = self.until_semicolon(line)[len("Acquire,"):].strip().rstrip(";")
            return {"acquire": [b.strip() for b in payload.split(",") if b.strip()]}
        if line.startswith("set "):
            payload = self.until_semicolon(line)[4:].strip().rstrip(";")
            return {"set": re.findall(r"([A-Za-z0-9_]+)\.[Ss]tatus\s*=\s*'\"([^\"]*)\"'", payload)}
        if line.startswith("comment"):
            statement = self.until_semicolon(line)
            return {"comment": re.search(r"comment\s*\('(.*)'\)\s*;", statement, re.S).group(1)}
        if line.startswith("wait_until"):
            return {"wait_until": params_of(self.until_semicolon(line))}
        if line.startswith("AddWork"):
            return {"add_work": params_of(self.until_semicolon(line))}
        match = re.match(r"([A-Za-z0-9_]+) \[([A-Za-z ]+)\]\s*$", line)
        if not match:
            raise ValueError(f"unparsed statement: {line!r}")
        statement = self.until_semicolon(self.take())
        depth = 0
        for index, char in enumerate(statement):
            depth += (char == "(") - (char == ")")
            if depth == 0 and char == ")":
                break
        tail = statement[index + 1:].strip().rstrip(";").strip()
        return {"device": match.group(1), "action": match.group(2),
                "params": params_of(statement[: index + 1]),
                "containers": [b.strip() for b in tail.split(",") if b.strip()] if tail else []}


def flatten(entries, path="", out=None):
    out = [] if out is None else out
    for index, entry in enumerate(entries):
        here = f"{path}{index}"
        if isinstance(entry, dict) and "parallel" in entry:
            out.append((here, {"parallel": len(entry["parallel"])}))
            for number, branch in enumerate(entry["parallel"], start=1):
                flatten(branch, f"{here}.b{number}.", out)
        else:
            out.append((here, entry))
    return out


def canon(statement):
    """Whitespace-insensitive, parameter-order-insensitive form. `.status` is folded to
    `.Status` because Momentum ignores the case and the references mix the two."""
    out = {}
    for key, value in statement.items():
        if key in ("params", "wait_until", "add_work"):
            out[key] = dict(value)
        elif key == "containers":
            out[key] = [" ".join(c.split()) for c in value]
        elif key == "acquire":
            out[key] = [" ".join(c.split()).replace(".status==", ".Status==") for c in value]
        elif key == "set":
            out[key] = [list(pair) for pair in value]
        else:
            out[key] = value
    return out


def apply_expected(text):
    for before, after in EXPECTED:
        text = text.replace(before, after)
    return text


def fixed_sections(path):
    """Everything above `process [`, minus blank and comment lines: the runtime, devices,
    pools and variables blocks that script-assembler says must be copied unchanged."""
    text = path.read_text(encoding="utf-8", errors="replace")
    body = text[: text.index("\tprocess [")]
    return [line.rstrip() for line in body.splitlines()
            if line.strip() and not line.strip().startswith("//")]


def compare(reference, generated):
    ref_name, ref_body = process_body(reference)
    gen_name, gen_body = process_body(generated)
    problems = []
    reference_fixed, generated_fixed = fixed_sections(reference), fixed_sections(generated)
    if reference_fixed != generated_fixed:
        for line_number, (left, right) in enumerate(zip(reference_fixed, generated_fixed), start=1):
            if left != right:
                problems.append(f"fixed section line {line_number}: {left!r} != {right!r}")
        if len(reference_fixed) != len(generated_fixed):
            problems.append(f"fixed sections: {len(reference_fixed)} lines in the reference, "
                            f"{len(generated_fixed)} generated")
    if ref_name != gen_name:
        problems.append(f"process name: {ref_name!r} != {gen_name!r}")
    ref = flatten(Parser(ref_body).block())
    gen = flatten(Parser(gen_body).block())
    if len(ref) != len(gen):
        problems.append(f"statement count: reference {len(ref)}, generated {len(gen)}")
    for (ref_path, ref_statement), (gen_path, gen_statement) in zip(ref, gen):
        left = apply_expected(json.dumps(canon(ref_statement), ensure_ascii=False, sort_keys=True))
        right = json.dumps(canon(gen_statement), ensure_ascii=False, sort_keys=True)
        if ref_path != gen_path or left != right:
            problems.append(f"at {ref_path}:\n    reference {left[:400]}\n    generated {right[:400]}")
    return len(ref), problems


def check_procedure_map():
    """Every code step the natural-language map names must exist, and every step in the
    step maps must be reachable from it -- otherwise a step silently has no description
    and nothing connects it to a sentence of the experimenter's protocol."""
    references = SKILL_DIR / "references"
    procedure = json.loads((references / "procedure-map.yaml").read_text(encoding="utf-8"))
    problems = []
    for entry in procedure["protocols"]:
        name = entry["standard_name"]
        steps = json.loads(
            (references / f"step-map-{name.replace('_', '-')}.yaml").read_text(encoding="utf-8")
        )["steps"]
        named = [step for stage in entry["stages"] for sub in stage["substeps"]
                 for step in sub["code_steps"]]
        unknown = sorted(set(named) - set(steps))
        uncovered = sorted(set(steps) - set(named))
        if unknown:
            problems.append(f"{name}: names steps that do not exist: {', '.join(unknown)}")
        if uncovered:
            problems.append(f"{name}: steps with no description: {', '.join(uncovered)}")
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", help="Write the generated scripts here instead of a temp dir.")
    arguments = parser.parse_args()

    with tempfile.TemporaryDirectory() as temporary:
        out = Path(arguments.keep) if arguments.keep else Path(temporary)
        out.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [sys.executable, "-I", str(Path(__file__).with_name("generate_script.py")),
             "--request", "生成96突变体大肠杆菌质粒构建与检测实验脚本",
             "--output-dir", str(out), "--timestamp", TIMESTAMP],
            capture_output=True, text=True, encoding="utf-8",
        )
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            sys.exit("generation failed")

        failures = 0
        for source, standard_name in PAIRS:
            count, problems = compare(SOURCES / source, out / f"foundry_{standard_name}_{TIMESTAMP}.txt")
            status = "PASS" if not problems else f"FAIL ({len(problems)})"
            print(f"  {status}  {source}  [{count} statements, fixed sections included]")
            for problem in problems:
                print(f"      {problem}")
            failures += bool(problems)

    print()
    map_problems = check_procedure_map()
    for problem in map_problems:
        print(f"  FAIL  procedure-map.yaml: {problem}")
    if not map_problems:
        print("  PASS  procedure-map.yaml describes every step and names no step that is missing")

    print()
    if failures or map_problems:
        sys.exit(f"{failures} script mismatch(es), {len(map_problems)} procedure-map problem(s)")
    print(f"all {len(PAIRS)} scripts match their reference, "
          f"allowing for the {len(EXPECTED)} documented renames")


if __name__ == "__main__":
    main()
