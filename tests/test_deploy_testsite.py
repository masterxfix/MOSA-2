"""Offline tests of testsite scope, explicit file sets and probe lifecycle."""
import importlib.util
import io
from pathlib import Path
import stat
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import deploy_test_sftp as testsite
import deploy_sftp as shared

SPEC = importlib.util.spec_from_file_location("legacy_test_fixtures", Path(__file__).with_name("test_deployment.py"))
fixtures = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixtures)


class ScopedSFTP(fixtures.FakeSFTP):
    def __init__(self):
        super().__init__()
        self.nodes = {shared.TEST_ROOT: stat.S_IFDIR | 0o755}
        self.accesses = []
        self.removed = []

    def lstat(self, path):
        self.accesses.append(path)
        return super().lstat(path)

    def open(self, path, mode):
        self.accesses.append(path)
        return super().open(path, mode)

    def posix_rename(self, source, target):
        self.accesses.extend([source, target])
        super().posix_rename(source, target)
        self.nodes[target] = stat.S_IFREG | 0o644

    def remove(self, path):
        self.removed.append(path)
        self.accesses.append(path)
        del self.nodes[path]
        del self.contents[path]


class TestsiteDeploymentTests(unittest.TestCase):
    def env(self):
        values = dict(testsite.EXPECTED, PASSWORD="offline-test-fixture",
                      HOST_KEY_SHA256="SHA256:" + "A" * 43)
        return {testsite.PREFIX + key: value for key, value in values.items()}

    def test_all_required_configuration_fails_before_connection(self):
        for name in testsite.NAMES:
            env = self.env()
            env[name] = ""
            with self.subTest(name=name), patch.dict(testsite.os.environ, env, clear=True), \
                    patch.object(testsite, "execute") as connect, \
                    patch("sys.argv", ["deploy_test_sftp.py", "probe"]):
                with self.assertRaises(ValueError):
                    testsite.main()
                connect.assert_not_called()

    def test_exact_host_port_user_and_root_only(self):
        for key, bad in [("HOST", "mosa.scharwerk.de"), ("PORT", "2222"),
                         ("USER", "web213_vscode"), ("PATH", shared.ABSOLUTE_ROOT),
                         ("PATH", shared.TEST_ROOT + "/"), ("PATH", "/mosa2-test.scharwerk.de"),
                         ("PATH", shared.TEST_ROOT + "/../mosa.scharwerk.de")]:
            env = self.env()
            env[testsite.PREFIX + key] = bad
            with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                testsite.configuration(env)
        self.assertEqual(testsite.configuration(self.env())["path"], shared.TEST_ROOT)

    def test_profiles_cannot_cross_targets(self):
        for profile, root in [("test", shared.ABSOLUTE_ROOT), ("test", "/mosa.scharwerk.de"),
                              ("legacy", shared.TEST_ROOT), ("typo", shared.TEST_ROOT)]:
            sftp = ScopedSFTP()
            with self.subTest(profile=profile, root=root), self.assertRaises(ValueError):
                shared.upload(sftp, root, [("index.html", b"MOSA")], profile=profile)
            self.assertEqual(sftp.accesses, [])

    def test_unsafe_filenames_rejected_before_remote_access(self):
        for name in ("../other", "/index.html", "assets/../../other", "a\\b", "a//b", "a\nb", ""):
            sftp = ScopedSFTP()
            with self.subTest(name=name), self.assertRaises(ValueError):
                shared.upload(sftp, shared.TEST_ROOT, [(name, b"x")], profile="test")
            self.assertEqual(sftp.accesses, [])

    def test_symlinks_in_explicit_set_rejected_before_writes(self):
        sftp = ScopedSFTP()
        sftp.nodes[shared.TEST_ROOT + "/api"] = stat.S_IFLNK | 0o777
        with self.assertRaises(ValueError):
            shared.upload(sftp, shared.TEST_ROOT,
                          [("index.html", b"MOSA"), ("api/market.php", b"x")], profile="test")
        self.assertEqual(sftp.writes, [])

    def test_explicit_file_set_never_selects_other_tracked_files(self):
        with patch.object(shared, "web_files", return_value=[("index.html", b"MOSA"), ("api/market.php", b"php")]):
            self.assertEqual(testsite.selected_files('["index.html"]'), [("index.html", b"MOSA")])
            for encoded in ('[]', '{}', 'null', '["../other"]', '["index.html","index.html"]', '[1]', 'bad json'):
                with self.subTest(encoded=encoded), self.assertRaises(ValueError):
                    testsite.selected_files(encoded)

    def test_probe_upload_rename_readback_delete_stay_inside_test_root(self):
        sftp = ScopedSFTP()
        testsite.probe(sftp, "offline-run")
        self.assertEqual(len(sftp.removed), 1)
        self.assertEqual(sftp.contents, {})
        self.assertEqual(sftp.nodes, {shared.TEST_ROOT: stat.S_IFDIR | 0o755})
        self.assertTrue(all(p == shared.TEST_ROOT or p.startswith(shared.TEST_ROOT + "/") for p in sftp.accesses))
        self.assertTrue(any("/.mosa-upload-" in p for p in sftp.writes))
        self.assertTrue(sftp.removed[0].startswith(shared.TEST_ROOT + "/.mosa2-actions-probe-"))

    def test_corrupt_final_readback_is_not_deleted_or_reported_success(self):
        sftp = ScopedSFTP()
        original = sftp.open
        def read(path, mode):
            if mode == "rb" and "/.mosa2-actions-probe-" in path:
                return io.BytesIO(b"corrupt")
            return original(path, mode)
        with patch.object(sftp, "open", side_effect=read), self.assertRaises(ValueError):
            testsite.probe(sftp, "offline-run")
        self.assertEqual(sftp.removed, [])

    def test_workflow_is_manual_and_uses_separate_configuration(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/deploy-testsite.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("  push:", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertNotIn("MOSA_DEPLOY_", workflow)
        self.assertIn("default: probe", workflow)
        self.assertIn("persist-credentials: false", workflow)
        for name in testsite.NAMES:
            self.assertIn(name, workflow)


if __name__ == "__main__":
    unittest.main()
