#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODEL_ROOT="${MODEL_ROOT:-${SCRIPT_DIR}/primekg_cgi_graph_graph_only_e50}"
TRAIN_DIR="${MODEL_ROOT}/train"
PREPARED_DIR="${MODEL_ROOT}/prepared"
EVAL_DIR="${MODEL_ROOT}/eval"
PYTHON_BIN="${PYTHON_BIN:-python3}"

required_files=(
  "${SCRIPT_DIR}/SKILL.md"
  "${SCRIPT_DIR}/README.md"
  "${SCRIPT_DIR}/environment.yml"
  "${SCRIPT_DIR}/manifest.json"
  "${SCRIPT_DIR}/score.sh"
  "${SCRIPT_DIR}/model_source/src/primekg_graph_indication_multitoken_cgi_graph/__init__.py"
  "${SCRIPT_DIR}/model_source/src/primekg_graph_indication_multitoken_cgi_graph/model.py"
  "${SCRIPT_DIR}/src/primekg_cgi_graph_delivery/cli.py"
  "${SCRIPT_DIR}/src/primekg_cgi_graph_delivery/inference.py"
  "${TRAIN_DIR}/best_bundle.pt"
  "${TRAIN_DIR}/bundle.pt"
  "${TRAIN_DIR}/best_test_drug_embeddings.pt"
  "${TRAIN_DIR}/best_val_drug_embeddings.pt"
  "${TRAIN_DIR}/early_stop_summary.json"
  "${PREPARED_DIR}/candidate_pool.csv"
  "${PREPARED_DIR}/disease_catalog.csv"
  "${PREPARED_DIR}/drug_perturbation_edges.csv"
  "${PREPARED_DIR}/drug_protein_edges.csv"
  "${PREPARED_DIR}/prepare_summary.json"
  "${EVAL_DIR}/metrics.json"
)

for path in "${required_files[@]}"; do
  if [[ ! -f "${path}" ]]; then
    echo "[verify_handoff] missing required file: ${path}" >&2
    exit 2
  fi
done

"${PYTHON_BIN}" - <<'PYCHECK' "${SCRIPT_DIR}"
from pathlib import Path
import csv
import importlib.util
import json
import sys

root = Path(sys.argv[1])
required_modules = ['numpy', 'pandas', 'torch', 'dgl', 'rdkit']
missing_modules = [name for name in required_modules if importlib.util.find_spec(name) is None]
if missing_modules:
    raise SystemExit('[verify_handoff] missing Python modules: ' + ', '.join(missing_modules))
print('[verify_handoff] python=', sys.executable)
print('[verify_handoff] required_modules=', ','.join(required_modules))

model = root / 'primekg_cgi_graph_graph_only_e50'
with (model / 'prepared' / 'candidate_pool.csv').open(newline='', encoding='utf-8') as f:
    rows = sum(1 for _ in csv.DictReader(f))
if rows != 6945:
    raise SystemExit(f'[verify_handoff] candidate_pool rows expected 6945, got {rows}')
summary = json.loads((model / 'prepared' / 'prepare_summary.json').read_text(encoding='utf-8'))
metrics = json.loads((model / 'eval' / 'metrics.json').read_text(encoding='utf-8'))
manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
if summary.get('candidate_drugs') != 6945:
    raise SystemExit('[verify_handoff] prepare_summary candidate_drugs mismatch')
if 'metrics' not in metrics or 'indication_test_mrr' not in metrics['metrics']:
    raise SystemExit('[verify_handoff] eval metrics missing indication_test_mrr')
if manifest.get('model_name') != 'primekg_cgi_graph_graph_only_e50':
    raise SystemExit('[verify_handoff] manifest model_name mismatch')
print('[verify_handoff] ok')
print('[verify_handoff] candidate_pool_rows=', rows)
print('[verify_handoff] test_mrr=', metrics['metrics']['indication_test_mrr'])
PYCHECK
