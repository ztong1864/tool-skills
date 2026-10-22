#!/usr/bin/env python3
"""Check frozen HDF/BATMAN case evidence and network output invariants."""

import csv
import json
from pathlib import Path

from run_combination_network import sha256


ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets" / "hdf_skin_aging_51"
OUTPUT = ROOT / "examples" / "hdf_skin_aging_51"


def rows(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def main():
    manifest = json.loads((ASSETS / "source_manifest.json").read_text(encoding="utf-8"))
    for filename, expected in manifest["artifact_sha256"].items():
        assert sha256(ASSETS / filename) == expected, filename
    for source in manifest["sources"].values():
        path = ASSETS / "source" / Path(source["file"]).name
        assert sha256(path) == source["sha256"], path
    for filename, expected in manifest["case_input_snapshots"].items():
        path = ASSETS / "source" / Path(filename).name
        assert sha256(path) == expected, path

    audit = rows(ASSETS / "identity_audit.csv")
    excluded = rows(ASSETS / "excluded_compounds.csv")
    candidates = rows(ASSETS / "candidate_compounds.csv")
    edges = rows(ASSETS / "target_edges.csv")
    assert (len(audit), len(excluded), len(candidates)) == (81, 30, 51)
    assert len({r["candidate_id"] for r in candidates}) == 51
    assert all(r["identity_status"] == "exact_stereo" and
               r["exact_structure_cid_match_count"] == "1"
               for r in audit if r["selection_status"] == "selected")
    assert all(r["selection_status"] != "selected" for r in excluded)
    by_candidate = {r["candidate_id"]: r for r in candidates}
    targets = {candidate_id: set() for candidate_id in by_candidate}
    ppi_targets = {candidate_id: set() for candidate_id in by_candidate}
    for edge in edges:
        candidate_id = edge["candidate_id"]
        assert candidate_id in by_candidate
        assert edge["evidence_type"] in ("known", "predicted")
        if edge["evidence_type"] == "known":
            assert edge["prediction_score"] == ""
        else:
            assert float(edge["prediction_score"]) > 0.6
        targets[candidate_id].add(edge["gene_symbol"])
        if edge["in_primekg_ppi_lcc"] == "1":
            ppi_targets[candidate_id].add(edge["gene_symbol"])
    for candidate_id, candidate in by_candidate.items():
        assert targets[candidate_id] == set(candidate["human_target_genes"].split(";"))
        assert len(ppi_targets[candidate_id]) == int(candidate["ppi_lcc_target_count"])
        assert len(ppi_targets[candidate_id]) >= 2

    pair_names = rows(ASSETS / "source" / "hdf_pair_names.csv")
    assert set(pair_names[0]) == {"drug_a_name", "drug_b_name"}
    names = {r["candidate_name"] for r in candidates}
    overlap = sum(r["drug_a_name"] in names and r["drug_b_name"] in names for r in pair_names)
    assert (len(pair_names), overlap) == (480, 214)

    summary = json.loads((OUTPUT / "run_summary.json").read_text(encoding="utf-8"))
    all_pairs = rows(OUTPUT / "all_pair_metrics.csv")
    ranked = rows(OUTPUT / "ranked_pairs.csv")
    assert summary["candidate_id_field"] == "candidate_id"
    assert (summary["candidate_drugs"], summary["ppi_mapped_drugs"], summary["pairs_all"],
            summary["pairs_scorable"], summary["pairs_separation_eligible"],
            summary["eligible_pairs"]) == (51, 51, 1275, 1275, 1275, 504)
    assert (len(all_pairs), len(ranked)) == (1275, 504)
    assert all(r["eligible_pair"] == "1" for r in ranked)
    assert all(r["selection_status"] == "eligible" for r in ranked)
    assert all(r["selection_status"] != "" for r in all_pairs)
    assert [int(r["rank"]) for r in ranked] == list(range(1, 505))
    assert all(float(a["network_score"]) >= float(b["network_score"])
               for a, b in zip(ranked, ranked[1:]))
    observed_names = {tuple(sorted((r["drug_a_name"], r["drug_b_name"]))) for r in pair_names}
    observed_scored = [r for r in all_pairs
                       if tuple(sorted((r["candidate_name_A"], r["candidate_name_B"]))) in observed_names]
    assert len(observed_scored) == 214
    assert sum(r["eligible_pair"] == "1" for r in observed_scored) == 80
    assert sha256(ASSETS / "candidate_compounds.csv") == summary["input_sha256"][summary["candidate_source"]]
    print("HDF 51 case verified: 51 compounds, 214 observed name pairs (80 eligible), 1275 scored pairs, 504 ranked pairs")


if __name__ == "__main__":
    main()
