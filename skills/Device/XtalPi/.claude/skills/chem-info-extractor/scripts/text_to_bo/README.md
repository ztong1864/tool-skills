# text_to_bo

`text_to_bo` is the text-processing half of the workflow. It handles:

- candidate extraction, fact extraction, normalization, and deduplication
- descriptor generation
- BO table generation

PDF text extraction lives in `../pdf_to_text.py` and writes artifacts into
`.claude/skills/chem-info-extractor/output/pdf/<pdf_id>/`.
`text_to_bo` only reads those text artifacts and writes downstream outputs into
`.claude/skills/chem-info-extractor/output/<run_name>/`.
It reads shared LLM settings from the workspace root `.env`.

## Main Flow

```text
PDF -> page text -> candidates -> facts -> descriptors -> BO table
```

## Layout

- `pipeline_src/process/`: page screening, candidate extraction, and fact processing
- `pipeline_src/pipeline/`: orchestration for process and publish runs
- `pipeline_src/descriptors/`: descriptor-space generation
- `pipeline_src/bo/`: final BO-table assembly
- `pipeline_src/llm/`: OpenAI-compatible client, caching, and prompt validation

## Outputs

- `../../../output/pdf/<pdf_id>/`
- `../../../output/<run_name>/process/candidates/`
- `../../../output/<run_name>/process/facts/`
- `../../../output/<run_name>/publish/descriptors/`
- `../../../output/<run_name>/publish/bo_inputs/manual_conditions_round0.csv`

## Entrypoint

Use the PDF text extractor first from the `scripts/` directory:

```bash
python pdf_to_text.py <pdf_dir> ../output/pdf
```

Then run the text_to_bo pipeline from `scripts/text_to_bo/`:

```bash
python -m pipeline_src.pipeline.prepare_bo_table --mode full --config configs/default.yaml
```

If you want to choose the output folder yourself, pass `--run-root ../../../output/<name>`.
