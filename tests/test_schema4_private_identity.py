"""Private-path identity across actual generated Schema-4 helpers; no remote I/O."""
from contextlib import contextmanager
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from scripts import deploy_private_collector as deploy
from scripts import collector_schema4_once as once
from test_collector_private_directories import FakeOS


class Schema4PrivateIdentityTests(unittest.TestCase):
    commit = "a" * 40

    def setUp(self):
        self.files = {"scripts/synthetic.php": b"<?php // offline fixture\n"}
        self.meta = dict(format="mosa2-collector-release-v1", commit=self.commit,
            payload_bytes=sum(map(len, self.files.values())), runtime={}, files=[dict(
                path=p, size=len(raw), sha256=hashlib.sha256(raw).hexdigest(), mode="0600")
                for p, raw in self.files.items()])
        self.manifest = (json.dumps(self.meta, sort_keys=True, separators=(",", ":")) + "\n").encode()

    def wire(self, **extra):
        return dict(commit=self.commit, authorization=once.TOKEN + self.commit, run_id="123",
            manifest=self.meta, manifest_sha256=hashlib.sha256(self.manifest).hexdigest(), **extra)

    def scope(self, kind="upload"):
        scope = {"__name__": "fixture"}
        source = (once.remote_source(self.meta) if kind == "supervisor" else
                  deploy.remote_source("schema4-once", self.meta) if kind == "upload" else
                  deploy.remote_source())
        modules = {name: Mock() for name in ("fcntl", "resource")} if os.name == "nt" else {}
        with patch.dict(sys.modules, modules):
            exec(compile(source, "<schema4-path-identity>", "exec"), scope)
        api = FakeOS(scope)
        api.nodes[scope["BASE"]].st_dev = 70000
        api.nodes[scope["BASE"]].st_ino = 8000000
        for index, path in enumerate(scope["TARGETS"]):
            api.nodes[path] = SimpleNamespace(st_mode=stat.S_IFDIR | 0o700,
                st_uid=10317, st_gid=1003, st_dev=70000, st_ino=9000000 + index)
        scope["os"] = api
        return scope, api

    def captured(self):
        scope, api = self.scope()
        snapshot = scope["bind_private_paths"](self.wire(action="prepare"), capture=True)
        expected = {path: [api.nodes[path].st_dev, api.nodes[path].st_ino]
                    for path in (scope["BASE"], *scope["TARGETS"])}
        self.assertEqual(snapshot, expected)
        self.assertEqual(api.writes, [])
        self.assertEqual(api.fds, {})
        return scope, api, snapshot

    def test_current_identity_is_checked_and_carried_into_generated_supervisor(self):
        scope, api, snapshot = self.captured()
        scope["guard"]()
        # Fresh interpreters must accept the captured identities, including the
        # supervisor assembled after the historical supervisor's guard function.
        for kind in ("upload", "supervisor"):
            with self.subTest(helper=kind):
                fresh, filesystem = self.scope(kind)
                data = self.wire(action="inspect", private_path_identity=copy.deepcopy(snapshot))
                if kind == "upload":
                    result = fresh["upload_operation"](data)
                    self.assertTrue(result["ok"])
                else:
                    fresh["bind_private_paths"](data)
                fresh["guard"]()
                self.assertEqual(filesystem.writes, [])
                self.assertEqual(filesystem.fds, {})

    def test_changed_base_or_private_identity_is_rejected_within_and_between_phases(self):
        for target in ("base", "private"):
            for field in ("st_dev", "st_ino"):
                with self.subTest(target=target, field=field):
                    scope, api, snapshot = self.captured()
                    path = scope["BASE"] if target == "base" else scope["TARGETS"][-1]
                    setattr(api.nodes[path], field, getattr(api.nodes[path], field) + 1)
                    with self.assertRaises(scope["Stop"]):
                        scope["guard"]()
                    self.assertEqual(api.writes, [])
                    self.assertEqual(api.fds, {})
                    for kind in ("upload", "supervisor"):
                        fresh, filesystem = self.scope(kind)
                        setattr(filesystem.nodes[path], field, getattr(filesystem.nodes[path], field) + 1)
                        with self.assertRaises(fresh["Stop"]):
                            fresh["bind_private_paths"](self.wire(private_path_identity=snapshot))
                        self.assertEqual(filesystem.writes, [])
                        self.assertEqual(filesystem.fds, {})

    def test_capture_preserves_owner_mode_symlink_canonical_and_race_checks(self):
        for defect in ("base_owner", "private_owner", "mode", "symlink", "canonical", "cwd", "race"):
            with self.subTest(defect=defect):
                scope, api = self.scope()
                if defect == "base_owner":
                    api.nodes[scope["BASE"]].st_uid = 0
                elif defect == "private_owner":
                    api.nodes[scope["TARGETS"][0]].st_gid = 1002
                elif defect == "mode":
                    api.nodes[scope["TARGETS"][-1]].st_mode = stat.S_IFDIR | 0o755
                elif defect == "symlink":
                    api.nodes[scope["TARGETS"][0]].st_mode = stat.S_IFLNK | 0o777
                elif defect == "canonical":
                    api.canonical_override = "/unexpected"
                elif defect == "cwd":
                    api.cwd = "/"
                else:
                    api.mutate_inode = True
                with self.assertRaises(scope["Stop"]):
                    scope["bind_private_paths"](self.wire(action="prepare"), capture=True)
                self.assertEqual(api.writes, [])
                self.assertEqual(api.fds, {})

    def test_later_phase_cannot_recapture_or_accept_missing_or_malformed_snapshot(self):
        scope, api, snapshot = self.captured()
        with self.assertRaises(scope["Stop"]):
            scope["bind_private_paths"](self.wire(action="prepare"), capture=True)
        for defect in ("missing", "short", "extra", "bool", "zero_inode"):
            with self.subTest(defect=defect):
                fresh, filesystem = self.scope()
                data = self.wire(action="inspect")
                modified = copy.deepcopy(snapshot)
                if defect == "short":
                    modified.pop(fresh["TARGETS"][-1])
                elif defect == "extra":
                    modified["/unexpected"] = [70000, 1]
                elif defect == "bool":
                    modified[fresh["BASE"]][0] = True
                elif defect == "zero_inode":
                    modified[fresh["BASE"]][1] = 0
                if defect != "missing":
                    data["private_path_identity"] = modified
                with self.assertRaises(fresh["Stop"]):
                    fresh["upload_operation"](data)
                self.assertEqual(filesystem.writes, [])
                self.assertEqual(filesystem.fds, {})
        fresh, filesystem = self.scope()
        with self.assertRaises(fresh["Stop"]):
            fresh["bind_private_paths"](self.wire(action="inspect"), capture=True)
        self.assertEqual(filesystem.writes, [])

    def test_controllers_preserve_one_snapshot_through_upload_and_execution(self):
        _, _, snapshot = self.captured()
        modules = deploy.modules()
        captured = []
        @contextmanager
        def ssh(*args):
            yield Mock()
        def remote_call(transport, action, data, **options):
            captured.append((action, copy.deepcopy(data)))
            if action == "prepare":
                return dict(ok=True, staging=deploy.PROPOSED_ROOT + "/staging/" + self.commit + "-123",
                    stage_inode=100, lock_inode=200, private_path_identity=copy.deepcopy(snapshot))
            return dict(ok=True)
        env = dict(GITHUB_ACTIONS="true", GITHUB_RUN_ATTEMPT="1", GITHUB_RUN_ID="123",
            GITHUB_EVENT_NAME="workflow_dispatch", GITHUB_REF="refs/heads/main",
            GITHUB_REPOSITORY="masterxfix/MOSA-2", GITHUB_SHA=self.commit,
            MOSA_PRIVATE_EXPECTED_COMMIT=self.commit,
            MOSA_PRIVATE_UPLOAD_AUTHORIZATION=deploy.SCHEMA4_TOKEN + self.commit,
            MOSA_SCHEMA4_EXPECTED_COMMIT=self.commit,
            MOSA_SCHEMA4_AUTHORIZATION=once.TOKEN + self.commit,
            MOSA_TEST_DB_PASSWORD="SYNTHETIC-SECRET")
        with patch.object(modules[3], "git", return_value=(self.commit + "\n").encode()), \
             patch.object(deploy, "artifact", return_value=(self.meta, self.manifest, self.files)), \
             patch.object(modules[3], "build", return_value=(b"offline", self.manifest)), \
             patch("deploy_test_sftp.configuration", return_value={}), \
             patch.object(modules[0], "ssh_client", side_effect=ssh), \
             patch.object(deploy, "call", side_effect=remote_call), \
             patch.object(deploy, "readback", return_value={"status": "PASS"}):
            installation = deploy.upload(deploy.PROPOSED_ROOT, env=env,
                paramiko=MagicMock(), profile="schema4-once")
        self.assertTrue(installation["ok"], installation)
        self.assertEqual([action for action, _ in captured], ["prepare", "inspect", "publish", "inspect"])
        self.assertNotIn("private_path_identity", captured[0][1])
        for _, data in captured[1:]:
            self.assertEqual(data["private_path_identity"], snapshot)
        self.assertEqual(installation["private_path_identity"], snapshot)
        complete = dict(ok=True, status="COMPLETE", provider_requests=1,
            readback="PASS", web_readback="PASS", release_readback="PASS")
        with patch.object(once.shared, "configuration", return_value={}), \
             patch.object(once.release, "git", return_value=(self.commit + "\n").encode()), \
             patch.object(once.upload, "artifact", return_value=(self.meta, self.manifest, {})), \
             patch.object(once.shared, "ssh_client", side_effect=ssh), \
             patch.object(once, "runtime"), \
             patch.object(once.upload, "upload", return_value=installation), \
             patch.object(once.remote, "remote_call", return_value=(
                 0, json.dumps(complete).encode(), False, 1)) as execute:
            report = once.execute(env, paramiko=Mock())
        self.assertTrue(report["ok"], report)
        self.assertEqual(execute.call_count, 1)
        dispatched = json.loads(execute.call_args.args[2])
        self.assertEqual(dispatched["private_path_identity"], snapshot)

    def test_historical_profile_still_rejects_changed_original_identity(self):
        scope, api = self.scope("historical")
        with self.assertRaisesRegex(scope["Stop"], "BASE_IDENTITY_CHANGED"):
            scope["guard"]()
        self.assertEqual(api.writes, [])
        self.assertEqual(api.fds, {})
        self.assertNotIn("bind_private_paths", scope)


if __name__ == "__main__":
    unittest.main()
