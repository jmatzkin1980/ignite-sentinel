"""IMP-285: secrets and sensitive data at ingestion.

The secrets below are assembled at runtime so this file never carries one (the
repo's own `/doctor` scan would flag it otherwise).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from sentinel.discovery import ingest
from sentinel.doctor import tracked_secrets_check, workspaces_ignored_check
from sentinel.memory import redact_for_memory
from sentinel.secrets_scan import (
    OutputLeak,
    SECRET_TYPES,
    assert_no_leaks,
    detect_pii,
    detect_secrets,
    fingerprint,
    redact,
)
from sentinel.sync import sync_change

SEEDED = {
    "private_key": "-----BEGIN " + "RSA PRIVATE KEY-----\nMIIBOgIBAAJBAKj34GkxFhD90vcNLYLInFEX6Ppy1tPf9Cnzj4p4WGeKLs1P\n-----END RSA " + "PRIVATE KEY-----",
    "cloud_key": "AKIA" + "IOSFODNN7EXAMPLE",
    "jwt": "eyJ" + "hbGciOiJIUzI1NiJ9" + ".eyJ" + "zdWIiOiIxMjM0NTY3ODkwIn0" + ".dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
    "token": "ghp" + "_" + "1234567890abcdefghijABCDEFGHIJ123456",
    "url_credentials": "postgres://admin:" + "s3cr3tPass@db.internal:5432/app",
    "connection_string": "Server=tcp:db.example.local;Database=app;User ID=sa;" + "Password=Sup3rS3cret!;",
}
REQUIREMENT = (
    "We need a dashboard with metric cards. Login must support roles and permissions.\n\n"
    "Integration notes pasted by the client:\n\n"
    + "\n\n".join(f"- {kind}: {value}" for kind, value in SEEDED.items())
    + "\n"
)


class DetectorTests(unittest.TestCase):
    def test_each_type_is_detected_once(self) -> None:
        self.assertEqual(set(SECRET_TYPES), set(SEEDED))
        for kind, value in SEEDED.items():
            with self.subTest(kind=kind):
                findings = detect_secrets(f"before {value} after")
                self.assertEqual([item.type for item in findings], [kind])

    def test_six_seeded_secrets_give_six_redactions(self) -> None:
        findings = detect_secrets(REQUIREMENT)
        self.assertEqual(sorted(item.type for item in findings), sorted(SEEDED))
        clean = redact(REQUIREMENT, findings)
        for value in SEEDED.values():
            self.assertNotIn(value, clean)
        for kind in SEEDED:
            self.assertIn(f"<SECRETO:{kind}>", clean)

    def test_allowlist_by_fingerprint(self) -> None:
        allow = {fingerprint(SEEDED["cloud_key"])}
        kinds = [item.type for item in detect_secrets(REQUIREMENT, allow)]
        self.assertNotIn("cloud_key", kinds)
        self.assertEqual(len(kinds), 5)

    def test_ordinary_prose_is_not_a_secret(self) -> None:
        text = "See https://example.com/docs and mail ana@example.com. Server=web01 handles login; the token expires."
        self.assertEqual(detect_secrets(text), [])

    def test_pii_is_detected_for_the_report(self) -> None:
        kinds = {kind for kind, _ in detect_pii("Contact ana@example.com or +54 11 4555-1234. Card 4111 1111 1111 1111.")}
        self.assertEqual(kinds, {"email", "phone", "card_number"})


class _Workspace(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp()).resolve()
        self.old_cwd = Path.cwd()
        os.chdir(self.temp)
        self.addCleanup(self._cleanup)
        self.source = self.temp / "requirement.md"
        self.source.write_text(REQUIREMENT, encoding="utf-8")

    def _cleanup(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def workspace_text(self, project_id: str) -> str:
        chunks = []
        for path in (self.temp / "workspaces" / project_id).rglob("*"):
            if path.is_file():
                try:
                    chunks.append(path.read_bytes().decode("utf-8"))
                except UnicodeDecodeError:
                    chunks.append(path.read_bytes().decode("latin-1"))
        return "\n".join(chunks)


class IngestRedactionTests(_Workspace):
    def test_ingest_redacts_alerts_and_leaves_the_original_untouched(self) -> None:
        result = ingest("SECDEMO", self.source)
        self.assertEqual(result["secret_redactions"], 6)
        self.assertEqual(self.source.read_text(encoding="utf-8"), REQUIREMENT)
        everything = self.workspace_text("SECDEMO")
        for kind, value in SEEDED.items():
            with self.subTest(kind=kind):
                self.assertNotIn(value, everything)
        raw_copy = (self.temp / "workspaces" / "SECDEMO" / "00_raw" / "requirement.md").read_text(encoding="utf-8")
        self.assertEqual(raw_copy.count("<SECRETO:"), 6)
        alerts = (self.temp / "workspaces" / "SECDEMO" / "01_discovery" / "secret_alerts.md").read_text(encoding="utf-8")
        self.assertEqual(sum(1 for line in alerts.splitlines() if "`requirement.md`" in line), 6)

    def test_allowlisted_value_passes_through(self) -> None:
        workspace = self.temp / "workspaces" / "SECALLOW"
        workspace.mkdir(parents=True)
        (workspace / "secrets_allowlist.txt").write_text(f"{fingerprint(SEEDED['cloud_key'])}  # sample key from vendor docs\n", encoding="utf-8")
        result = ingest("SECALLOW", self.source)
        self.assertEqual(result["secret_redactions"], 5)
        self.assertIn(SEEDED["cloud_key"], (workspace / "00_raw" / "requirement.md").read_text(encoding="utf-8"))

    def test_clean_source_is_copied_byte_for_byte(self) -> None:
        clean = self.temp / "clean.md"
        clean.write_bytes(b"We need a dashboard with metric cards.\r\nLogin uses roles.\r\n")
        result = ingest("SECCLEAN", clean)
        self.assertEqual(result["secret_redactions"], 0)
        self.assertEqual((self.temp / "workspaces" / "SECCLEAN" / "00_raw" / "clean.md").read_bytes(), clean.read_bytes())
        self.assertFalse((self.temp / "workspaces" / "SECCLEAN" / "01_discovery" / "secret_alerts.md").exists())

    def test_pii_report_is_opt_in_and_never_redacts(self) -> None:
        source = self.temp / "contacts.md"
        source.write_text("We need a dashboard. Contact ana@example.com for login roles.\n", encoding="utf-8")
        ingest("SECPII", source)
        workspace = self.temp / "workspaces" / "SECPII"
        self.assertFalse((workspace / "01_discovery" / "pii_report.md").exists())
        config = workspace / "workspace.config.yaml"
        config_path = config if config.exists() else next(workspace.glob("*.yaml"))
        config_path.write_text(config_path.read_text(encoding="utf-8") + "pii_report: true\n", encoding="utf-8")
        ingest("SECPII", source)
        report = (workspace / "01_discovery" / "pii_report.md").read_text(encoding="utf-8")
        self.assertIn("| email |", report)
        self.assertNotIn("ana@example.com", report)
        self.assertIn("ana@example.com", (workspace / "00_raw" / "contacts.md").read_text(encoding="utf-8"))

    def test_sync_redacts_the_change_copy(self) -> None:
        ingest("SECSYNC", self._clean_source())
        change = self.temp / "meeting.md"
        change.write_text("Client meeting: new login rule. Staging access " + SEEDED["url_credentials"] + "\n", encoding="utf-8")
        result = sync_change("SECSYNC", change, "meeting")
        self.assertEqual(result["secret_redactions"], 1)
        self.assertNotIn(SEEDED["url_credentials"], self.workspace_text("SECSYNC"))
        self.assertIn(SEEDED["url_credentials"], change.read_text(encoding="utf-8"))

    def _clean_source(self) -> Path:
        path = self.temp / "base.md"
        path.write_text("We need a dashboard with metric cards. Login must support roles.\n", encoding="utf-8")
        return path


class OutputGuardTests(_Workspace):
    def test_memory_never_stores_a_secret(self) -> None:
        (self.temp / "workspaces" / "MEM").mkdir(parents=True)
        self.assertEqual(redact_for_memory("MEM", "key " + SEEDED["token"]), "key <SECRETO:token>")

    def test_secret_in_an_output_is_refused(self) -> None:
        workspace = self.temp / "workspaces" / "OUT"
        workspace.mkdir(parents=True)
        with self.assertRaises(OutputLeak):
            assert_no_leaks("OUT", "export body " + SEEDED["jwt"], workspace, "export")

    def test_reference_to_another_workspace_is_refused(self) -> None:
        workspace = self.temp / "workspaces" / "ALPHA"
        workspace.mkdir(parents=True)
        (self.temp / "workspaces" / "BETA").mkdir()
        assert_no_leaks("ALPHA", "see workspaces/ALPHA/01_discovery/gaps.md and workspaces/BETAX", workspace, "view")
        with self.assertRaises(OutputLeak) as caught:
            assert_no_leaks("ALPHA", "copied from workspaces\\BETA\\03_specs\\prd.md", workspace, "view")
        self.assertIn("BETA", str(caught.exception))


def _git_repo(root: Path) -> bool:
    try:
        return subprocess.run(["git", "init", "-q", str(root)], capture_output=True).returncode == 0
    except OSError:
        return False


class DoctorRepoChecks(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.root, True)
        if not _git_repo(self.root):
            self.skipTest("git not available")

    def _add(self, name: str, text: str) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        subprocess.run(["git", "add", "-f", name], cwd=self.root, capture_output=True, check=True)

    def test_tracked_secret_fails_and_allowlist_clears_it(self) -> None:
        self._add("README.md", "Nothing to see.\n")
        self.assertEqual(tracked_secrets_check(self.root)["status"], "PASS")
        self._add("config/settings.txt", "aws " + SEEDED["cloud_key"] + "\n")
        result = tracked_secrets_check(self.root)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("config/settings.txt:1 cloud_key", result["detail"])
        self.assertNotIn(SEEDED["cloud_key"], result["detail"])
        (self.root / "secrets_allowlist.txt").write_text(fingerprint(SEEDED["cloud_key"]) + "\n", encoding="utf-8")
        self.assertEqual(tracked_secrets_check(self.root)["status"], "PASS")

    def test_workspaces_must_be_ignored_by_default(self) -> None:
        self.assertEqual(workspaces_ignored_check(self.root)["status"], "FAIL")
        (self.root / ".gitignore").write_text("workspaces/*\n!workspaces/_template/\n!workspaces/_template/**\n", encoding="utf-8")
        self.assertEqual(workspaces_ignored_check(self.root)["status"], "PASS")
        self._add("workspaces/_template/01_discovery/.gitkeep", "")
        self.assertEqual(workspaces_ignored_check(self.root)["status"], "PASS")
        self._add("workspaces/ACME/01_discovery/gaps.md", "# Gaps\n")
        result = workspaces_ignored_check(self.root)
        self.assertEqual(result["status"], "WARN")
        self.assertIn("ACME", result["detail"])

    def test_not_a_git_checkout_warns(self) -> None:
        plain = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, plain, True)
        env = {"GIT_CEILING_DIRECTORIES": str(plain.parent)}
        old = {key: os.environ.get(key) for key in env}
        os.environ.update(env)
        try:
            self.assertEqual(tracked_secrets_check(plain)["status"], "WARN")
            self.assertEqual(workspaces_ignored_check(plain)["status"], "WARN")
        finally:
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
