"""Integration checks for the real campaign CLI using a disposable candidate pool."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "campaign.py"


class CampaignTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.campaign = self.root / "campaign"
        candidates = self.root / "candidates.csv"
        with candidates.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["candidate_id", "name", "smiles", "base_score", "feature", "structure_group_id", "activity_score"])
            for index in range(12):
                writer.writerow([f"C{index:02d}", f"Drug {index}", "CC", 1 - index / 20, index,
                                 f"group_{index}", 1.0])
        (self.root / "features.json").write_text('["base_score", "feature"]', encoding="utf-8")
        config = {
            "profile": "test", "task_name": "test", "dataset_name": "test", "disease_name": "test",
            "candidate_table": "candidates.csv", "candidate_id_col": "candidate_id", "target_col": "activity_score",
            "higher_is_better": True, "base_score_col": "base_score", "smiles_col": "smiles",
            "feature_columns_json": "features.json", "split_manifest": None,
            "activity_score_transform": {"version": "test_v1", "minimum": 0, "maximum": 1},
            "campaign": {"num_rounds": 3, "batch_size": 2, "round_batch_sizes": {},
                         "allow_runtime_batch_size_override": True, "max_total_candidates": 6},
            "strategy": {"strategy_version": "test_v1", "min_feedback_to_fit": 2,
                         "feedback_model": {"type": "RandomForestRegressor", "n_estimators": 8,
                                            "min_samples_leaf": 1, "max_features": 1.0},
                         "fusion": {"type": "fixed_weight", "base_weight": 0.0, "feedback_weight": 1.0},
                         "acquisition": {"type": "greedy_final_score", "explore_fraction": 0}}
        }
        (self.root / "config.json").write_text(json.dumps(config), encoding="utf-8")

    def run_cli(self, *args, success=True):
        result = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def test_two_rounds_retrain_and_freeze(self):
        self.run_cli("init-campaign", "--config", self.root / "config.json", "--campaign-dir", self.campaign)
        with (self.campaign / "round_001" / "next_candidates.csv").open(encoding="utf-8") as stream:
            first = list(csv.DictReader(stream))
        self.assertEqual([row["candidate_id"] for row in first], ["C00", "C01"])
        self.assertTrue(all(row["ranking_source"] == "base_only" for row in first))
        snapshot = (self.campaign / "candidate_pool_snapshot.csv").read_text(encoding="utf-8")
        self.assertNotIn("activity_score", snapshot)

        feedback = self.root / "feedback.csv"
        with feedback.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["candidate_id", "activity_score"])
            writer.writerows([["C00", "0"], ["C01", "1"]])
        self.run_cli("ingest-feedback", "--campaign-dir", self.campaign, "--feedback-csv", feedback)
        self.assertEqual(len(list((self.campaign / "feedback_inputs").glob("*.csv"))), 1)
        self.run_cli("ingest-feedback", "--campaign-dir", self.campaign, "--feedback-csv", feedback, success=False)
        self.run_cli("recommend-next", "--campaign-dir", self.campaign)
        with (self.campaign / "round_002" / "next_candidates.csv").open(encoding="utf-8") as stream:
            second = list(csv.DictReader(stream))
        self.assertEqual(len(second), 2)
        self.assertTrue(all(row["ranking_source"] == "base_feedback_fusion" for row in second))
        self.assertTrue(all(float(row["ranking_score"]) == float(row["final_score"]) for row in second))
        self.assertTrue(all(row["feedback_score"] for row in second))
        self.assertTrue((self.campaign / "round_002" / "feedback_model.joblib").exists())
        self.assertTrue({row["candidate_id"] for row in first}.isdisjoint({row["candidate_id"] for row in second}))
        self.run_cli("recommend-next", "--campaign-dir", self.campaign, success=False)

    def test_invalid_feedback_does_not_mutate(self):
        self.run_cli("init-campaign", "--config", self.root / "config.json", "--campaign-dir", self.campaign)
        before = (self.campaign / "state.json").read_bytes()
        feedback = self.root / "bad.csv"
        feedback.write_text("candidate_id,activity_score\nC00,1.2\n", encoding="utf-8")
        self.run_cli("ingest-feedback", "--campaign-dir", self.campaign, "--feedback-csv", feedback, success=False)
        self.assertEqual(before, (self.campaign / "state.json").read_bytes())

    def test_precomputed_pair_groups_do_not_require_smiles(self):
        candidate_path = self.root / "candidates.csv"
        with candidate_path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        with candidate_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=[key for key in rows[0] if key != "smiles"])
            writer.writeheader()
            for row in rows:
                row.pop("smiles")
                writer.writerow(row)
        self.run_cli("init-campaign", "--config", self.root / "config.json", "--campaign-dir", self.campaign)
        self.assertTrue((self.campaign / "round_001" / "next_candidates.csv").exists())

    def test_technical_failure_can_retry_once(self):
        self.run_cli("init-campaign", "--config", self.root / "config.json", "--campaign-dir", self.campaign)
        feedback = self.root / "technical.csv"
        feedback.write_text("candidate_id,activity_score,result_status\nC00,,technical_failure\n", encoding="utf-8")
        self.run_cli("ingest-feedback", "--campaign-dir", self.campaign, "--feedback-csv", feedback)
        self.run_cli("recommend-next", "--campaign-dir", self.campaign)
        with (self.campaign / "round_002" / "next_candidates.csv").open(encoding="utf-8") as stream:
            second = list(csv.DictReader(stream))
        retried = [row for row in second if row["candidate_id"] == "C00"]
        self.assertEqual(len(retried), 1)
        self.assertEqual(retried[0]["selection_reason"], "technical_retry")
        state = json.loads((self.campaign / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["attempts"]["C00"], 2)


if __name__ == "__main__":
    unittest.main()
