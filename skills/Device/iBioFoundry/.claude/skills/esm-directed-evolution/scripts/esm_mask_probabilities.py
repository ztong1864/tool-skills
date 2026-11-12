#!/usr/bin/env python3
"""Amino-acid substitution scores at chosen positions of a protein, from the ProEngAgent API.

The scoring runs on the ProEngAgent service (`multievolve_api`: ESM-2 650M, wild-type marginals), reached over
HTTP at PROENGAGENT_BASE_URL. Nothing is computed here and no model file is needed: this script sends the
sequence, brings the service's full single-mutant scan back as a CSV, keeps the positions that were asked for,
and prints them in the same shape earlier versions printed (probabilities, log ratio against the wild type and
the wild type's own rank), so the rest of the flow and the reply format are unchanged.

What the numbers are: the service scores every single substitution of the whole protein in one pass over the
wild type and reports `log_ratio_vs_wild_type` directly. The wild type is the 0 reference, so its rank is one
plus the number of substitutions the model finds more likely than it. The probability printed for a position is
the softmax of those scores over the 20 standard amino acids -- a ranking aid within that position, not the
model's absolute token probability, and not comparable with masked-marginal numbers from another service.

Only the standard library is used. Every scoring call also saves the service's scan CSV next to --output-json,
so a registered artifact carries the full scan and not only the positions that were read out.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

SCORING_TOOL = "multievolve_api"
STANDARD_AA = "ACDEFGHIKLMNPQRSTVWY"
MUTATION = re.compile(r"^([A-Z])(\d+)([A-Z])$")
GENBANK_SUFFIXES = {".gb", ".gbk", ".genbank"}
CODONS = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L", "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M", "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S", "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T", "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*", "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K", "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W", "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R", "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def base_url(args: argparse.Namespace) -> str:
    url = (args.base_url or os.environ.get("PROENGAGENT_BASE_URL") or "").strip().rstrip("/")
    if not url:
        fail("the ProEngAgent address is not configured: set PROENGAGENT_BASE_URL (or pass --base-url). "
             "This is an administrator's setting on the server, not something to guess (需要管理员处理).")
    return url


# --- the sequence ------------------------------------------------------------------------------------------

def fasta_records(text: str) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    name, parts = None, []
    for line in text.splitlines():
        if line.startswith(">"):
            if name is not None:
                records.append((name, "".join(parts)))
            name, parts = line[1:].strip(), []
        elif line.strip():
            parts.append(line.strip())
    if name is not None:
        records.append((name, "".join(parts)))
    return records


def genbank_protein(text: str, translate: bool) -> str:
    """The CDS translation of a GenBank record: its /translation if it carries one, else the ORIGIN."""
    if not translate:
        fail("a GenBank file holds DNA: add --translate to score the protein its CDS codes for.")
    found = re.search(r'/translation="([^"]+)"', text, re.S)
    if found:
        return re.sub(r"[^A-Za-z]", "", found.group(1)).upper()
    origin = text.split("ORIGIN", 1)
    if len(origin) < 2:
        fail("this GenBank record has neither a /translation qualifier nor an ORIGIN block to translate.")
    dna = re.sub(r"[^A-Za-z]", "", origin[1]).upper().replace("U", "T")
    protein = []
    for i in range(0, len(dna) - 2, 3):
        aa = CODONS.get(dna[i:i + 3])
        if aa is None:
            fail(f"the ORIGIN block has an unreadable codon at base {i + 1}.")
        if aa == "*":
            break
        protein.append(aa)
    return "".join(protein)


def read_sequence(args: argparse.Namespace) -> tuple[str, str]:
    """(sequence, where it came from). Parsing happens here: the remote engine takes amino acids only."""
    if args.fasta and args.sequence:
        fail("give --sequence or --fasta, not both")
    if args.fasta:
        path = Path(args.fasta)
        if not path.is_file():
            fail(f"no such file: {path}")
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix.lower() in GENBANK_SUFFIXES:
            return genbank_protein(text, args.translate), f"{path.name} (GenBank CDS)"
        records = fasta_records(text)
        if not records:
            fail(f"{path.name} holds no FASTA record (a line starting with '>').")
        if args.record:
            wanted = [r for r in records if r[0].split()[0] == args.record or r[0] == args.record]
            if not wanted:
                names = ", ".join(r[0].split()[0] for r in records)
                fail(f"no record named {args.record!r} in {path.name}; it holds: {names}")
            name, seq = wanted[0]
        else:
            name, seq = records[0]
        return seq.upper(), f"{path.name} record {name.split()[0]}"
    if args.sequence:
        raw = args.sequence.strip()
        if raw.startswith(">") or any(c.isspace() for c in raw) or any(c.isdigit() for c in raw):
            fail("--sequence takes plain amino acids: use --fasta for a file with a header, line breaks or "
                 "numbering.")
        return raw.upper(), "--sequence"
    fail("give --sequence or --fasta")
    raise AssertionError  # unreachable, keeps type checkers quiet


def check_sequence(seq: str) -> None:
    if not seq:
        fail("the sequence is empty")
    if "<MASK>" in seq.upper():
        fail("this engine scores substitutions against the wild type, so it needs the residue that is there: "
             "give the wild-type sequence and name the residues with --positions instead of writing <mask>.")
    odd = sorted({c for c in seq if c not in STANDARD_AA})
    if odd:
        fail(f"the sequence has characters the scoring engine does not take: {''.join(odd)}. "
             "Give the protein as the 20 standard amino acids (translate a CDS with --translate).")


def parse_positions(raw: str, seq: str) -> list[int]:
    try:
        positions = [int(p) for p in raw.replace(" ", "").split(",") if p]
    except ValueError:
        fail(f"--positions must be 1-based residue numbers such as 45,120, got {raw!r}")
        raise AssertionError
    if not positions:
        fail("--positions is empty")
    out_of_range = [p for p in positions if p < 1 or p > len(seq)]
    if out_of_range:
        fail(f"these positions are outside the sequence (1-{len(seq)}): "
             f"{', '.join(str(p) for p in out_of_range)}")
    return sorted(dict.fromkeys(positions))


# --- the service -------------------------------------------------------------------------------------------

def get_json(url: str, timeout: float) -> Any:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}),
                                    timeout=timeout) as answer:
            return json.loads(answer.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        fail(f"the ProEngAgent service answered HTTP {exc.code} for {url}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        fail(f"the ProEngAgent service at {url} could not be reached ({exc}). Report that it needs an "
             "administrator (需要管理员处理); do not start a local model or call another service instead.")
    raise AssertionError


def call_tool(base: str, name: str, inputs: dict[str, Any], timeout: float) -> dict[str, Any]:
    body = json.dumps({"inputs": inputs}).encode("utf-8")
    request = urllib.request.Request(f"{base}/api/general/tool/{name}", data=body,
                                     headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as answer:
            payload = json.loads(answer.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        fail(f"the ProEngAgent service refused the {name} call with HTTP {exc.code}: {detail}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        fail(f"the {name} call to {base} did not finish ({exc}). A whole-protein scan takes seconds, so this "
             "is the service or the network: report that it needs an administrator (需要管理员处理).")
    if not payload.get("success") or payload.get("error"):
        fail(f"the {name} call failed: {payload.get('error') or payload}")
    output = payload.get("output")
    if not isinstance(output, dict):
        fail(f"the {name} call returned no result object: {str(payload)[:300]}")
    if output.get("success") is False:
        fail(f"the {name} call reported failure: {output.get('error') or output}")
    output["_downloads"] = payload.get("downloads") or []
    return output


def catalog_entry(base: str, timeout: float) -> dict[str, Any]:
    tools = get_json(f"{base}/api/general/tools", timeout).get("tools") or []
    for tool in tools:
        if tool.get("name") == SCORING_TOOL:
            tool["_n_tools"] = len(tools)
            return tool
    fail(f"the service at {base} does not list {SCORING_TOOL} among its {len(tools)} tools, so scoring is not "
         "available there (需要管理员处理).")
    raise AssertionError


def fetch_scan(base: str, output: dict[str, Any], destination: Path, timeout: float) -> str:
    """Bring the scan CSV here, so the artifact carries the full scan and not only the chosen positions."""
    remote = str(output.get("output_file") or "")
    url = None
    for item in output.get("_downloads", []):
        if str(item.get("name", "")).endswith(".csv") and item.get("url"):
            url = f"{base}{item['url']}"
            break
    if url is None and remote:
        url = f"{base}/api/upload/file?path={urllib.parse.quote(remote)}"
    if url is None:
        fail("the scoring call returned no scan file to read")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as answer:
            text = answer.read().decode("utf-8", errors="replace")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        # The catalog's own read_file tool is the other way in; use it before giving up.
        read = call_tool(base, "read_file", {"file_path": remote, "max_chars": 4_000_000}, timeout)
        text = str(read.get("content") or "")
        if not text:
            fail(f"the scan file could not be read ({exc})")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    return text


def scan_scores(csv_text: str) -> dict[int, dict[str, Any]]:
    """{position: {"wild_type": aa, "scores": {substitution: log ratio}}} from the service's scan CSV."""
    lines = [l for l in csv_text.splitlines() if l.strip()]
    if not lines:
        fail("the scan file is empty")
    header = [h.strip() for h in lines[0].split(",")]
    try:
        name_at = header.index("mutations")
    except ValueError:
        fail(f"the scan file does not look like a mutation scan; its header is: {lines[0][:200]}")
        raise AssertionError
    score_at = header.index("average_model_logratio") if "average_model_logratio" in header else \
        header.index("model_1_logratio") if "model_1_logratio" in header else -1
    if score_at < 0:
        fail(f"the scan file has no log-ratio column; its header is: {lines[0][:200]}")
    found: dict[int, dict[str, Any]] = {}
    for line in lines[1:]:
        cells = line.split(",")
        if len(cells) <= max(name_at, score_at):
            continue
        parsed = MUTATION.match(cells[name_at].strip())
        if not parsed:
            continue
        wild, position, mutant = parsed.group(1), int(parsed.group(2)), parsed.group(3)
        try:
            score = float(cells[score_at])
        except ValueError:
            continue
        site = found.setdefault(position, {"wild_type": wild, "scores": {}})
        site["scores"][mutant] = score
    if not found:
        fail("the scan file holds no readable mutation rows")
    return found


