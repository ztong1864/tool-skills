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
- canonical or canonically resolvable SMILES;
- every frozen feature named in `feature_columns_json`.

Optional columns include `name` and a precomputed `structure_group_id`. Candidate IDs must be unique. Reject missing or nonfinite base scores and feature values unless the strategy explicitly defines a frozen imputation rule.

Derive `structure_group_id` from canonical SMILES when it is absent. The V1 default allows one candidate per structure group in a campaign unless the task config explicitly permits otherwise.

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

The manifest records the base model identity, candidate-table hash, feature-list hash, activity-transform version, strategy version, campaign budget, and batch schedule.
