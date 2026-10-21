"""Finite-path metadata safety tests; fake OS/SFTP only, no network or DB."""
from contextlib import contextmanager
import ast
import copy
import errno
import json
from pathlib import Path
import stat
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"scripts"))
import collector_private_path as probe


def attrs(mode=stat.S_IFDIR|0o700, uid=1001, gid=1002):
    return SimpleNamespace(st_mode=mode, st_uid=uid, st_gid=gid, st_size=4096,
                           st_mtime=100, st_dev=8, st_ino=12)


class FakeOS:
    def __init__(self, nodes=None, cwd="/"):
        self.nodes = dict(nodes or {})
        self.calls = []
        self.cwd = cwd
    def getcwd(self):return self.cwd
    def getuid(self):return 1001
    def geteuid(self):return 1001
    def getgid(self):return 1002
    def getegid(self):return 1002
    def lstat(self, path):
        self.calls.append(("lstat", path))
        v = self.nodes.get(path, FileNotFoundError(errno.ENOENT, "synthetic"))
        if isinstance(v, Exception):raise v
        return v
    def statvfs(self, path):
        self.calls.append(("statvfs", path))
        return SimpleNamespace(f_frsize=4096, f_blocks=100, f_bfree=80, f_bavail=70,
                               f_files=50, f_ffree=40, f_favail=30)


class FakeSFTP(FakeOS):
    def __init__(self, nodes=None):
        super().__init__(nodes)
        self.timeouts = []
    def get_channel(self):return self
    def settimeout(self, t):self.timeouts.append(t)
    def normalize(self, path):
        self.calls.append(("normalize", path))
        return probe.HOST_ROOT
    def __enter__(self):return self
    def __exit__(self, *args):pass


def remote_assess(api, context=probe.HOST_ROOT):
    scope = {"__name__":"fixture"}
    exec(compile(probe.REMOTE_SOURCE, "<read-only-probe>", "exec"), scope)
    return scope["assess"](api, context)


def full_nodes():
    nodes = {p:attrs() for p in (*probe.CHAIN, probe.TEST_ROOT)}
    for i, value in enumerate(nodes.values()):value.st_ino = 100+i
    return nodes


