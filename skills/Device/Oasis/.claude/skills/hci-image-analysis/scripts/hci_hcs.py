#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backends import cellprofiler_backend, cellpose_backend, skimage_backend  # noqa: E402


SOFTWARE_MEASUREMENT = "Positive W2 Mean Cyto Integr Intens (MultiWaveScoring)"
DEFAULT_WELLS = [f"{row}{col:02d}" for row in "BCDEFG" for col in range(2, 12)]
DEFAULT_CP_PIPELINE = ROOT / "assets" / "cellprofiler" / "default_positive_w2.cppipe"
CP_LOADDATA_NAME = "cp_loaddata.csv"


def parse_wells(value: str | None) -> set[str] | None:
    if not value:
        return None
    return {x.strip().upper() for x in value.split(",") if x.strip()}


def cmd_prepare(args: argparse.Namespace) -> None:
    image_root = Path(args.image_root)
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    wells = parse_wells(args.wells) or set(DEFAULT_WELLS)
    position_map = _read_position_map(Path(args.position_map), args.plate_map_sheet) if args.position_map else {}
    pattern = re.compile(r"_([A-H][0-9]{2})_s([0-9]+)_w([12])", re.I)
    grouped: dict[tuple[str, str, str, str], dict[str, Path]] = {}
    for tif in image_root.rglob("*.tif"):
        if "thumb" in tif.name.lower():
            continue
        m = pattern.search(tif.name)
        if not m:
            continue
        well, site, channel = m.group(1).upper(), m.group(2), m.group(3)
        if well not in wells:
            continue
        acquisition = _infer_acquisition(image_root, tif)
        experiment = _infer_experiment(tif.name, well)
        grouped.setdefault((experiment, acquisition, well, site), {})[channel] = tif

    rows = []
    for (experiment, acq, well, site), channels in sorted(grouped.items()):
        if "1" not in channels or "2" not in channels:
            continue
        row = {
            "experiment": experiment,
            "acquisition": acq,
            **_parse_acquisition_name(experiment),
            "well": well,
            "site": site,
            "group": _group_for_well(well, args.group_mode),
            "nucleus_path": str(channels["1"]),
            "marker_path": str(channels["2"]),
        }
        row.update(_lookup_position_map(position_map, acq, well))
        if not row.get("group"):
            row["group"] = _group_for_well(well, args.group_mode)
        rows.append(row)
    if not rows:
        raise SystemExit(f"No W1/W2 image pairs found under {image_root}")
    manifest_path = outdir / "manifest.csv"
    _write_csv(manifest_path, rows)
    _write_cp_loaddata(manifest_path, outdir / CP_LOADDATA_NAME)
    (outdir / "run_manifest.json").write_text(
        json.dumps(
            {
                "image_root": str(image_root),
                "image_sets": len(rows),
                "group_mode": args.group_mode,
                "position_map": str(args.position_map) if args.position_map else None,
                "cellprofiler_loaddata": str(outdir / CP_LOADDATA_NAME),
            },
            indent=2,
        )
    )
    print(f"wrote {outdir / 'manifest.csv'} ({len(rows)} image sets)")


def _infer_acquisition(root: Path, tif: Path) -> str:
    rel = tif.relative_to(root)
    parts = rel.parts
    if "TimePoint_1" in parts:
        idx = parts.index("TimePoint_1")
        return parts[idx - 1] if idx >= 1 else root.name
    if len(parts) >= 2:
        return parts[0]
    return root.name


def _infer_experiment(filename: str, well: str) -> str:
    marker = f"_{well}_"
    if marker in filename:
        return filename.split(marker, 1)[0]
    return filename.split(f"_{well}", 1)[0] if f"_{well}" in filename else ""


def _group_for_well(well: str, mode: str) -> str:
    if mode == "bc":
        if well.startswith("B"):
            return "control"
        if well.startswith("C"):
            return "model"
        return "treat"
    if mode == "bodipy0513":
        if well.startswith("B"):
            return "BSA"
        if well.startswith("C"):
            return "FM"
        return "drug"
    return ""


def _parse_acquisition_name(acquisition: str) -> dict[str, str]:
    parts = acquisition.split()
    meta = {"date_batch": "", "plate_repeat": "", "treatment_set": ""}
    if len(parts) >= 1:
        meta["date_batch"] = parts[0]
    if len(parts) >= 2:
        meta["plate_repeat"] = parts[1]
    if len(parts) >= 3:
        meta["treatment_set"] = parts[2]
    return meta


