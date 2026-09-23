#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import contextlib
import io
import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from monitor_task import (  # noqa: E402
    DEFAULT_MAX_DURATION_SECONDS,
    DEFAULT_SCI_AGENT_API_BASE,
    execute,
    parse_args,
    resolve_start_context,
)
from monitoring_utils import MonitoringError  # noqa: E402


class SequenceClient:
    def __init__(self, task_infos, notices):
        self.task_infos = list(task_infos)
        self.notices = list(notices)
        self.login_calls = 0
        self.task_calls = 0
        self.notice_calls = 0

    def login(self):
        self.login_calls += 1
        return "token"

    def get_task_info(self, task_id):
        self.task_calls += 1
        if len(self.task_infos) > 1:
            return self.task_infos.pop(0)
        return self.task_infos[0]

    def get_notice(self, types=None):
        self.notice_calls += 1
        if len(self.notices) > 1:
            return self.notices.pop(0)
        return self.notices[0]


def args(**kwargs):
    defaults = {
        "task_id": 1,
        "submit_result_file": None,
        "base_url": "http://127.0.0.1:4669",
        "username": "admin",
        "password": "admin",
        "timeout": 20,
        "poll_interval": 1.0,
        "max_duration": 10.0,
        "sci_agent_api_base": DEFAULT_SCI_AGENT_API_BASE,
        "conversation_id": "conv-1",
        "push_token": None,
        "push_timeout": 20,
        "output": None,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


def fake_alert_sender(**kwargs):
    return {"success": True, "messageId": "msg-test"}


class MonitorTaskTests(unittest.TestCase):
    def test_default_max_duration_is_48_hours(self):
        parsed = parse_args(["--conversation-id", "conv-1"])
        self.assertEqual(parsed.max_duration, DEFAULT_MAX_DURATION_SECONDS)
        self.assertEqual(parsed.sci_agent_api_base, DEFAULT_SCI_AGENT_API_BASE)
        self.assertEqual(parsed.conversation_id, "conv-1")

    def test_parse_args_requires_conversation_id(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parse_args([])

    def test_start_context_resolves_task_and_conversation_before_polling(self):
        context = resolve_start_context(args(task_id=494, conversation_id="conv-fixed"))
        self.assertEqual(context.task_id, 494)
        self.assertEqual(context.conversation_id, "conv-fixed")

    def test_monitor_stops_on_completed_status(self):
        client = SequenceClient(
            task_infos=[
                {"task_id": 1, "status": 1, "tube_sums": 2, "tube_finish": 1},
                {"task_id": 1, "status": 2, "tube_sums": 2, "tube_finish": 2},
            ],
            notices=[{"sums": 0, "list": []}],
        )
        clock = FakeClock()
        result = execute(args(), client=client, sleep_fn=clock.sleep, clock_fn=clock.now, alert_sender=fake_alert_sender)

        self.assertEqual(result["stop_reason"], "terminal_status:COMPLETED")
        self.assertEqual(result["conversation_id"], "conv-1")
        self.assertEqual(result["final_status"]["label"], "COMPLETED")
        self.assertEqual(len(result["timeline"]), 2)
        self.assertEqual(client.login_calls, 1)

    def test_monitor_stops_on_fault(self):
        client = SequenceClient(
            task_infos=[{"task_id": 1, "status": 1}],
            notices=[{"sums": 1, "list": [{"id": 7, "type": 1, "error_code": "F001"}]}],
        )
        clock = FakeClock()
        result = execute(args(), client=client, sleep_fn=clock.sleep, clock_fn=clock.now, alert_sender=fake_alert_sender)

        self.assertEqual(result["stop_reason"], "fault_detected")
        self.assertEqual(len(result["faults_seen"]), 1)
        self.assertEqual(len(result["timeline"]), 1)
        self.assertTrue(result["alert_push"]["success"])

    def test_monitor_stops_on_alarm(self):
        client = SequenceClient(
            task_infos=[{"task_id": 1, "status": 1}],
            notices=[{"sums": 1, "list": [{"id": 8, "type": 2, "error_code": "A001"}]}],
        )
        clock = FakeClock()
        result = execute(args(), client=client, sleep_fn=clock.sleep, clock_fn=clock.now)

        self.assertEqual(result["stop_reason"], "alarm_detected")
        self.assertEqual(len(result["alarms_seen"]), 1)

    def test_monitor_stops_on_max_duration(self):
        client = SequenceClient(
            task_infos=[{"task_id": 1, "status": 1}],
            notices=[{"sums": 0, "list": []}],
        )
        clock = FakeClock()
        result = execute(
            args(poll_interval=2.0, max_duration=3.0),
            client=client,
            sleep_fn=clock.sleep,
            clock_fn=clock.now,
        )

        self.assertEqual(result["stop_reason"], "max_duration_reached")
        self.assertGreaterEqual(len(result["timeline"]), 2)

    def test_zero_max_duration_does_not_stop_by_time(self):
        client = SequenceClient(
            task_infos=[
                {"task_id": 1, "status": 1},
                {"task_id": 1, "status": 1},
                {"task_id": 1, "status": 2},
            ],
            notices=[{"sums": 0, "list": []}],
        )
        clock = FakeClock()
        result = execute(
            args(poll_interval=100.0, max_duration=0.0),
            client=client,
            sleep_fn=clock.sleep,
            clock_fn=clock.now,
        )

        self.assertEqual(result["stop_reason"], "terminal_status:COMPLETED")
        self.assertEqual(len(result["timeline"]), 3)

    def test_monitor_pushes_alert_when_conversation_id_is_provided(self):
        client = SequenceClient(
            task_infos=[{"task_id": 1, "status": 4}],
            notices=[{"sums": 0, "list": []}],
        )
        pushes = []

        def fake_sender(**kwargs):
            pushes.append(kwargs)
            return {"success": True, "messageId": "msg-1"}

        clock = FakeClock()
        result = execute(
            args(conversation_id="conv-1"),
            client=client,
            sleep_fn=clock.sleep,
            clock_fn=clock.now,
            alert_sender=fake_sender,
        )

        self.assertEqual(result["stop_reason"], "terminal_status:FAILED")
        self.assertTrue(result["alert_push"]["success"])
        self.assertEqual(pushes[0]["conversation_id"], "conv-1")
        self.assertEqual(pushes[0]["api_base"], DEFAULT_SCI_AGENT_API_BASE)
        self.assertIn("FDU 设备任务监控提醒", pushes[0]["content"])

    def test_execute_requires_conversation_id(self):
        client = SequenceClient(
            task_infos=[{"task_id": 1, "status": 1}],
            notices=[{"sums": 0, "list": []}],
        )
        with self.assertRaises(MonitoringError):
            execute(args(conversation_id=None), client=client)


if __name__ == "__main__":
    unittest.main()