def read_out(position: int, site: dict[str, Any], seq: str, top: int) -> dict[str, Any]:
    wild = site["wild_type"]
    if wild != seq[position - 1]:
        fail(f"the scan calls residue {position} {wild} while the sequence has {seq[position - 1]}: the "
             "numbering does not match. Check that the sequence sent is the one the positions refer to.")
    scored = [(wild, 0.0)] + [(aa, s) for aa, s in site["scores"].items() if aa != wild]
    partition = sum(math.exp(s) for _, s in scored)
    probability = {aa: math.exp(s) / partition for aa, s in scored}
    ranked = sorted(scored, key=lambda pair: (-pair[1], pair[0]))
    return {
        "position": position,
        "wild_type": wild,
        "substitutions_scored": len(scored) - 1,
        "probabilities": {aa: probability[aa] for aa, _ in sorted(scored)},
        "selected_probability_mass": 1.0,
        "renormalized": True,
        "top_standard": [{"aa": aa, "probability": probability[aa], "mutation": f"{wild}{position}{aa}",
                          "log_ratio_vs_wild_type": score} for aa, score in ranked[:max(top, 1)]],
        "wild_type_probability": probability[wild],
        "wild_type_rank": 1 + sum(1 for aa, s in scored if aa != wild and s > 0.0),
    }


