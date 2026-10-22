#!/usr/bin/env python3
"""Build an auditable PubChem/BATMAN candidate case from a named compound list.

The input is an MCE name audit with ingredient_name and mce_canonical_smiles.
Only exact stereochemical structure matches with enough PPI targets are selected.
Experimental response columns are never read.
"""

import argparse
import csv
import gzip
import json
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from rdkit import Chem

from run_combination_network import read_ppi, sha256, write_csv


BATMAN_BASE = "http://batman2.cloudna.cn/downloadApiFile/data/browser/"
BATMAN_FILES = {
    "known_by_ingredients": "known_browse_by_ingredients.txt.gz",
    "predicted_by_ingredients": "predicted_browse_by_ingredients.txt.gz",
    "predicted_by_targets": "predicted__browse_by_targets.txt.gz",
}
PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/"
HEADERS = {"User-Agent": "combination-efficacy-prediction/2.0 (academic coverage audit)"}


def request_json(url):
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            if exc.code not in (429, 500, 502, 503, 504):
                raise
        except (TimeoutError, urllib.error.URLError):
            pass
        time.sleep(attempt + 1)
    raise RuntimeError(f"PubChem request failed after retries: {url}")


def fetch_cid(row):
    name = row["ingredient_name"].strip()
    cas = (row.get("mce_cas_numbers") or "").split(" | ")[0].strip()
    for method, query in (("name", name), ("cas", cas)):
        if not query:
            continue
        url = PUBCHEM_BASE + "name/" + urllib.parse.quote(query, safe="") + "/cids/JSON"
        result = request_json(url)
        cids = (result or {}).get("IdentifierList", {}).get("CID", [])
        if cids:
            return name, method, cids
    return name, "unresolved", []


def canonical(smiles, stereo=True):
    molecule = Chem.MolFromSmiles(smiles) if smiles else None
    if molecule is None:
        return None
    return Chem.MolToSmiles(molecule, canonical=True, isomericSmiles=stereo)


def download_sources(source_dir):
    source_dir.mkdir(parents=True, exist_ok=True)
    sources = {}
    for key, filename in BATMAN_FILES.items():
        path = source_dir / filename
        url = BATMAN_BASE + filename
        if not path.is_file():
            temporary = path.with_suffix(path.suffix + ".partial")
            try:
                request = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as output:
                    shutil.copyfileobj(response, output)
                with gzip.open(temporary, "rb") as handle:
                    handle.read(1)
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        sources[key] = {"url": url, "file": str(path), "sha256": sha256(path), "bytes": path.stat().st_size}
    return sources


def batman_targets(sources, cids):
    known = {cid: set() for cid in cids}
    predicted_ids = {cid: {} for cid in cids}
    with gzip.open(sources["known_by_ingredients"]["file"], "rt", encoding="utf-8") as handle:
        next(handle)
        for line in handle:
            parts = line.rstrip("\r\n").split("\t")
            if len(parts) >= 3 and parts[0].isdigit():
                cid = int(parts[0])
                if cid in known:
                    known[cid] = {gene for gene in parts[2].split("|") if gene}
    with gzip.open(sources["predicted_by_ingredients"]["file"], "rt", encoding="utf-8") as handle:
        next(handle)
        for line in handle:
            cid_text = line.split(" ", 1)[0]
            if not cid_text.isdigit() or int(cid_text) not in predicted_ids:
                continue
            cid = int(cid_text)
            target_text = line.rstrip("\r\n").rsplit(" ", 1)[-1]
            for entry in target_text.split("|"):
                match = re.fullmatch(r"(\d+)\((\d+(?:\.\d+)?)\)", entry)
                if match:
                    score = float(match.group(2))
                    if score > 0.6:
                        predicted_ids[cid][int(match.group(1))] = score
    wanted = set().union(*(set(targets) for targets in predicted_ids.values()))
    symbols = {}
    with gzip.open(sources["predicted_by_targets"]["file"], "rt", encoding="utf-8") as handle:
        next(handle)
        for line in handle:
            parts = line.split("\t", 2)
            if len(parts) >= 2 and parts[0].isdigit() and int(parts[0]) in wanted:
                symbols[int(parts[0])] = parts[1]
    missing = wanted - symbols.keys()
    if missing:
        raise ValueError(f"BATMAN predicted gene IDs lack symbols: {sorted(missing)[:10]}")
    predicted = {cid: {symbols[gene_id]: score for gene_id, score in targets.items()}
                 for cid, targets in predicted_ids.items()}
    return known, predicted


