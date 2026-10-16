"""Offline safety tests; no credentials, network or production filesystem."""

import base64
import hashlib
import importlib.util
import io
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "deployment", Path(__file__).resolve().parents[1] / "scripts/deploy_sftp.py"
)
deployment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deployment)


class FakeSFTP:
    def __init__(self):
        self.nodes = {"/mosa.scharwerk.de": stat.S_IFDIR | 0o755}
        self.writes = []
        self.contents = {}

    def lstat(self, path):
        if path not in self.nodes:
            raise FileNotFoundError(2, "not found")
        return SimpleNamespace(st_mode=self.nodes[path])

    def mkdir(self, path):
        self.writes.append(path)
        self.nodes[path] = stat.S_IFDIR | 0o755

    def open(self, path, mode):
        if mode == "rb":
            return io.BytesIO(self.contents[path])
        self.writes.append(path)
        owner = self

        class Output(io.BytesIO):
            def close(self):
                owner.contents[path] = self.getvalue()
                super().close()

        return Output()

    def posix_rename(self, source, target):
        self.writes.append(target)
        self.contents[target] = self.contents.pop(source)


class DeploymentTests(unittest.TestCase):
    def config(self):
        # Synthetic offline fixtures, never usable production credentials.
        return dict(zip(deployment.SECRET_NAMES, (
            "server10.configcenter.info", "22", "offline-fixture", "offline-fixture",
            "mosa.scharwerk.de", "SHA256:" + "A" * 43,
        )))

    def test_every_missing_secret_fails_before_connection(self):
        for name in deployment.SECRET_NAMES:
            with self.subTest(name=name):
                env = self.config()
                env[name] = ""
                with patch.dict(deployment.os.environ, env, clear=True), \
                        patch.object(deployment, "deploy") as connect, \
                        patch("sys.argv", ["deploy_sftp.py", "deploy"]):
                    with self.assertRaisesRegex(ValueError, name):
                        deployment.main()
                    connect.assert_not_called()

    def test_rejects_other_domains_parent_paths_and_invalid_ports(self):
        for path in ("/", ".", "httpdocs", "../mosa.scharwerk.de",
                     "mosa.scharwerk.de/../scharwerk.de", "/mosa.scharwerk.de/",
                     "/httpdocs/scharwerk.de", "/mosa.scharwerk.de-other"):
            with self.subTest(path=path):
                env = self.config()
                env["MOSA_DEPLOY_PATH"] = path
                with self.assertRaises(ValueError):
                    deployment.configuration(env)
        for port in ("0", "65536", "22; echo unsafe"):
            env = self.config()
            env["MOSA_DEPLOY_PORT"] = port
            with self.assertRaises(ValueError):
                deployment.configuration(env)
        env = self.config()
        env["MOSA_DEPLOY_HOST"] = "other.example"
        with self.assertRaises(ValueError):
            deployment.configuration(env)

    def test_host_key_must_match(self):
        key = b"offline host-key fixture"
        fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(key).digest()).decode().rstrip("=")
        deployment.verify_fingerprint(key, fingerprint)
        with self.assertRaises(ValueError):
            deployment.verify_fingerprint(b"wrong key", fingerprint)

    def test_requires_visible_mosa_not_metadata_or_hidden_text(self):
        deployment.validate_html(b"<html><body><h1>MOSA</h1></body></html>")
        for html in (b"<head><title>MOSA</title></head><body>Other</body>",
                     b"<!-- MOSA -->", b"<script>MOSA</script>",
                     b"<div hidden>MOSA</div>", b"<p style='display:none'>MOSA</p>",
                     b"<h1>MOSAIC</h1>"):
            with self.subTest(html=html), self.assertRaises(ValueError):
                deployment.validate_html(html)

    def test_packages_entire_tracked_web_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, content in {
                "index.html": "<h1>MOSA</h1>", "assets/site.css": "body {}",
                "php/app.php": "<?php echo 'MOSA';", ".htaccess": "Options -Indexes",
                "docs/private.md": "not deployed", "tests/check.py": "not deployed",
                "scripts/build.py": "not deployed", "README.md": "not deployed",
                ".github/workflows/deploy.yml": "not deployed",
            }.items():
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(content, encoding="utf-8")
            (root / "untracked.txt").write_text("not deployed", encoding="utf-8")
            names = [p.relative_to(root).as_posix() for p in root.rglob("*")
                     if p.is_file() and p.name != "untracked.txt"]
            tracked = "\0".join("100644 " + "0" * 40 + " 0\t" + n for n in names)
            with patch.object(deployment.subprocess, "check_output", return_value=tracked.encode()):
                self.assertEqual(set(dict(deployment.web_files(root))),
                                 {"index.html", "assets/site.css", "php/app.php", ".htaccess"})
                (root / "index.html").unlink()
                with self.assertRaises(FileNotFoundError):
                    deployment.web_files(root)

    def test_remote_preflight_rejects_links_before_any_write(self):
        for path in ("/mosa.scharwerk.de", "/mosa.scharwerk.de/assets",
                     "/mosa.scharwerk.de/index.html"):
            sftp = FakeSFTP()
            sftp.nodes[path] = stat.S_IFLNK | 0o777
            with self.subTest(path=path), self.assertRaises(ValueError):
                deployment.upload(sftp, "/mosa.scharwerk.de",
                                  [("index.html", b"MOSA"), ("assets/site.css", b"body {}")])
            self.assertEqual(sftp.writes, [])

    def test_remote_root_must_be_exact_and_existing(self):
        for root in ("/", "/httpdocs/scharwerk.de", "/mosa.scharwerk.de-other"):
            sftp = FakeSFTP()
            with self.assertRaises(ValueError):
                deployment.upload(sftp, root, [("index.html", b"MOSA")])
            self.assertEqual(sftp.writes, [])
        sftp = FakeSFTP()
        sftp.nodes.clear()
        with self.assertRaises(ValueError):
            deployment.upload(sftp, "/mosa.scharwerk.de", [("index.html", b"MOSA")])
        self.assertEqual(sftp.writes, [])

    def test_upload_tree_and_readback_stay_inside_root(self):
        sftp = FakeSFTP()
        files = [("index.html", b"MOSA"), ("assets/css/site.css", b"body {}")]
        deployment.upload(sftp, "/mosa.scharwerk.de", files)
        for name, content in files:
            self.assertEqual(sftp.contents["/mosa.scharwerk.de/" + name], content)
        self.assertTrue(all(p.startswith("/mosa.scharwerk.de/") for p in sftp.writes))

    def test_permission_and_transfer_errors_propagate(self):
        sftp = FakeSFTP()
        with patch.object(sftp, "lstat", side_effect=PermissionError(13, "denied")):
            with self.assertRaises(PermissionError):
                deployment.upload(sftp, "/mosa.scharwerk.de", [("index.html", b"MOSA")])
        self.assertEqual(sftp.writes, [])
        with patch.object(sftp, "posix_rename", side_effect=OSError("transfer failed")):
            with self.assertRaises(OSError):
                deployment.upload(sftp, "/mosa.scharwerk.de", [("index.html", b"MOSA")])

    def test_readback_mismatch_never_replaces_destination(self):
        sftp = FakeSFTP()
        original_open = sftp.open

        def corrupt_readback(path, mode):
            return io.BytesIO(b"corrupted") if mode == "rb" else original_open(path, mode)

        with patch.object(sftp, "open", side_effect=corrupt_readback), \
                patch.object(sftp, "posix_rename") as replace:
            with self.assertRaisesRegex(ValueError, "readback mismatch"):
                deployment.upload(sftp, "/mosa.scharwerk.de", [("index.html", b"MOSA")])
            replace.assert_not_called()

    def test_local_env_keys_and_symlinks_are_rejected(self):
        for name, mode in ((".env", "100644"), ("config/private.key", "100644"),
                           ("assets/link", "120000"), ("../other/index.html", "100644")):
            entry = f"{mode} {'0' * 40} 0\t{name}\0".encode()
            with self.subTest(name=name), \
                    patch.object(deployment.subprocess, "check_output", return_value=entry):
                with self.assertRaises(ValueError):
                    deployment.web_files()


if __name__ == "__main__":
    unittest.main()
