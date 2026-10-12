from __future__ import annotations

import csv
import math
import os
from collections import defaultdict
from pathlib import Path

import numpy as np
import tifffile
from scipy import ndimage as ndi
from skimage.filters import gaussian, threshold_otsu
from skimage.segmentation import watershed
from skimage.transform import resize


MAX_CELL_AREA = 15000
GPU = os.environ.get("HCI_CELLPOSE_GPU", "0").lower() in {"1", "true", "yes", "on"}
DOWNSAMPLE = 2
DIAMETER = 35
FLOW_THRESH = 0.4
CELLPROB_THRESH = 0.0
_MODEL = None


MANIFEST_PATH_COLUMNS = {"nucleus_path", "marker_path"}


def _manifest_metadata(row: dict[str, str]) -> dict[str, object]:
    return {k: v for k, v in row.items() if k not in MANIFEST_PATH_COLUMNS}


def _model():
    global _MODEL
    if _MODEL is None:
        try:
            from cellpose import models
        except ImportError as exc:
            raise RuntimeError("cellpose is not installed in this Python environment. Activate the cellpose conda env.") from exc
        _MODEL = models.CellposeModel(gpu=GPU)
    return _MODEL


def _segment(img: np.ndarray) -> np.ndarray:
    h, w = img.shape
    small = img if DOWNSAMPLE == 1 else resize(img, (h // DOWNSAMPLE, w // DOWNSAMPLE), order=1, preserve_range=True)
    result = _model().eval(
        small,
        diameter=DIAMETER,
        flow_threshold=FLOW_THRESH,
        cellprob_threshold=CELLPROB_THRESH,
        normalize=True,
    )
    masks = result[0].astype(np.int32)
    if DOWNSAMPLE != 1:
        masks = resize(masks, (h, w), order=0, preserve_range=True, anti_aliasing=False).astype(np.int32)
    return masks


def _read_manifest(manifest: Path, wells: set[str] | None = None) -> list[dict[str, str]]:
    with manifest.open() as f:
        rows = list(csv.DictReader(f))
    if wells:
        rows = [r for r in rows if r["well"] in wells]
    return rows


def analyze_site(nucleus_path: Path, marker_path: Path) -> tuple[int, list[dict[str, float]]]:
    w1 = tifffile.imread(nucleus_path).astype(np.float32)
    w2 = tifffile.imread(marker_path).astype(np.float32)
    nuclei = _segment(w1)
    cell_count = int(nuclei.max())
    nb = nuclei > 0
    smooth = gaussian(w2, 2, preserve_range=True)
    marker_fg = smooth > threshold_otsu(smooth)
    cells = watershed(-smooth, nuclei, mask=(marker_fg | nb))

    objects = []
    slices = ndi.find_objects(cells)
    for label in range(1, cell_count + 1):
        sl = slices[label - 1] if label - 1 < len(slices) else None
        if sl is None:
            continue
        cyto = (cells[sl] == label) & ~(nuclei[sl] == label)
        area = int(cyto.sum())
        if area == 0:
            continue
        objects.append({"object_number": label, "integr_raw": float(w2[sl][cyto].sum()), "area": area})
    return cell_count, objects


def run(manifest: Path, outdir: Path, wells: set[str] | None = None) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    site_rows: list[dict[str, object]] = []
    object_rows: list[dict[str, object]] = []
    for r in _read_manifest(manifest, wells):
        cell_count, objects = analyze_site(Path(r["nucleus_path"]), Path(r["marker_path"]))
        integr = np.array([o["integr_raw"] for o in objects], dtype=float)
        area = np.array([o["area"] for o in objects], dtype=float)
        keep = area <= MAX_CELL_AREA if len(area) else np.array([], dtype=bool)
        kept_integr = integr[keep] if keep.any() else integr
        total_integr = float(integr.sum()) if len(integr) else math.nan
        total_area = float(area.sum()) if len(area) else math.nan
        site_rows.append(
            {
                **_manifest_metadata(r),
                "acquisition": r.get("acquisition", ""),
                "well": r["well"],
                "site": r["site"],
                "group": r.get("group") or ("control" if r["well"].startswith("B") else "model"),
                "cell_count": cell_count,
                "n_measured": len(objects),
                "mean_integr": float(kept_integr.mean()) if len(kept_integr) else math.nan,
                "total_integr": total_integr,
                "total_area": total_area,
                "per_area": total_integr / total_area if total_area and not math.isnan(total_area) else math.nan,
                "site_cv": math.nan,
                "backend": "cellpose",
            }
        )
        for o in objects:
            object_rows.append({**r, **o, "backend": "cellpose"})

    _write_outputs(outdir, site_rows, object_rows)


def _write_outputs(outdir: Path, site_rows: list[dict[str, object]], object_rows: list[dict[str, object]]) -> None:
    well_map: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in site_rows:
        well_map[(str(row["acquisition"]), str(row["well"]))].append(row)
    for rows in well_map.values():
        values = np.array([float(r["mean_integr"]) for r in rows if not math.isnan(float(r["mean_integr"]))])
        cv = float(np.std(values, ddof=1) / np.mean(values)) if len(values) > 1 and np.mean(values) else 0.0
        for r in rows:
            r["site_cv"] = cv

    well_rows = []
    for (acq, well), rows in sorted(well_map.items()):
        values = [float(r["mean_integr"]) for r in rows if not math.isnan(float(r["mean_integr"]))]
        totals = [float(r["total_integr"]) for r in rows if not math.isnan(float(r["total_integr"]))]
        areas = [float(r["total_area"]) for r in rows if not math.isnan(float(r["total_area"]))]
        total_integr = float(np.mean(totals)) if totals else math.nan
        total_area = float(np.mean(areas)) if areas else math.nan
        well_meta = {k: v for k, v in rows[0].items() if k not in {"site", "cell_count", "n_measured", "mean_integr", "total_integr", "total_area", "per_area", "site_cv", "backend"}} if rows else {}
        well_rows.append(
            {
                **well_meta,
                "acquisition": acq,
                "well": well,
                "site": "well_mean",
                "group": rows[0].get("group") if rows and rows[0].get("group") else ("control" if well.startswith("B") else "model"),
                "cell_count": float(np.mean([float(r["cell_count"]) for r in rows])),
                "n_measured": float(np.sum([float(r["n_measured"]) for r in rows])),
                "mean_integr": float(np.mean(values)) if values else math.nan,
                "total_integr": total_integr,
                "total_area": total_area,
                "per_area": total_integr / total_area if total_area and not math.isnan(total_area) else math.nan,
                "site_cv": rows[0]["site_cv"],
                "backend": "cellpose",
            }
        )

    _write_csv(outdir / "per_site_metrics.csv", site_rows)
    _write_csv(outdir / "per_well_metrics.csv", well_rows)
    _write_csv(outdir / "object_metrics.csv", object_rows)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as f:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

