#!/usr/bin/env python3
"""Rank two-drug candidates for any named disease with network proximity and separation.

Use an explicit candidate CSV, or sample 100 target-mapped drugs from a
DrugBank candidate pool with a fixed seed. No measured efficacy is inferred.
"""

import argparse
import csv
import hashlib
import itertools
import json
import math
import random
import shutil
import urllib.request
from array import array
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

SEED = 12345
N_RANDOM = 1000
MIN_BIN = 100
OT_API = "https://api.platform.opentargets.org/api/v4/graphql"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def mean(values):
    values = tuple(values)
    return sum(values) / len(values)


def read_disease(path, disease_id=None, disease_name=None):
    if not disease_id and not disease_name:
        raise ValueError("Provide a local disease ID or exact disease name")
    rows = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            matches = row["disease_id"] == disease_id if disease_id else row["disease_name"].casefold() == disease_name.casefold()
            if matches:
                raw_score = row["overall_score"].strip()
                row["overall_score"] = float(raw_score) if raw_score else ""
                row["genetic_score"] = ""
                row["ranking_score"] = row["overall_score"]
                row["ranking_score_type"] = "local_overall_score" if raw_score else "unscored_local"
                rows.append(row)
    if not rows:
        return None
    names = {row["disease_name"] for row in rows}
    ids = {row["disease_id"] for row in rows}
    if len(names) != 1 or len(ids) != 1:
        raise ValueError(f"Ambiguous local disease match: names={names}, ids={ids}; use --disease-id")
    # Missing scores cannot determine membership or order in a truncated module.
    rows.sort(key=lambda x: (x["ranking_score"] == "",
                             -x["ranking_score"] if x["ranking_score"] != "" else 0,
                             x["gene"], x["gene_id"]))
    return names.pop(), rows


