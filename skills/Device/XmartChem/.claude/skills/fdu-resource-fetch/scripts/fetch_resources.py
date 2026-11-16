#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读查询复旦智能合成工作站当前的资源清单：刷新设备资源快照，按区域、托盘和资源类型汇总，写成一份 JSON。

只调用设备的登录和 GetResourceInfo 两个接口，不创建、启动或修改设备任务。"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parents[1]
SCHEMA = "fdu-resource-snapshot.v1"
FIELDS = ("layout_code", "working_code", "source_layout_code", "resource_type", "substance", "unit",
          "initial_volume", "available_volume", "initial_weight", "available_weight", "tray_QR_code", "QR_code",
          "chemical_id", "status")


def load_device_env() -> None:
    """设备接口的配置：服务器环境变量优先；没有时读设备目录的 .env（`skills/Device/<设备>/.env`），
    本技能目录和 `.claude/skills` 下的 .env 也认，先找到的那份优先。load_dotenv 不覆盖已有的环境变量。"""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    here = Path(__file__).resolve()
    # parents: [0] scripts, [1] 技能, [2] .claude/skills, [3] .claude, [4] 设备目录
    for root in (here.parents[1], here.parents[2], here.parents[4]):
        env_path = root / ".env"
        if env_path.is_file():
            load_dotenv(env_path)


def device_settings() -> tuple[str, str, str, int]:
    """FDU_DEVICE_*；缺少的只报名字，不打印任何取值。"""
    missing = [name for name in ("FDU_DEVICE_BASE_URL", "FDU_DEVICE_USERNAME", "FDU_DEVICE_PASSWORD")
               if not os.getenv(name)]
    if missing:
        raise SystemExit(f"设备接口没有配置：缺少 {'、'.join(missing)}（服务器环境变量或 skills/Device/<设备>/.env，"
                         "由管理员配置）。配置之前不能刷新资源快照。")
    timeout = os.getenv("FDU_DEVICE_TIMEOUT") or "20"
    if not timeout.isdigit():
        raise SystemExit(f"FDU_DEVICE_TIMEOUT 必须是秒数（整数），现在是 {timeout!r}。")
    return (os.environ["FDU_DEVICE_BASE_URL"].rstrip("/"), os.environ["FDU_DEVICE_USERNAME"],
            os.environ["FDU_DEVICE_PASSWORD"], int(timeout))


