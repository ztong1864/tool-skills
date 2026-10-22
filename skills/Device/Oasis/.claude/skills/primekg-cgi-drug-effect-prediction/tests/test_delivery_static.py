from pathlib import Path
import csv
import json

ROOT = Path(__file__).resolve().parents[1]


def test_manifest_and_required_files_exist():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["model_name"] == "primekg_cgi_graph_graph_only_e50"
    assert (ROOT / manifest["bundle_dir"] / "best_bundle.pt").exists()
    assert (ROOT / manifest["prepared_dir"] / "candidate_pool.csv").exists()


def test_candidate_pool_count():
    with (ROOT / "primekg_cgi_graph_graph_only_e50" / "prepared" / "candidate_pool.csv").open(newline="", encoding="utf-8") as f:
        assert sum(1 for _ in csv.DictReader(f)) == 6945