def ot_graphql(query, variables):
    request = urllib.request.Request(
        OT_API,
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.load(response)
    if result.get("errors"):
        raise RuntimeError(result["errors"])
    return result["data"]


def read_open_targets(disease_name, efo_id, output_dir, snapshot_input=None):
    if snapshot_input:
        snapshot = json.loads(snapshot_input.read_text(encoding="utf-8"))
        if disease_name and snapshot["disease_name"].casefold() != disease_name.casefold():
            raise ValueError("API snapshot disease name does not match --disease-name")
        if efo_id and snapshot["disease_id"] != efo_id:
            raise ValueError("API snapshot disease ID does not match --efo-id")
        disease_id = snapshot["disease_id"]
        canonical_name = snapshot["disease_name"]
        associations = snapshot["rows"]
        count = snapshot["association_count"]
        if snapshot.get("enableIndirect") is not False or len(associations) != count:
            raise ValueError("API snapshot must contain all direct association rows")
        snapshot_path = output_dir / "open_targets_direct_snapshot.json"
        if snapshot_input.resolve() != snapshot_path.resolve():
            shutil.copyfile(snapshot_input, snapshot_path)
    else:
        return fetch_open_targets(disease_name, efo_id, output_dir)
    return parse_open_targets(canonical_name, disease_id, associations, count, snapshot_path)


def fetch_open_targets(disease_name, efo_id, output_dir):
    if efo_id:
        disease_id = efo_id
    else:
        query = """query Q($q:String!){search(queryString:$q,entityNames:[\"disease\"],
          page:{index:0,size:50}){total hits{id name entity score}}}"""
        hits = ot_graphql(query, {"q": disease_name})["search"]["hits"]
        exact = [row for row in hits if row["entity"] == "disease" and row["name"].casefold() == disease_name.casefold()]
        if len(exact) != 1:
            raise ValueError(f"Open Targets exact disease match is ambiguous or absent: name={disease_name!r}, matches={exact}")
        disease_id = exact[0]["id"]
    query = """query Q($id:String!,$index:Int!){disease(efoId:$id){id name
      associatedTargets(enableIndirect:false,page:{index:$index,size:500}){
        count rows{target{id approvedSymbol} score datatypeScores{id score}}
      }}}"""
    associations = []
    count = None
    canonical_name = None
    for page in itertools.count():
        disease = ot_graphql(query, {"id": disease_id, "index": page})["disease"]
        if disease is None:
            raise ValueError(f"Open Targets disease not found: {disease_id}")
        canonical_name = disease["name"]
        if disease_name and canonical_name.casefold() != disease_name.casefold():
            raise ValueError(f"Open Targets ID {disease_id} resolves to {canonical_name!r}, not {disease_name!r}")
        target_rows = disease["associatedTargets"]
        count = target_rows["count"]
        associations.extend(target_rows["rows"])
        if len(associations) >= count:
            break
    if len(associations) != count:
        raise RuntimeError(f"Incomplete Open Targets pagination: {len(associations)}/{count}")
    snapshot = {"retrieved_utc": datetime.now(timezone.utc).isoformat(),
                "endpoint": OT_API, "disease_id": disease_id,
                "disease_name": canonical_name, "enableIndirect": False,
                "association_count": count, "rows": associations}
    snapshot_path = output_dir / "open_targets_direct_snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
    return parse_open_targets(canonical_name, disease_id, associations, count, snapshot_path)


def parse_open_targets(canonical_name, disease_id, associations, count, snapshot_path):
    rows = []
    for association in associations:
        datatype = {d["id"]: d["score"] for d in association["datatypeScores"]}
        genetic_score = float(datatype.get("genetic_association", 0) or 0)
        target = association["target"]
        if genetic_score > 0 and target["approvedSymbol"]:
            rows.append({"disease_id": disease_id, "disease_name": canonical_name,
                         "gene": target["approvedSymbol"], "gene_id": target["id"],
                         "source": "OpenTargets:direct_genetic_association",
                         "overall_score": float(association["score"]),
                         "genetic_score": genetic_score, "ranking_score": genetic_score,
                         "ranking_score_type": "direct_genetic_association"})
    rows.sort(key=lambda row: (-row["ranking_score"], -row["overall_score"], row["gene"], row["gene_id"]))
    print(f"Open Targets {disease_id}: {count} direct associations, {len(rows)} with genetic score", flush=True)
    return canonical_name, rows, {"api_disease_id": disease_id,
                                  "api_disease_name": canonical_name,
                                  "api_association_count": count,
                                  "api_genetic_rows": len(rows),
                                  "api_snapshot_path": str(snapshot_path)}


def read_ppi(path):
    adjacency = defaultdict(set)
    drug_targets = defaultdict(set)
    raw = 0
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or ())
        if {"head", "tail"} <= fields:
            edge_format = "head_tail"
        elif {"relation", "x_name", "y_name"} <= fields:
            edge_format = "primekg_protein_protein"
        else:
            raise ValueError(f"Unsupported PPI columns: {reader.fieldnames}")
        for row in reader:
            if edge_format == "primekg_protein_protein":
                if row["relation"] == "drug_protein" and row["display_relation"] == "target":
                    if row["x_type"] == "drug" and row["y_type"] == "gene/protein":
                        drug_targets[row["x_id"]].add(row["y_name"].strip())
                    elif row["y_type"] == "drug" and row["x_type"] == "gene/protein":
                        drug_targets[row["y_id"]].add(row["x_name"].strip())
                if row["relation"] != "protein_protein":
                    continue
            raw += 1
            a, b = (row["head"].strip(), row["tail"].strip()) if edge_format == "head_tail" else (row["x_name"].strip(), row["y_name"].strip())
            if a and b and a != b:
                adjacency[a].add(b)
                adjacency[b].add(a)
    seen, largest = set(), set()
    for start in adjacency:
        if start in seen:
            continue
        component = {start}
        queue = deque([start])
        seen.add(start)
        while queue:
            for neighbor in adjacency[queue.popleft()]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    component.add(neighbor)
                    queue.append(neighbor)
        if len(component) > len(largest):
            largest = component
    names = sorted(largest)
    index = {name: i for i, name in enumerate(names)}
    graph = [tuple(index[b] for b in adjacency[a] if b in largest) for a in names]
    return graph, index, drug_targets, {"ppi_format": edge_format,
                          "ppi_parse_policy": "drop_blank_endpoints",
                          "ppi_raw_rows": raw, "ppi_nodes": len(adjacency),
                          "ppi_lcc_nodes": len(graph), "ppi_lcc_edges": sum(map(len, graph)) // 2}


def read_candidates(path, target_map, ppi_index, random_pool=None, random_count=100, random_seed=12345):
    source = random_pool if random_pool else path
    if source is None:
        raise ValueError("Provide --candidates or --candidate-pool for random selection")
    with source.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or ())
        if {"candidate_id", "candidate_name"} <= fields:
            id_field, name_field = "candidate_id", "candidate_name"
        elif {"drugbank_id", "drug_name"} <= fields:
            id_field, name_field = "drugbank_id", "drug_name"
        else:
            raise ValueError(f"{source}: expected candidate_id,candidate_name or drugbank_id,drug_name columns")
        if random_pool and id_field != "drugbank_id":
            raise ValueError("The random candidate pool must use DrugBank IDs")
        drugs = list(reader)
    ids = [r[id_field].strip() for r in drugs]
    if not ids or any(not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError(f"{source}: {id_field} values must be present and unique")
    for drug in drugs:
        drug_id = drug[id_field].strip()
        drug[id_field] = drug_id
        drug[name_field] = drug[name_field].strip()
        if not drug[name_field]:
            raise ValueError(f"{source}: {name_field} must be present for {drug_id}")
        drug["candidate_id"] = drug_id
        drug["candidate_name"] = drug[name_field]
        supplied = {g.strip() for g in drug.get("human_target_genes", "").split(";") if g.strip()}
        if supplied:
            genes = supplied
            target_source = (drug.get("target_source") or "candidate_file").strip() if id_field == "candidate_id" else "candidate_file"
        else:
            genes, target_source = target_map.get(drug_id, set()), "PrimeKG:drug_protein_target"
        drug["human_target_genes"] = ";".join(sorted(genes))
        drug["target_source"] = target_source if genes else "unmapped"
        drug["ppi_lcc_target_count"] = len(genes & ppi_index.keys())
    if random_pool:
        eligible = sorted((d for d in drugs if d["ppi_lcc_target_count"]), key=lambda d: d["candidate_id"])
        if len(eligible) < random_count:
            raise ValueError(f"Only {len(eligible)} target-mapped drugs in candidate pool; need {random_count}")
        drugs = sorted(random.Random(random_seed).sample(eligible, random_count), key=lambda d: d["candidate_id"])
        mode = "random_target_mapped"
    else:
        eligible = None
        drugs.sort(key=lambda d: d["candidate_id"])
        mode = "provided"
    return drugs, {"candidate_mode": mode, "candidate_source": str(source),
                   "candidate_id_field": id_field, "candidate_name_field": name_field,
                   "random_pool_eligible": len(eligible) if eligible is not None else None,
                   "random_count": random_count if random_pool else None,
                   "random_seed": random_seed if random_pool else None}


def bfs(graph, sources):
    distances = array("h", [-1]) * len(graph)
    queue = deque(sources)
    for source in sources:
        distances[source] = 0
    while queue:
        next_distance = distances[queue[0]] + 1
        for neighbor in graph[queue.popleft()]:
            if distances[neighbor] < 0:
                distances[neighbor] = next_distance
                queue.append(neighbor)
    return distances


def degree_bins(graph):
    groups = defaultdict(list)
    for node, neighbors in enumerate(graph):
        groups[len(neighbors)].append(node)
    bins, current = [], []
    for degree in sorted(groups):
        current.extend(groups[degree])
        if len(current) >= MIN_BIN:
            bins.append(np.array(current, dtype=np.int64))
            current = []
    if current:
        bins[-1] = np.concatenate((bins[-1], np.array(current, dtype=np.int64)))
    bin_of = np.empty(len(graph), dtype=np.int64)
    for b, members in enumerate(bins):
        bin_of[members] = b
    return bins, bin_of


def drug_seed(candidate_id):
    digest = hashlib.sha256(f"{SEED}:{candidate_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disease-id", help="Exact local ID, or an Open Targets disease ID if absent locally")
    parser.add_argument("--disease-name", help="Exact disease name; search local CSV first, then Open Targets")
    parser.add_argument("--efo-id", help="Pin Open Targets disease ID and use API even when the name matches locally")
    parser.add_argument("--disease-catalog", type=Path, required=True)
    parser.add_argument("--api-snapshot", type=Path, help="Previously saved Open Targets snapshot for offline reuse")
    parser.add_argument("--ppi", type=Path, required=True, help="PrimeKG prepared KG CSV containing protein_protein and drug_protein rows")
    parser.add_argument("--candidates", type=Path, help="Explicit list: candidate_id,candidate_name or legacy drugbank_id,drug_name; optionally human_target_genes")
    parser.add_argument("--candidate-pool", type=Path, help="DrugBank pool used only when --candidates is absent")
    parser.add_argument("--random-count", type=int, default=100)
    parser.add_argument("--random-seed", type=int, default=20261010)
    parser.add_argument("--max-pairs", type=int, default=100000,
                        help="Stop accidental all-DrugBank enumeration; increase explicitly for a larger run")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if bool(args.disease_id) == bool(args.disease_name):
        parser.error("Provide exactly one of --disease-id or --disease-name")
    if args.disease_id and args.efo_id:
        parser.error("--efo-id can only be combined with --disease-name")
    if args.random_count < 2:
        parser.error("--random-count must be at least 2")
    if args.max_pairs < 1:
        parser.error("--max-pairs must be positive")
    ppi_file = args.ppi.expanduser().resolve()
    disease_file = args.disease_catalog.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    graph, index, target_map, ppi_stats = read_ppi(ppi_file)
    print(f"PPI LCC: {ppi_stats['ppi_lcc_nodes']} nodes, {ppi_stats['ppi_lcc_edges']} edges", flush=True)
    candidate_file = args.candidates.expanduser().resolve() if args.candidates else None
    pool_file = args.candidate_pool.expanduser().resolve() if (not candidate_file and args.candidate_pool) else None
    if not candidate_file and not pool_file:
        standard_pool = ppi_file.parent.parent.parent.parent / "data" / "candidate_pool.csv"
        if standard_pool.is_file():
            pool_file = standard_pool.resolve()
        else:
            parser.error("No --candidates supplied and standard candidate pool was not found; pass --candidate-pool")
    drugs, candidate_meta = read_candidates(candidate_file, target_map, index, pool_file,
                                            args.random_count, args.random_seed)
    id_field = candidate_meta["candidate_id_field"]
    name_field = candidate_meta["candidate_name_field"]
    id_a, id_b = f"{id_field}_A", f"{id_field}_B"
    name_a, name_b = f"{name_field}_A", f"{name_field}_B"
    if len(drugs) < 2:
        parser.error("At least two candidate drugs are required to score a combination")
    requested_pairs = len(drugs) * (len(drugs) - 1) // 2
    if requested_pairs > args.max_pairs:
        parser.error(f"{len(drugs)} drugs form {requested_pairs} pairs, above --max-pairs={args.max_pairs}; narrow candidates or raise the limit")
    write_csv(output_dir / "candidate_drugs_selected.csv",
              [id_field, name_field, "human_target_genes", "target_source", "ppi_lcc_target_count"], drugs)
    local = None if args.efo_id else (read_disease(disease_file, disease_name=args.disease_name)
                                      if args.disease_name else read_disease(disease_file, disease_id=args.disease_id))
    if local:
        disease_name, disease_rows = local
        disease_id = disease_rows[0]["disease_id"]
        disease_meta = {"disease_source_mode": "local_exact_name" if args.disease_name else "local_id"}
    else:
        api_id = args.efo_id or args.disease_id
        disease_name, disease_rows, disease_meta = read_open_targets(args.disease_name, api_id,
                                                                       output_dir, args.api_snapshot)
        disease_id = disease_meta["api_disease_id"]
        disease_meta["disease_source_mode"] = "open_targets_pinned_id" if args.efo_id else "open_targets_api_fallback"
    if not disease_rows:
        raise ValueError(f"No usable disease genes for {disease_name}")
    print(f"Disease {disease_id} {disease_name}: {len(disease_rows)} association rows", flush=True)
    selected = []
    seen_genes = set()
    local_unscored_ppi = len({row["gene"].strip() for row in disease_rows
                              if row["ranking_score"] == "" and row["gene"].strip() in index}) if local else 0
    for row in disease_rows:
        if row["ranking_score"] == "":
            continue
        gene = row["gene"].strip()
        if gene in index and gene not in seen_genes:
            selected.append({**row, "rank": len(selected) + 1})
            seen_genes.add(gene)
        if len(selected) == 50:
            break
    if local and len(selected) < 20:
        api_name = args.disease_name or disease_name
        api_name, api_rows, api_meta = read_open_targets(api_name, args.efo_id, output_dir, args.api_snapshot)
        disease_meta.update(api_meta)
        disease_meta["disease_source_mode"] += "+open_targets_supplement"
        for row in api_rows:
            gene = row["gene"].strip()
            if gene in index and gene not in seen_genes:
                selected.append({**row, "rank": len(selected) + 1})
                seen_genes.add(gene)
            if len(selected) == 50:
                break
    if not selected:
        raise ValueError("No scored disease genes map to PPI LCC; unscored local rows cannot define ordered modules")
    k10, k50 = min(10, len(selected)), len(selected)
    write_csv(output_dir / "disease_genes_selected.csv",
              ["rank", "disease_id", "disease_name", "gene", "gene_id", "source",
               "ranking_score", "ranking_score_type", "genetic_score", "overall_score"], selected)
    print(f"Disease modules: t10={k10}, t50={k50}", flush=True)

    for drug in drugs:
        genes = [g.strip() for g in drug["human_target_genes"].split(";") if g.strip()]
        nodes = tuple(sorted({index[g] for g in genes if g in index}))
        drug["nodes"] = nodes
        drug["ppi_lcc_target_count"] = len(nodes)
        drug["ppi_lcc_target_genes"] = ";".join(sorted(set(g for g in genes if g in index)))
    bins, bin_of = degree_bins(graph)
    modules = {}
    for tag, k in (("t10", k10), ("t50", k50)):
        dist = np.asarray(bfs(graph, [index[row["gene"]] for row in selected[:k]]), dtype=float)
        bin_mean = np.array([dist[members].mean() for members in bins])
        bin_var = np.array([dist[members].var() for members in bins])
        modules[tag] = {"distance": dist, "bin_mean": bin_mean, "bin_var": bin_var}
    for drug in drugs:
        nodes = np.array(drug["nodes"], dtype=np.int64)
        for tag, module in modules.items():
            if len(nodes) == 0:
                drug[f"z_{tag}"] = None
                drug[f"dc_{tag}"] = None
                continue
            rng = np.random.default_rng(drug_seed(drug["candidate_id"]))
            sampled = np.empty((len(nodes), N_RANDOM), dtype=np.int64)
            for j, b in enumerate(bin_of[nodes]):
                members = bins[b]
                sampled[j] = members[rng.integers(0, len(members), N_RANDOM)]
            dc = float(module["distance"][nodes].mean())
            null = module["distance"][sampled].mean(axis=0)
            sd = float(null.std())
            drug[f"dc_{tag}"] = dc
            drug[f"z_{tag}"] = (dc - float(null.mean())) / sd if sd > 0 else None
    single_rows = [{id_field: d["candidate_id"], name_field: d["candidate_name"],
                    "ppi_lcc_target_count": d["ppi_lcc_target_count"],
                    "ppi_lcc_target_genes": d["ppi_lcc_target_genes"],
                    "dc_t10": d["dc_t10"], "prox_z_t10": d["z_t10"],
                    "dc_t50": d["dc_t50"], "prox_z_t50": d["z_t50"],
                    "network_status": "missing_targets_or_ppi" if not d["nodes"] else
                    ("zero_null_variance" if any(d[f"z_{tag}"] is None for tag in modules) else "ok")}
                   for d in drugs]
    write_csv(output_dir / "single_drug_network.csv", list(single_rows[0]), single_rows)
    print(f"PPI-mapped drugs: {sum(bool(d['nodes']) for d in drugs)}/{len(drugs)}", flush=True)

    used_targets = sorted(set(itertools.chain.from_iterable(d["nodes"] for d in drugs)))
    target_dist = {}
    for i, node in enumerate(used_targets, 1):
        target_dist[node] = bfs(graph, [node])
        if i % 50 == 0:
            print(f"Target shortest paths: {i}/{len(used_targets)}", flush=True)
    def internal(nodes):
        return mean(min(target_dist[x][y] for y in nodes if y != x) for x in nodes) if len(nodes) > 1 else 0.0
    def cross(a, b):
        return (sum(min(target_dist[x][y] for y in b) for x in a) +
                sum(min(target_dist[y][x] for x in a) for y in b)) / (len(a) + len(b))
    within = {d["candidate_id"]: internal(d["nodes"]) for d in drugs if d["nodes"]}
    pairs = []
    for a, b in itertools.combinations(drugs, 2):
        na, nb = a["nodes"], b["nodes"]
        row = {id_a: a["candidate_id"], name_a: a["candidate_name"],
               id_b: b["candidate_id"], name_b: b["candidate_name"],
               "n_target_A": len(na), "n_target_B": len(nb),
               "separation_eligible": int(len(na) >= 2 and len(nb) >= 2)}
        if not na or not nb:
            row["network_status"] = "missing_targets_or_ppi"
            row["selection_status"] = "missing_targets_or_ppi"
            pairs.append(row)
            continue
        if any(d[f"z_{tag}"] is None for d in (a, b) for tag in modules):
            row["network_status"] = "zero_null_variance"
            row["selection_status"] = "zero_null_variance"
            pairs.append(row)
            continue
        row["network_status"] = "ok"
        s = cross(na, nb) - (within[a["candidate_id"]] + within[b["candidate_id"]]) / 2
        row["s_AB"] = s
        # For one target, the within-drug distance is conventionally zero and
        # positive separation is nearly automatic for distinct singleton targets.
        separation_eligible = bool(row["separation_eligible"])
        union = np.array(sorted(set(na) | set(nb)), dtype=np.int64)
        for tag, module in modules.items():
            za, zb = a[f"z_{tag}"], b[f"z_{tag}"]
            dist, bm, bv = module["distance"], module["bin_mean"], module["bin_var"]
            mu = bm[bin_of[union]].mean()
            var = bv[bin_of[union]].mean() / len(union)
            if var <= 0:
                row["network_status"] = "zero_null_variance"
                break
            zu = float((dist[union].mean() - mu) / math.sqrt(var))
            row[f"prox_z_A_{tag}"] = za
            row[f"prox_z_B_{tag}"] = zb
            row[f"prox_z_AB_{tag}"] = zu
            row[f"comp_exposure_{tag}"] = int(separation_eligible and s > 0 and za < 0 and zb < 0)
        if row["network_status"] != "ok":
            row["selection_status"] = row["network_status"]
            pairs.append(row)
            continue
        per_drug = mean(row[f"prox_z_{side}_{tag}"] for tag in ("t10", "t50") for side in ("A", "B"))
        union_z = mean(row[f"prox_z_AB_{tag}"] for tag in ("t10", "t50"))
        row["network_score"] = -(per_drug + union_z) / 2
        row["eligible_pair"] = int(bool(row["comp_exposure_t10"] and row["comp_exposure_t50"]))
        reasons = []
        if not separation_eligible:
            reasons.append("ppi_targets_lt2")
        if s <= 0:
            reasons.append("s_ab_nonpositive")
        for tag in ("t10", "t50"):
            if a[f"z_{tag}"] >= 0 or b[f"z_{tag}"] >= 0:
                reasons.append(f"not_proximal_{tag}")
        row["selection_status"] = ";".join(reasons) if reasons else "eligible"
        row["both_significant"] = int(all(row[f"prox_z_{side}_{tag}"] < -1.64
                                           for tag in ("t10", "t50") for side in ("A", "B")))
        pairs.append(row)
    eligible = sorted((p for p in pairs if p.get("eligible_pair")),
                      key=lambda x: (-x["network_score"], x[id_a], x[id_b]))
    for rank, row in enumerate(eligible, 1):
        row["rank"] = rank
    ranked_fields = ["rank", "network_score", "both_significant", id_a, name_a,
                     id_b, name_b, "n_target_A", "n_target_B", "s_AB",
                     "separation_eligible",
                     "prox_z_A_t10", "prox_z_B_t10", "prox_z_AB_t10", "comp_exposure_t10",
                     "prox_z_A_t50", "prox_z_B_t50", "prox_z_AB_t50", "comp_exposure_t50",
                     "eligible_pair", "network_status"]
    if id_field == "candidate_id":
        ranked_fields.append("selection_status")
    write_csv(output_dir / "ranked_pairs.csv", ranked_fields, eligible)
    pairs.sort(key=lambda x: (x.get("rank", math.inf), x[id_a], x[id_b]))
    write_csv(output_dir / "all_pair_metrics.csv", ranked_fields, pairs)

    summary = {"disease_id": disease_id, "disease_name": disease_name,
               "method_version": "network_v2",
               "script_sha256": sha256(Path(__file__).resolve()),
               **disease_meta,
               "disease_input_rows": len(disease_rows),
               "local_unscored_genes_in_ppi_lcc": local_unscored_ppi,
               "disease_scored_genes_selected": len(selected),
               "disease_source_counts": dict(Counter(row["source"] for row in selected)),
               "disease_genes_in_ppi_lcc": len({r["gene"] for r in disease_rows if r["gene"] in index}),
               "module_t10_actual": k10, "module_t50_actual": k50,
               **ppi_stats, **candidate_meta, "candidate_drugs": len(drugs),
               "ppi_mapped_drugs": sum(bool(d["nodes"]) for d in drugs),
               "pairs_all": len(pairs), "pairs_scorable": sum(p["network_status"] == "ok" for p in pairs),
               "pairs_separation_eligible": sum(p.get("separation_eligible", 0) for p in pairs),
               "P2_t10": sum(p.get("comp_exposure_t10", 0) for p in pairs),
               "P2_t50": sum(p.get("comp_exposure_t50", 0) for p in pairs),
               "eligible_pairs": len(eligible),
               "both_significant_eligible": sum(p["both_significant"] for p in eligible),
               "selection": "both drugs have >=2 PPI targets; s_AB>0 and z_A,z_B<0 in both t10 and t50; rank network_score descending",
               "score_formula": "network_score=-((zA10+zB10+zA50+zB50)/4+(zAB10+zAB50)/2)/2",
               "parameters": {"n_random": N_RANDOM, "min_degree_bin": MIN_BIN,
                              "proximity_seed": f"first_64_bits_sha256(12345:{id_field})",
                              "min_separation_targets_per_drug": 2, "significant_z": -1.64,
                              "max_pairs": args.max_pairs},
               "ppi_path": str(ppi_file),
               "input_sha256": {str(p): sha256(p) for p in (disease_file, ppi_file, Path(candidate_meta["candidate_source"]))},
               "created_utc": datetime.now(timezone.utc).isoformat(),
               "meaning": "network ranking only, not clinical efficacy or measured drug synergy"}
    if disease_meta.get("api_snapshot_path"):
        snapshot_path = Path(disease_meta["api_snapshot_path"])
        summary["input_sha256"][str(snapshot_path)] = sha256(snapshot_path)
    (output_dir / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
