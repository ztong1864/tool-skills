import argparse
import os
from datetime import datetime
from pathlib import Path

from pipeline_src.llm.client import LLMClient
from pipeline_src.pipeline.process_pipeline import run_process_pipeline
from pipeline_src.pipeline.publish_pipeline import run_publish_pipeline
from pipeline_src.utils.config import load_config, load_schema_config
from pipeline_src.utils.env import load_env_file


def _find_workspace_env_file() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".claude").is_dir():
            candidate = parent / ".env"
            if candidate.exists():
                return candidate
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Unable to locate workspace .env")


def _resolve_runtime_paths(args: argparse.Namespace, config) -> dict:
    if args.run_root:
        run_root = args.run_root
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_root = os.path.join(config.artifacts_dir, f"text_to_bo_{timestamp}")
    process_out = args.process_out or os.path.join(run_root, "process")
    publish_out = args.publish_out or os.path.join(run_root, "publish")
    pdf_in = args.pdf_in or config.pdf_artifacts_dir
    process_in = args.process_in or process_out
    return {
        "run_root": run_root,
        "pdf_in": pdf_in,
        "process_out": process_out,
        "publish_out": publish_out,
        "process_in": process_in,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(Path(__file__).resolve().parents[2] / "configs" / "default.yaml"))
    parser.add_argument("--mode", choices=["process", "publish", "full"], default="full")
    parser.add_argument("--run-root", default=None, help="Base output directory for process/publish.")
    parser.add_argument("--process-out", default=None, help="Output directory for process stage.")
    parser.add_argument("--publish-out", default=None, help="Output directory for publish stage.")
    parser.add_argument("--pdf-in", default=None, help="Input directory for process stage (PDF text artifacts).")
    parser.add_argument("--process-in", default=None, help="Input directory for publish stage (process outputs).")
    parser.add_argument("--subset-ids", default=None, help="Comma-separated PDF IDs under pdf_in to include.")
    parser.add_argument("--subset-file", default=None, help="File with one PDF ID per line to include.")
    parser.add_argument("--max-payloads", type=int, default=None, help="Limit number of extracted page text files for process.")
    parser.add_argument("--candidate-limit", type=int, default=None, help="Limit total candidates extracted.")
    args = parser.parse_args()

    config = load_config(args.config)
    load_env_file(str(_find_workspace_env_file()))
    schema = None
    if args.mode in {"process", "publish", "full"}:
        schema = load_schema_config(os.path.join(config.project_root, "configs"), config.schema_id)

    llm = None
    if args.mode in {"process", "full"}:
        llm = LLMClient(config.raw["llm"])

    paths = _resolve_runtime_paths(args, config)
    print(
        f"\n=== [Run] mode={args.mode}\n"
        f"    pdf_in={paths['pdf_in']}\n"
        f"    process_out={paths['process_out']}\n"
        f"    publish_out={paths['publish_out']}\n"
        f"    process_in={paths['process_in']}",
        flush=True,
    )

    if args.mode in {"process", "full"}:
        if llm is None:
            raise RuntimeError("LLM client is required for process mode.")
        run_process_pipeline(
            llm=llm,
            pdf_in=paths["pdf_in"],
            process_out=paths["process_out"],
            subset_ids=args.subset_ids,
            subset_file=args.subset_file,
            max_payloads=args.max_payloads,
            candidate_limit=args.candidate_limit,
            normalization_cfg=(schema or {}).get("normalization", {}) if schema else {},
            target_scope=(schema or {}).get("target_scope", {}) if schema else {},
        )

    if args.mode in {"publish", "full"}:
        if schema is None:
            schema = load_schema_config(os.path.join(config.project_root, "configs"), config.schema_id)
        run_publish_pipeline(
            schema=schema,
            process_in=paths["process_in"],
            publish_out=paths["publish_out"],
            project_root=config.project_root,
            template_dir=config.raw.get("data", {}).get("descriptors_template_dir"),
        )


if __name__ == "__main__":
    main()
