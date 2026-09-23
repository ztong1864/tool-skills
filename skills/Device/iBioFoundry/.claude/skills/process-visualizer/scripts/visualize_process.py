#!/usr/bin/env python
"""Generate a Mermaid flowchart from a Momentum process block."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


PROCESS_RE = re.compile(
    r"\bprocess\s+(?:\[([^\]]+)\]|([A-Za-z_][A-Za-z0-9_]*))\s*\{"
)
DEVICE_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\[([^\]]+)\]", re.M)
PARAM_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*'([^']*)'")
CONTAINER_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\s+in\s+'([^']+)')?"
    r".*?(GetMyOwnContainer|HoldLid|UseExistingContainer|AcquireContainer)?\s*$",
    re.M,
)
BRANCH_RE = re.compile(r"\bbranch\b[^{]*\{", re.I)
PARALLEL_RE = re.compile(r"\bparallel\s*\{", re.I)


def strip_line_comments(text: str) -> str:
    return "\n".join(line.split("//", 1)[0].rstrip() for line in text.splitlines())


def process_match_name(match: re.Match[str]) -> str:
    return match.group(1) or match.group(2) or "process"


def find_matching_brace(text: str, open_index: int) -> int:
    depth = 0
    quote: str | None = None
    i = open_index
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError("Could not find closing brace for process block.")


def extract_process(text: str, process_name: str | None = None) -> tuple[str, str]:
    matches = list(PROCESS_RE.finditer(text))
    if not matches:
        raise ValueError("No process block found.")

    selected = None
    if process_name:
        for match in matches:
            if process_match_name(match) == process_name:
                selected = match
                break
        if selected is None:
            names = ", ".join(process_match_name(match) for match in matches)
            raise ValueError(f"Process '{process_name}' not found. Available: {names}")
    else:
        selected = matches[0]

    open_index = text.find("{", selected.start())
    close_index = find_matching_brace(text, open_index)
    return process_match_name(selected), text[open_index + 1 : close_index]


def find_statement_end(text: str, start: int) -> int:
    paren_depth = 0
    quote: str | None = None

    for i in range(start, len(text)):
        ch = text[i]
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "(":
            paren_depth += 1
        elif ch == ")":
            paren_depth = max(0, paren_depth - 1)
        elif ch == ";" and paren_depth == 0:
            return i
    return len(text)


def parse_sequence(process_body: str) -> list:
    items = []
    index = 0
    while index < len(process_body):
        while index < len(process_body) and process_body[index].isspace():
            index += 1
        if index >= len(process_body):
            break

        parallel_match = PARALLEL_RE.match(process_body, index)
        if parallel_match:
            open_index = process_body.find("{", parallel_match.start())
            close_index = find_matching_brace(process_body, open_index)
            items.append({"parallel": parse_parallel(process_body[open_index + 1 : close_index])})
            index = close_index + 1
            continue

        end = find_statement_end(process_body, index)
        statement = process_body[index:end].strip()
        if statement:
            items.append(statement)
        index = end + 1
    return items


def parse_parallel(parallel_body: str) -> list[list]:
    branches = []
    index = 0
    while index < len(parallel_body):
        match = BRANCH_RE.search(parallel_body, index)
        if not match:
            break
        open_index = parallel_body.find("{", match.start())
        close_index = find_matching_brace(parallel_body, open_index)
        branches.append(parse_sequence(parallel_body[open_index + 1 : close_index]))
        index = close_index + 1
    return branches


def clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip().rstrip(",")).strip()


def mermaid_escape(text: str) -> str:
    text = text.replace("\\", "\\\\")
    text = text.replace('"', "&quot;")
    text = text.replace("[", "&#91;").replace("]", "&#93;")
    text = text.replace("{", "&#123;").replace("}", "&#125;")
    return text


def compact_value(value: str, max_len: int = 68) -> str:
    value = clean_line(value)
    if len(value) <= max_len:
        return value
    return value[: max_len - 3] + "..."


def summarize_containers(statement: str) -> list[str]:
    lines: list[str] = []
    for match in CONTAINER_RE.finditer(statement):
        container, location, verb = match.groups()
        raw = match.group(0)
        if "[" in raw or "=" in raw or not verb:
            continue
        label = container
        if location:
            label += f" @ {location}"
        if verb != "GetMyOwnContainer":
            label += f" ({verb})"
        if label not in lines:
            lines.append(label)
    return lines


def summarize_statement(statement: str) -> tuple[str, str]:
    lines = [clean_line(line) for line in statement.splitlines() if clean_line(line)]
    first = lines[0] if lines else "Step"

    if first.startswith("Acquire"):
        detail = [line for line in lines[1:] if line]
        label_lines = ["Acquire"] + [compact_value(line) for line in detail[:3]]
        if len(detail) > 3:
            label_lines.append(f"+ {len(detail) - 3} more")
        return "acquire", "<br/>".join(label_lines)

    if first.startswith("set "):
        return "set", "<br/>".join(["Set", compact_value(first[4:])])

    if first.startswith("comment"):
        match = re.search(r"comment\s*\('([\s\S]*?)'\)", statement)
        comment = match.group(1) if match else first
        return "comment", "<br/>".join(["Comment", compact_value(comment)])

    device_match = DEVICE_RE.search(statement)
    if device_match:
        device, action = device_match.groups()
        label_lines = [f"{device}: {action}"]
        params = dict(PARAM_RE.findall(statement))
        for key in ("ProtocolName", "MethodName", "ScriptName", "Duration"):
            if params.get(key):
                label_lines.append(f"{key}: {compact_value(params[key], 48)}")
        label_lines.extend(compact_value(line, 58) for line in summarize_containers(statement)[:4])
        return "device", "<br/>".join(label_lines)

    return "step", compact_value(first)


def node_shape(node_id: str, label: str) -> str:
    return f'{node_id}["{mermaid_escape(label)}"]'


def render_items(
    output: list[str],
    items: list,
    previous_ids: list[str],
    counter: dict[str, int],
) -> list[str]:
    for item in items:
        counter["node"] += 1
        if isinstance(item, str):
            _, label = summarize_statement(item)
            node_id = f"step{counter['node']}"
            output.append(f"    {node_shape(node_id, label)}")
            for previous_id in previous_ids:
                output.append(f"    {previous_id} --> {node_id}")
            previous_ids = [node_id]
            continue

        split_id = f"parallel{counter['node']}"
        join_id = f"join{counter['node']}"
        output.append(f'    {split_id}{{"Parallel"}}')
        for previous_id in previous_ids:
            output.append(f"    {previous_id} --> {split_id}")

        branch_ends = []
        for branch_index, branch_items in enumerate(item.get("parallel", []), start=1):
            branch_id = f"{split_id}_branch{branch_index}"
            output.append(f'    {branch_id}["Branch {branch_index}"]')
            output.append(f"    {split_id} --> {branch_id}")
            branch_ends.extend(render_items(output, branch_items, [branch_id], counter))

        output.append(f'    {join_id}{{"Join"}}')
        for branch_end in branch_ends or [split_id]:
            output.append(f"    {branch_end} --> {join_id}")
        previous_ids = [join_id]
    return previous_ids


def build_mermaid(process_name: str, items: list) -> str:
    output = [
        f"%% Process: {process_name}",
        "flowchart TD",
        '    start(("Start"))',
    ]
    previous_ids = render_items(output, items, ["start"], {"node": 0})
    output.append('    finish(("End"))')
    for previous_id in previous_ids:
        output.append(f"    {previous_id} --> finish")
    return "\n".join(output) + "\n"


def default_output_path(input_path: Path) -> Path:
    return input_path.with_suffix(".mmd")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Mermaid flowchart from a Momentum process block."
    )
    parser.add_argument("script", type=Path, help="Momentum .txt script path")
    parser.add_argument("--process", help="Process name to visualize; defaults to first process")
    parser.add_argument("--output", type=Path, help="Output .mmd path")
    parser.add_argument("--stdout", action="store_true", help="Print Mermaid to stdout")
    args = parser.parse_args()

    text = args.script.read_text(encoding="utf-8-sig")
    text = strip_line_comments(text)
    process_name, process_body = extract_process(text, args.process)
    items = parse_sequence(process_body)
    mermaid = build_mermaid(process_name, items)

    if args.stdout:
        print(mermaid, end="")

    output_path = args.output or default_output_path(args.script)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(mermaid, encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
