from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd


MAX_CELL_AREA = 15000.0
MANIFEST_PATH_COLUMNS = {"nucleus_path", "marker_path"}
CORE_METADATA_COLUMNS = {"acquisition", "well", "site"}


def _cp_dirs(root: Path) -> list[Path]:
    if (root / "MyExpt_Image.csv").exists() and (root / "MyExpt_Cytoplasm.csv").exists():
        return [root]
    return sorted(p for p in root.iterdir() if p.is_dir() and (p / "MyExpt_Image.csv").exists() and (p / "MyExpt_Cytoplasm.csv").exists())


def _manifest_metadata(manifest: Path | None) -> tuple[pd.DataFrame, list[str]]:
    if manifest is None:
        return pd.DataFrame(), []
    meta = pd.read_csv(manifest)
    if meta.empty:
        return pd.DataFrame(), []
    drop_cols = [c for c in MANIFEST_PATH_COLUMNS if c in meta.columns]
    meta = meta.drop(columns=drop_cols)
    for col in ["acquisition", "well", "site"]:
        if col not in meta.columns:
            raise RuntimeError(f"{manifest} missing {col}")
        meta[col] = meta[col].astype(str)
    metadata_cols = [c for c in meta.columns if c not in CORE_METADATA_COLUMNS]
    return meta.drop_duplicates(subset=["acquisition", "well", "site"]), metadata_cols


def _fallback_group(well: object) -> str:
    well = str(well)
    if well.startswith("B"):
        return "control"
    if well.startswith("C"):
        return "model"
    return "treat"


def _merge_manifest(obj: pd.DataFrame, manifest_meta: pd.DataFrame) -> pd.DataFrame:
    if manifest_meta.empty:
        return obj
    merged = obj.merge(manifest_meta, on=["acquisition", "well", "site"], how="left")
    if bool(merged["group"].isna().all()) if "group" in merged.columns else False:
        well_meta = manifest_meta.drop(columns=["site"]).drop_duplicates(subset=["acquisition", "well"])
        merged = obj.merge(well_meta, on=["acquisition", "well"], how="left")
    return merged


