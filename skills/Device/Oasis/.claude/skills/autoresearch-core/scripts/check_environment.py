#!/usr/bin/env python3
"""检查 AutoResearch Core 的本地运行入口，不启动研究循环。"""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    required = [
        ROOT / "scripts" / "autoresearch_core.py",
        ROOT / "assets" / "config.template.json",
        ROOT / "references" / "protocol.md",
        ROOT / "references" / "provider-adapters.md",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    result = {
        "ok": not missing and sys.version_info >= (3, 10),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "skill_root": str(ROOT),
        "missing_files": missing,
        "note": "核心只使用 Python 标准库；领域评估器和提案器依赖需分别检查。",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
