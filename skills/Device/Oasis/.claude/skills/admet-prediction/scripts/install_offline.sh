#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WHEELHOUSE="${WHEELHOUSE:-}"

if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
  echo "ERROR: bundled wheel manifest is for Linux x86-64 only" >&2
  exit 1
fi
if [[ -z "$WHEELHOUSE" || ! -d "$WHEELHOUSE" ]]; then
  echo "ERROR: set WHEELHOUSE to the directory containing the 68 verified wheels" >&2
  exit 1
fi

(
  cd "$WHEELHOUSE"
  sha256sum -c "$SKILL_DIR/wheels_sha256.txt"
)

python -m pip install --no-index --find-links="$WHEELHOUSE" admet-ai==1.4.0
python - <<'PY'
import importlib.metadata as metadata
for name in ("admet-ai", "chemprop", "torch", "rdkit", "numpy", "pandas"):
    print(f"{name}=={metadata.version(name)}")
PY
