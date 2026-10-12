# PRISM primary LUAD smoke test bundle

This folder is a portable offline test fixture for the `drug-feedback-optimization` skill.

## Contents

- `base_scored_oracle.csv`: 4,684 unique compounds, frozen base scores, 268 model features, and retrospective `activity_score` labels.
- `feature_columns.json`: the exact 268 feature columns exposed to the feedback model.
- `split_manifest.json`: fixed development, warm-start, acquisition-pool, and locked-test IDs for seeds 42-51.
- `strategy.py`: frozen RandomForest feedback strategy used in the verified smoke run.
- `protocol.py` and `run_dev_eval.py`: bundled evaluator.
- `run_smoke.py`: portable wrapper with configurable rounds and batch size.
- `expected_smoke_summary.json`: result from the verified 2-round, batch-size-17 run.
- `checksums.sha256`: file-integrity hashes.

The CSV includes retrospective labels for offline evaluation. It must not be passed to an online recommender as unobserved candidate feedback.

## Install dependencies

```bash
python -m pip install -r requirements-smoke.txt
```

## Reproduce the verified smoke run

Run this command inside this folder:

```bash
python run_smoke.py --rounds 2 --batch-size 17 --top-k 17
```

Outputs are written to `smoke_output/`. A successful run contains 10 seeds, rounds 0-2, and exactly 17 acquired rows in each active round.

## Change the number selected each round

For example, select 35 compounds per round:

```bash
python run_smoke.py --rounds 2 --batch-size 35 --top-k 35
```

Use the same rounds, batch size, top-k, splits, and total budget for every strategy in a formal comparison.


## Auto-Research integration

This fixture supports two interfaces:

1. `autoresearch_backend.py` for direct domain-specific `init`, `trial`, `status`, and `freeze` commands.
2. The separately bundled `autoresearch-core` for a model-agnostic JSON loop.

Run the generic smoke loop from this directory:

```bash
python ../../../autoresearch-core/scripts/autoresearch_core.py validate-config --config generic_autoresearch_config.smoke.json
python ../../../autoresearch-core/scripts/autoresearch_core.py loop --config generic_autoresearch_config.smoke.json --run-dir generic-autoresearch-run
python ../../../autoresearch-core/scripts/autoresearch_core.py freeze --run-dir generic-autoresearch-run --version prism_luad_feedback_v1
```

`generic_catalog_proposer.py` is a deterministic test proposer. It verifies proposal, evaluation, selection, state tracking, and freezing without calling a model API. For a hosted or local model, replace `proposer.command` in `generic_autoresearch_config.full.json` with an adapter that reads context JSON from stdin and returns proposal JSON on stdout.

Use `run_acquisition_eval.py` for the fixed `acquisition_ncg_auc_mean` metric and `guard_autoresearch.py` to protect frozen inputs.