def _read_position_map(path: Path, sheet: str | None = None) -> dict[tuple[str, str], dict[str, object]]:
    if not path.exists():
        raise SystemExit(f"Position map not found: {path}")
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path, sheet_name=sheet or 0)
    else:
        sep = "\t" if path.suffix.lower() in {".tsv", ".tab"} else ","
        df = pd.read_csv(path, sep=sep)
    if df.empty:
        raise SystemExit(f"Position map is empty: {path}")

    original_columns = list(df.columns)
    normalized = {_normalize_column(c): c for c in original_columns}
    well_col = None
    for candidate in ["well", "孔位", "position", "位置"]:
        key = _normalize_column(candidate)
        if key in normalized:
            well_col = normalized[key]
            break
    if well_col is None:
        raise SystemExit("Position map must contain a well/孔位 column")

    df = df.rename(columns={c: _normalize_column(c) for c in df.columns})
    if _normalize_column(well_col) != "well":
        df = df.rename(columns={_normalize_column(well_col): "well"})

    mapping: dict[tuple[str, str], dict[str, object]] = {}
    for _, row in df.iterrows():
        well = str(row.get("well", "")).strip().upper()
        if not re.fullmatch(r"[A-H][0-9]{2}", well):
            continue
        acquisition_value = row.get("acquisition", "")
        acquisition = "" if pd.isna(acquisition_value) else str(acquisition_value).strip()
        meta = {}
        for col, value in row.items():
            if col == "well" or pd.isna(value):
                continue
            if isinstance(value, str):
                value = value.strip()
                if value == "":
                    continue
            meta[col] = value
        mapping[(acquisition, well)] = meta
    return mapping


def _lookup_position_map(mapping: dict[tuple[str, str], dict[str, object]], acquisition: str, well: str) -> dict[str, object]:
    if not mapping:
        return {}
    return dict(mapping.get((acquisition, well), mapping.get(("", well), {})))


def _write_cp_loaddata(manifest: Path, out_csv: Path) -> None:
    frame = pd.read_csv(manifest, dtype=str)
    rows = []
    for _, row in frame.iterrows():
        nucleus = Path(row["nucleus_path"])
        marker = Path(row["marker_path"])
        rows.append(
            {
                "Image_FileName_DNA": nucleus.name,
                "Image_PathName_DNA": str(nucleus.parent),
                "Image_FileName_Marker": marker.name,
                "Image_PathName_Marker": str(marker.parent),
                "Metadata_Acquisition": row.get("acquisition", ""),
                "Metadata_Well": row.get("well", ""),
                "Metadata_Site": row.get("site", ""),
            }
        )
    _write_csv(out_csv, rows)


def _materialize_cp_pipeline(template: Path, outdir: Path) -> Path:
    if not template.exists():
        raise SystemExit(f"Default CellProfiler pipeline not found: {template}")
    loaddata = outdir / CP_LOADDATA_NAME
    if not loaddata.exists():
        raise SystemExit(f"CellProfiler LoadData CSV not found: {loaddata}. Run prepare first or pass the matching manifest.")
    text = template.read_text()
    text = re.sub(
        r"(\s*)Input data file location:Elsewhere\.\.\.\|.*",
        lambda match: f"{match.group(1)}Input data file location:Elsewhere...|{outdir}",
        text,
    )
    text = re.sub(r"(\s*)Name of the file:.*", rf"\1Name of the file:{CP_LOADDATA_NAME}", text)
    runtime = outdir / "runtime_default_positive_w2.cppipe"
    runtime.write_text(text)
    return runtime


def _normalize_column(name: object) -> str:
    value = str(name).strip().lower()
    value = re.sub(r"[^0-9a-zA-Z_\u4e00-\u9fff]+", "_", value)
    return value.strip("_")


