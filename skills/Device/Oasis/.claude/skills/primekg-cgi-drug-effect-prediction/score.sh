#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -lt 2 || "$#" -gt 5 ]]; then
  echo "Usage: bash score.sh <disease_id_or_exact_name> <output_csv> [python_bin] [device] [top_k]" >&2
  echo "Example: bash score.sh \"diabetic retinopathy\" output_scores.csv python auto 100" >&2
  exit 1
fi

DISEASE_QUERY="$1"
OUTPUT_CSV="$2"
PYTHON_BIN="${3:-python}"
DEVICE="${4:-auto}"
TOP_K="${5:-0}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUNDLE_DIR="${BUNDLE_DIR:-${SCRIPT_DIR}/primekg_cgi_graph_graph_only_e50/train}"
PREPARED_DIR="${PREPARED_DIR:-${SCRIPT_DIR}/primekg_cgi_graph_graph_only_e50/prepared}"
KG_PROJECT_SRC="${KG_PROJECT_SRC:-${SCRIPT_DIR}/model_source/src}"

if [[ ! -d "${KG_PROJECT_SRC}" ]]; then
  echo "[score] 模型源码目录不存在：${KG_PROJECT_SRC}" >&2
  echo "[score] 请保留随包 model_source/src，或用 KG_PROJECT_SRC 指向其它源码 src 目录。" >&2
  exit 2
fi

PYTHONPATH="${SCRIPT_DIR}/src:${KG_PROJECT_SRC}:${PYTHONPATH:-}" "${PYTHON_BIN}" -m primekg_cgi_graph_delivery.cli score \
  --bundle-dir "${BUNDLE_DIR}" \
  --prepared-dir "${PREPARED_DIR}" \
  --disease "${DISEASE_QUERY}" \
  --output "${OUTPUT_CSV}" \
  --device "${DEVICE}" \
  --top-k "${TOP_K}"