def score(input_dir: Path, outdir: Path, manifest: Path | None = None) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    manifest_meta, metadata_cols = _manifest_metadata(manifest)
    site_rows = []
    object_rows = []
    for cp_dir in _cp_dirs(input_dir):
        image = pd.read_csv(cp_dir / "MyExpt_Image.csv")
        cyt = pd.read_csv(cp_dir / "MyExpt_Cytoplasm.csv")
        required = ["ImageNumber", "Metadata_Well", "Metadata_Site"]
        for col in required:
            if col not in image.columns:
                raise RuntimeError(f"{cp_dir}/MyExpt_Image.csv missing {col}")
        if "Metadata_Acquisition" not in image.columns:
            image["Metadata_Acquisition"] = cp_dir.name
        if "Scaling_Marker" not in image.columns:
            image["Scaling_Marker"] = 65535.0
        if "Count_Nuclei" not in image.columns:
            image["Count_Nuclei"] = np.nan
        if "Count_Cytoplasm" not in image.columns:
            image["Count_Cytoplasm"] = np.nan
        cols = [
            "ImageNumber",
            "Metadata_Acquisition",
            "Metadata_Well",
            "Metadata_Site",
            "Scaling_Marker",
            "Count_Nuclei",
            "Count_Cytoplasm",
        ]
        obj = cyt.merge(image[cols], on="ImageNumber", how="left")
        if "Intensity_IntegratedIntensity_Marker" not in obj.columns:
            raise RuntimeError(f"{cp_dir}/MyExpt_Cytoplasm.csv missing Intensity_IntegratedIntensity_Marker")
        if "AreaShape_Area" not in obj.columns:
            obj["AreaShape_Area"] = np.nan
        obj["integr_raw"] = obj["Intensity_IntegratedIntensity_Marker"].astype(float) * obj["Scaling_Marker"].astype(float)
        obj["area"] = obj["AreaShape_Area"].astype(float)
        obj["acquisition"] = obj["Metadata_Acquisition"].astype(str)
        obj["well"] = obj["Metadata_Well"].astype(str)
        obj["site"] = obj["Metadata_Site"].astype(str)
        obj = _merge_manifest(obj, manifest_meta)
        if "group" not in obj.columns:
            obj["group"] = obj["well"].map(_fallback_group)
        else:
            obj["group"] = obj["group"].fillna(obj["well"].map(_fallback_group))
        obj["backend"] = "cellprofiler"
        obj_cols = [
            "acquisition",
            "well",
            "site",
            *metadata_cols,
            "ImageNumber",
            "ObjectNumber",
            "integr_raw",
            "area",
            "backend",
        ]
        obj_cols = [c for c in obj_cols if c in obj.columns]
        object_rows.append(obj[obj_cols].rename(columns={"ObjectNumber": "object_number"}))
        for (acq, well, site), g in obj.groupby(["acquisition", "well", "site"], sort=True):
            integr = g["integr_raw"].to_numpy(float)
            area = g["area"].to_numpy(float)
            finite_area = area[np.isfinite(area)]
            keep = np.isfinite(area) & (area <= MAX_CELL_AREA)
            kept = integr[keep] if keep.any() else integr
            total_area = float(finite_area.sum()) if len(finite_area) else math.nan
            total_integr = float(integr.sum()) if len(integr) else math.nan
            first = g.iloc[0]
            meta = {col: first.get(col, np.nan) for col in metadata_cols if col in g.columns}
            site_rows.append(
                {
                    "acquisition": acq,
                    "well": well,
                    "site": site,
                    **meta,
                    "group": first.get("group", _fallback_group(well)),
                    "cell_count": float(first.get("Count_Nuclei", np.nan)),
                    "n_measured": int(len(g)),
                    "mean_integr": float(np.mean(kept)) if len(kept) else math.nan,
                    "total_integr": total_integr,
                    "total_area": total_area,
                    "per_area": total_integr / total_area if total_area and not math.isnan(total_area) else math.nan,
                    "site_cv": math.nan,
                    "backend": "cellprofiler",
                }
            )

    sites = pd.DataFrame(site_rows)
    if sites.empty:
        raise RuntimeError(f"No CellProfiler site rows found in {input_dir}")
    objects = pd.concat(object_rows, ignore_index=True) if object_rows else pd.DataFrame()

    for (_, _), idx in sites.groupby(["acquisition", "well"]).groups.items():
        values = sites.loc[idx, "mean_integr"].dropna().to_numpy(float)
        cv = float(np.std(values, ddof=1) / np.mean(values)) if len(values) > 1 and np.mean(values) else 0.0
        sites.loc[idx, "site_cv"] = cv

    well_rows = []
    for (acq, well), frame in sites.groupby(["acquisition", "well"], sort=True):
        obj = objects[(objects["acquisition"].eq(acq)) & (objects["well"].eq(well))] if not objects.empty else pd.DataFrame()
        vals = obj["integr_raw"].dropna().to_numpy(float) if not obj.empty else np.array([], dtype=float)
        n_top50 = max(1, int(math.ceil(len(vals) * 0.50))) if len(vals) else 0
        n_top25 = max(1, int(math.ceil(len(vals) * 0.25))) if len(vals) else 0
        total_integr = float(frame["total_integr"].mean())
        total_area = float(frame["total_area"].mean()) if frame["total_area"].notna().any() else math.nan
        integr_p95 = float(np.quantile(vals, 0.95)) if len(vals) else math.nan
        integr_p98 = float(np.quantile(vals, 0.98)) if len(vals) else math.nan
        first = frame.iloc[0]
        meta = {col: first.get(col, np.nan) for col in metadata_cols if col in frame.columns}
        row = {
            "acquisition": acq,
            "well": well,
            "site": "well_mean",
            **meta,
            "group": first.get("group", _fallback_group(well)),
            "cell_count": float(frame["cell_count"].mean()),
            "n_measured": float(frame["n_measured"].sum()),
            "mean_integr": float(frame["mean_integr"].mean()),
            "total_integr": total_integr,
            "total_area": total_area,
            "per_area": total_integr / total_area if total_area and not math.isnan(total_area) else math.nan,
            "site_cv": float(frame["site_cv"].max()),
            "backend": "cellprofiler",
            "top50_integr_mean": float(np.mean(np.sort(vals)[-n_top50:])) if n_top50 else math.nan,
            "top25_integr_mean": float(np.mean(np.sort(vals)[-n_top25:])) if n_top25 else math.nan,
            "integr_p95": integr_p95,
            "integr_p98": integr_p98,
            "calibrated_integr_p95_1p25": integr_p95**1.25 if not math.isnan(integr_p95) else math.nan,
            "calibrated_integr_p95_1p30": integr_p95**1.30 if not math.isnan(integr_p95) else math.nan,
        }
        well_rows.append(row)

    sites.to_csv(outdir / "per_site_metrics.csv", index=False)
    pd.DataFrame(well_rows).to_csv(outdir / "per_well_metrics.csv", index=False)
    objects.to_csv(outdir / "object_metrics.csv", index=False)
