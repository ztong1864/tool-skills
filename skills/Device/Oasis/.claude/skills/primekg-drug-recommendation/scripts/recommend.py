#!/usr/bin/env python3
"""PrimeKG 药物推荐 Skill 调用脚本。

输入 disease_catalog.csv 中的 disease_id 或精确 disease_name，输出候选药物推荐。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
SRC_DIR = SKILL_DIR / "src"
DEFAULT_OUTPUT_DIR = SKILL_DIR / "outputs"


def _read_top_rows(csv_path: Path, top_n: int) -> list[dict]:
    rows: list[dict] = []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= top_n:
                break
            rows.append(row)
    return rows


def _format_score(value: object) -> str:
    try:
        return f"{float(value):.6f}"
    except Exception:
        return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="PrimeKG 疾病药物推荐")
    parser.add_argument("disease", help="disease_catalog.csv 中的 disease_id 或精确 disease_name")
    parser.add_argument("--top", type=int, default=10, help="在终端展示前 N 个推荐，默认 10")
    parser.add_argument("--output", help="完整推荐结果 CSV 输出路径；不传则自动写入 outputs/ 目录")
    parser.add_argument("--python-bin", default=sys.executable, help="Python 可执行文件，默认当前 Python")
    parser.add_argument("--json", action="store_true", help="输出 JSON 摘要，便于程序读取")
    args = parser.parse_args()

    if args.top < 1:
        parser.error("--top 必须 >= 1")

    disease_safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(args.disease).strip())[:80]
    output = Path(args.output) if args.output else DEFAULT_OUTPUT_DIR / f"drug_recommendations_{disease_safe}.csv"
    output.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_DIR) + os.pathsep + env.get("PYTHONPATH", "")

    cmd = [
        args.python_bin,
        "-m",
        "primekg_indication_delivery.cli",
        "score",
        "--bundle-dir",
        str(SKILL_DIR),
        "--disease",
        str(args.disease),
        "--output",
        str(output),
    ]

    proc = subprocess.run(cmd, cwd=str(SKILL_DIR), env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr or proc.stdout)
        return proc.returncode

    top_rows = _read_top_rows(output, args.top)

    if args.json:
        print(json.dumps({"status": "ok", "disease": args.disease, "output": str(output), "top": top_rows}, ensure_ascii=False, indent=2))
        return 0

    print(f"[OK] 药物推荐完成")
    print(f"疾病查询: {args.disease}")
    print(f"完整结果 CSV: {output}")
    print(f"\nTop {len(top_rows)} 推荐药物：")
    print("rank\tdrugbank_id\tdrug_name\tindication_score")
    for row in top_rows:
        print(f"{row.get('rank','')}\t{row.get('drugbank_id','')}\t{row.get('drug_name','')}\t{_format_score(row.get('indication_score',''))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
