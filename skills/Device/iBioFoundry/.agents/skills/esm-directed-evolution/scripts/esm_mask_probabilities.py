#!/usr/bin/env python3
"""Amino-acid probabilities at masked positions of a protein, from a local ESM-2 model (Meta's fair-esm).

Runs on the CPU with the model files of this skill's Python environment (venv/iBioFoundry/esm/models on
FounDryClaw, fetched by venv/build_envs.py); nothing is sent to an online service and no key is needed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

STANDARD_AA = list("ACDEFGHIKLMNPQRSTVWY")
DEFAULT_SPECIAL = ["X", "B", "Z", "U", "O", "-", ".", "<unk>", "<mask>"]
DEFAULT_TOKEN_ORDER = STANDARD_AA + DEFAULT_SPECIAL
RESIDUE_LETTERS = set("ACDEFGHIKLMNPQRSTVWYXBZUO")
MASK = "<mask>"
MAX_RESIDUES = 1022  # ESM-2 was trained on at most 1022 residues (1024 tokens with the start and end tokens)
MODEL_FILES = {
    "esm2-8m": "esm2_t6_8M_UR50D",
    "esm2-35m": "esm2_t12_35M_UR50D",
    "esm2-150m": "esm2_t30_150M_UR50D",
    "esm2-650m": "esm2_t33_650M_UR50D",
    "esm2-3b": "esm2_t36_3B_UR50D",
    "esm2-15b": "esm2_t48_15B_UR50D",
}
# The vocabulary of every ESM-2 model, in its order (fair-esm Alphabet.all_toks); used by --mock only.
ESM2_VOCAB = ["<cls>", "<pad>", "<eos>", "<unk>", "L", "A", "G", "V", "S", "E", "R", "T", "I", "D", "P", "K",
              "Q", "N", "F", "Y", "M", "H", "W", "C", "X", "B", "U", "Z", "O", ".", "-", "<null_1>", "<mask>"]


def fail(message: str) -> None:
    raise SystemExit(f"esm_mask_probabilities: {message}")


def softmax(logits: list[float]) -> list[float]:
    maximum = max(logits)
    exps = [math.exp(value - maximum) for value in logits]
    total = sum(exps)
    return [value / total for value in exps]


# --- input -------------------------------------------------------------------------------------------------

def read_record(path: str, record_id: str | None) -> tuple[str, str]:
    """(id, sequence) of one record of a FASTA or GenBank file (Biopython)."""
    from Bio import SeqIO

    file_format = "genbank" if Path(path).suffix.lower() in {".gb", ".gbk", ".genbank", ".gbff"} else "fasta"
    try:
        records = list(SeqIO.parse(path, file_format))
    except (OSError, ValueError) as exc:
        fail(f"cannot read {path} as {file_format}: {exc}")
    if not records:
        fail(f"no {file_format} records in {path}")
    if record_id:
        matches = [record for record in records if record.id == record_id]
        if not matches:
            fail(f"no record {record_id!r} in {path}; records: {', '.join(record.id for record in records[:20])}")
        record = matches[0]
    else:
        record = records[0]
    return record.id, str(record.seq)


def translate(dna: str) -> str:
    from Bio.Seq import Seq

    cleaned = "".join(dna.split()).upper().replace("U", "T")
    if set(cleaned) - set("ACGTN"):
        fail("--translate needs a DNA/RNA sequence (A, C, G, T/U, N)")
    if len(cleaned) % 3:
        fail(f"the DNA is {len(cleaned)} nt long, not a whole number of codons; give the coding sequence only")
    return str(Seq(cleaned).translate())


def tokens_of(sequence: str) -> list[str]:
    """One token per residue: letters and <mask>. Rejects anything else with a clear message."""
    tokens: list[str] = []
    index = 0
    while index < len(sequence):
        if sequence.startswith(MASK, index):
            tokens.append(MASK)
            index += len(MASK)
            continue
        letter = sequence[index]
        if letter.upper() in RESIDUE_LETTERS:
            tokens.append(letter.upper())
        elif letter == "*":
            fail(f"stop symbol '*' inside the sequence (residue {len(tokens) + 1}); give one protein chain")
        elif letter.isspace() or letter.isdigit() or letter in ">;":
            fail("the sequence contains spaces, digits or a FASTA header; pass only residue letters and <mask>, "
                 "or use --fasta for a file")
        else:
            fail(f"unexpected character {letter!r} at residue {len(tokens) + 1}; residues are "
                 f"{''.join(sorted(RESIDUE_LETTERS))} and masks are written {MASK}")
        index += 1
    return tokens


def prepare(args: argparse.Namespace) -> tuple[list[str], dict[int, str], list[str], str | None]:
    """(tokens with masks, {mask residue position: wild-type residue}, notes, record id)."""
    notes: list[str] = []
    record_id = None
    if args.fasta:
        if args.sequence:
            fail("give --sequence or --fasta, not both")
        record_id, sequence = read_record(args.fasta, args.record)
    elif args.sequence:
        sequence = args.sequence.strip()
    else:
        fail("give --sequence (with <mask>, or a wild type with --positions) or --fasta")
    if args.translate:
        sequence = translate(sequence)
        notes.append("Translated the DNA sequence to protein (standard genetic code).")
    if sequence.endswith("*"):
        sequence = sequence[:-1]
        notes.append("Removed the terminal '*' stop symbol.")
    if not args.translate and len(sequence) >= 30 and set(sequence.upper()) <= set("ACGTUN"):
        notes.append("The sequence contains only A, C, G, T/U and N: if it is DNA, use --translate.")
    tokens = tokens_of(sequence)
    wild_types: dict[int, str] = {}
    if args.positions:
        if MASK in tokens:
            fail("use either <mask> in the sequence or --positions on a wild-type sequence, not both")
        try:
            positions = [int(item) for item in args.positions.replace(";", ",").split(",") if item.strip()]
        except ValueError:
            fail(f"--positions must be 1-based residue numbers such as 45,120, got {args.positions!r}")
        for position in positions:
            if not 1 <= position <= len(tokens):
                fail(f"position {position} is outside the sequence (1-{len(tokens)})")
            wild_types[position] = tokens[position - 1]
            tokens[position - 1] = MASK
    if MASK not in tokens:
        fail("no position to predict: put <mask> in the sequence or pass --positions")
    if len(tokens) > MAX_RESIDUES:
        fail(f"the sequence has {len(tokens)} residues; ESM-2 handles at most {MAX_RESIDUES}. Pass the domain "
             "around the positions of interest")
    return tokens, wild_types, notes, record_id


# --- model ---------------------------------------------------------------------------------------------------

def models_dir(args: argparse.Namespace) -> Path:
    return Path(args.models_dir or os.environ.get("ESM_MODELS_DIR") or Path(sys.prefix) / "models")


def installed_models(folder: Path) -> list[str]:
    names = {path.stem for path in folder.glob("*.pt") if not path.stem.endswith("-contact-regression")}
    short = {file: name for name, file in MODEL_FILES.items()}
    return sorted(short.get(name, name) for name in names)


def model_file(args: argparse.Namespace) -> Path:
    folder = models_dir(args)
    name = MODEL_FILES.get(args.model.lower(), args.model)
    path = folder / f"{name}.pt"
    if not path.is_file():
        installed = installed_models(folder)
        kind = "ESM-1v is not installed here" if args.model.lower().startswith("esm1v") else f"model {args.model} is not installed"
        choice = f"Installed: {', '.join(installed)}; use one of those." if installed else "No model is installed."
        fail(f"{kind} (looked in {folder}). {choice} An administrator can add models in venv/packages.json "
             "(the downloads of iBioFoundry/esm, then venv/build_envs.py).")
    return path


def load_model(path: Path):
    import torch
    import esm

    # fair-esm's own loader calls torch.load with torch's default weights_only=True since torch 2.6, which
    # cannot read these checkpoints; the files are Meta's, checked against their sha256 when downloaded.
    model_data = torch.load(str(path), map_location="cpu", weights_only=False)
    regression = path.with_name(f"{path.stem}-contact-regression.pt")
    regression_data = torch.load(str(regression), map_location="cpu", weights_only=False) if regression.is_file() else None
    model, alphabet = esm.pretrained.load_model_and_alphabet_core(path.stem, model_data, regression_data)
    model.eval()
    return model, alphabet


def masked_logits(model, alphabet, variants: list[list[str]], batch_size: int = 8) -> list[list[list[float]]]:
    """For each variant (tokens with masks), the logits over the vocabulary at each of its masks, in order."""
    import torch

    converter = alphabet.get_batch_converter()
    results: list[list[list[float]]] = []
    for start in range(0, len(variants), batch_size):
        chunk = variants[start:start + batch_size]
        _, _, batch = converter([(str(index), "".join(tokens)) for index, tokens in enumerate(chunk)])
        with torch.no_grad():
            logits = model(batch)["logits"]
        for row in range(len(chunk)):
            where = (batch[row] == alphabet.mask_idx).nonzero(as_tuple=True)[0].tolist()
            results.append([logits[row, index].tolist() for index in where])
    return results


def mock_logits(variants: list[list[str]]) -> list[list[list[float]]]:
    """Deterministic made-up logits, for checking the output format without torch or a model."""
    out = []
    for tokens in variants:
        rows = []
        for index, token in enumerate(tokens):
            if token == MASK:
                seed = hashlib.sha256(f"{''.join(tokens)}:{index}".encode()).digest()
                rows.append([(seed[i % len(seed)] - 128) / 40 for i in range(len(ESM2_VOCAB))])
        out.append(rows)
    return out


# --- output --------------------------------------------------------------------------------------------------

def position_result(mask_index: int, position: int, wild_type: str | None, logits: list[float], vocab: list[str],
                    token_order: list[str], renormalize: bool, top: int) -> dict[str, Any]:
    full = dict(zip(vocab, softmax([float(value) for value in logits])))
    selected = {token: full[token] for token in token_order if token in full}
    mass = sum(selected.values())
    if renormalize:
        if mass <= 0:
            fail("the selected tokens have no probability mass; cannot renormalize")
        selected = {token: probability / mass for token, probability in selected.items()}
    result: dict[str, Any] = {"mask_index": mask_index, "position": position}
    if wild_type:
        result["wild_type"] = wild_type
    result.update(probabilities=selected, selected_probability_mass=mass, renormalized=renormalize)
    ranked = sorted(STANDARD_AA, key=lambda aa: full.get(aa, 0.0), reverse=True)
    best = []
    for aa in ranked[:top]:
        item: dict[str, Any] = {"aa": aa, "probability": selected.get(aa, full.get(aa, 0.0))}
        if wild_type:
            item["mutation"] = f"{wild_type}{position}{aa}"
            if full.get(wild_type, 0) > 0 and full.get(aa, 0) > 0:
                # masked-marginal score: log p(mutant) - log p(wild type) at the masked position
                item["log_ratio_vs_wild_type"] = math.log(full[aa]) - math.log(full[wild_type])
        best.append(item)
    result["top_standard"] = best
    if wild_type and wild_type in full:
        result["wild_type_probability"] = selected.get(wild_type, full[wild_type])
        result["wild_type_rank"] = ranked.index(wild_type) + 1 if wild_type in ranked else None
    return result


def parse_token_order(raw: str | None, standard_only: bool) -> list[str]:
    if raw:
        tokens = [token.strip() for token in raw.split(",") if token.strip()]
        if not tokens:
            fail("--tokens was given but no tokens were parsed")
        return tokens
    return STANDARD_AA if standard_only else DEFAULT_TOKEN_ORDER


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Amino-acid probabilities at masked protein positions from a "
                                                 "local ESM-2 model (no online service, no key).")
    parser.add_argument("--sequence", help="Protein sequence with one or more <mask>, or a wild type with --positions.")
    parser.add_argument("--fasta", help="FASTA or GenBank file (.gb/.gbk) holding the sequence instead of --sequence.")
    parser.add_argument("--record", help="Record id in --fasta (default: the first record).")
    parser.add_argument("--translate", action="store_true", help="The input is DNA/RNA coding sequence: translate it first.")
    parser.add_argument("--positions", help="1-based residues of the wild type to mask, e.g. 45,120.")
    parser.add_argument("--model", default="esm2-35m", help="Installed ESM-2 model: esm2-35m (default), esm2-150m, esm2-650m ...")
    parser.add_argument("--models-dir", help="Folder with the model files (default: models/ of this Python environment).")
    parser.add_argument("--independent", action="store_true",
                        help="With --positions: predict each position with only that one masked (the others keep "
                             "the wild type). Default: all positions masked together in one pass.")
    parser.add_argument("--tokens", help="Comma-separated output tokens (default: 20 amino acids plus ESM's special tokens).")
    parser.add_argument("--standard-only", action="store_true", help="Output only the 20 standard amino acids.")
    parser.add_argument("--renormalize-selected", action="store_true", help="Renormalize over the output tokens so they sum to 1.")
    parser.add_argument("--top", type=int, default=5, help="How many best standard amino acids to list per position.")
    parser.add_argument("--output-json", help="Also write the JSON to this file.")
    parser.add_argument("--mock", action="store_true", help="Made-up logits, no torch or model: checks the output format only.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tokens, wild_types, notes, record_id = prepare(args)
    token_order = parse_token_order(args.tokens, args.standard_only)
    mask_positions = [index + 1 for index, token in enumerate(tokens) if token == MASK]
    if args.independent:
        if not wild_types:
            fail("--independent needs --positions: the other masked positions need their wild-type residues")
        variants = []
        for position in mask_positions:
            variant = list(tokens)
            for other in mask_positions:
                if other != position:
                    variant[other - 1] = wild_types[other]
            variants.append(variant)
    else:
        variants = [tokens]

    if args.mock:
        vocab, engine, model_name = ESM2_VOCAB, "mock (made-up logits; not a model result)", "mock"
        per_variant = mock_logits(variants)
    else:
        path = model_file(args)
        from importlib.metadata import version

        model, alphabet = load_model(path)
        vocab = list(alphabet.all_toks)
        engine = f"fair-esm {version('fair-esm')}, local CPU"
        model_name = args.model.lower() if args.model.lower() in MODEL_FILES else path.stem
        per_variant = masked_logits(model, alphabet, variants)
    logits_by_mask = per_variant[0] if not args.independent else [rows[0] for rows in per_variant]

    available = [token for token in token_order if token in vocab]
    if not available:
        fail("none of the requested output tokens is in the model's vocabulary")
    positions = [position_result(index, position, wild_types.get(position), logits, vocab, available,
                                 args.renormalize_selected, max(args.top, 0))
                 for index, (position, logits) in enumerate(zip(mask_positions, logits_by_mask))]
    output: dict[str, Any] = {
        "model": model_name,
        "engine": engine,
        "sequence": "".join(tokens),
        "masking": "independent" if args.independent else "joint",
        "token_order": available,
        "positions": positions,
    }
    if record_id:
        output["record"] = record_id
    if notes:
        output["notes"] = notes
    text = json.dumps(output, indent=2, ensure_ascii=False)
    if args.output_json:
        Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_json).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
