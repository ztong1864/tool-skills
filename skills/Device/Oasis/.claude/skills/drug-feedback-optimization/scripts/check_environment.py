#!/usr/bin/env python3
"""检查药效反馈技能的文件、相邻核心和离线评估依赖，不运行模型。"""

from __future__ import annotations

import importlib.util
import json
import platform
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT.parent
FIXTURE = ROOT / "test-data" / "prism-primary-luad-smoke-v1"


def main() -> int:
    required_files = [
        ROOT / "assets" / "task_config.template.json",
        ROOT / "scripts" / "validate_task_config.py",
        FIXTURE / "base_scored_oracle.csv",
        FIXTURE / "feature_columns.json",
        FIXTURE / "split_manifest.json",
        FIXTURE / "run_smoke.py",
        SKILLS_ROOT / "autoresearch-core" / "scripts" / "autoresearch_core.py",
    ]
    missing_files = [str(path) for path in required_files if not path.is_file()]
    packages = ["numpy", "pandas", "scipy", "sklearn"]
    package_status = {name: importlib.util.find_spec(name) is not None for name in packages}
    ok = sys.version_info >= (3, 10) and not missing_files and all(package_status.values())
    result = {
        "ok": ok,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "skill_root": str(ROOT),
        "autoresearch_core_present": (SKILLS_ROOT / "autoresearch-core").is_dir(),
        "packages": package_status,
        "missing_files": missing_files,
        "note": "该检查不运行 smoke、训练或 AutoResearch。",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
