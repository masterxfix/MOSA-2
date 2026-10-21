"""Exact six-directory safety tests using an in-memory filesystem and fake SSH/SFTP."""
import ast
import copy
import errno
import json
from pathlib import Path
import posixpath
import stat
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch
from contextlib import contextmanager

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import collector_private_directories as helper


def library():
    scope={"__name__":"fixture"}
    exec(compile(helper.REMOTE_SOURCE,"<directory-contract>","exec"),scope)
    return scope


class FakeOS:
    O_RDONLY=0
    O_DIRECTORY=65536
    O_NOFOLLOW=131072
    def __init__(self, lib):
        self.lib=lib
        self.nodes={}
        self.fds={}
        self.next_fd=0
        self.calls=[]
        self.writes=[]
        self.mask=None
        self.uid=10317;self.gid=1003
        self.cwd=lib["BASE"]
        self.bad_after_create=None
        self.fail_at=None
        self.collision_at=None
        self.canonical_override=None
        self.mutate_inode=False
        self.path=SimpleNamespace(realpath=self.realpath)
        paths=("/", "/var","/var/www","/var/www/vhosts",lib["BASE"])
        for i,p in enumerate(paths):
            self.nodes[p]=SimpleNamespace(st_mode=stat.S_IFDIR|(0o710 if p==lib["BASE"] else 0o755),
                st_uid=10317 if p==lib["BASE"] else 0,
                st_gid=1002 if p==lib["BASE"] else 0,st_dev=64768,
                st_ino=5248112 if p==lib["BASE"] else i+1)
    def getuid(self):return self.uid
    def geteuid(self):return self.uid
    def getgid(self):return self.gid
    def getegid(self):return self.gid
    def getcwd(self):return self.cwd
    def full(self,path,dir_fd=None):
        if path.startswith("/"):return path
        return posixpath.join(self.fds[dir_fd],path)
    def realpath(self,path):
        self.calls.append(("realpath",path))
        return self.canonical_override or path
    def open(self,path,flags,dir_fd=None):
        full=self.full(path,dir_fd)
        self.calls.append(("open",full))
        assert flags & self.O_DIRECTORY and flags & self.O_NOFOLLOW
        s=self.nodes.get(full)
        if s is None:raise FileNotFoundError(errno.ENOENT,"fixture")
        if not stat.S_ISDIR(s.st_mode):raise OSError(errno.ENOTDIR,"fixture")
        self.next_fd+=1;self.fds[self.next_fd]=full
        return self.next_fd
    def close(self,fd):del self.fds[fd]
    def stat(self,path,dir_fd=None,follow_symlinks=True):
        assert follow_symlinks is False
        full=self.full(path,dir_fd)
        self.calls.append(("stat",full))
        if full not in self.nodes:raise FileNotFoundError(errno.ENOENT,"fixture")
        return copy.copy(self.nodes[full])
    def fstat(self,fd):
        path=self.fds[fd];self.calls.append(("fstat",path))
        s=copy.copy(self.nodes[path])
        if self.mutate_inode and path==self.lib["BASE"]:s.st_ino+=1
        return s
    def umask(self,value):
        self.calls.append(("umask",value));self.mask=value;return 0o022
    def mkdir(self,name,mode,dir_fd=None):
        full=self.full(name,dir_fd)
        self.calls.append(("mkdir",full))
        self.writes.append(full)
        assert self.mask==0o077 and mode==0o700
        if self.fail_at==len(self.writes):raise PermissionError(errno.EACCES,"private-error-text")
        if full in self.nodes or self.collision_at==len(self.writes):
            raise FileExistsError(errno.EEXIST,"private-error-text")
        s=SimpleNamespace(st_mode=stat.S_IFDIR|mode,st_uid=10317,st_gid=1003,
                          st_dev=64768,st_ino=6000+len(self.writes))
        if self.bad_after_create and len(self.writes)==1:
            key,value=self.bad_after_create;setattr(s,key,value)
        self.nodes[full]=s