def fetch_from_device() -> Any:
    """登录后调用 GetResourceInfo。出错时只报错误类型和 HTTP 状态，不带设备地址和账号。"""
    load_device_env()
    base_url, username, password, timeout = device_settings()
    import requests

    session = requests.Session()
    step = "登录"
    try:
        resp = session.post(f"{base_url}/api/Token", json={"username": username, "password": password},
                            timeout=timeout)
        resp.raise_for_status()
        token = (resp.json() or {}).get("access_token")
        if not token:
            raise SystemExit("刷新资源快照失败：设备登录的返回里没有 access_token（账号或口令可能不对，需要管理员核对）。")
        session.headers.update({"Authorization": f"Bearer {token}"})
        step = "读取资源（GetResourceInfo）"
        resp = session.post(f"{base_url}/api/GetResourceInfo", json={}, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        raise SystemExit(f"刷新资源快照失败：{step}时设备接口返回 HTTP {status}。")
    except ValueError:  # before RequestException: requests' JSONDecodeError is both
        raise SystemExit(f"刷新资源快照失败：{step}的返回不是 JSON。")
    except requests.RequestException as exc:
        raise SystemExit(f"刷新资源快照失败：{step}时连不上设备接口（{type(exc).__name__}）。")


def resource_list(raw: Any) -> list[dict[str, Any]]:
    """设备返回（或已有快照文件）里的资源列表，每条只留资源字段。"""
    if isinstance(raw, dict):
        for candidate in (raw.get("resources"), raw.get("resource_list"),
                          (raw.get("result") or {}).get("resource_list") if isinstance(raw.get("result"), dict) else None):
            if isinstance(candidate, list):
                raw = candidate
                break
    if not isinstance(raw, list):
        raise SystemExit("返回里没有资源列表（resource_list）。")
    return [{key: item.get(key) for key in FIELDS} for item in raw if isinstance(item, dict)]


def _amount(item: dict[str, Any]) -> float:
    total = 0.0
    for key in ("available_volume", "available_weight"):
        try:
            total += float(item.get(key) or 0)
        except (TypeError, ValueError):
            pass
    return total


def _area(code: str) -> str:
    return code.split("-", 1)[0] if code else "(无位点编号)"


def _tray(code: str) -> str:
    return code.split(":", 1)[0] if code else "(无位点编号)"


def summarize(resources: list[dict[str, Any]]) -> dict[str, Any]:
    """按区域（layout_code 第一个 - 之前）和托盘（: 之前）汇总；有物质的位点单独列出。"""
    areas: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    trays: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for item in resources:
        code = str(item.get("layout_code") or "")
        substance = str(item.get("substance") or "").strip()
        area = areas.setdefault(_area(code), {"area": _area(code), "positions": 0, "with_substance": 0,
                                               "trays": set(), "resource_types": Counter()})
        area["positions"] += 1
        area["with_substance"] += bool(substance)
        area["trays"].add(_tray(code))
        area["resource_types"][str(item.get("resource_type") or "")] += 1
        tray = trays.setdefault(_tray(code), {"tray": _tray(code), "area": _area(code), "positions": 0,
                                              "resource_types": Counter(), "tray_QR_codes": set(), "substances": []})
        tray["positions"] += 1
        tray["resource_types"][str(item.get("resource_type") or "")] += 1
        if item.get("tray_QR_code"):
            tray["tray_QR_codes"].add(str(item["tray_QR_code"]))
        if substance:
            tray["substances"].append({key: item.get(key) for key in (
                "layout_code", "substance", "unit", "available_volume", "available_weight", "status")})
    return {
        "resource_count": len(resources),
        "with_substance_count": sum(area["with_substance"] for area in areas.values()),
        "resource_types": dict(Counter(str(item.get("resource_type") or "") for item in resources).most_common()),
        "areas": [{**area, "trays": len(area["trays"]), "resource_types": dict(area["resource_types"].most_common())}
                  for area in areas.values()],
        "trays": [{**tray, "resource_types": dict(tray["resource_types"].most_common()),
                   "tray_QR_codes": sorted(tray["tray_QR_codes"])} for tray in trays.values()],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="只读查询复旦智能合成工作站当前的资源清单（刷新设备资源快照并汇总）。")
    parser.add_argument("--output", default=None,
                        help="资源快照 JSON 写到这里；在 LabOntology 中写进 mission 的 artifacts 目录。"
                             "默认 output/resource_snapshot_<timestamp>.json（本技能目录下）")
    parser.add_argument("--layout-prefix", default=None,
                        help="只汇总 layout_code 以它开头的位点，例如 T-8 或 W4（快照本身仍是全量读取）")
    parser.add_argument("--from-file", default=None,
                        help="不调设备，汇总一份已有的快照文件（只在用户明确要求看本地或缓存快照时用）")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.from_file:
        source_path = Path(args.from_file).expanduser().resolve()
        if not source_path.is_file():
            raise SystemExit(f"找不到快照文件：{source_path}")
        raw = json.loads(source_path.read_text(encoding="utf-8-sig"))
        source = {"source": "file", "source_file": str(source_path),
                  "source_file_modified": datetime.fromtimestamp(source_path.stat().st_mtime).astimezone()
                  .isoformat(timespec="seconds"),
                  "note": "本地或缓存的快照文件，不是设备现状，不能当成当前库存"}
    else:
        raw = fetch_from_device()
        source = {"source": "device"}
    fetched_at = datetime.now().astimezone()
    resources = resource_list(raw)
    if args.layout_prefix:
        resources = [item for item in resources if str(item.get("layout_code") or "").startswith(args.layout_prefix)]

    snapshot = {"schema": SCHEMA, "timestamp": fetched_at.isoformat(timespec="seconds"), **source,
                "layout_prefix": args.layout_prefix, **summarize(resources), "resources": resources}
    output = Path(args.output) if args.output else (
        SKILL_DIR / "output" / f"resource_snapshot_{fetched_at.strftime('%Y%m%d_%H%M%S')}.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"snapshot saved to: {output}")
    print(f"source: {snapshot['source']}   timestamp: {snapshot['timestamp']}")
    print(f"resources: {snapshot['resource_count']}   with substance: {snapshot['with_substance_count']}")
    for area in snapshot["areas"]:
        print(f"  {area['area']}: {area['positions']} positions on {area['trays']} trays, "
              f"{area['with_substance']} with substance")
    return 0


if __name__ == "__main__":
    sys.exit(main())
