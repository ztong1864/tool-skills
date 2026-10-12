# AutoResearch Core

`autoresearch-core` is a model-agnostic measured search engine. It connects any proposal source to a fixed evaluator through JSON and external commands.

It can be used with hosted or local models, custom agents, deterministic search code, or manual proposals through an external command adapter.

## Quick start

```bash
python scripts/autoresearch_core.py validate-config --config config.json
python scripts/autoresearch_core.py loop --config config.json --run-dir autoresearch-run
python scripts/autoresearch_core.py freeze --run-dir autoresearch-run --version winner_v1
```

See `references/protocol.md` for the JSON contracts and `references/provider-adapters.md` for model, agent, and manual integration patterns. The bundled drug-feedback package contains a complete PRISM integration and a deterministic proposer for testing.
