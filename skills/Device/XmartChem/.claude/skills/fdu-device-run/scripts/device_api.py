#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import requests
from typing import Any, Dict, Optional


class DeviceRunError(Exception):
    """Raised when device API interaction or protocol submission fails."""


class DeviceAPIClient:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        timeout: int = 20,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        self.token: Optional[str] = None

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def login(self) -> str:
        url = self._url("/api/Token")
        payload = {
            "username": self.username,
            "password": self.password,
        }
        resp = self.session.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()

        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise DeviceRunError(f"Login failed: missing access_token in response: {data}")

        self.token = token
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        return token

    def post(self, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = self._url(path)
        resp = self.session.post(url, json=payload or {}, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        # API 文档中成功一般返回 code=200；HTTP 200 但业务失败也要拦住
        code = data.get("code")
        if code is not None and code != 200:
            msg = data.get("msg", "")
            prompt_msg = data.get("prompt_msg", "")
            raise DeviceRunError(
                f"Device API business error at {path}: code={code}, msg={msg}, prompt_msg={prompt_msg}, raw={data}"
            )
        return data

    def add_task(self, task_payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.post("/api/AddTask", task_payload)

    def start_task(
        self,
        task_id: int,
        *,
        skip_curr_taskunit: int = 1,
        run_by_single_tube: int = 0,
        quick_cap: int = 1,
        use_tip_type: str = "",
    ) -> Dict[str, Any]:
        payload = {
            "task_id": task_id,
            "skip_curr_taskunit": skip_curr_taskunit,
            "run_by_single_tube": run_by_single_tube,
            "quick_cap": quick_cap,
            "use_tip_type": use_tip_type,
        }
        return self.post("/api/StartTask", payload)
