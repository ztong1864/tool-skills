# Provider adapter guide

AutoResearch Core does not import a model SDK. It launches the configured proposer command, writes one context JSON object to its standard input, and expects one proposal JSON object on standard output.

## Minimal adapter shape

```python
import json
import sys

context = json.load(sys.stdin)

# Call any model, agent, search algorithm, or human queue here.
# Keep credentials in environment variables.
proposal = {
    "candidate_id": "unique_candidate_001",
    "parameter_a": 1,
    "rationale": "Why this candidate may improve the measured metric."
}

print(json.dumps(proposal))
```

Point `proposer.command` at that wrapper:

```json
{
  "proposer": {
    "command": ["{python}", "my_provider_adapter.py"]
  }
}
```

The wrapper may use Claude, Gemini, Qwen, DeepSeek, Ollama, vLLM, an OpenAI-compatible endpoint, a coding agent CLI, a deterministic optimizer, or another service. Provider-specific authentication and retries stay inside the wrapper.

## Manual or externally scheduled mode

A proposer does not have to run inside the loop. Initialize the run, create a proposal JSON elsewhere, and submit it:

```bash
python scripts/autoresearch_core.py init --config config.json --run-dir run
python scripts/autoresearch_core.py submit --run-dir run --proposal proposal.json
```

This mode works with web chat models, humans, job queues, and orchestration systems that cannot expose a local command.

## Required behavior

- Read the complete context object from stdin.
- Return one JSON object with a unique `candidate_id`.
- Respect `proposal_schema`, `search_guidance`, evaluated IDs, and remaining budget.
- Return `{"action":"stop","reason":"..."}` when further search is unjustified.
- Print secrets nowhere. Keep API keys in environment variables or a provider secret store.
- Do not modify the evaluator, frozen inputs, split manifests, metric, or guard.

The domain evaluator remains responsible for validating proposal fields and rejecting unsupported or unsafe candidates.