# --- main --------------------------------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Amino-acid substitution scores at chosen protein positions, "
                                                 "from the ProEngAgent service (ESM-2 650M, wild-type "
                                                 "marginals). No local model.")
    parser.add_argument("--sequence", help="Protein sequence (the 20 standard amino acids, no header).")
    parser.add_argument("--fasta", help="FASTA or GenBank file holding the sequence.")
    parser.add_argument("--record", help="With --fasta: which record, by its first name field.")
    parser.add_argument("--translate", action="store_true", help="With a GenBank file: score the protein its "
                                                                 "CDS codes for.")
    parser.add_argument("--positions", help="1-based residues to read out, e.g. 2,61,62. Without it every "
                                            "position of the scan is reported.")
    parser.add_argument("--top", type=int, default=5, help="How many amino acids to list per position "
                                                           "(default 5; the wild type is one of them).")
    parser.add_argument("--output-json", help="Write the whole answer to this file (register it as the step's "
                                              "output). The service's scan CSV is saved beside it.")
    parser.add_argument("--scan-csv", help="Where to save the service's full scan CSV (default: beside "
                                           "--output-json, else the working directory).")
    parser.add_argument("--base-url", help="The ProEngAgent service (default: PROENGAGENT_BASE_URL).")
    parser.add_argument("--timeout", type=float, default=600.0, help="Seconds to wait for the service.")
    parser.add_argument("--health", action="store_true", help="Print whether the service is reachable and "
                                                              "which scoring tool and model it offers.")
    parser.add_argument("--list-models", action="store_true", help="Same as --health: the service decides the "
                                                                   "model, and its catalog entry names it.")
    # Flags from the local-service version. They are accepted so an old command still runs and explains
    # itself, or refused where the remote engine cannot honour them.
    parser.add_argument("--independent", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--standard-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--renormalize-selected", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--model", help=argparse.SUPPRESS)
    parser.add_argument("--tokens", help=argparse.SUPPRESS)
    parser.add_argument("--models-dir", help=argparse.SUPPRESS)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.models_dir:
        fail("--models-dir is gone: there is no local model. The ProEngAgent service holds it; --health says "
             "which one it reports.")
    if args.model:
        fail("--model is gone: the ProEngAgent service decides the model (its catalog entry names it, see "
             "--health). Ask an administrator to change the service if another model is needed.")
    if args.tokens:
        fail("--tokens is gone: the scan covers the 20 standard amino acids only.")
    base = base_url(args)

    if args.health or args.list_models:
        entry = catalog_entry(base, min(args.timeout, 30.0))
        print(json.dumps({
            "service": base,
            "status": "ok",
            "tools_offered": entry.pop("_n_tools", None),
            "scoring_tool": entry.get("name"),
            "model": entry.get("description"),
            "reliability": entry.get("reliability"),
            "speed": entry.get("speed"),
            "requirements": entry.get("requirements"),
            "note": "The service holds the model; this skill keeps no weights and no local service.",
        }, ensure_ascii=False, indent=1))
        return

    sequence, origin = read_sequence(args)
    check_sequence(sequence)
    wanted = parse_positions(args.positions, sequence) if args.positions else None

    started = time.monotonic()
    output = call_tool(base, SCORING_TOOL, {"sequence": sequence}, args.timeout)
    round_trip = time.monotonic() - started

    if args.scan_csv:
        csv_path = Path(args.scan_csv)
    elif args.output_json:
        stem = Path(args.output_json)
        csv_path = stem.with_name(f"{stem.stem}_scan.csv")
    else:
        csv_path = Path("proengagent_scan.csv")
    csv_text = fetch_scan(base, output, csv_path, args.timeout)
    sites = scan_scores(csv_text)

    if wanted is None:
        wanted = sorted(sites)
    missing = [p for p in wanted if p not in sites]
    if missing:
        fail(f"the scan has no rows for position(s) {', '.join(str(p) for p in missing)}; it covers "
             f"{min(sites)}-{max(sites)}.")

    answer = {
        "service": base,
        "engine": f"ProEngAgent {SCORING_TOOL}, wild-type marginals, remote",
        "model": output.get("model") or "ESM-2 650M (as the service's catalog entry states)",
        "sequence": sequence,
        "sequence_from": origin,
        "masking": "wild-type marginals: one pass over the wild type, no per-position masking",
        "probability_meaning": "softmax of the log ratios over the 20 standard amino acids at that position; "
                               "a ranking aid, not the model's absolute token probability",
        "token_order": list(STANDARD_AA),
        "positions": [read_out(p, sites[p], sequence, args.top) for p in wanted],
        "n_mutations_scored": output.get("n_mutations_scored"),
        "scan_csv": str(csv_path),
        "remote_scan_file": output.get("output_file"),
        "elapsed_s": output.get("elapsed_sec"),
        "round_trip_s": round(round_trip, 3),
    }
    if args.independent or args.standard_only or args.renormalize_selected:
        answer["flags_ignored"] = ("--independent, --standard-only and --renormalize-selected describe the "
                                  "old local masked-marginal engine; this engine always scores every single "
                                  "substitution in one wild-type pass over the 20 standard amino acids.")

    text = json.dumps(answer, ensure_ascii=False, indent=1)
    if args.output_json:
        path = Path(args.output_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {path} and {csv_path}")
    print(text)


if __name__ == "__main__":
    main()
