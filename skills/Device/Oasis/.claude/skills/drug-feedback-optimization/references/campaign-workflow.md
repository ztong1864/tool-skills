# Real campaign workflow

## Campaign states

Track each candidate as one of:

- `available`
- `recommended`
- `pending`
- `observed`
- `retryable_failure`
- `failed`
- `excluded`

Only `available` candidates may enter a new recommendation. A recommendation reserves the candidate immediately. Ingestion converts it to `observed`, `retryable_failure`, or `failed` according to the submitted result.

## Initialization

1. Validate the task config and candidate table.
2. Freeze and hash inputs, feature definitions, score transform, software environment, and strategy version.
3. Create an empty feedback ledger and append-only event log.
4. Select the first batch from the frozen base ranking. This batch counts against the total campaign budget.
5. Write `round_001/next_candidates.csv`, `summary.json`, and `report.md`.

## Feedback ingestion

Ingest each CSV once using a content hash or stable batch ID. Refuse conflicting re-ingestion. Preserve the original input as `round_NNN/input_feedback.csv`.

- Valid observations enter cumulative model training.
- Compound failures affect realized campaign utility but do not become artificial activity labels.
- Technical failures may be retried once. After the allowed retry they become unavailable.

## Next-batch recommendation

Resolve the effective batch count before fitting and scoring. Resolve the score that actually drives recommendation as follows:

```text
if valid_feedback < strategy.min_feedback_to_fit:
    ranking_score = base_score
    ranking_source = "base_only"
else:
    ranking_score = final_score
    ranking_source = "base_feedback_fusion"
```

When valid feedback reaches the threshold, calculating `final_score` without using it for recommendation is invalid. The default greedy acquisition must rank eligible candidates by descending `ranking_score`. A frozen exploration or diversity rule may select candidates outside the pure score order, but it must still use `ranking_score` for exploitation and record the deviation in `selection_reason`.

At or above the threshold:

1. fit the frozen feedback strategy on all valid cumulative observations;
2. score every eligible candidate;
3. combine base and feedback scores using the frozen strategy config;
4. set `ranking_score=final_score` and apply the frozen acquisition rule and structural deduplication;
5. verify the output count, uniqueness, eligibility, score finiteness, ranking source, score ordering for greedy selections, and deterministic tie-breaking;
6. reserve the selected candidates and write all round outputs atomically.

Recommended round outputs:

- `model_summary.json`
- `scored_candidates.csv`
- `next_candidates.csv`
- `summary.json`
- `report.md`

`next_candidates.csv` should contain `candidate_id`, `name`, `base_score`, `feedback_score`, `final_score`, `ranking_score`, `ranking_source`, `base_rank`, `final_rank`, `selection_reason`, `structure_group_id`, `strategy_version`, and `round`.

## Campaign close

Write:

- `campaign_summary.json`
- `all_recommendations.csv`
- `activity_curve.csv`
- final `report.md`

Report cumulative observed utility, discovered high-activity compounds, failed/pending counts, structural coverage, base-rank distribution, strategy version, and all effective per-round batch sizes.

## Reproducibility checks

Before returning a recommendation:

- replay the same state and verify identical IDs and ordering;
- verify that `ranking_source` matches the valid-feedback threshold and that `ranking_score` equals the declared source column;
- for greedy selections, verify descending `ranking_score`; for exploration or diversity selections, verify an explicit `selection_reason`;
- verify no selected candidate appears in any unavailable state;
- verify total recommended count does not exceed the frozen campaign budget;
- verify the strategy code and config hashes match the campaign manifest;
- record requested versus effective batch size and any cap.
