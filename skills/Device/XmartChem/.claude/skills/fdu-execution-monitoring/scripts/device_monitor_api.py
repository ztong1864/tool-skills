#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

from monitoring_utils import MonitoringError


class DeviceMonitorAPIClient:
    """Read-only client for post-submit task observation."""

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
        resp = self.session.post(
            self._url("/api/Token"),
            json={"username": self.username, "password": self.password},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise MonitoringError(f"Login failed: missing access_token in response: {data}")
        self.token = token
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        return token

    def post(self, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        resp = self.session.post(self._url(path), json=payload or {}, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        code = data.get("code")
        if code is not None and code != 200:
            raise MonitoringError(
                f"Device API business error at {path}: code={code}, "
                f"msg={data.get('msg', '')}, prompt_msg={data.get('prompt_msg', '')}, raw={data}"
            )
        return data

    def get_task_list(
        self,
        *,
        sort: str = "desc",
        offset: int = 0,
        limit: int = 20,
        status: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "sort": sort,
            "offset": offset,
            "limit": limit,
        }
        if status is not None:
            payload["status"] = status
        return self.post("/api/GetTaskList", payload)

    def get_task_info(self, task_id: int) -> Dict[str, Any]:
        return self.post("/api/GetTaskInfo", {"task_id": int(task_id)})

    def get_notice(self, types: Optional[List[int]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if types is not None:
            payload["type"] = types
        return self.post("/api/Notice", payload)
