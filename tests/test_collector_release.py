"""Offline release, dependency, integrity and locked-deployment regression tests."""
import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from scripts import collector_release as release
from scripts import deploy_private_collector as private
from scripts.market_collector import live_bridge
import test_market_collector_v1 as fixtures

ROOT = Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
        cls.archive, cls.manifest = release.build(ROOT, cls.commit)
        cls.metadata = release.verify(ROOT, cls.commit, cls.archive, cls.manifest)

    def materialize(self, root):
        root.mkdir(mode=0o700)
        with tarfile.open(fileobj=io.BytesIO(self.archive), mode="r:") as bundle:
            for member in bundle:
                dest = root / member.name
                for directory in reversed(dest.parents):
                    if directory == root or root in directory.parents:
                        directory.mkdir(mode=0o700, exist_ok=True)
                with dest.open("xb") as f:
                    f.write(bundle.extractfile(member).read())
                dest.chmod(0o600)
        return root

    def mutated_tar(self, change):
        output = io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(self.archive), mode="r:") as source, \
             tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as target:
            for index, member in enumerate(source):
                raw = source.extractfile(member).read()
                edited = change(index, member, raw)
                if edited is not None:
                    member, raw = edited
                    target.addfile(member, io.BytesIO(raw) if member.isfile() else None)
        return output.getvalue()

    def test_reproducible_commit_hashes_sizes_modes_and_exact_closure(self):
        self.assertEqual((self.archive, self.manifest), release.build(ROOT, self.commit))
        self.assertEqual(self.metadata["commit"], self.commit)
        self.assertEqual(len(self.metadata["files"]), 33)
        self.assertLess(self.metadata["payload_bytes"], 4 * 1024 * 1024)
        self.assertTrue(all(r["mode"] == "0600" for r in self.metadata["files"]))
        self.assertEqual(sum(r["size"] for r in self.metadata["files"]), self.metadata["payload_bytes"])
        with tempfile.TemporaryDirectory() as tmp:
            root = self.materialize(Path(tmp)/"release")
            release.validate_directory(root, self.metadata)

    def test_archive_rejects_paths_links_duplicate_unknown_metadata_and_corruption(self):
        def altered(field, value):
            def change(index, item, raw):
                if index == 0:
                    setattr(item, field, value)
                return item, raw
            return change
        cases = [altered("name", p) for p in ("../escape", "/absolute", "a/../../b", "a\\b", "a//b",
                                            "./a", ".env", "scripts/unknown.py")]
        cases += [altered("type", tarfile.SYMTYPE), altered("type", tarfile.LNKTYPE),
                  altered("mode", 0o644), altered("mtime", 1), altered("uid", 1),
                  altered("name", self.metadata["files"][1]["path"]),
                  lambda i, m, b: None if i == 0 else (m, b),
                  lambda i, m, b: (m, bytes([b[0] ^ 1]) + b[1:]) if i == 0 else (m, b)]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(ValueError):
                release.verify(ROOT, self.commit, self.mutated_tar(change), self.manifest)

    def test_manifest_forgery_other_commit_and_unknown_json_fail_closed(self):
        for field, value in (("commit", "0"*40), ("payload_bytes", 0), ("unknown", True)):
            m = copy.deepcopy(self.metadata);m[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                release.verify(ROOT, self.commit, self.archive, release.canonical(m))
        with self.assertRaises(ValueError):
            release.verify(ROOT, "main", self.archive, self.manifest)
        with self.assertRaises(ValueError):
            release.decode(b'{"commit":1,"commit":2}')

    def test_materialized_missing_extra_symlinks_modes_and_hashes_rejected(self):
        for change in ("missing", "unknown", "symlink", "parent-link", "mode", "hash", "extra-dir"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                root = self.materialize(Path(tmp)/"release")
                path = root/self.metadata["files"][0]["path"]
                if change == "missing":path.unlink()
                elif change == "unknown":(root/"password.txt").write_text("SYNTHETIC-NOT-A-SECRET")
                elif change == "symlink":
                    path.unlink();path.symlink_to(ROOT/"AGENTS.md")
                elif change == "parent-link":
                    other = Path(tmp)/"aliased";root.rename(other);root.symlink_to(other, target_is_directory=True)
                elif change == "mode":path.chmod(0o644)
                elif change == "hash":path.write_bytes(b"changed")
                else:(root/"unknown").mkdir(mode=0o700)
                with self.assertRaises(ValueError):release.validate_directory(root, self.metadata)

    def test_git_source_and_static_missing_dependencies_fail_closed(self):
        known = {"scripts/x/a.py"}
        with self.assertRaises(ValueError):
            release.python_dependencies("scripts/x/a.py", "from scripts.missing import thing", known)
        # Working-tree tampering is tested in an isolated local clone; no network.
        with tempfile.TemporaryDirectory() as tmp:
            clone = Path(tmp)/"repo"
            subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", str(ROOT), str(clone)], check=True)
            path = clone/"scripts/market_collector/contracts.py"
            path.write_bytes(path.read_bytes()+b"\n# changed\n")
            with self.assertRaisesRegex(ValueError, "differs"):release.build(clone, self.commit)
            subprocess.run(["git", "restore", "--", str(path.relative_to(clone))], cwd=clone, check=True)
            path.unlink();path.symlink_to(ROOT/"scripts/market_collector/contracts.py")
            with self.assertRaisesRegex(ValueError, "symlink"):release.build(clone, self.commit)

    def test_package_has_no_secret_environment_or_unlisted_private_files(self):
        sentinel = "SYNTHETIC-CREDENTIAL-CANARY-DO-NOT-PACKAGE"
        with patch.dict(os.environ, {"MOSA_TEST_DB_PASSWORD": sentinel,
                                     "MOSA_TEST_SFTP_PASSWORD": sentinel}), \
             patch.object(socket, "socket", side_effect=AssertionError("offline only")):
            archive, manifest = release.build(ROOT, self.commit)
        self.assertNotIn(sentinel.encode(), archive+manifest)
        names = {r["path"] for r in self.metadata["files"]}
        self.assertFalse(any("tests/" in n or "diagnostic" in n or "actions_acceptance" in n for n in names))
        self.assertNotIn("scripts/deploy_sftp.py", names)
        template = json.loads((ROOT/"config/collector-private.example.json").read_text())
        self.assertIsNone(template["approved_root"])
        self.assertFalse(template["execution_enabled"])
        self.assertFalse(template["upload_enabled"])

    def test_packaged_php_include_closure_is_loadable_with_no_legacy_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.materialize(Path(tmp)/"release")
            code = 'require $argv[1]; echo json_encode(get_included_files());'
            result = subprocess.run(["php", "-r", code, str(root/"scripts/market_collector/live_batch.php")],
                                    capture_output=True, text=True, check=True, timeout=10)
            included = {Path(p).relative_to(root).as_posix() for p in json.loads(result.stdout)}
            contract = json.loads((ROOT/release.CONTRACT).read_text())
            graph = {r["path"]: r["requires"] for r in contract["files"]}
            expected, pending = set(), ["scripts/market_collector/live_batch.php"]
            while pending:
                path = pending.pop()
                if path in expected:continue
                expected.add(path)
                pending.extend(p for p in graph[path] if p.endswith(".php"))
            self.assertEqual(included, expected)
            self.assertFalse(result.stderr)
            release.validate_directory(root, self.metadata)

    def test_same_package_for_one_two_five_assets_and_real_normalizer_replay(self):
        fixture = fixtures.FrankfurtCollectorTests();fixture.setUp()
        acquired = dict(adapter_module="scripts.market_collector.boerse_frankfurt",
                        adapter_class="FrankfurtSnapshotV1", provider_key=fixture.adapter.provider_key,
                        instrument=fixture.request.instrument, request_key=fixture.request.request_key,
                        requested_at=fixture.request.requested_at,
                        response=None)
        # Explicit response serialization uses the unchanged bridge transport.
        from dataclasses import asdict, replace
        from test_market_live_batch import isin
        acquired["response"] = live_bridge.transport(asdict(fixture.response))
        with tempfile.TemporaryDirectory() as tmp:
            root = self.materialize(Path(tmp)/"release")
            for size in (1, 2, 5):
                for index in range(size):
                    route = dict(fixture.route.route, id=str(302+index), asset_id=str(102+index))
                    instrument = isin(index+1)
                    document = json.loads(fixture.response.payload_bytes)
                    document["isin"] = instrument
                    response = replace(fixture.response, payload_bytes=json.dumps(document).encode())
                    item = dict(acquired, instrument=instrument,
                                response=live_bridge.transport(asdict(response)))
                    request = dict(action="plan", acquired=item, route=route,
                                   created_at=fixture.created, existing=[])
                    expected = live_bridge.run(request)
                    self.assertEqual(expected["plan"]["decision"], "INSERT")
                    result = subprocess.run([sys.executable, "-I", "-B",
                                str(root/"scripts/market_collector/live_bridge.py")],
                                input=json.dumps(request), capture_output=True, text=True, check=True, timeout=20)
                    self.assertEqual(json.loads(result.stdout), expected)
                    self.assertFalse(result.stderr)
                    plan = expected["plan"]
                    request = dict(action="replay", route=route, stored=plan["normalized"],
                        created_at=fixture.created, existing=[dict(format_version=2,
                            payload=plan["normalized"], dedupe_key=plan["dedupe_key"])])
                    result = subprocess.run([sys.executable, "-I", "-B",
                                str(root/"scripts/market_collector/live_bridge.py")],
                                input=json.dumps(request), capture_output=True, text=True, check=True, timeout=20)
                    self.assertEqual(json.loads(result.stdout), live_bridge.run(request))
                    self.assertEqual(json.loads(result.stdout)["plan"]["decision"], "DUPLICATE_UNCHANGED")
            release.validate_directory(root, self.metadata)

    def test_runtime_pins_and_child_php_path_are_fixed_without_core_changes(self):
        runtime = (ROOT/"scripts/collector_release/runtime.php").read_text()
        contract = json.loads((ROOT/release.CONTRACT).read_text())
        for text in ("/opt/alt/python311/bin/python3.11", "3.11.17",
                     "/opt/plesk/php/8.4/bin/php", "8.4.12",
                     "/opt/plesk/php/8.4/bin:/usr/bin:/bin"):
            self.assertIn(text, runtime)
        self.assertNotIn("MarketBatch\\run(", runtime)
        for row in contract["files"]:
            if row["path"].startswith("scripts/market_collector/") or "/phase" in row["path"]:
                self.assertIsNotNone(row["source_blob"])


class PrivateDeploymentTests(unittest.TestCase):
    def test_missing_or_forged_approval_always_blocks_before_remote_or_environment_access(self):
        class NoRemote:
            def __getattr__(self, key):raise AssertionError("remote access")
        with patch.dict(os.environ, {}, clear=True):
            for approved in (None, False, True, {"authorized": True, "root": private.PROPOSED_ROOT}):
                with self.assertRaises(PermissionError):
                    private.upload(NoRemote(), approval=approved)

    def test_proposal_is_not_authorization_and_rejects_webroots_and_path_manipulation(self):
        result = private.proposal(private.PROPOSED_ROOT, ())
        self.assertFalse(result["authorized"])
        self.assertFalse(result["remote_verified"])
        self.assertFalse(result["upload_enabled"])
        self.assertEqual(result["plan_reserve_bytes"], 64*1024*1024)
        for path in (private.shared.TEST_ROOT, private.shared.ABSOLUTE_ROOT, "/", "../x",
                     private.PROPOSED_ROOT+"/../x", private.PROPOSED_ROOT+"/", private.PROPOSED_ROOT+"//x",
                     private.shared.TEST_ROOT+"/private", "/var/www/vhosts"):
            with self.subTest(path=path), self.assertRaises(ValueError):private.proposal(path, ())
        with self.assertRaises(ValueError):
            private.proposal(private.PROPOSED_ROOT, (private.PROPOSED_ROOT,))

    def test_shared_host_key_algorithm_and_existing_deployment_are_unchanged(self):
        key = b"SYNTHETIC-HOST-KEY"
        pin = "SHA256:"+base64.b64encode(hashlib.sha256(key).digest()).decode().rstrip("=")
        private.verify_host_key_material(key, pin)
        with self.assertRaises(ValueError):private.verify_host_key_material(b"wrong", pin)
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
        paths = ("scripts/deploy_sftp.py", "scripts/deploy_test_sftp.py",
                 ".github/workflows/deploy-testsite.yml")
        expected_blobs = {"scripts/deploy_sftp.py":"7678f600876b72899da9f35b4ca21b23ba22868c","scripts/deploy_test_sftp.py":"cf4f5cce8225168d3783139bd740ca420ac79233",".github/workflows/deploy-testsite.yml":"1d06c152acd88a74e775c8c96caa0a82d525d8d1"}
        for path in paths:
            self.assertEqual(release.git(ROOT, "rev-parse", commit+":"+path).decode().strip(),
                             expected_blobs[path])


if __name__ == "__main__":
    unittest.main()
