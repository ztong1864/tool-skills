#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
bash score.sh 43789 examples/score_43789_top100.csv python auto 100