class PrivatePathTests(unittest.TestCase):
    def test_full_paths_owner_mode_capacity_and_matching_views(self):
        api = FakeOS(full_nodes(), probe.HOST_ROOT)
        ssh = remote_assess(api)
        sftp = probe.sftp_probe(FakeSFTP(full_nodes()))
        r = probe.compare(ssh, sftp)
        self.assertEqual(ssh["selected_view"], "HOST_ABSOLUTE")
        self.assertEqual(r["path_views"], "MATCH_METADATA")
        self.assertEqual(r["webroot_isolation"], "PASS")
        self.assertEqual(r["all_webroots_and_public_urls"], "UNCONFIRMED")
        self.assertEqual(ssh["capacity"]["available_bytes"], 70*4096)
        self.assertEqual(ssh["capacity"]["available_inodes"], 30)
        self.assertEqual(ssh["capacity"]["hosting_quota"], "UNCONFIRMED")
        self.assertEqual(ssh["selected_chain"][-1]["mode"], "0700")
        self.assertEqual(ssh["selected_chain"][-1]["uid"], 1001)

    def test_missing_target_or_parent_is_not_created_and_capacity_uses_existing_ancestor(self):
        for missing in (probe.PRIVATE_ROOT, probe.HOST_ROOT+"/private"):
            nodes = full_nodes();del nodes[missing]
            api = FakeOS(nodes)
            r = remote_assess(api)
            self.assertEqual(r["selected_chain"][-1]["status"], "MISSING")
            self.assertEqual(r["selected_chain"][-1]["path"], missing)
            self.assertNotEqual(r["capacity"]["path"], missing)
            self.assertFalse(any(p.startswith(missing+"/") for op,p in api.calls))
            self.assertTrue(all(op in ("lstat","statvfs") for op,p in api.calls))

    def test_finite_chroot_alias_requires_enoent_and_canonical_anchor(self):
        nodes = {p:attrs() for p in ("/","/private","/private/mosa2-collector","/mosa2-test.scharwerk.de")}
        api = FakeOS(nodes)
        r = remote_assess(api)
        self.assertEqual(r["selected_view"], "CHROOT_RELATIVE")
        self.assertEqual(probe.compare(r, probe.sftp_probe(FakeSFTP(full_nodes())))["path_views"],
                         "MATCH_METADATA")
        self.assertTrue(set(p for op,p in api.calls) <=
                        set(probe.CHAIN)|set(nodes))
        no_context = remote_assess(FakeOS(nodes), None)
        self.assertIsNone(no_context["selected_view"])

    def test_denial_symlink_non_directory_never_followed_or_bypassed(self):
        for value in (PermissionError(errno.EACCES,"private-message"),
                      PermissionError(errno.EPERM,"private-message"),
                      attrs(stat.S_IFLNK|0o777),attrs(stat.S_IFREG|0o600)):
            nodes = full_nodes();nodes["/var/www"] = value
            api = FakeOS(nodes)
            r = remote_assess(api)
            self.assertIsNone(r["selected_view"])
            self.assertIsNone(r["capacity"])
            self.assertEqual(api.calls, [("lstat","/"),("lstat","/var"),("lstat","/var/www")])
            ftp = FakeSFTP(nodes)
            f = probe.sftp_probe(ftp)
            self.assertIsNone(f["anchor"])
            self.assertEqual(ftp.calls, api.calls)
        # Also stop at a private-parent link in the chroot view.
        api = FakeOS({"/":attrs(),"/private":attrs(stat.S_IFLNK|0o777)})
        r = remote_assess(api)
        self.assertIsNone(r["test_webroot"])
        self.assertIsNone(r["capacity"])
        self.assertNotIn(("lstat","/private/mosa2-collector"),api.calls)

    def test_mismatch_or_missing_webroot_never_claims_proven_isolation(self):
        ssh = remote_assess(FakeOS(full_nodes()))
        sftp = probe.sftp_probe(FakeSFTP(full_nodes()))
        changed = copy.deepcopy(sftp)
        changed["chain"][-1]["uid"] += 1
        self.assertEqual(probe.compare(ssh,changed)["path_views"],"UNCONFIRMED")
        changed = copy.deepcopy(sftp);changed["test_webroot"]=None
        self.assertEqual(probe.compare(ssh,changed)["webroot_isolation"],"UNCONFIRMED")
        alias = copy.deepcopy(ssh)
        alias["test_webroot"]["inode"] = alias["selected_chain"][-1]["inode"]
        self.assertEqual(probe.compare(alias,sftp)["webroot_isolation"],"FAIL")

    def test_sftp_only_finite_metadata_and_enforces_budget(self):
        ftp = FakeSFTP(full_nodes())
        probe.sftp_probe(ftp)
        self.assertTrue(all(op in ("lstat","normalize") for op,p in ftp.calls))
        self.assertTrue(set(p for op,p in ftp.calls) <= set(probe.CHAIN)|{probe.TEST_ROOT,"."})
        self.assertTrue(all(0<t<=8 for t in ftp.timeouts))
        with self.assertRaises(probe.remote.ProbeError):
            probe.sftp_probe(FakeSFTP(full_nodes()), clock=Mock(side_effect=[0,46]))

    def test_remote_source_has_no_write_inventory_db_or_subprocess_capability(self):
        tree = ast.parse(probe.REMOTE_SOURCE)
        calls = {n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertFalse(calls & {"mkdir","makedirs","chmod","chown","unlink","remove","rename",
                                 "listdir","scandir","walk","open","readlink","realpath",
                                 "connect","system","popen","exec","spawn","write"})
        self.assertEqual({n.names[0].name for n in ast.walk(tree) if isinstance(n,ast.Import)},
                         {"errno","json","os","stat","sys"})
        self.assertNotIn("MOSA_TEST_DB_PASSWORD", probe.REMOTE_SOURCE)

    def run_mock(self, ftp, ssh=None):
        @contextmanager
        def connection(*args):
            args[1].update(ssh="PASS",host_key="PASS")
            yield Mock()
        paramiko=Mock()
        paramiko.SFTPClient.from_transport.return_value=ftp
        result = ssh or remote_assess(FakeOS(full_nodes()))
        with patch.object(probe.profile,"configuration",return_value={}), \
             patch.object(probe.shared,"ssh_client",connection), \
             patch.object(probe.remote,"remote_call",return_value=(0,json.dumps(result).encode(),False,1)) as call:
            report=probe.execute({},paramiko)
        return report,call

    def test_execute_reuses_pinned_client_and_sends_no_credentials_or_db_secret(self):
        report,call=self.run_mock(FakeSFTP(full_nodes()))
        self.assertTrue(report["ok"])
        self.assertEqual(report["remote_writes"],0)
        self.assertEqual(report["directory_listings"],0)
        self.assertEqual(report["database_connections"],0)
        self.assertEqual(call.call_args.kwargs["timeout"],30)
        self.assertEqual(json.loads(call.call_args.args[2]),{"sftp_anchor":probe.HOST_ROOT})
        self.assertTrue(call.call_args.args[1].startswith(probe.PYTHON+" -I -B -c "))
        self.assertFalse(report["deployment_enabled"])

    def test_sftp_boundary_blocks_ssh_probe_and_configuration_fails_before_network(self):
        nodes=full_nodes();nodes[probe.HOST_ROOT+"/private"]=PermissionError(errno.EACCES,"sensitive")
        report,call=self.run_mock(FakeSFTP(nodes))
        self.assertTrue(report["ok"]);call.assert_not_called()
        self.assertEqual(report["blocker"],"SFTP_PATH_BOUNDARY_STOP")
        with patch.object(probe.shared,"ssh_client") as connect:
            report=probe.execute({},Mock())
        self.assertFalse(report["ok"]);connect.assert_not_called()
        self.assertNotIn("sensitive",json.dumps(report))

    def test_output_guard_and_stderr_suppression(self):
        report={"ok":True,"metadata":"synthetic-password-canary"}
        out=probe.shared.public_text(report,{"MOSA_TEST_SFTP_PASSWORD":"synthetic-password-canary"})
        self.assertNotIn("synthetic-password-canary",out)
        self.assertFalse(json.loads(out)["ok"])

    def test_workflow_has_no_db_secret_upload_or_collector_and_fixed_scope(self):
        text=(ROOT/".github/workflows/collector-private-path.yml").read_text()
        self.assertNotIn("MOSA_TEST_DB_PASSWORD",text)
        self.assertNotIn("deploy_private_collector",text)
        self.assertNotIn("collector-live-test",text)
        self.assertNotIn("schedule:",text)
        self.assertIn("github.run_attempt == 1",text)
        self.assertIn("contents: read",text)
        self.assertEqual(probe.PRIVATE_ROOT,
            "/var/www/vhosts/web213.server10.configcenter.info/private/mosa2-collector")


if __name__=="__main__":
    unittest.main()