def cmd_run(args: argparse.Namespace) -> None:
    wells = parse_wells(args.wells)
    if args.backend == "skimage":
        skimage_backend.run(Path(args.manifest), Path(args.out), wells=wells)
    elif args.backend == "cellpose":
        cellpose_backend.run(Path(args.manifest), Path(args.out), wells=wells)
    elif args.backend == "cellprofiler":
        outdir = Path(args.out)
        outdir.mkdir(parents=True, exist_ok=True)
        _write_cp_loaddata(Path(args.manifest), outdir / CP_LOADDATA_NAME)
        pipeline = Path(args.pipeline) if args.pipeline else _materialize_cp_pipeline(DEFAULT_CP_PIPELINE, outdir)
        subprocess.run(
            [args.cellprofiler_bin, "-c", "-r", "-p", str(pipeline), "-o", str(outdir)],
            check=True,
        )
        cellprofiler_backend.score(outdir, outdir, manifest=Path(args.manifest))
    print(f"wrote backend outputs to {args.out}")


def cmd_score(args: argparse.Namespace) -> None:
    if args.backend != "cellprofiler":
        src = Path(args.input)
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        for name in ["per_site_metrics.csv", "per_well_metrics.csv", "object_metrics.csv"]:
            p = src / name
            if p.exists():
                (out / name).write_text(p.read_text())
        print(f"copied {args.backend} score tables to {out}")
        return
    cellprofiler_backend.score(Path(args.input), Path(args.out), manifest=Path(args.manifest) if args.manifest else None)
    print(f"wrote CellProfiler score tables to {args.out}")


def cmd_compare_backends(args: argparse.Namespace) -> None:
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    frames = []
    for input_dir in args.inputs:
        p = Path(input_dir) / "per_well_metrics.csv"
        if not p.exists():
            continue
        frames.append(pd.read_csv(p))
    if not frames:
        raise SystemExit("No per_well_metrics.csv files found in --inputs")
    all_rows = pd.concat(frames, ignore_index=True)
    all_rows.to_csv(outdir / "backend_per_well_long.csv", index=False)

    rows = []
    metrics = ["mean_integr", "per_area", "total_integr", "cell_count"]
    for metric in metrics:
        pivot = all_rows.pivot_table(index=["acquisition", "well"], columns="backend", values=metric, aggfunc="mean")
        for a in pivot.columns:
            for b in pivot.columns:
                if a >= b:
                    continue
                valid = pivot[[a, b]].dropna()
                rows.append(
                    {
                        "metric": metric,
                        "backend_a": a,
                        "backend_b": b,
                        "n": len(valid),
                        "pearson": valid[a].corr(valid[b]) if len(valid) > 1 else math.nan,
                        "median_ratio_a_over_b": (valid[a] / valid[b]).replace([np.inf, -np.inf], np.nan).median() if len(valid) else math.nan,
                    }
                )
    pd.DataFrame(rows).to_csv(outdir / "backend_comparison.csv", index=False)
    print(f"wrote backend comparison to {outdir}")


def cmd_compare_software(args: argparse.Namespace) -> None:
    scores = pd.read_csv(args.scores)
    software = extract_software(Path(args.software_root))
    merged = scores.merge(software, on=["acquisition", "well", "group"], how="left")
    metric_cols = [
        c
        for c in [
            "mean_integr",
            "top50_integr_mean",
            "integr_p95",
            "integr_p98",
            "calibrated_integr_p95_1p25",
            "calibrated_integr_p95_1p30",
            "per_area",
        ]
        if c in merged.columns
    ]
    rows = []
    for col in metric_cols:
        rows.append(_summary(merged, col))
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    merged.to_csv(outdir / "software_comparison_per_well.csv", index=False)
    pd.DataFrame(rows).to_csv(outdir / "software_comparison_summary.csv", index=False)
    print(f"wrote software comparison to {outdir}")


def extract_software(root: Path) -> pd.DataFrame:
    rows = []
    for xlsx in sorted(root.rglob("*.xlsx")):
        if xlsx.name.startswith(".~"):
            continue
        try:
            df = pd.read_excel(xlsx, sheet_name="cyto intensity", header=None)
        except Exception:
            continue
        matches = df.index[df.iloc[:, 1].astype(str).eq(SOFTWARE_MEASUREMENT)].tolist()
        if len(matches) != 1:
            continue
        acquisition = xlsx.parent.name
        start = matches[0]
        for row_label in list("BCDEFG"):
            row_idx = None
            for i in range(start + 2, min(start + 10, len(df))):
                if str(df.iat[i, 0]) == row_label:
                    row_idx = i
                    break
            if row_idx is None:
                continue
            for col in range(2, 12):
                rows.append(
                    {
                        "acquisition": acquisition,
                        "well": f"{row_label}{col:02d}",
                        "group": _group_for_well(f"{row_label}{col:02d}", "bc"),
                        "software_value": float(df.iat[row_idx, col]) if pd.notna(df.iat[row_idx, col]) else math.nan,
                    }
                )
    if not rows:
        raise SystemExit(f"No software measurement blocks found under {root}")
    return pd.DataFrame(rows)


