"""One-shot uploader regression tests; local fixture tree, no remote service."""
import base64
from contextlib import contextmanager
import copy
import ctypes
import errno
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from scripts import deploy_private_collector as deploy


class UploadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
        cls.meta,cls.manifest,cls.files=deploy.artifact(ROOT,cls.commit)

    def env(self):
        return dict(MOSA_PRIVATE_EXPECTED_COMMIT=self.commit,
                    MOSA_PRIVATE_UPLOAD_AUTHORIZATION=deploy.TOKEN+self.commit,
                    GITHUB_ACTIONS="true",GITHUB_RUN_ATTEMPT="1",GITHUB_RUN_ID="123",
                    GITHUB_EVENT_NAME="workflow_dispatch",GITHUB_REF="refs/heads/main")

    def data(self):
        return dict(commit=self.commit,authorization=deploy.TOKEN+self.commit,run_id="123",
                    manifest=copy.deepcopy(self.meta),manifest_sha256=hashlib.sha256(self.manifest).hexdigest(),
                    files={p:base64.b64encode(b).decode() for p,b in self.files.items()})

    @contextmanager
    def fixture(self):
        # The existing root/identity checker already has directory-contract tests.
        # Adapt only that host namespace to a temporary LOCAL Linux tree; exercise
        # the actual new no-follow writer/auditor and libc no-replace rename.
        scope={"__name__":"fixture"}
        exec(compile(deploy.remote_source(),"<private-upload>","exec"),scope)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"private"/"mosa2-collector"
            root.mkdir(mode=0o700,parents=True)
            for name in ("releases","staging","runs","locks"):(root/name).mkdir(mode=0o700)
            scope["ROOT"]=str(root);scope["UID"]=os.getuid();scope["GID"]=os.getgid()
            calls=[]
            def guard():
                calls.append("guard")
                for p in (root,*(root/n for n in ("releases","staging","runs","locks"))):
                    s=p.lstat()
                    if not stat.S_ISDIR(s.st_mode) or stat.S_ISLNK(s.st_mode) or stat.S_IMODE(s.st_mode)!=0o700:
                        raise scope["Stop"]("FIXTURE_ROOT_GUARD")
            def checked_fd(api,path):
                guard()
                if path!=str(root):raise AssertionError("fixture root scope")
                return os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            scope["guard"]=guard;scope["checked_fd"]=checked_fd
            yield scope,root,calls

    def test_no_authorization_wrong_root_attempt_ref_or_commit_fails_before_connection(self):
        self.assertEqual(deploy.authorization(deploy.PROPOSED_ROOT,self.env()),self.commit)
        with self.assertRaises(PermissionError):deploy.upload(approval=True)
        for key,value in (("MOSA_PRIVATE_UPLOAD_AUTHORIZATION",""),("GITHUB_RUN_ATTEMPT","2"),
                          ("GITHUB_REF","refs/heads/other"),("GITHUB_EVENT_NAME","schedule"),
                          ("MOSA_PRIVATE_EXPECTED_COMMIT","main"),("GITHUB_ACTIONS","false")):
            env=self.env();env[key]=value
            with self.subTest(key=key),self.assertRaises(PermissionError):
                deploy.authorization(deploy.PROPOSED_ROOT,env)
        for root in ("/",deploy.shared.TEST_ROOT,deploy.PROPOSED_ROOT+"/../x",deploy.PROPOSED_ROOT+"/"):
            with self.assertRaises(PermissionError):deploy.authorization(root,self.env())

    def test_qualified_package_reproducible_and_credentials_never_enter_artifact(self):
        sentinel="SYNTHETIC-CREDENTIAL-CANARY-NEVER-TRANSFER"
        with patch.dict(os.environ,{"MOSA_TEST_SFTP_PASSWORD":sentinel}):
            meta,manifest,files=deploy.artifact(ROOT,self.commit)
        self.assertEqual(manifest,self.manifest)
        self.assertEqual((len(files),sum(map(len,files.values()))),(33,248105))
        self.assertNotIn(sentinel.encode(),manifest+b"".join(files.values()))
        self.assertEqual(meta["commit"],self.commit)

    def test_full_staging_write_audit_and_atomic_publish_exact_files(self):
        with self.fixture() as (scope,root,calls):
            result=scope["upload_operation"](dict(self.data(),action="prepare"))
            self.assertTrue(result["ok"])
            self.assertGreater(len(calls),60)
            self.assertEqual(result["audit"]["files"],33)
            data=dict(self.data(),action="publish",independent_staging_readback=True,
                      stage_inode=result["stage_inode"],lock_inode=result["lock_inode"])
            published=scope["upload_operation"](data)
            self.assertTrue(published["atomic_noreplace"])
            target=root/"releases"/self.commit
            self.assertTrue(target.is_dir())
            self.assertFalse(Path(result["staging"]).exists())
            self.assertEqual(scope["audit"](str(target),self.meta["files"],
                scope["plan"](self.data())[3])["sha256"],"PASS")
            self.assertEqual({p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()},
                             set(self.files))
            for p in target.rglob("*"):
                self.assertEqual(stat.S_IMODE(p.lstat().st_mode),0o700 if p.is_dir() else 0o600)

    def test_bad_file_set_hash_or_manifest_prevents_first_write(self):
        for case in ("extra","hash","manifest"):
            with self.fixture() as (scope,root,calls):
                data=dict(self.data(),action="prepare")
                if case=="extra":data["files"]["unknown.php"]=""
                elif case=="hash":data["files"][next(iter(self.files))]=base64.b64encode(b"changed").decode()
                else:data["manifest"]["commit"]="0"*40
                with self.assertRaises((scope["Stop"],ValueError)):scope["upload_operation"](data)
                self.assertFalse(list((root/"locks").iterdir()))
                self.assertFalse(list((root/"staging").iterdir()))

    def test_root_guard_failure_prevents_all_writes(self):
        with self.fixture() as (scope,root,calls):
            (root/"runs").chmod(0o755)
            with self.assertRaises(scope["Stop"]):
                scope["upload_operation"](dict(self.data(),action="prepare"))
            self.assertFalse(list((root/"locks").iterdir()))

    def test_target_or_one_shot_collision_never_overwrites_or_retries(self):
        for place in ("target","lock"):
            with self.fixture() as (scope,root,calls):
                target=(root/"releases"/self.commit) if place=="target" else root/"locks"/deploy.ONCE
                target.mkdir(mode=0o700)
                with self.assertRaises(scope["Stop"]):
                    scope["upload_operation"](dict(self.data(),action="prepare"))
                self.assertTrue(target.is_dir())
                self.assertFalse(list((root/"staging").iterdir()))

    def test_hash_unknown_file_symlink_or_mode_drift_prevents_publication_without_cleanup(self):
        for case in ("hash","extra","link","mode"):
            with self.fixture() as (scope,root,calls):
                prepared=scope["upload_operation"](dict(self.data(),action="prepare"))
                stage=Path(prepared["staging"])
                path=stage/next(iter(self.files))
                if case=="hash":path.write_bytes(b"changed")
                elif case=="extra":(stage/"unexpected").write_text("SYNTHETIC")
                elif case=="mode":path.chmod(0o644)
                else:path.unlink();path.symlink_to(stage/next(p for p in self.files if p!=next(iter(self.files))))
                data=dict(self.data(),action="publish",independent_staging_readback=True,
                          stage_inode=prepared["stage_inode"],lock_inode=prepared["lock_inode"])
                with self.assertRaises(scope["Stop"]):scope["upload_operation"](data)
                self.assertFalse((root/"releases"/self.commit).exists())
                self.assertTrue(stage.exists())

    def test_publication_requires_independent_readback_and_handles_atomic_collision(self):
        with self.fixture() as (scope,root,calls):
            prepared=scope["upload_operation"](dict(self.data(),action="prepare"))
            data=dict(self.data(),action="publish",stage_inode=prepared["stage_inode"],
                      lock_inode=prepared["lock_inode"])
            with self.assertRaises(scope["Stop"]):scope["upload_operation"](data)
            data["independent_staging_readback"]=True
            # Inject a collision at the final syscall, after the ordinary absent check.
            real=scope["capability"]()
            def no_replace(src,name,dst,commit,flags):
                os.mkdir(commit.decode(),0o700,dir_fd=dst)
                return real(src,name,dst,commit,flags)
            scope["capability"]=lambda:no_replace
            with self.assertRaises(OSError):scope["upload_operation"](data)
            self.assertTrue(Path(prepared["staging"]).is_dir())
            self.assertEqual(list((root/"releases"/self.commit).iterdir()),[])

    def sftp(self,base):
        def metadata(path):
            actual=base/path[len(deploy.PROPOSED_ROOT):].lstrip("/") if path.startswith(deploy.PROPOSED_ROOT) else None
            if actual is None:
                return SimpleNamespace(st_mode=stat.S_IFDIR|(0o710 if path.endswith("configcenter.info") else
                    0o700 if path.endswith("/private") else 0o755),
                    st_uid=10317 if path.endswith(("configcenter.info","/private")) else 0,
                    st_gid=1002 if path.endswith("configcenter.info") else
                    1003 if path.endswith("/private") else 0,st_size=4096)
            s=actual.lstat()
            return SimpleNamespace(st_mode=s.st_mode,st_uid=10317,st_gid=1003,st_size=s.st_size)
        class Handle:
            def __init__(inner,path):
                inner.path=path;inner.file=(base/path[len(deploy.PROPOSED_ROOT):].lstrip("/")).open("rb")
            def read(inner,n):return inner.file.read(n)
            def stat(inner):return metadata(inner.path)
            def __enter__(inner):return inner
            def __exit__(inner,*args):inner.file.close()
        class FTP:
            lstat=staticmethod(metadata)
            def normalize(inner,path):return path
            def open(inner,path,mode):
                if mode!="rb":raise AssertionError("read-only SFTP")
                return Handle(path)
            def listdir_iter(inner,path,read_aheads):
                for p in (base/path[len(deploy.PROPOSED_ROOT):].lstrip("/")).iterdir():
                    yield SimpleNamespace(filename=p.name)
        return FTP()

    def test_independent_sftp_reads_full_tree_and_rejects_unknowns_hash_links_or_wrong_path(self):
        with self.fixture() as (scope,root,calls):
            p=scope["upload_operation"](dict(self.data(),action="prepare"))
            # Rename the local fixture stage to a matching fake remote release path.
            local=root/"releases"/self.commit
            os.rename(p["staging"],local)
            ftp=self.sftp(root)
            result=deploy.readback(ftp,deploy.PROPOSED_ROOT+"/releases/"+self.commit,self.meta)
            self.assertEqual((result["files"],result["bytes"]),(33,248105))
            with self.assertRaises(ValueError):deploy.readback(ftp,"/other",self.meta)
            (local/"unexpected").write_text("SYNTHETIC")
            with self.assertRaises(ValueError):
                deploy.readback(ftp,deploy.PROPOSED_ROOT+"/releases/"+self.commit,self.meta)

    def test_failed_staging_readback_never_calls_publish_and_no_cleanup(self):
        env=self.env()
        @contextmanager
        def ssh(config,status,paramiko):
            yield Mock()
        modules=deploy.modules()
        calls=[]
        def call(transport,action,data):
            calls.append(action)
            return dict(staging=deploy.PROPOSED_ROOT+"/staging/"+self.commit+"-123",
                        stage_inode=1,lock_inode=2,ok=True)
        with patch.object(modules[3],"git",side_effect=lambda root,*args:
                          (self.commit+"\trefs/heads/main\n").encode() if args[0]=="ls-remote"
                          else (self.commit+"\n").encode()), \
             patch.object(deploy,"artifact",return_value=(self.meta,self.manifest,self.files)), \
             patch("deploy_test_sftp.configuration",return_value={}), \
             patch.object(modules[0],"ssh_client",side_effect=ssh), \
             patch.object(deploy,"call",side_effect=call), \
             patch.object(deploy,"readback",side_effect=ValueError("SYNTHETIC")):
            r=deploy.upload(deploy.PROPOSED_ROOT,env=env,paramiko=MagicMock())
        self.assertFalse(r["ok"])
        self.assertEqual(calls,["prepare","inspect"])
        self.assertTrue(r["no_retry_or_cleanup"])
        self.assertEqual(r["automatic_retries"],0)

    def test_remote_policy_has_no_collector_network_repair_or_delete(self):
        import ast
        own=(ROOT/"scripts/collector_private_upload_remote.py").read_text()
        tree=ast.parse(own)
        attrs={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertFalse(attrs & {"chmod","chown","unlink","rmdir","remove","system","popen","connect"})
        imports={n.names[0].name for n in ast.walk(tree) if isinstance(n,ast.Import)}
        self.assertEqual(imports,{"base64","ctypes","hashlib","re"})
        self.assertFalse({n.func.id for n in ast.walk(tree) if isinstance(n,ast.Call)
                          and isinstance(n.func,ast.Name)} & {"exec","eval","compile","__import__"})
        self.assertIn("renameat2",own)
        self.assertIn("O_EXCL",own)
        self.assertIn("PRIVATE_INODES",own)
        self.assertIn('guard()\n                    need(os.write',own)

    def test_existing_testsite_blobs_unchanged_and_output_guard(self):
        release=deploy.modules()[3]
        pins={"scripts/deploy_sftp.py":"7678f600876b72899da9f35b4ca21b23ba22868c",
              "scripts/deploy_test_sftp.py":"cf4f5cce8225168d3783139bd740ca420ac79233",
              ".github/workflows/deploy-testsite.yml":"1d06c152acd88a74e775c8c96caa0a82d525d8d1"}
        for path,pin in pins.items():
            self.assertEqual(release.git(ROOT,"rev-parse","HEAD:"+path).decode().strip(),pin)
        encoded=deploy.modules()[0].public_text(dict(ok=True,value="SYNTHETIC-SECRET"),
                    {"MOSA_TEST_SFTP_PASSWORD":"SYNTHETIC-SECRET"})
        self.assertFalse(json.loads(encoded)["ok"]);self.assertNotIn("SYNTHETIC-SECRET",encoded)


if __name__=="__main__":
    unittest.main()
