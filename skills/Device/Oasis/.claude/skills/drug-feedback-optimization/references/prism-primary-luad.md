# Existing PRISM primary LUAD profile

The repository currently contains a historical benchmark implementation at:

- `experiments/prism_primary_luad_autoresearch/`
- `experiments/prism_primary_luad_feedback/`

The Auto-Research evaluator uses 4,684 compounds, a 10% activity-stratified warm start, 10 feedback rounds, a default batch size of 50, and the historical final-round development `NDCG@50` objective. It keeps the base scores frozen and exposes `--rounds` and `--batch-size` in the evaluation entry points.

Use these files as a compatibility profile and evidence source. Do not present an old retained winner as selected under the newer acquisition-curve objective. Re-run candidate strategies under the new batch schedule, primary metric, stability rule, and locked-test procedure before freezing a new strategy version.

When invoking an existing file:

1. inspect its current `--help`;
2. pass the same `--rounds`, `--batch-size`, and `--top-k` to all compared strategies;
3. label outputs with the exact historical or new protocol;
4. keep development search separate from locked-test evaluation;
5. record the command and source hashes in provenance.

The existing evaluator forbids feedback and response columns from candidate features and checks that an acquisition returns the requested number of unique candidates from the pool. Preserve those invariants when generalizing it.
