#!/usr/bin/env python3
"""Call BioLM ESM masked prediction and emit amino-acid probability vectors."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.error
import urllib.request
from typing import Any


STANDARD_AA = list("ACDEFGHIKLMNPQRSTVWY")
DEFAULT_SPECIAL = ["X", "B", "Z", "U", "O", "-", ".", "<unk>", "<mask>"]
DEFAULT_TOKEN_ORDER = STANDARD_AA + DEFAULT_SPECIAL
DEFAULT_SECRET_FILES = [
    os.path.join(".claude", "secrets", "biolm.env"),
    ".biolm.env",
]


MOCK_RESPONSE = {
    "results": [
        {
            "sequence_index": 0,
            "sequence_tokens": ["M", "K", "T", "<mask>", "F", "V"],
            "vocab_tokens": DEFAULT_TOKEN_ORDER + ["<pad>", "<cls>", "<eos>"],
            "logits": [[
                0.5, 0.1, -0.4, 0.2, 0.0,
                0.7, -0.8, 0.3, 0.6, 1.3,
                0.9, -0.2, 0.4, 0.2, 0.8,
                0.1, -0.1, 1.1, -0.6, -0.9,
                -1.0, -1.2, -1.3, -1.4, -1.5,
                -1.6, -1.7, -1.8, -1.9, -2.0,
                -2.1, -2.2
            ]],
        }
    ]
}


def softmax(logits: list[float]) -> list[float]:
    if not logits:
        return []
    maximum = max(logits)
    exps = [math.exp(value - maximum) for value in logits]
    total = sum(exps)
    return [value / total for value in exps]


def read_api_key_file(path: str) -> str | None:
    if not path or not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                if key.strip() == "BIOLM_API_KEY":
                    return value.strip().strip('"').strip("'")
            else:
                return line
    return None


def resolve_api_key(cli_api_key: str | None, api_key_file: str | None) -> str | None:
    if cli_api_key:
        return cli_api_key
    env_api_key = os.environ.get("BIOLM_API_KEY")
    if env_api_key:
        return env_api_key

    candidate_files = []
    env_file = os.environ.get("BIOLM_API_KEY_FILE")
    if api_key_file:
        candidate_files.append(api_key_file)
    if env_file:
        candidate_files.append(env_file)
    candidate_files.extend(DEFAULT_SECRET_FILES)

    for path in candidate_files:
        api_key = read_api_key_file(path)
        if api_key:
            return api_key
    return None


def call_biolm(
    sequence: str,
    model: str,
    api_key: str,
    base_url: str,
    timeout: float,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/api/v3/{model}/predict/"
    payload = json.dumps({"items": [{"sequence": sequence}]}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"BioLM HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"BioLM request failed: {exc}") from exc


def parse_token_order(raw_tokens: str | None, include_special: bool) -> list[str]:
    if raw_tokens:
        tokens = [token.strip() for token in raw_tokens.split(",") if token.strip()]
        if not tokens:
            raise ValueError("--tokens was provided but no tokens were parsed")
        return tokens
    if include_special:
        return DEFAULT_TOKEN_ORDER
    return STANDARD_AA


def sanitize_sequence(sequence: str) -> tuple[str, list[str]]:
    notes = []
    cleaned = sequence.strip()
    if cleaned.endswith("*"):
        cleaned = cleaned[:-1]
        notes.append("Removed terminal '*' stop symbol before BioLM submission.")
    return cleaned, notes


def format_esm1v_result(
    result: dict[str, Any],
    sequence: str,
    model: str,
    token_order: list[str],
) -> dict[str, Any]:
    model_outputs = [
        value for key, value in result.items()
        if key.startswith("esm1v-") and isinstance(value, list)
    ]
    if not model_outputs:
        raise ValueError("ESM-1v response did not contain esm1v-* model outputs")

    scores_by_token: dict[str, list[float]] = {}
    for output in model_outputs:
        for item in output:
            if not isinstance(item, dict):
                continue
            token = str(item.get("token_str", ""))
            if token not in token_order:
                continue
            score = item.get("score")
            if score is None:
                continue
            scores_by_token.setdefault(token, []).append(float(score))

    probabilities = {}
    for token in token_order:
        scores = scores_by_token.get(token)
        if scores:
            probabilities[token] = sum(scores) / len(scores)

    if not probabilities:
        raise ValueError("No requested amino acid tokens were found in the ESM-1v response")

    return {
        "model": model,
        "sequence": sequence,
        "token_order": list(probabilities.keys()),
        "positions": [
            {
                "mask_index": 0,
                "probabilities": probabilities,
                "selected_probability_mass": sum(probabilities.values()),
                "aggregation": "mean_across_esm1v_submodels",
            }
        ],
    }


def format_result(
    api_response: dict[str, Any],
    sequence: str,
    model: str,
    token_order: list[str],
    renormalize_selected: bool,
) -> dict[str, Any]:
    results = api_response.get("results")
    if not isinstance(results, list) or not results:
        raise ValueError("BioLM response did not contain a non-empty results array")

    result = results[0]
    if isinstance(result, dict) and any(key.startswith("esm1v-") for key in result):
        return format_esm1v_result(
            result=result,
            sequence=sequence,
            model=model,
            token_order=token_order,
        )

    vocab_tokens = result.get("vocab_tokens")
    logits_by_mask = result.get("logits")
    if not isinstance(vocab_tokens, list) or not isinstance(logits_by_mask, list):
        raise ValueError("BioLM result must contain vocab_tokens and logits arrays")

    vocab_index = {str(token): index for index, token in enumerate(vocab_tokens)}
    available_tokens = [token for token in token_order if token in vocab_index]
    if not available_tokens:
        raise ValueError("None of the requested output tokens appeared in vocab_tokens")

    positions = []
    for mask_index, logits in enumerate(logits_by_mask):
        if not isinstance(logits, list) or len(logits) != len(vocab_tokens):
            raise ValueError(f"logits[{mask_index}] length does not match vocab_tokens")

        full_probabilities = softmax([float(value) for value in logits])
        selected = {
            token: full_probabilities[vocab_index[token]]
            for token in available_tokens
        }
        selected_mass = sum(selected.values())

        if renormalize_selected:
            if selected_mass <= 0:
                raise ValueError("Selected probability mass is zero; cannot renormalize")
            selected = {
                token: probability / selected_mass
                for token, probability in selected.items()
            }

        positions.append({
            "mask_index": mask_index,
            "probabilities": selected,
            "selected_probability_mass": selected_mass,
            "renormalized": renormalize_selected,
        })

    return {
        "model": model,
        "sequence": sequence,
        "token_order": available_tokens,
        "positions": positions,
        "raw_sequence_tokens": result.get("sequence_tokens"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Predict masked amino acid probabilities with BioLM ESM models."
    )
    parser.add_argument("--sequence", help="Protein sequence containing one or more <mask> tokens.")
    parser.add_argument("--model", default="esm2-35m", help="BioLM model name, e.g. esm2-35m.")
    parser.add_argument("--api-key", help="BioLM API token. Prefer env/file storage for normal Agent use.")
    parser.add_argument("--api-key-file", help="Path to a file containing BIOLM_API_KEY=... or a raw token.")
    parser.add_argument("--base-url", default="https://biolm.ai", help="BioLM API base URL.")
    parser.add_argument("--timeout", type=float, default=60.0, help="Request timeout in seconds.")
    parser.add_argument("--tokens", help="Comma-separated output token order. Defaults to 20 AAs plus selected special tokens.")
    parser.add_argument("--standard-only", action="store_true", help="Only output the 20 standard amino acids.")
    parser.add_argument("--renormalize-selected", action="store_true", help="Renormalize probabilities over selected output tokens.")
    parser.add_argument("--output-json", help="Optional path to write JSON output.")
    parser.add_argument("--mock", action="store_true", help="Use bundled mock response instead of calling BioLM.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    sequence, notes = sanitize_sequence(args.sequence or "MKT<mask>FV")
    if "<mask>" not in sequence:
        raise SystemExit("Input sequence must contain at least one literal <mask> token.")

    token_order = parse_token_order(args.tokens, include_special=not args.standard_only)
    if args.mock:
        response = MOCK_RESPONSE
    else:
        api_key = resolve_api_key(args.api_key, args.api_key_file)
        if not api_key:
            raise SystemExit(
                "BioLM API key not found. Set BIOLM_API_KEY, pass --api-key-file, "
                "or create .claude/secrets/biolm.env with BIOLM_API_KEY=..."
            )
        response = call_biolm(
            sequence=sequence,
            model=args.model,
            api_key=api_key,
            base_url=args.base_url,
            timeout=args.timeout,
        )

    output = format_result(
        api_response=response,
        sequence=sequence,
        model=args.model,
        token_order=token_order,
        renormalize_selected=args.renormalize_selected,
    )
    if notes:
        output["notes"] = notes
    text = json.dumps(output, indent=2, ensure_ascii=False)
    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
