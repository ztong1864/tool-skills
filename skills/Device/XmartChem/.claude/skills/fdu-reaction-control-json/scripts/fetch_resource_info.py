#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv


def load_device_env() -> None:
    """设备接口的配置放在设备目录的 .env（`skills/Device/<设备>/.env`），技能目录和 `.claude/skills` 下的
    .env 也认，先找到的那份优先（和 fdu-execution-monitoring 的 load_env 一致）。

    这个脚本原来把工作站地址和登录名写死在代码里（一台换掉的机器加 admin/admin），所以换工作站时它还在
    连旧地址，口令也明文留在技能目录里。现在和 fdu-resource-verify 一样只从环境或设备目录的 .env 取。"""
    here = Path(__file__).resolve()
    # parents: [0] scripts, [1] 技能, [2] .claude/skills, [3] .claude, [4] 设备目录
    for root in (here.parents[1], here.parents[2], here.parents[4]):
        env_path = root / ".env"
        if env_path.is_file():
            load_dotenv(env_path)


load_device_env()

BASE_URL = os.getenv("FDU_DEVICE_BASE_URL")
USERNAME = os.getenv("FDU_DEVICE_USERNAME")
PASSWORD = os.getenv("FDU_DEVICE_PASSWORD")
TIMEOUT = int(os.getenv("FDU_DEVICE_TIMEOUT") or "20")

ROOT = Path(__file__).resolve().parents[1]
KB_DIR = ROOT / "KB"
KB_DIR.mkdir(parents=True, exist_ok=True)


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


def main() -> int:
    missing = [name for name, value in (("FDU_DEVICE_BASE_URL", BASE_URL), ("FDU_DEVICE_USERNAME", USERNAME),
                                        ("FDU_DEVICE_PASSWORD", PASSWORD)) if not value]
    if missing:
        raise SystemExit(f"设备接口没有配置：缺少 {'、'.join(missing)}（服务器环境变量或 "
                         "skills/Device/<设备>/.env，由管理员配置）。配置之前不能刷新资源快照。")
    client = DeviceAPIClient(BASE_URL, USERNAME, PASSWORD, TIMEOUT)
    client.login()
    raw = client.get_resource_info()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = KB_DIR / f"resource_info_raw_{ts}.json"
    raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    simplified = extract_resource_list(raw)
    latest_path = KB_DIR / "resource_info_latest.json"
    latest_path.write_text(json.dumps(simplified, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"raw saved to: {raw_path}")
    print(f"latest saved to: {latest_path}")
    print(f"resources: {len(simplified)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
