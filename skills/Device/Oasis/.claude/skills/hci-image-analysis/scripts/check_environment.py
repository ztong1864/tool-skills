#!/usr/bin/env python3
"""Read-only environment check for hci-image-analysis."""
import argparse, importlib.util, json, platform, shutil, sys
from pathlib import Path

REQUIRED = ["numpy", "pandas", "skimage", "tifffile", "PIL"]
OPTIONAL = ["openpyxl", "cellpose"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json-output")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    checks = {m: bool(importlib.util.find_spec(m)) for m in REQUIRED + OPTIONAL}
    cp = shutil.which("cellprofiler") or shutil.which("cellprofiler.exe")
    checks["cellprofiler_cli"] = bool(cp)
    checks["default_cp_pipeline"] = (root / "assets/cellprofiler/default_positive_w2.cppipe").is_file()
    required_ok = all(checks[m] for m in REQUIRED) and checks["default_cp_pipeline"]
    result = {
        "skill": "hci-image-analysis", "status": "passed" if required_ok else "failed",
        "can_run_skimage": required_ok, "python": sys.executable,
        "python_version": platform.python_version(), "platform": platform.platform(),
        "checks": checks, "optional_backends": {
            "cellprofiler": "available" if cp else "unavailable",
            "cellpose": "available" if checks["cellpose"] else "unavailable"
        }
    }
    for k, v in checks.items(): print(f"[{'PASS' if v else 'WARN' if k in OPTIONAL or k == 'cellprofiler_cli' else 'FAIL'}] {k}")
    print("[RESULT]", result["status"])
    if args.json_output: Path(args.json_output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if required_ok else 1
if __name__ == "__main__": raise SystemExit(main())
