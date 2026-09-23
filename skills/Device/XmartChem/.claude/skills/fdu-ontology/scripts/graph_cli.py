from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    script_path = Path(__file__).resolve()
    skill_root = script_path.parents[1]
    sys.path.insert(0, str(skill_root))
    from fdu_graph.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
