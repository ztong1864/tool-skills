import hashlib
import importlib.util
import io
import json
import stat
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace


SCRIPT = Path(__file__).parents[1] / "scripts" / "fetch_report.py"
fetch = None
if SCRIPT.exists():
    spec = importlib.util.spec_from_file_location("fetch_report", SCRIPT)
    fetch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fetch)


def entry(name, mtime, size=3, mode=stat.S_IFREG):
    return SimpleNamespace(filename=name, st_mtime=mtime, st_size=size, st_mode=mode)


class FakeSFTP:
    def __init__(self, entries, data=b"abc"):
        self.entries = entries
        self.data = data
        self.changed = False

    def listdir_attr(self, directory):
        return self.entries

    def lstat(self, path):
        value = next(e for e in self.entries if e.filename == path.rsplit("/", 1)[1])
        return entry(value.filename, value.st_mtime + int(self.changed), value.st_size, value.st_mode)

    def open(self, path, mode):
        return io.BytesIO(self.data)


class SkillFiles(unittest.TestCase):
    def test_fetcher_exists(self):
        self.assertTrue(SCRIPT.is_file(), "SSH report fetcher has not been implemented")


@unittest.skipIf(fetch is None, "fetcher not implemented")
class FetchTests(unittest.TestCase):
    def setUp(self):
        self.config = {"host": "lab.example", "username": "reader", "remote_dir": "/data/reports",
                       "patterns": ["*A*.pdf"], "stable_seconds": 0.01}

    def test_requires_real_host_and_directory_before_connecting(self):
        for field in ("host", "remote_dir", "username"):
            with self.subTest(field=field), self.assertRaises(fetch.ReportError):
                fetch.validate_config({**self.config, field: None})

    def test_selects_sample_by_mtime_and_excludes_symlinks_and_temporary_files(self):
        sftp = FakeSFTP([entry("A_old.pdf", 100), entry("A_new.pdf", 200),
                         entry("B.pdf", 999), entry("A_link.pdf", 999, mode=stat.S_IFLNK),
                         entry(".A_hidden.pdf", 999), entry("A_in_progress.pdf.part", 999)])
        with tempfile.TemporaryDirectory() as tmp:
            result = fetch.fetch_report(sftp, self.config, Path(tmp), sleep=lambda _: None)
            self.assertEqual(result["remote_path"], "/data/reports/A_new.pdf")
            self.assertEqual(Path(result["local_path"]).read_bytes(), b"abc")
            self.assertEqual(result["sha256"], hashlib.sha256(b"abc").hexdigest())
            manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["remote_filename"], "A_new.pdf")

    def test_empty_latest_report_does_not_fall_back_to_older_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(fetch.ReportError, "EMPTY_REPORT"):
                fetch.fetch_report(FakeSFTP([entry("A_old.pdf", 100), entry("A_empty.pdf", 200, size=0)]),
                                   self.config, Path(tmp), sleep=lambda _: None)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_ssh_connection_rejects_unknown_hosts_and_uses_configured_identity(self):
        import paramiko
        with patch.object(paramiko, "SSHClient") as cls:
            fetch.connect(self.config)
            cls.return_value.load_system_host_keys.assert_called_once()
            policy = cls.return_value.set_missing_host_key_policy.call_args.args[0]
            self.assertIsInstance(policy, paramiko.RejectPolicy)
            self.assertEqual(cls.return_value.connect.call_args.kwargs["hostname"], "lab.example")
            self.assertEqual(cls.return_value.connect.call_args.kwargs["username"], "reader")

    def test_ssh_uses_saved_password_and_preserves_significant_spaces(self):
        import paramiko
        with tempfile.TemporaryDirectory() as tmp, patch.object(paramiko, "SSHClient") as cls:
            credential = Path(tmp) / "ssh-password.local"
            credential.write_bytes(b" example-test-password+ \r\n")
            fetch.connect({**self.config, "password_file": str(credential)})
            self.assertEqual(cls.return_value.connect.call_args.kwargs["password"], " example-test-password+ ")

    def test_missing_saved_password_is_reported_before_network_authentication(self):
        import paramiko
        with tempfile.TemporaryDirectory() as tmp, patch.object(paramiko, "SSHClient") as cls:
            credential = Path(tmp) / "missing-password.local"
            with self.assertRaisesRegex(fetch.ReportError, "AUTH:.*password file"):
                fetch.connect({**self.config, "password_file": str(credential)})
            cls.return_value.connect.assert_not_called()

    def test_ssh_failures_are_not_retried_with_weaker_settings(self):
        import paramiko
        with patch.object(paramiko, "SSHClient") as cls:
            cls.return_value.connect.side_effect = paramiko.SSHException("unknown host key")
            with self.assertRaises(paramiko.SSHException):
                fetch.connect(self.config)
            cls.return_value.connect.assert_called_once()
            cls.return_value.close.assert_called_once()

    def test_does_not_fall_back_to_older_report_when_latest_is_changing(self):
        sftp = FakeSFTP([entry("A_old.pdf", 100), entry("A_new.pdf", 200)])
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(fetch.ReportError, "REPORT_CHANGING"):
                fetch.fetch_report(sftp, self.config, Path(tmp), sleep=lambda _: setattr(sftp, "changed", True))
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_rejects_changes_during_transfer_and_removes_partial_files(self):
        sftp = FakeSFTP([entry("A.pdf", 100)])
        original = sftp.open
        def changing_open(path, mode):
            sftp.changed = True
            return original(path, mode)
        sftp.open = changing_open
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(fetch.ReportError, "REPORT_CHANGING"):
                fetch.fetch_report(sftp, self.config, Path(tmp), sleep=lambda _: None)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_rejects_truncated_transfer(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(fetch.ReportError, "SIZE_MISMATCH"):
                fetch.fetch_report(FakeSFTP([entry("A.pdf", 100)], b"a"), self.config,
                                   Path(tmp), sleep=lambda _: None)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_no_match_and_equal_latest_times_are_explicit_errors(self):
        for entries, code in (([entry("B.pdf", 100)], "NO_REPORT"),
                              ([entry("A_1.pdf", 100), entry("A_2.pdf", 100)], "AMBIGUOUS_LATEST")):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(fetch.ReportError, code):
                    fetch.fetch_report(FakeSFTP(entries), self.config, Path(tmp), sleep=lambda _: None)

    def test_repeat_fetch_does_not_overwrite_prior_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = fetch.fetch_report(FakeSFTP([entry("A.pdf", 100)]), self.config,
                                       Path(tmp), sleep=lambda _: None)
            second = fetch.fetch_report(FakeSFTP([entry("A.pdf", 100)], b"xyz"), self.config,
                                        Path(tmp), sleep=lambda _: None)
            self.assertNotEqual(first["local_path"], second["local_path"])
            self.assertEqual(Path(first["local_path"]).read_bytes(), b"abc")


if __name__ == "__main__":
    unittest.main()