class DirectoryTests(unittest.TestCase):
    def setUp(self):
        self.lib=library();self.api=FakeOS(self.lib)
    def run_create(self):
        return self.lib["run"]("create",helper.AUTHORIZATION,self.api)
    def test_exact_six_exclusive_mkdirs_and_immediate_full_verification(self):
        r=self.run_create()
        self.assertTrue(r["ok"],r)
        self.assertEqual(r["created"],list(self.lib["TARGETS"]))
        self.assertEqual(self.api.writes,list(self.lib["TARGETS"]))
        self.assertEqual(len(r["verified"]),6)
        self.assertEqual(r["plan_budget_bytes"],67108864)
        self.assertEqual(self.api.fds,{})
        for row in r["verified"]:
            self.assertEqual((row["uid"],row["gid"],row["mode"]),(10317,1003,"0700"))
            self.assertFalse(row["symlink"])
            self.assertTrue(row["directory"])
        # Each mkdir must be followed by the immediate no-follow stat before another mkdir.
        writes=[i for i,c in enumerate(self.api.calls) if c[0]=="mkdir"]
        for i,next_i in zip(writes,writes[1:]+[len(self.api.calls)]):
            self.assertIn(("stat",self.api.calls[i][1]),self.api.calls[i+1:next_i])

    def test_missing_authorization_identity_cwd_and_base_drift_are_prewrite_failures(self):
        self.assertFalse(self.lib["run"]("create","wrong",self.api)["ok"])
        self.assertEqual(self.api.calls,[])
        for field,value in (("uid",0),("gid",1002),("cwd","/")):
            api=FakeOS(self.lib);setattr(api,field,value)
            r=self.lib["run"]("create",helper.AUTHORIZATION,api)
            self.assertFalse(r["ok"]);self.assertEqual(api.writes,[])
        for field,value in (("st_uid",0),("st_gid",1003),("st_mode",stat.S_IFDIR|0o755),
                            ("st_ino",1),("st_dev",1)):
            api=FakeOS(self.lib);setattr(api.nodes[self.lib["BASE"]],field,value)
            self.assertFalse(self.lib["run"]("create",helper.AUTHORIZATION,api)["ok"])
            self.assertEqual(api.writes,[]);self.assertEqual(api.fds,{})

    def test_existing_objects_symlinks_ancestor_and_path_alias_abort_without_repairs(self):
        for mode in (stat.S_IFDIR|0o700,stat.S_IFREG|0o600,stat.S_IFLNK|0o777):
            api=FakeOS(self.lib)
            api.nodes[self.lib["TARGETS"][0]]=SimpleNamespace(st_mode=mode,st_uid=10317,
                st_gid=1003,st_dev=64768,st_ino=5)
            r=self.lib["run"]("create",helper.AUTHORIZATION,api)
            self.assertEqual(r["failure"],"UNEXPECTED_EXISTING_TARGET")
            self.assertEqual(api.writes,[])
        for case in ("symlink","canonical","race"):
            api=FakeOS(self.lib)
            if case=="symlink":api.nodes["/var/www"].st_mode=stat.S_IFLNK|0o777
            elif case=="canonical":api.canonical_override="/unexpected"
            else:api.mutate_inode=True
            self.assertFalse(self.lib["run"]("create",helper.AUTHORIZATION,api)["ok"])
            self.assertEqual(api.writes,[]);self.assertEqual(api.fds,{})

    def test_wrong_new_owner_group_mode_or_type_stops_after_one_no_chown_or_chmod(self):
        for field,value in (("st_uid",0),("st_gid",1002),("st_mode",stat.S_IFDIR|0o755),
                            ("st_mode",stat.S_IFLNK|0o777)):
            api=FakeOS(self.lib);api.bad_after_create=(field,value)
            r=self.lib["run"]("create",helper.AUTHORIZATION,api)
            self.assertFalse(r["ok"]);self.assertEqual(len(r["created"]),1)
            self.assertEqual(len(api.writes),1)
            self.assertIn("last_created_metadata",r)
            self.assertEqual(api.fds,{})
            self.assertFalse(any(c[0] in ("chmod","chown","unlink","rmdir") for c in api.calls))

    def test_partial_permission_failure_and_exclusive_collision_stop_without_retry(self):
        for kind in ("fail_at","collision_at"):
            api=FakeOS(self.lib);setattr(api,kind,3)
            r=self.lib["run"]("create",helper.AUTHORIZATION,api)
            self.assertFalse(r["ok"])
            self.assertEqual(len(api.writes),3)
            self.assertEqual(len(r["created"]),2)
            self.assertEqual(api.fds,{})
            self.assertNotIn("private-error-text",json.dumps(r))

    def test_fresh_readback_has_zero_mutations_and_rejects_later_drift(self):
        self.assertTrue(self.run_create()["ok"])
        self.api.calls=[];self.api.writes=[]
        r=self.lib["run"]("readback",helper.AUTHORIZATION,self.api)
        self.assertTrue(r["ok"])
        self.assertEqual(self.api.writes,[])
        self.assertFalse(any(c[0] in ("mkdir","umask") for c in self.api.calls))
        self.api.nodes[self.lib["TARGETS"][-1]].st_mode=stat.S_IFDIR|0o755
        self.assertFalse(self.lib["run"]("readback",helper.AUTHORIZATION,self.api)["ok"])

    def test_scope_and_remote_ast_have_no_file_write_repair_inventory_network_or_exec(self):
        self.assertEqual(len(self.lib["TARGETS"]),6)
        for p in self.lib["TARGETS"]:
            self.assertFalse(any(self.lib["inside"](p,w) or self.lib["inside"](w,p)
                                 for w in self.lib["WEBROOTS"]))
        tree=ast.parse(helper.REMOTE_SOURCE)
        attrs={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertFalse(attrs & {"chmod","chown","unlink","remove","rmdir","rename","makedirs",
                                  "listdir","scandir","walk","connect","write","system","popen"})
        self.assertNotIn("MOSA_TEST_DB_PASSWORD",helper.REMOTE_SOURCE)
        self.assertEqual({n.names[0].name for n in ast.walk(tree) if isinstance(n,ast.Import)},
                         {"json","os","stat","sys"})

    def test_sftp_readback_only_lstat_normalize_and_rejects_unknown_scope(self):
        r=self.run_create();calls=[]
        class FTP:
            def lstat(inner,path):
                calls.append(("lstat",path));return self.api.nodes[path]
            def normalize(inner,path):
                calls.append(("normalize",path));return path
        rows=helper.sftp_readback(FTP(),r["verified"])
        self.assertEqual(len(rows),6)
        self.assertEqual({c[0] for c in calls},{"lstat","normalize"})
        with self.assertRaises(helper.remote.ProbeError):helper.sftp_readback(FTP(),[dict(path="/other")])
        self.api.nodes[self.lib["TARGETS"][0]].st_mode=stat.S_IFLNK|0o777
        with self.assertRaises(helper.remote.ProbeError):helper.sftp_readback(FTP(),r["verified"])

    def test_driver_uses_two_connections_once_and_unknown_create_outcome_is_not_retried(self):
        good=self.run_create()
        read=self.lib["run"]("readback",helper.AUTHORIZATION,self.api)
        @contextmanager
        def ssh(config,status,paramiko):
            status.update(ssh="PASS",host_key="PASS");yield Mock()
        env={"MOSA_PRIVATE_DIRECTORY_AUTHORIZATION":helper.AUTHORIZATION}
        for outcomes,ok in (([good,read],True),([RuntimeError("synthetic-private-error"),read],False)):
            with patch.object(helper.profile,"configuration",return_value={}), \
                 patch.object(helper.shared,"ssh_client",side_effect=ssh) as connections, \
                 patch.object(helper,"invoke",side_effect=outcomes) as invoke, \
                 patch.object(helper,"sftp_readback",return_value=[{}]*6):
                r=helper.execute(env,MagicMock())
            self.assertEqual(r["ok"],ok,r)
            self.assertEqual(connections.call_count,2)
            self.assertEqual([c.args[1] for c in invoke.call_args_list],["create","readback"])
            self.assertNotIn("synthetic-private-error",json.dumps(r))
        with patch.object(helper.shared,"ssh_client") as connection:
            self.assertFalse(helper.execute({},Mock())["ok"]);connection.assert_not_called()

    def test_configuration_failure_and_host_key_rejection_prevent_remote_command(self):
        env={"MOSA_PRIVATE_DIRECTORY_AUTHORIZATION":helper.AUTHORIZATION}
        with patch.object(helper.shared,"ssh_client") as connect:
            r=helper.execute(env,Mock())
        self.assertFalse(r["ok"]);connect.assert_not_called()
        with patch.object(helper.profile,"configuration",return_value={}), \
             patch.object(helper.shared,"ssh_client",side_effect=ValueError("pin mismatch")), \
             patch.object(helper,"invoke") as call:
            self.assertFalse(helper.execute(env,Mock())["ok"]);call.assert_not_called()

    def test_manual_workflow_and_default_locked_private_deployment(self):
        wf=(ROOT/".github/workflows/collector-private-directories.yml").read_text()
        self.assertIn("github.run_attempt == 1",wf)
        self.assertIn("MOSA_PRIVATE_DIRECTORY_AUTHORIZATION",wf)
        self.assertNotIn("MOSA_TEST_DB_PASSWORD",wf)
        self.assertNotIn("schedule:",wf)
        import deploy_private_collector as locked
        with self.assertRaises(PermissionError):locked.upload(approval=True)

if __name__=="__main__":
    unittest.main()