def _summary(df: pd.DataFrame, col: str) -> dict[str, object]:
    valid = df.dropna(subset=[col, "software_value"]).copy()
    pos = valid[(valid[col] > 0) & (valid["software_value"] > 0)]
    control = valid[valid["group"].eq("control")]
    model = valid[valid["group"].eq("model")]
    cp_cb = model[col].mean() / control[col].mean() if len(model) and len(control) else math.nan
    sw_cb = model["software_value"].mean() / control["software_value"].mean() if len(model) and len(control) else math.nan
    return {
        "method": col,
        "n": len(valid),
        "raw_pearson": valid[col].corr(valid["software_value"]) if len(valid) > 1 else math.nan,
        "log10_pearson": np.log10(pos[col]).corr(np.log10(pos["software_value"])) if len(pos) > 1 else math.nan,
        "spearman": valid[col].rank().corr(valid["software_value"].rank()) if len(valid) > 1 else math.nan,
        "cp_C_over_B": cp_cb,
        "software_C_over_B": sw_cb,
        "cb_abs_error": abs(cp_cb - sw_cb) if not math.isnan(cp_cb) and not math.isnan(sw_cb) else math.nan,
    }


def cmd_qc_report(args: argparse.Namespace) -> None:
    scores = pd.read_csv(args.scores)
    flags = []
    for _, row in scores.iterrows():
        reasons = []
        if float(row.get("site_cv", 0) or 0) > args.site_cv_threshold:
            reasons.append("site_cv_gt_threshold")
        if "cell_count" in row and pd.notna(row["cell_count"]) and float(row["cell_count"]) < args.min_cell_count:
            reasons.append("low_cell_count")
        if "n_measured" in row and pd.notna(row["n_measured"]) and float(row["n_measured"]) <= 0:
            reasons.append("no_measured_objects")
        if reasons:
            flags.append({**row.to_dict(), "qc_reasons": ";".join(reasons)})
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(flags).to_csv(outdir / "qc_flags.csv", index=False)
    print(f"wrote {len(flags)} QC flags to {outdir / 'qc_flags.csv'}")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(prog="hci-hcs")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("prepare")
    p.add_argument("--image-root", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--wells")
    p.add_argument("--group-mode", choices=["bc", "bodipy0513", "none"], default="bc", help="Fallback plate grouping rule when no position map group is provided")
    p.add_argument("--position-map", "--plate-map", dest="position_map", help="Optional CSV/XLSX with at least a well column; extra columns such as compound/dose/replicate are preserved")
    p.add_argument("--plate-map-sheet", help="Optional sheet name for an Excel position map")
    p.set_defaults(func=cmd_prepare)

    p = sub.add_parser("run")
    p.add_argument("--backend", choices=["cellprofiler", "skimage", "cellpose"], required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--wells")
    p.add_argument("--pipeline", help="Optional CellProfiler .cppipe file. If omitted, uses assets/cellprofiler/default_positive_w2.cppipe")
    p.add_argument("--cellprofiler-bin", default="cellprofiler")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("score")
    p.add_argument("--backend", choices=["cellprofiler", "skimage", "cellpose"], required=True)
    p.add_argument("--input", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--manifest", help="Optional manifest.csv used to restore group/compound/dose metadata for CellProfiler scores")
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("compare-backends")
    p.add_argument("--inputs", nargs="+", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_compare_backends)

    p = sub.add_parser("compare-software")
    p.add_argument("--scores", required=True)
    p.add_argument("--software-root", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_compare_software)

    p = sub.add_parser("qc-report")
    p.add_argument("--scores", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--site-cv-threshold", type=float, default=0.5)
    p.add_argument("--min-cell-count", type=float, default=50)
    p.set_defaults(func=cmd_qc_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
