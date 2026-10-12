# Auto-Research and evaluation

Auto-Research is an offline strategy-discovery process. The agent proposes bounded strategy changes, the evaluator runs them on fixed data and splits, and the campaign retains only candidates supported by the predefined metric and stability rules. It does not control an ongoing real experiment.

## Level 1: partial historical feedback

Eligibility: at least `max(100, 2 * default_batch_size)` valid observations from the same task semantics.

Search:

- feedback estimator family and bounded hyperparameters;
- allowed feature subsets;
- fixed or round-dependent fusion weights.

Use out-of-fold predictions. Primary metric: OOF `NDCG@20`. Secondary metric: true activity among the OOF top 20. Limit V1 to 15 evaluated candidates. Level 1 does not claim to optimize acquisition behavior because labels outside the historical observations are unknown.

## Level 2: fully labeled retrospective pool

Eligibility: a broad labeled pool containing at least twice the total simulated acquisition budget. Use fixed development splits and one locked test partition.

Primary metric: mean area under the oracle-normalized cumulative gain curve across the full simulated budget, named `acquisition_ncg_auc_mean`.

For budget `B`, define:

`NCG@B = cumulative activity acquired by the strategy through B / cumulative activity of the oracle top-B compounds`.

Report at least:

- `acquisition_ncg_auc_mean`
- final `NCG@budget`
- cumulative activity of acquired top-20 compounds
- per-batch mean activity, labeled descriptive
- batch efficiency against the oracle top-k among the remaining pool
- fixed-holdout `NDCG@50`
- acquired base-rank distribution
- structural coverage and redundancy

Search may include model, features, fusion schedule, warm start, and acquisition. A V1 budget of 30 trials can allocate 8 to model/features, 7 to fusion, 10 to warm start/acquisition, and 5 to joint refinement. Stop after eight consecutive non-improving trials.

Candidate acquisition settings may include top/explore splits `50/0`, `48/2`, `45/5`, `40/10`, and `35/15`; shortlist sizes `100`, `150`, and `250`; round-dependent fusion; and Morgan-similarity deduplication. Keep greedy selection as a mandatory baseline.

## Stable winner

Call a strategy a stable winner only when all are true:

- mean primary-metric improvement over the frozen baseline is greater than zero;
- paired bootstrap 95% confidence-interval lower bound is greater than zero;
- improvement is positive on at least 70% of seeds or tasks;
- late-round performance shows no material degradation;
- interface, leakage, determinism, replay, dependency, and artifact-hash checks pass.

If mean improvement is positive but the confidence interval crosses zero, label it exploratory. Do not replace the primary frozen winner with an exploratory candidate.

## Freeze and publish

After development selection, evaluate the final winner once on the locked test. Save:

- `strategy.py`
- `strategy_config.json`
- `metrics_summary.json`
- `selection_report.md`
- `provenance.json`

The report must describe the baseline, search space, number of trials, primary and auxiliary metrics, per-seed/task results, failures, selection reason, and protocol limitations. Bind the artifact directory to a unique immutable `strategy_version`.
