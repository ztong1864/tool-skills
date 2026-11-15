# Task configuration and data contract

Use one JSON task config per disease-specific experimental program. Copy `../assets/task_config.template.json` and replace paths and identifiers. Do not hard-code LUAD in reusable code.

## Required task fields

- `task_name`, `dataset_name`, `disease_name`
- `candidate_table`
- `candidate_id_col`, `target_col`, `higher_is_better`
- `base_score_col`, `smiles_col`, `feature_columns_json`
- `activity_score_transform.version`
- `campaign.num_rounds`, `campaign.batch_size`, `campaign.max_total_candidates`
- `strategy.strategy_version`

Record the upstream model and its version in optional `base_model`, and the origin/version of precomputed features in `feature_generation_version`; the real campaign manifest freezes these values when supplied.

`split_manifest` is required for simulated evaluation and optional for a real campaign.

## Batch configuration

```json
{
  "campaign": {
    "num_rounds": 10,
    "batch_size": 50,
    "round_batch_sizes": {"1": 40, "2": 60},
    "allow_runtime_batch_size_override": true,
    "max_total_candidates": 500
  }
}
```

`round_batch_sizes` is optional. Keys are one-based round numbers encoded as strings. A runtime `--batch-size` applies to the current round only and must be recorded in that round's manifest. The effective count is capped by both the unspent campaign budget and the number of eligible candidates.

Changing the schedule during an offline comparison invalidates direct comparison to runs made under the old schedule. Keep one frozen schedule across all compared strategies.

## Candidate table

Required columns:

- candidate ID, using the configured `candidate_id_col`;
- frozen base score;
- canonical or canonically resolvable SMILES when `structure_group_id` is absent;
- every frozen feature named in `feature_columns_json`.

The real campaign CLI consumes precomputed numeric features. It does not create Morgan fingerprints or other molecular descriptors. If the upstream score column is named `indication_score`, set `base_score_col` accordingly. For fixed-weight fusion, values must be finite and in `[0,1]`; when the upstream score does not meet that contract, transform it before initialization and record the transformation in the task provenance.

Optional columns include `name` and a precomputed `structure_group_id`. Candidate IDs must be unique. Reject missing or nonfinite base scores and feature values unless the strategy explicitly defines a frozen imputation rule.

Derive `structure_group_id` from canonical SMILES when it is absent. The V1 default allows one candidate per structure group in a campaign unless the task config explicitly permits otherwise.

The implemented CLI uses a supplied `structure_group_id`, or RDKit to canonicalize a single SMILES per row when the column is absent. For drug pairs, prepare pair-level features and a stable pair-level `structure_group_id` upstream; the SMILES column may then be absent. The CLI does not construct pair features from two SMILES. A feedback model using only `base_score` as a feature can recalibrate the base ranking but cannot learn pair-specific molecular relationships absent from its features.

## Feedback CSV

Required columns:

- `candidate_id`
- `activity_score`

Supported optional columns:

- `result_status`: `valid`, `compound_failure`, or `technical_failure`
- `failure_reason`
- `raw_value`
- `round`, `batch_id`, `source`, `notes`

Treat a missing `result_status` as `valid` only when `activity_score` is present and numeric. Reject duplicate IDs within an input file, unknown IDs, scores outside `[0, 1]`, and feedback that conflicts with an already finalized observation.

The external assay pipeline owns raw-value transformation, replicate aggregation, and image-to-number conversion. Store `raw_value` for traceability when available, but fit the feedback model only on valid `activity_score` values.

## Frozen artifacts

At initialization, create:

- `campaign_manifest.json`
- `candidate_pool_snapshot.csv`
- a copy of the task config
- the strategy-version artifacts or immutable reference plus hashes
- `feedback_ledger.csv`
- `events.jsonl`
- `feedback_inputs/` for exact copies of ingested feedback files

Run `python scripts/campaign.py init-campaign --config task_config.json --campaign-dir campaign_dir` to create these artifacts and the first recommendation. The campaign directory must not already exist. Config paths to input files are resolved relative to the original task config file before freezing snapshots.

The manifest records the base model identity, candidate-table hash, feature-list hash, activity-transform version, strategy version, campaign budget, and batch schedule.
