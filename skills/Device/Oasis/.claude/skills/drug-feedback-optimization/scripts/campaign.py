#!/usr/bin/env python3
"""Run a disease-specific, file-backed experimental feedback campaign."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from validate_task_config import resolve_batch_size, validate_config


def stamp():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_write(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def file_from_config(config_path, value):
    path = Path(value)
    return (path if path.is_absolute() else config_path.parent / path).resolve()


def load_config(path):
    path = Path(path).resolve()
    config = json.loads(path.read_text(encoding="utf-8"))
    validate_config(config)
    return config, path


def validate_strategy(config):
    strategy = config["strategy"]
    model = strategy.get("feedback_model", {})
    fusion = strategy.get("fusion", {})
    acquisition = strategy.get("acquisition", {})
    if model.get("type") != "RandomForestRegressor":
        raise ValueError("real campaign currently supports RandomForestRegressor only")
    if fusion.get("type") != "fixed_weight":
        raise ValueError("real campaign currently supports fixed_weight fusion only")
    weights = [float(fusion.get(key, math.nan)) for key in ("base_weight", "feedback_weight")]
    if not all(0 <= weight <= 1 for weight in weights) or not math.isclose(sum(weights), 1.0):
        raise ValueError("fusion weights must be in [0,1] and sum to one")
    if acquisition.get("type") != "greedy_final_score" or float(acquisition.get("explore_fraction", 0)) != 0:
        raise ValueError("real campaign currently supports greedy_final_score without exploration only")
    for key in ("n_estimators", "min_samples_leaf"):
        if int(model.get(key, 0)) < 1:
            raise ValueError(f"feedback_model.{key} must be a positive integer")
    max_features = float(model.get("max_features", math.nan))
    if not 0 < max_features <= 1:
        raise ValueError("feedback_model.max_features must be in (0,1]")


def clean_id(value):
    result = str(value).strip()
    if not result or result.lower() in {"nan", "none"}:
        raise ValueError("candidate_id cannot be empty")
    return result


def prepare_pool(config, config_path):
    candidate_path = file_from_config(config_path, config["candidate_table"])
    features_path = file_from_config(config_path, config["feature_columns_json"])
    features = json.loads(features_path.read_text(encoding="utf-8"))
    if not isinstance(features, list) or not features or len(features) != len(set(features)):
        raise ValueError("feature_columns_json must contain a nonempty list of unique column names")
    raw = pd.read_csv(candidate_path, dtype={config["candidate_id_col"]: str}, low_memory=False)
    mapping = {config["candidate_id_col"]: "candidate_id", config["base_score_col"]: "base_score",
               config["smiles_col"]: "smiles"}
    if len(mapping) != 3:
        raise ValueError("candidate_id, base_score and smiles source columns must be distinct")
    required_source = {config["candidate_id_col"], config["base_score_col"]}
    if "structure_group_id" not in raw.columns:
        required_source.add(config["smiles_col"])
    if not required_source.issubset(raw.columns):
        raise ValueError(f"candidate table missing columns: {sorted(required_source - set(raw.columns))}")
    raw = raw.rename(columns={source: target for source, target in mapping.items() if source in raw.columns})
    if "smiles" not in raw.columns:
        raw["smiles"] = ""
    if raw.columns.duplicated().any():
        raise ValueError("candidate table has duplicate column names after field mapping")
    if config["target_col"] in raw.columns:
        raw = raw.drop(columns=[config["target_col"]])  # Never expose retrospective labels to a live campaign.
    features = ["base_score" if name == config["base_score_col"] else name for name in features]
    missing = set(features) - set(raw.columns)
    if missing:
        raise ValueError(f"candidate table missing frozen features: {sorted(missing)}")
    raw["candidate_id"] = [clean_id(x) for x in raw["candidate_id"]]
    if raw["candidate_id"].duplicated().any():
        raise ValueError("candidate_id must be unique")
    raw["base_score"] = pd.to_numeric(raw["base_score"], errors="raise")
    if not np.isfinite(raw["base_score"]).all() or not raw["base_score"].between(0, 1).all():
        raise ValueError("base_score must be finite and in [0,1] for fixed-weight fusion")
    for name in features:
        raw[name] = pd.to_numeric(raw[name], errors="raise")
    if not np.isfinite(raw[features].to_numpy(dtype=float)).all():
        raise ValueError("frozen features must all be finite")
    if "structure_group_id" not in raw:
        try:
            from rdkit import Chem
        except ImportError as exc:
            raise ValueError("RDKit is needed to derive structure_group_id; provide that column or install RDKit") from exc
        groups = []
        for value in raw["smiles"]:
            molecule = Chem.MolFromSmiles(str(value))
            if molecule is None:
                raise ValueError(f"cannot canonicalize SMILES: {value}")
            groups.append(Chem.MolToSmiles(molecule, canonical=True))
        raw["structure_group_id"] = groups
    if raw["structure_group_id"].isna().any() or raw["structure_group_id"].astype(str).str.strip().eq("").any():
        raise ValueError("structure_group_id cannot be empty")
    if "name" not in raw:
        raw["name"] = raw["candidate_id"]
    columns = list(dict.fromkeys(["candidate_id", "name", "smiles", "base_score", "structure_group_id", *features]))
    return raw[columns].copy(), features, candidate_path, features_path


@contextmanager
def locked(directory):
    lock = directory / ".campaign.lock"
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise ValueError(f"campaign is locked: {lock}") from exc
    try:
        yield
    finally:
        lock.rmdir()


def load_campaign(directory):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / "campaign_manifest.json").read_text(encoding="utf-8"))
    state = json.loads((directory / "state.json").read_text(encoding="utf-8"))
    config, _ = load_config(directory / "task_config.json")
    validate_strategy(config)
    if digest(directory / "task_config.json") != manifest["config_sha256"]:
        raise ValueError("frozen task config changed")
    if digest(directory / "candidate_pool_snapshot.csv") != manifest["candidate_sha256"]:
        raise ValueError("frozen candidate pool changed")
    if digest(directory / "feature_columns.json") != manifest["features_sha256"]:
        raise ValueError("frozen feature list changed")
    if digest(Path(__file__).resolve()) != manifest["campaign_code_sha256"]:
        raise ValueError("campaign implementation changed since initialization")
    pool = pd.read_csv(directory / "candidate_pool_snapshot.csv", dtype={"candidate_id": str}, low_memory=False)
    features = json.loads((directory / "feature_columns.json").read_text(encoding="utf-8"))
    return directory, manifest, state, config, pool, features


def log_event(directory, event, **fields):
    with (directory / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"at": stamp(), "event": event, **fields}, ensure_ascii=False) + "\n")


def score_pool(pool, state, config, features):
    statuses = state["statuses"]
    groups_by_id = dict(zip(pool.candidate_id, pool.structure_group_id))
    selected_groups = {str(groups_by_id[cid]) for cid, attempts in state["attempts"].items() if attempts > 0}
    eligible = pool.loc[[statuses[cid] == "retryable_failure" or
                         (statuses[cid] == "available" and str(group) not in selected_groups)
                         for cid, group in zip(pool.candidate_id, pool.structure_group_id)]].copy()
    observed = state["feedback"]
    valid = [row for row in observed if row["result_status"] == "valid"]
    enabled = len(valid) >= int(config["strategy"].get("min_feedback_to_fit", 30))
    model = None
    if enabled and len(eligible):
        training = pool.merge(pd.DataFrame(valid)[["candidate_id", "activity_score"]], on="candidate_id", validate="one_to_one")
        parameters = config["strategy"]["feedback_model"]
        model = RandomForestRegressor(n_estimators=int(parameters["n_estimators"]),
                                      min_samples_leaf=int(parameters["min_samples_leaf"]),
                                      max_features=float(parameters["max_features"]),
                                      random_state=42, n_jobs=1)
        model.fit(training[features], training["activity_score"].astype(float))
        eligible["feedback_score"] = np.clip(model.predict(eligible[features]), 0, 1)
        weight = float(config["strategy"]["fusion"]["base_weight"])
        eligible["final_score"] = weight * eligible["base_score"] + (1 - weight) * eligible["feedback_score"]
        eligible["ranking_source"] = "base_feedback_fusion"
        eligible["ranking_score"] = eligible["final_score"]
    else:
        eligible["feedback_score"] = np.nan
        eligible["final_score"] = eligible["base_score"]
        eligible["ranking_source"] = "base_only"
        eligible["ranking_score"] = eligible["base_score"]
    eligible = eligible.sort_values(["ranking_score", "candidate_id"], ascending=[False, True]).reset_index(drop=True)
    base_order = pool.sort_values(["base_score", "candidate_id"], ascending=[False, True]).candidate_id.tolist()
    base_ranks = {cid: index + 1 for index, cid in enumerate(base_order)}
    eligible["base_rank"] = eligible.candidate_id.map(base_ranks)
    eligible["final_rank"] = np.arange(1, len(eligible) + 1)
    return eligible, model, len(valid)


def make_round(directory, state, config, pool, features, batch_override=None):
    round_number = len(state["rounds"]) + 1
    scored, model, valid_count = score_pool(pool, state, config, features)
    resolution = resolve_batch_size(config, round_number, batch_override,
                                    already_selected=sum(len(item["candidate_ids"]) for item in state["rounds"]),
                                    remaining_candidates=len(scored))
    count = resolution["effective_batch_size"]
    if count == 0:
        raise ValueError("no eligible candidates or campaign budget remain")
    chosen = scored.drop_duplicates("structure_group_id").head(count).copy()
    if len(chosen) < count:
        resolution["effective_batch_size"] = len(chosen)
        resolution["cap_applied"] = True
        resolution["cap_reasons"].append("unique_structures_remaining")
    if chosen.empty:
        raise ValueError("no unique eligible structures remain")
    chosen["selection_reason"] = ["technical_retry" if state["statuses"][cid] == "retryable_failure"
                                  else "greedy_ranking_score" for cid in chosen.candidate_id]
    chosen["strategy_version"] = config["strategy"]["strategy_version"]
    chosen["round"] = round_number
    fields = ["candidate_id", "name", "base_score", "feedback_score", "final_score", "ranking_score",
              "ranking_source", "base_rank", "final_rank", "selection_reason", "structure_group_id",
              "strategy_version", "round"]
    round_dir = directory / f"round_{round_number:03d}"
    if round_dir.exists():
        raise ValueError(f"round output already exists: {round_dir}")
    temporary = Path(tempfile.mkdtemp(prefix=f".round_{round_number:03d}_", dir=directory))
    try:
        scored.to_csv(temporary / "scored_candidates.csv", index=False)
        chosen[fields].to_csv(temporary / "next_candidates.csv", index=False)
        model_summary = {"feedback_model_enabled": model is not None, "valid_feedback": valid_count,
                         "features": features, "model": config["strategy"]["feedback_model"] if model is not None else None,
                         "fusion": config["strategy"]["fusion"] if model is not None else None}
        json_write(temporary / "model_summary.json", model_summary)
        if model is not None:
            joblib.dump(model, temporary / "feedback_model.joblib")
        summary = {**resolution, "ranking_source": chosen["ranking_source"].iloc[0],
                   "valid_feedback": valid_count, "selected_ids": chosen.candidate_id.tolist(), "created_at": stamp()}
        json_write(temporary / "summary.json", summary)
        status_counts = {status: list(state["statuses"].values()).count(status)
                         for status in sorted(set(state["statuses"].values()))}
        recommendation_rows = "\n".join(
            f"| {row.candidate_id} | {row.name} | {row.base_score:.6f} | "
            f"{row.feedback_score if pd.notna(row.feedback_score) else '—'} | "
            f"{row.final_score:.6f} | {row.base_rank} | {row.final_rank} | {row.selection_reason} |"
            for row in chosen.itertuples(index=False)
        )
        (temporary / "report.md").write_text(
            f"# 第 {round_number} 轮推荐\n\n策略版本：`{config['strategy']['strategy_version']}`。"
            f"累计有效反馈：{valid_count}；排序来源：`{summary['ranking_source']}`。\n\n"
            f"请求 {resolution['requested_batch_size']} 个，实际推荐 {len(chosen)} 个；"
            f"缩减原因：{', '.join(resolution['cap_reasons']) or '无'}。\n\n"
            f"融合规则：`{json.dumps(config['strategy']['fusion'], ensure_ascii=False)}`。\n\n"
            f"推荐前候选状态：`{json.dumps(status_counts, ensure_ascii=False)}`。\n\n"
            "| 候选 ID | 名称 | 基座分数 | 反馈分数 | 最终分数 | 基座排名 | 本轮排名 | 选择原因 |\n"
            "|---|---|---:|---:|---:|---:|---:|---|\n"
            f"{recommendation_rows}\n\n完整分数、结构组与冻结输入哈希见 `next_candidates.csv`、"
            "`scored_candidates.csv` 和 `../campaign_manifest.json`。\n",
            encoding="utf-8")
        os.replace(temporary, round_dir)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    ids = chosen.candidate_id.tolist()
    for cid in ids:
        state["statuses"][cid] = "pending"
        state["attempts"][cid] += 1
    state["rounds"].append({"round": round_number, "candidate_ids": ids,
                            "feedback_count_at_recommendation": len(state["feedback"]), "summary": summary})
    json_write(directory / "state.json", state)
    log_event(directory, "recommend", round=round_number, candidate_ids=ids, ranking_source=summary["ranking_source"])
    return round_dir, summary


def initialize(args):
    config, config_path = load_config(args.config)
    validate_strategy(config)
    pool, features, candidate_path, features_path = prepare_pool(config, config_path)
    output = Path(args.campaign_dir).resolve()
    if output.exists():
        raise ValueError(f"campaign directory already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".campaign_", dir=output.parent))
    try:
        shutil.copyfile(config_path, temporary / "task_config.json")
        json_write(temporary / "feature_columns.json", features)
        pool.to_csv(temporary / "candidate_pool_snapshot.csv", index=False)
        manifest = {"created_at": stamp(), "task_name": config["task_name"], "disease_name": config["disease_name"],
                    "base_model": config.get("base_model"),
                    "feature_generation_version": config.get("feature_generation_version"),
                    "strategy_version": config["strategy"]["strategy_version"],
                    "activity_score_transform": config["activity_score_transform"],
                    "config_sha256": digest(temporary / "task_config.json"),
                    "candidate_sha256": digest(temporary / "candidate_pool_snapshot.csv"),
                    "features_sha256": digest(temporary / "feature_columns.json"),
                    "campaign_code_sha256": digest(Path(__file__).resolve()),
                    "source_candidate_sha256": digest(candidate_path), "source_features_sha256": digest(features_path),
                    "python": sys.version.split()[0], "pandas": pd.__version__, "sklearn": __import__("sklearn").__version__}
        json_write(temporary / "campaign_manifest.json", manifest)
        state = {"statuses": {cid: "available" for cid in pool.candidate_id},
                 "attempts": {cid: 0 for cid in pool.candidate_id},
                 "rounds": [], "feedback": [], "ingested_hashes": []}
        json_write(temporary / "state.json", state)
        with (temporary / "feedback_ledger.csv").open("w", newline="", encoding="utf-8") as stream:
            csv.writer(stream).writerow(["candidate_id", "activity_score", "result_status", "round", "batch_id", "source", "failure_reason", "ingested_at"])
        (temporary / "events.jsonl").write_text("", encoding="utf-8")
        (temporary / "feedback_inputs").mkdir()
        make_round(temporary, state, config, pool, features, args.batch_size)
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    print(json.dumps({"campaign_dir": str(output), "round": 1, "next_candidates": str(output / "round_001" / "next_candidates.csv")}, ensure_ascii=False))


def ingest(args):
    directory = Path(args.campaign_dir).resolve()
    with locked(directory):
        directory, manifest, state, config, pool, features = load_campaign(directory)
        source = Path(args.feedback_csv).resolve()
        file_hash = digest(source)
        if file_hash in state["ingested_hashes"]:
            raise ValueError("feedback file was already ingested")
        frame = pd.read_csv(source, dtype={"candidate_id": str}, keep_default_na=False)
        required = {"candidate_id", "activity_score"}
        if not required.issubset(frame.columns):
            raise ValueError(f"feedback CSV missing columns: {sorted(required - set(frame.columns))}")
        if frame.empty:
            raise ValueError("feedback CSV is empty")
        ids = [clean_id(value) for value in frame.candidate_id]
        if len(ids) != len(set(ids)):
            raise ValueError("feedback CSV contains duplicate candidate_id")
        assigned_round = {cid: item["round"] for item in state["rounds"] for cid in item["candidate_ids"]}
        entries = []
        for row in frame.to_dict(orient="records"):
            cid = clean_id(row["candidate_id"])
            if cid not in state["statuses"]:
                raise ValueError(f"unknown candidate_id: {cid}")
            if state["statuses"][cid] != "pending":
                raise ValueError(f"candidate {cid} is not pending; feedback must match a reserved recommendation")
            status = str(row.get("result_status", "valid") or "valid").strip().lower()
            if status not in {"valid", "compound_failure", "technical_failure"}:
                raise ValueError(f"invalid result_status for {cid}: {status}")
            score = str(row["activity_score"]).strip()
            if status == "valid":
                if not score:
                    raise ValueError(f"missing activity_score for valid candidate {cid}")
                numeric = float(score)
                if not math.isfinite(numeric) or not 0 <= numeric <= 1:
                    raise ValueError(f"activity_score for {cid} must be finite and in [0,1]")
            elif score:
                raise ValueError(f"failure row {cid} must not contain activity_score")
            else:
                numeric = None
            entries.append({"candidate_id": cid, "activity_score": numeric, "result_status": status,
                            "round": assigned_round[cid], "batch_id": str(row.get("batch_id", "")),
                            "source": str(row.get("source", "")), "failure_reason": str(row.get("failure_reason", "")),
                            "ingested_at": stamp()})
        for entry in entries:
            cid = entry["candidate_id"]
            if entry["result_status"] == "technical_failure":
                state["statuses"][cid] = "retryable_failure" if state["attempts"][cid] < 2 else "failed"
            else:
                state["statuses"][cid] = "observed" if entry["result_status"] == "valid" else "failed"
        state["feedback"].extend(entries)
        state["ingested_hashes"].append(file_hash)
        shutil.copyfile(source, directory / "feedback_inputs" / f"{file_hash}.csv")
        json_write(directory / "state.json", state)
        with (directory / "feedback_ledger.csv").open("a", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(entries[0]))
            writer.writerows(entries)
        log_event(directory, "ingest_feedback", sha256=file_hash, count=len(entries), rounds=sorted({x["round"] for x in entries}))
        print(json.dumps({"ingested": len(entries), "valid_total": sum(x["result_status"] == "valid" for x in state["feedback"]),
                          "feedback_sha256": file_hash}, ensure_ascii=False))


def recommend(args):
    directory = Path(args.campaign_dir).resolve()
    with locked(directory):
        directory, manifest, state, config, pool, features = load_campaign(directory)
        if not state["rounds"]:
            raise ValueError("campaign has no initial round")
        if len(state["feedback"]) <= state["rounds"][-1]["feedback_count_at_recommendation"]:
            raise ValueError("ingest new feedback before recommending another round")
        round_dir, summary = make_round(directory, state, config, pool, features, args.batch_size)
        print(json.dumps({"round": summary["round"], "next_candidates": str(round_dir / "next_candidates.csv"),
                          "ranking_source": summary["ranking_source"],
                          "effective_batch_size": summary["effective_batch_size"]}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init-campaign", help="freeze inputs and recommend round 1")
    init.add_argument("--config", type=Path, required=True)
    init.add_argument("--campaign-dir", type=Path, required=True)
    init.add_argument("--batch-size", type=int)
    ingest_parser = sub.add_parser("ingest-feedback", help="ingest results for pending candidates")
    ingest_parser.add_argument("--campaign-dir", type=Path, required=True)
    ingest_parser.add_argument("--feedback-csv", type=Path, required=True)
    next_parser = sub.add_parser("recommend-next", help="fit the feedback model and recommend a new round")
    next_parser.add_argument("--campaign-dir", type=Path, required=True)
    next_parser.add_argument("--batch-size", type=int)
    args = parser.parse_args()
    try:
        {"init-campaign": initialize, "ingest-feedback": ingest, "recommend-next": recommend}[args.command](args)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