def build(args):
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    source_dir = output / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    mce_snapshot = source_dir / "mce_name_audit.csv"
    if args.mce_audit.resolve() != mce_snapshot.resolve():
        shutil.copyfile(args.mce_audit, mce_snapshot)
    with args.mce_audit.open(newline="", encoding="utf-8-sig") as handle:
        ingredients = list(csv.DictReader(handle))
    names = [row["ingredient_name"].strip() for row in ingredients]
    if len(set(names)) != len(names):
        raise ValueError("Duplicate ingredient names in MCE audit")
    with ThreadPoolExecutor(max_workers=3) as executor:
        lookup = {name: (method, cids) for name, method, cids in executor.map(fetch_cid, ingredients)}
    cids = sorted({cid for _, found in lookup.values() for cid in found})
    properties = {}
    for start in range(0, len(cids), 50):
        batch = cids[start:start + 50]
        url = PUBCHEM_BASE + "cid/" + ",".join(map(str, batch)) + "/property/CanonicalSMILES,IsomericSMILES/JSON"
        data = request_json(url)
        for item in data["PropertyTable"]["Properties"]:
            properties[item["CID"]] = item
    sources = download_sources(source_dir)
    known, predicted = batman_targets(sources, set(cids))
    _, ppi_index, _, ppi_stats = read_ppi(args.ppi)
    ppi_genes = set(ppi_index)
    audit = []
    candidates = []
    edges = []
    for row in ingredients:
        name = row["ingredient_name"].strip()
        method, found = lookup[name]
        mce_smiles = (row.get("mce_canonical_smiles") or "").strip()
        exact_matches = [item for item in found
                         if mce_smiles and canonical(mce_smiles) == canonical(properties.get(item, {}).get("SMILES", ""))]
        cid = exact_matches[0] if len(exact_matches) == 1 else (found[0] if found else None)
        pubchem_smiles = properties.get(cid, {}).get("SMILES", "")
        if cid is None:
            identity = "unresolved"
        elif not mce_smiles:
            identity = "no_local_structure"
        elif len(exact_matches) > 1:
            identity = "ambiguous_exact_structure"
        elif canonical(mce_smiles) == canonical(pubchem_smiles):
            identity = "exact_stereo"
        elif canonical(mce_smiles, False) == canonical(pubchem_smiles, False):
            identity = "same_connectivity"
        else:
            identity = "structure_mismatch"
        known_genes = known.get(cid, set()) if cid else set()
        predicted_genes = predicted.get(cid, {}) if cid else {}
        genes = known_genes | predicted_genes.keys()
        mapped = genes & ppi_genes
        if identity != "exact_stereo":
            reason = identity
        elif not genes:
            reason = "no_batman_targets"
        elif len(mapped) < 2:
            reason = "ppi_targets_lt2"
        else:
            reason = "selected"
        candidate_id = f"PubChem:{cid}" if cid else ""
        audit.append({"ingredient_name": name, "mce_compound_id": row.get("mce_compound_id", ""),
                      "mce_catalog_numbers": row.get("mce_catalog_numbers", ""),
                      "mce_cas_numbers": row.get("mce_cas_numbers", ""),
                      "mce_canonical_smiles": mce_smiles, "candidate_id": candidate_id,
                      "pubchem_smiles": pubchem_smiles, "cid_lookup_method": method,
                      "cid_match_count": len(found),
                      "exact_structure_cid_match_count": len(exact_matches),
                      "identity_status": identity,
                      "known_target_count": len(known_genes),
                      "predicted_target_count_gt_0_6": len(predicted_genes),
                      "unique_target_count": len(genes), "ppi_lcc_target_count": len(mapped),
                      "selection_status": reason})
        if reason != "selected":
            continue
        candidates.append({"candidate_id": candidate_id, "candidate_name": name,
                           "human_target_genes": ";".join(sorted(genes)),
                           "target_source": "BATMAN-TCM 2.0:known+predicted_score>0.6",
                           "pubchem_cid": cid, "mce_compound_id": row.get("mce_compound_id", ""),
                           "mce_canonical_smiles": mce_smiles, "ppi_lcc_target_count": len(mapped)})
        for gene in sorted(known_genes):
            edges.append({"candidate_id": candidate_id, "candidate_name": name,
                          "pubchem_cid": cid, "gene_symbol": gene, "evidence_type": "known",
                          "prediction_score": "", "in_primekg_ppi_lcc": int(gene in ppi_genes)})
        for gene, score in sorted(predicted_genes.items()):
            edges.append({"candidate_id": candidate_id, "candidate_name": name,
                          "pubchem_cid": cid, "gene_symbol": gene, "evidence_type": "predicted",
                          "prediction_score": score, "in_primekg_ppi_lcc": int(gene in ppi_genes)})
    candidates.sort(key=lambda row: row["candidate_id"])
    edges.sort(key=lambda row: (row["candidate_id"], row["gene_symbol"], row["evidence_type"]))
    audit.sort(key=lambda row: row["ingredient_name"])
    if args.expect_candidates is not None and len(candidates) != args.expect_candidates:
        raise ValueError(f"Expected {args.expect_candidates} candidates, found {len(candidates)}; inspect source changes")
    audit_fields = list(audit[0])
    write_csv(output / "identity_audit.csv", audit_fields, audit)
    write_csv(output / "excluded_compounds.csv", audit_fields,
              [row for row in audit if row["selection_status"] != "selected"])
    write_csv(output / "candidate_compounds.csv", list(candidates[0]), candidates)
    write_csv(output / "target_edges.csv", list(edges[0]), edges)
    observed = None
    pair_snapshot = None
    if args.pair_list:
        with args.pair_list.open(newline="", encoding="utf-8-sig") as handle:
            pair_names = [(row["drug_a_name"], row["drug_b_name"]) for row in csv.DictReader(handle)]
        pair_snapshot = source_dir / "hdf_pair_names.csv"
        write_csv(pair_snapshot, ["drug_a_name", "drug_b_name"],
                  [{"drug_a_name": a, "drug_b_name": b} for a, b in pair_names])
        selected = {row["candidate_name"] for row in candidates}
        observed = sum(a in selected and b in selected for a, b in pair_names)
    summary = {"created_utc": datetime.now(timezone.utc).isoformat(),
               "selection": "exact MCE/PubChem stereochemical structure; BATMAN known plus predicted score >0.6; >=2 PrimeKG PPI LCC targets",
               "input_sha256": {str(args.mce_audit): sha256(args.mce_audit), str(args.ppi): sha256(args.ppi)},
               "case_input_snapshots": {str(mce_snapshot): sha256(mce_snapshot)},
               "sources": sources, "pubchem_api": PUBCHEM_BASE,
               "ingredients": len(audit), "candidate_drugs": len(candidates),
               "excluded_drugs": len(audit) - len(candidates),
               "identity_status_counts": dict(Counter(row["identity_status"] for row in audit)),
               "selection_status_counts": dict(Counter(row["selection_status"] for row in audit)),
               "known_target_drugs": sum(row["known_target_count"] > 0 for row in audit if row["selection_status"] == "selected"),
               "predicted_target_drugs": sum(row["predicted_target_count_gt_0_6"] > 0 for row in audit if row["selection_status"] == "selected"),
               "target_edges_known": sum(row["evidence_type"] == "known" for row in edges),
               "target_edges_predicted": sum(row["evidence_type"] == "predicted" for row in edges),
               "ppi_lcc_nodes": ppi_stats["ppi_lcc_nodes"],
               "possible_pairs": len(candidates) * (len(candidates) - 1) // 2,
               "observed_pair_names_with_both_candidates": observed}
    if args.pair_list:
        summary["input_sha256"][str(args.pair_list)] = sha256(args.pair_list)
        summary["case_input_snapshots"][str(pair_snapshot)] = sha256(pair_snapshot)
    summary["artifact_sha256"] = {name: sha256(output / name) for name in
                                   ("identity_audit.csv", "excluded_compounds.csv",
                                    "candidate_compounds.csv", "target_edges.csv")}
    (output / "source_manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key not in ("sources", "input_sha256")},
                     ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mce-audit", type=Path, required=True)
    parser.add_argument("--ppi", type=Path, required=True)
    parser.add_argument("--pair-list", type=Path, help="Optional name-only overlap audit; response columns are unused")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expect-candidates", type=int)
    build(parser.parse_args())


if __name__ == "__main__":
    main()
