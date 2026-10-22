# Handoff Notes For Engineers

This package is a prediction wrapper around a trained Graph CGI e50 model. Do not modify or retrain the model as part of ordinary scoring.

## Integration Contract

Input one supported disease, optionally restrict to a subset of known DrugBank IDs, and receive a ranked CSV of fitted candidate drugs. Downstream systems should treat `indication_score` as a ranking score.

## Cold-Start Boundary

Do not pass external SMILES or new compounds into this scoring path. If a future system needs KG-external molecules, implement a separate adaptation module that maps molecular structure to the trained Graph CGI compound representation, then validate it independently.

## Recommended Preflight

```bash
bash verify_handoff.sh
```

Then run one CPU smoke test before integrating with GPU jobs.


## Source Code And Version

Use this GitHub branch for the underlying Graph CGI e50 model implementation:

```text
git@github.com:lulu754022140/KG-drug-efficacy-models.git
branch: feature/cgi-graph-e50-handoff-clean
commit: 69fef47 Prepare Graph CGI e50 handoff
```

The branch was created from the previous `cgi` branch so the old branch remains a rollback point. It adds handoff documentation, an eval script for recovered server runs, and moves lightweight helper code into `primekg_graph_indication_multitoken_cgi_graph` to reduce hidden dependencies on earlier model packages.

Runtime dependencies include PyTorch, DGL, RDKit, pandas, NumPy and scikit-learn. The online Oasis skill uses the existing Python venv at `/home/vipuser/srv/foundryclaw_project/FounDryClaw_Web/venv/Oasis/primekg` (Python 3.10.22, CPU PyTorch); it does not use Conda. DGL is required by inference but is currently missing from that venv, so full verification and scoring remain blocked until DGL is available. The `dyz` environment mentioned in upstream training materials is not the online serving environment.

## Server Paths

Recommended source root:

```text
/slurm/home/yrd/fanlab/zhangjinlu/zjl_desktop/KG/PrimeKG/src
```

Server-side handoff docs:

```text
/slurm/home/yrd/fanlab/zhangjinlu/zjl_desktop/KG/PrimeKG/skill_graph_cgi_e50/docs
```

Recovered-training eval script:

```text
/slurm/home/yrd/fanlab/zhangjinlu/zjl_desktop/KG/PrimeKG/scripts/eval_recover_cgi_only.sh
```

Run `eval_recover_cgi_only.sh` only on a compute/GPU node. It writes `metrics.json`, `val_scored.csv`, `test_scored.csv`, `topk_repetition.json`, and `topk_predictions.csv`.


## If GitHub Access Is Not Available

Use the included source archive instead of private GitHub access:

```text
source_archives/KG-drug-efficacy-models_feature-cgi-graph-e50-handoff-clean_69fef47.zip
```

Unzip it on the target server and set:

```bash
export KG_PROJECT_SRC=/path/to/unzipped/KG-drug-efficacy-models/src
```

The source archive is enough for model class loading. It does not include model weights; keep the full skill package together with `primekg_cgi_graph_graph_only_e50/`.
