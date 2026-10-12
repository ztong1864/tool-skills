# Model-agnostic AutoResearch protocol

## Command contract

All configured commands are arrays of arguments and run with `shell=False` in the configured workspace.

Available placeholders:

- `{python}`: the interpreter running AutoResearch Core
- `{config}`: absolute config path
- `{config_dir}`: directory containing the config
- `{workspace}`: resolved workspace
- `{run_dir}`: persistent run directory
- `{trial_dir}`: current baseline or candidate directory
- `{proposal_path}`: current proposal JSON path; empty for baseline

A command may print logs before its result. The final JSON object in stdout is treated as the machine result.

## Proposer input

The proposer receives one JSON object on stdin containing:

- goal and metric direction;
- baseline and current-best metrics;
- completed and remaining budget;
- consecutive non-improvements and patience;
- evaluated candidate IDs;
- ten recent results;
- configured proposal schema and search guidance.

It returns either a proposal with a unique `candidate_id`, or:

```json
{"action": "stop", "reason": "No justified candidate remains."}
```

## Evaluator output

The baseline and trial evaluator must return the configured metric key. It may also return:

```json
{
  "status": "ok",
  "metric_name": 0.75,
  "artifacts": [
    "/absolute/path/to/strategy.py",
    "/absolute/path/to/summary.json"
  ]
}
```

Relative artifact paths are resolved against the trial directory first and the workspace second.

## State and outputs

The core writes:

- `config.snapshot.json`
- `state.json`
- `results.jsonl`
- `results.tsv`
- `trials/000_baseline/`
- `trials/NNN_candidate_id/`
- `frozen/version/`

Failed trial commands are recorded, consume budget, and increment consecutive non-improvements.

## Provider adapters

The core has no provider SDK dependency. A provider adapter may call:

- an OpenAI-compatible API;
- Anthropic Claude;
- Google Gemini;
- a local Ollama or vLLM endpoint;
- a CLI coding agent;
- an internal service;
- a deterministic search algorithm.

Keep API keys in environment variables owned by the adapter. Return only the proposal JSON to stdout.
