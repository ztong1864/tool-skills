#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

# 优先从.env文件加载配置，其次从环境变量加载
load_dotenv()  # 加载.env文件中的环境变量

ROOT = Path(__file__).resolve().parents[1]
KB_DIR = ROOT / "KB"


def device_settings() -> tuple[str, str, str, int]:
    """FDU_DEVICE_* from the server environment (or the .env above). Missing ones are named, never their values."""
    missing = [name for name in ("FDU_DEVICE_BASE_URL", "FDU_DEVICE_USERNAME", "FDU_DEVICE_PASSWORD")
               if not os.getenv(name)]
    if missing:
        raise SystemExit(f"设备接口没有配置：缺少 {'、'.join(missing)}（服务器环境变量或技能目录的 .env，由管理员配置）。"
                         "配置之前不能刷新资源快照，也不能创建设备任务。")
    timeout = os.getenv("FDU_DEVICE_TIMEOUT") or "20"
    if not timeout.isdigit():
        raise SystemExit(f"FDU_DEVICE_TIMEOUT 必须是秒数（整数），现在是 {timeout!r}。")
    return os.environ["FDU_DEVICE_BASE_URL"], os.environ["FDU_DEVICE_USERNAME"], os.environ["FDU_DEVICE_PASSWORD"], int(timeout)


class DeviceAPIClient:
    def __init__(self, base_url: str, username: str, password: str, timeout: int = 20):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def login(self) -> str:
        resp = self.session.post(
            self._url("/api/Token"),
            json={"username": self.username, "password": self.password},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError(f"登录失败，返回中没有 access_token: {data}")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        return token

    def post(self, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        resp = self.session.post(self._url(path), json=payload or {}, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_resource_info(self, layout_code: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if layout_code:
            payload["layout_code"] = layout_code
        return self.post("/api/GetResourceInfo", payload)


def extract_resource_list(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(raw, dict) and isinstance(raw.get("resources"), list):
        return list(raw["resources"])

    candidates = []
    if isinstance(raw, dict) and isinstance(raw.get("resource_list"), list):
        candidates = raw["resource_list"]
    elif isinstance(raw, dict) and isinstance(raw.get("result"), dict) and isinstance(raw["result"].get("resource_list"), list):
        candidates = raw["result"]["resource_list"]
    elif isinstance(raw, list):
        candidates = raw

    simplified: List[Dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        simplified.append(
            {
                "layout_code": item.get("layout_code", ""),
                "working_code": item.get("working_code", ""),
                "source_layout_code": item.get("source_layout_code", []),
                "resource_type": item.get("resource_type", ""),
                "substance": item.get("substance", ""),
                "unit": item.get("unit", ""),
                "initial_volume": item.get("initial_volume"),
                "available_volume": item.get("available_volume", 0.0),
                "initial_weight": item.get("initial_weight"),
                "available_weight": item.get("available_weight", 0.0),
                "tray_QR_code": item.get("tray_QR_code", ""),
                "QR_code": item.get("QR_code", ""),
                "chemical_id": item.get("chemical_id"),
                "status": item.get("status"),
            }
        )
    return simplified


def normalize_snapshot_timestamp(raw: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return raw

    normalized = dict(raw)
    normalized["timestamp"] = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    return normalized


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="刷新设备资源快照。")
    parser.add_argument("--resource-dir", default=str(KB_DIR),
                        help="资源快照写到这个目录（resource_info.json 和带时间戳的原始快照）；在 LabOntology 中用 "
                             "mission 的 artifacts 目录。默认是本技能的 KB/")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    client = DeviceAPIClient(*device_settings())
    client.login()
    raw = normalize_snapshot_timestamp(client.get_resource_info())

    resource_dir = Path(args.resource_dir)
    resource_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = resource_dir / f"resource_info_{ts}.json"
    raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    simplified = extract_resource_list(raw)
    latest_path = resource_dir / "resource_info.json"
    latest_path.write_text(json.dumps(simplified, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"raw saved to: {raw_path}")
    print(f"resource list saved to: {latest_path}")
    print(f"resources: {len(simplified)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
