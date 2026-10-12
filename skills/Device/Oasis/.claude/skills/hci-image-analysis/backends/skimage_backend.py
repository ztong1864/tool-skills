from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import tifffile
from scipy import ndimage as ndi
from skimage.feature import peak_local_max
from skimage.filters import gaussian, threshold_otsu
from skimage.morphology import remove_small_holes, remove_small_objects
from skimage.segmentation import watershed


NUC_SIGMA = 2
NUC_MIN_DIST = 18
NUC_MIN_AREA = 150
NUC_FILL_HOLE = 200
CELL_SIGMA = 2
MAX_CELL_AREA = 15000


MANIFEST_PATH_COLUMNS = {"nucleus_path", "marker_path"}


def _manifest_metadata(row: dict[str, str]) -> dict[str, object]:
    return {k: v for k, v in row.items() if k not in MANIFEST_PATH_COLUMNS}


def _read_manifest(manifest: Path, wells: set[str] | None = None) -> list[dict[str, str]]:
    with manifest.open() as f:
        rows = list(csv.DictReader(f))
    if wells:
        rows = [r for r in rows if r["well"] in wells]
    return rows


def _foreground(img: np.ndarray, sigma: float) -> tuple[np.ndarray, np.ndarray]:
    smooth = gaussian(img, sigma, preserve_range=True)
    return smooth > threshold_otsu(smooth), smooth


def analyze_site(nucleus_path: Path, marker_path: Path) -> tuple[int, list[dict[str, float]]]:
    w1 = tifffile.imread(nucleus_path).astype(np.float32)
    w2 = tifffile.imread(marker_path).astype(np.float32)

    nuclei_bin, _ = _foreground(w1, NUC_SIGMA)
    nuclei_bin = remove_small_holes(nuclei_bin, NUC_FILL_HOLE)
    nuclei_bin = remove_small_objects(nuclei_bin, NUC_MIN_AREA)
    dist = ndi.distance_transform_edt(nuclei_bin)
    coords = peak_local_max(dist, min_distance=NUC_MIN_DIST, labels=nuclei_bin)
    marker_img = np.zeros(dist.shape, bool)
    if len(coords):
        marker_img[tuple(coords.T)] = True
    markers, _ = ndi.label(marker_img)
    nuclei = watershed(-dist, markers, mask=nuclei_bin)
    cell_count = int(nuclei.max())

    marker_fg, marker_smooth = _foreground(w2, CELL_SIGMA)
    cells = watershed(-marker_smooth, nuclei, mask=(marker_fg | nuclei_bin))
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
        integr = float(w2[sl][cyto].sum())
        objects.append({"object_number": label, "integr_raw": integr, "area": area})
    return cell_count, objects


def run(manifest: Path, outdir: Path, wells: set[str] | None = None) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    rows = _read_manifest(manifest, wells)
    site_rows: list[dict[str, object]] = []
    object_rows: list[dict[str, object]] = []
    for r in rows:
        cell_count, objects = analyze_site(Path(r["nucleus_path"]), Path(r["marker_path"]))
        integr = np.array([o["integr_raw"] for o in objects], dtype=float)
        area = np.array([o["area"] for o in objects], dtype=float)
        keep = area <= MAX_CELL_AREA if len(area) else np.array([], dtype=bool)
        kept_integr = integr[keep] if keep.any() else integr
        kept_area = area[keep] if keep.any() else area
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
                "backend": "skimage",
            }
        )
        for o in objects:
            object_rows.append({**r, **o, "backend": "skimage"})

    _write_outputs(outdir, site_rows, object_rows, "skimage")


def _write_outputs(outdir: Path, site_rows: list[dict[str, object]], object_rows: list[dict[str, object]], backend: str) -> None:
    well_map: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in site_rows:
        well_map[(str(row["acquisition"]), str(row["well"]))].append(row)
    for (acq, well), rows in well_map.items():
        values = np.array([float(r["mean_integr"]) for r in rows if not math.isnan(float(r["mean_integr"]))])
        cv = float(np.std(values, ddof=1) / np.mean(values)) if len(values) > 1 and np.mean(values) else 0.0
        for r in rows:
            r["site_cv"] = cv

    well_rows = []
    for (acq, well), rows in sorted(well_map.items()):
        values = [float(r["mean_integr"]) for r in rows if not math.isnan(float(r["mean_integr"]))]
        totals = [float(r["total_integr"]) for r in rows if not math.isnan(float(r["total_integr"]))]
        areas = [float(r["total_area"]) for r in rows if not math.isnan(float(r["total_area"]))]
        cell_counts = [float(r["cell_count"]) for r in rows]
        n_measured = [float(r["n_measured"]) for r in rows]
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
                "cell_count": float(np.mean(cell_counts)) if cell_counts else math.nan,
                "n_measured": float(np.sum(n_measured)) if n_measured else math.nan,
                "mean_integr": float(np.mean(values)) if values else math.nan,
                "total_integr": total_integr,
                "total_area": total_area,
                "per_area": total_integr / total_area if total_area and not math.isnan(total_area) else math.nan,
                "site_cv": rows[0]["site_cv"] if rows else math.nan,
                "backend": backend,
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

