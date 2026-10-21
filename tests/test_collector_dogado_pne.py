"""Offline tests for the one-PNE supervisor and existing runtime integration."""
import copy
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch
from types import SimpleNamespace
from scripts import collector_dogado_pne as driver

ROOT=Path(__file__).resolve().parents[1]

class DogadoPneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=driver.package()
        cls.commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()

    def env(self):
        return dict(MOSA_PNE_EXPECTED_COMMIT=self.commit,MOSA_PNE_AUTHORIZATION=driver.TOKEN+self.commit,
            GITHUB_ACTIONS="true",GITHUB_RUN_ATTEMPT="1",GITHUB_EVENT_NAME="workflow_dispatch",
            GITHUB_REF="refs/heads/main",GITHUB_REPOSITORY="masterxfix/MOSA-2",GITHUB_SHA=self.commit)

    def test_explicit_commit_bound_main_first_attempt_authorization_before_access(self):
        self.assertEqual(driver.authorize(self.env()),self.commit)
        for key,value in (("GITHUB_RUN_ATTEMPT","2"),("GITHUB_REF","refs/heads/other"),
            ("GITHUB_EVENT_NAME","push"),("MOSA_PNE_AUTHORIZATION",""),("GITHUB_SHA","0"*40),
            ("GITHUB_REPOSITORY","masterxfix/fixlab"),("MOSA_PNE_EXPECTED_COMMIT","main")):
            env=self.env();env[key]=value
            with self.subTest(key=key),self.assertRaises(PermissionError):driver.authorize(env)

    def test_only_original_33_file_release_and_verbatim_manifest_library(self):
        self.assertEqual((self.manifest["commit"],len(self.manifest["files"]),self.manifest["payload_bytes"]),
                         (driver.RELEASE_COMMIT,33,248105))
        source=driver.php_source()
        original=(ROOT/"scripts/market_collector/actions_acceptance.php").read_text()
        body=original[original.index("function manifest("):original.index("function privateItem(")]
        self.assertIn(body,source)
        self.assertNotIn("function acceptance(",source)
        self.assertIn("runtimeRun(RUN",source)
        self.assertNotIn("INSERT INTO",source)
        self.assertNotIn("ONBOARD_NEW_ROUTE",source.replace(body,""))
        self.assertIn("existing_route_only",source)
        self.assertIn("PHPRC",source)
        self.assertIn("'/dev/null'",source)
        self.assertIn("'PYTHONDONTWRITEBYTECODE'=>'1'",source)

    def php(self,request):
        code=driver.php_source(release_root=str(ROOT),run_root=str(ROOT),entry=False)
        code+='\ntry{$d=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);'
        code+='if($d["action"]==="outcome")$v=\\Mosa2\\DogadoPne\\outcome($d["report"],$d["checkpoint"]);'
        code+='else $v=\\Mosa2\\DogadoPne\\delta($d["before"],$d["after"],$d["scope"]);'
        code+='echo json_encode(["ok"=>true,"value"=>$v],JSON_THROW_ON_ERROR);}'
        code+='catch(\\Throwable $e){echo json_encode(["ok"=>false,"failure"=>$e->getMessage()]);}'
        r=subprocess.run(["php","-d","log_errors=0","-r",code],input=json.dumps(request),
                         text=True,capture_output=True,check=True,timeout=10)
        self.assertFalse(r.stderr,r.stderr);return json.loads(r.stdout)

    def test_outcome_unknown_commit_and_readback_failures_never_become_complete(self):
        for report,checkpoint,expected in (
            (dict(ok=True,committed=True),4,"COMPLETE"),
            (dict(ok=False,committed=False),1,"FAILED"),
            (dict(ok=False,committed=False,rollback=True),3,"FAILED"),
            (dict(ok=False,committed=False),3,"OUTCOME_UNKNOWN"),
            (dict(ok=False,committed=True),4,"OUTCOME_UNKNOWN")):
            self.assertEqual(self.php(dict(action="outcome",report=report,checkpoint=checkpoint))["value"],expected)

    def test_exact_single_insert_duplicate_and_all_old_business_state_preserved(self):
        scope=dict(asset_id="5",source_id="6",route_id="7")
        old=dict(id="10",**scope,price="1")
        before=dict(m2_market_observations=[old],m2_market_current=[dict(id="1",price="1")],
            m2_market_bars=[dict(id="1",price="1")],m2_sources=[dict(id="6")],
            m2_asset_source_routes=[dict(id="7")],m2_units=[dict(unit_key="EUR")])
        for case in ("insert","duplicate","two","scope","old","current","bars","source","route","unit","deleted"):
            after=copy.deepcopy(before)
            if case!="duplicate":after["m2_market_observations"].append(dict(id="11",**scope,price="2"))
            if case=="two":after["m2_market_observations"].append(dict(id="12",**scope,price="3"))
            if case=="scope":after["m2_market_observations"][-1]["asset_id"]="8"
            if case=="old":after["m2_market_observations"][0]["price"]="9"
            if case=="deleted":after["m2_market_observations"].pop(0)
            for label,table in (("current","m2_market_current"),("bars","m2_market_bars"),
                               ("source","m2_sources"),("route","m2_asset_source_routes"),("unit","m2_units")):
                if case==label:after[table][0]["changed"]="true"
            r=self.php(dict(action="delta",before=before,after=after,scope=scope))
            self.assertEqual(r["ok"],case in ("insert","duplicate"),(case,r))

    def fixture(self,tmp):
        scope={"__name__":"fixture"}
        exec(compile(driver.remote_source(),"<one-pne-supervisor>","exec"),scope)
        root=Path(tmp)/"private"
        root.mkdir(mode=0o700)
        for name in ("runs","releases"):(root/name).mkdir(mode=0o700)
        release=root/"releases"/driver.RELEASE_COMMIT;release.mkdir(mode=0o700)
        (release/"unchanged").write_text("synthetic release")
        scope["ROOT"]=str(root);scope["RELEASE"]=str(release);scope["RUN"]=str(root/"runs"/driver.run_name(self.commit))
        scope["guard"]=lambda:None
        scope["integrity"]=Mock(return_value="PASS")
        def checked(api,path):
            if path!=str(root/"runs"):raise AssertionError("run scope")
            return os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        scope["checked_fd"]=checked
        def metadata(s,mode,directory=False):
            if not ((stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode))
                and s.st_uid==os.getuid() and s.st_gid==os.getgid() and stat.S_IMODE(s.st_mode)==mode):
                raise ValueError("fixture object metadata")
        scope["new_metadata"]=metadata
        code="SYNTHETIC-NOT-EXECUTED"
        data=dict(commit=self.commit,authorization=driver.TOKEN+self.commit,isin="DE000A0JBPG2",
            release_commit=driver.RELEASE_COMMIT,manifest=self.manifest,password="SYNTHETIC-SECRET-CANARY",
            php_source=code,php_sha256=hashlib.sha256(code.encode()).hexdigest())
        return scope,root,data

    def test_supervisor_once_collision_marker_retention_and_no_release_changes(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(resource,"setrlimit"),patch.dict(os.environ,{}):
            scope,root,data=self.fixture(tmp)
            def child(source,password):
                fd=os.open(scope["RUN"]+"/provider-consumed.lock",os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
                return dict(ok=True,status="COMPLETE",collector_ms=1,total_with_preflight_ms=2)
            scope["child"]=Mock(side_effect=child)
            first=scope["run_once"](data);second=scope["run_once"](data)
            self.assertTrue(first["ok"],first);self.assertEqual(first["provider_requests"],1)
            self.assertFalse(second["ok"]);self.assertEqual(scope["child"].call_count,1)
            folder=Path(scope["RUN"])
            self.assertEqual({p.name for p in folder.iterdir()},{"job.lock","started.json","provider-consumed.lock","result.json"})
            for p in folder.iterdir():self.assertEqual(stat.S_IMODE(p.stat().st_mode),0o600)
            self.assertEqual((Path(scope["RELEASE"])/"unchanged").read_text(),"synthetic release")
            self.assertNotIn(data["password"],"".join(p.read_text() for p in folder.iterdir()))

    def test_unknown_child_outcome_no_retry_secret_report_suppressed(self):
        for case in ("timeout","secret"):
            with tempfile.TemporaryDirectory() as tmp,patch.object(resource,"setrlimit"),patch.dict(os.environ,{}):
                scope,root,data=self.fixture(tmp)
                def child(source,password):
                    fd=os.open(scope["RUN"]+"/provider-consumed.lock",os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
                    if case=="timeout":raise TimeoutError("synthetic")
                    return dict(ok=False,status="OUTCOME_UNKNOWN",value=password)
                scope["child"]=Mock(side_effect=child)
                result=scope["run_once"](data)
                self.assertFalse(result["ok"]);self.assertEqual(result["status"],"OUTCOME_UNKNOWN")
                self.assertEqual(scope["child"].call_count,1)
                self.assertTrue((Path(scope["RUN"])/"provider-consumed.lock").exists())
                self.assertNotIn(data["password"],(Path(scope["RUN"])/"result.json").read_text())


    def test_common_private_path_metadata_reader_is_preserved(self):
        scope={"__name__":"fixture"};exec(driver.remote_source(),scope)
        scope["checked_fd"]=lambda api,path:12
        row=SimpleNamespace(st_mode=stat.S_IFDIR|0o700,st_uid=10317,st_gid=1003,
                            st_dev=64768,st_ino=97002064)
        api=SimpleNamespace(fstat=lambda fd:row,close=Mock())
        result=scope["inspect"](api,scope["TARGETS"][0])
        self.assertEqual((result["uid"],result["gid"],result["mode"]),(10317,1003,"0700"))

    def test_process_group_kill_output_deadline_and_stdin_only_secret(self):
        scope={"__name__":"fixture"};exec(driver.remote_source(),scope)
        process=Mock(pid=123);process.wait.return_value=0
        with patch.object(os,"killpg") as kill:
            scope["stop_group"](process)
            self.assertEqual([x.args for x in kill.call_args_list],[(123,signal.SIGTERM),(123,signal.SIGKILL)])
        source=(ROOT/"scripts/collector_dogado_pne_remote.py").read_text()
        self.assertIn("start_new_session=True",source)
        self.assertIn('p.stdin.write(wire)',source)
        self.assertIn('len(out)+len(err)<=65536',source)
        self.assertIn('time.monotonic()+120',source)
        import ast
        tree=ast.parse(source)
        popen=next(n for n in ast.walk(tree) if isinstance(n,ast.Call)
                   and isinstance(n.func,ast.Attribute) and n.func.attr=="Popen")
        environment=next(k.value for k in popen.keywords if k.arg=="env")
        self.assertEqual({k.arg for k in environment.keywords},{"PATH","PYTHONDONTWRITEBYTECODE"})
        self.assertNotIn("chmod(",source);self.assertNotIn("chown(",source)
        driver_source=(ROOT/"scripts/collector_dogado_pne.py").read_text()
        self.assertEqual(driver_source.count("remote.remote_call("),1)
        self.assertNotIn("shared.tunnel",driver_source)
        self.assertNotIn("upload(",driver_source)

    def test_safe_failure_vocabulary_and_actual_php_child_exit_are_preserved(self):
        scope={"__name__":"fixture"};exec(driver.remote_source(),scope)
        self.assertEqual(scope["safe_code"](scope["Stop"]("RUN_PATH")),"RUN_PATH")
        canary="secret-canary SELECT private raw data"
        self.assertEqual(scope["safe_code"](scope["Stop"](canary)),"SUPERVISOR_CHECK_FAILED")
        self.assertEqual(scope["safe_code"](RuntimeError("RUN_PATH")),"SUPERVISOR_CHECK_FAILED")
        real_popen=subprocess.Popen
        for script,expected,exitcode in (
            ("import sys;sys.stderr.write('Cannot allocate memory secret-canary');sys.exit(13)","PHP_ADDRESS_SPACE_EXHAUSTED",13),
            ("import sys;sys.stderr.write('syntax error secret-canary');sys.exit(255)","PHP_SYNTAX_ERROR",255),
            ("import sys;sys.stderr.write('arbitrary secret-canary');sys.exit(1)","PHP_STDERR",1),
            ("print('invalid secret-canary')","PHP_RESULT_INVALID",0)):
            def launch(*args,**kwargs):
                kwargs.pop("cwd",None)
                return real_popen([sys.executable,"-I","-B","-c",script],**kwargs)
            with self.subTest(expected=expected),patch.object(subprocess,"Popen",side_effect=launch):
                with self.assertRaises(scope["ChildStop"]) as caught:scope["child"]("NOT EXECUTED",canary)
                d=caught.exception.details
                self.assertEqual(d["failure_code"],expected);self.assertEqual(d["php_exitcode"],exitcode)
                self.assertTrue(d["php_process_started"]);self.assertNotIn("secret-canary",json.dumps(d))
        with patch.object(subprocess,"Popen",side_effect=PermissionError(canary)):
            with self.assertRaises(scope["ChildStop"]) as caught:scope["child"]("NOT EXECUTED",canary)
            self.assertEqual(caught.exception.details,dict(failure_code="PHP_SPAWN_FAILED",failure_phase="php_spawn",
                php_process_started=False,php_exitcode=None))

    def test_structured_failure_preserves_unknown_outcome_and_existing_run_bytes(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(resource,"setrlimit"),patch.dict(os.environ,{}):
            scope,root,data=self.fixture(tmp)
            error=scope["ChildStop"]("PHP_NONZERO_EXIT","php_exit",True,255)
            scope["child"]=Mock(side_effect=error)
            first=scope["run_once"](data)
            self.assertEqual(first["status"],"OUTCOME_UNKNOWN")
            self.assertEqual(first["commit_state"],"unbekannt")
            self.assertEqual(first["failure_code"],"PHP_NONZERO_EXIT")
            self.assertEqual(first["php_exitcode"],255)
            self.assertFalse(first["provider_started"])
            folder=Path(scope["RUN"])
            before={p.name:p.read_bytes() for p in folder.iterdir()}
            second=scope["run_once"](data)
            self.assertEqual(second["failure_code"],"RUN_ALREADY_EXISTS")
            self.assertFalse(second["php_process_started"])
            self.assertEqual(scope["child"].call_count,1)
            self.assertEqual(before,{p.name:p.read_bytes() for p in folder.iterdir()})

    def test_php_public_failure_codes_are_closed_and_no_raw_exception_is_emitted(self):
        source=driver.php_source(release_root=str(ROOT),run_root=str(ROOT),entry=False)
        source+='\necho json_encode([\\Mosa2\\DogadoPne\\safeFailureCode("php_pin"),\\Mosa2\\DogadoPne\\safeFailureCode("secret SELECT private")]);'
        r=subprocess.run(["php","-d","log_errors=0","-r",source],capture_output=True,text=True,check=True,timeout=10)
        self.assertEqual(json.loads(r.stdout),["php_pin","collector_check_failed"])
        self.assertFalse(r.stderr)

    def test_only_proven_virtual_address_limit_changes_all_other_guards_remain(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(resource,"setrlimit") as limits,patch.dict(os.environ,{}):
            scope,root,data=self.fixture(tmp)
            scope["child"]=Mock(return_value=dict(ok=True,status="COMPLETE",result=dict(committed=True)))
            r=scope["run_once"](data)
            self.assertTrue(r["ok"])
            self.assertEqual(r["commit_state"],"bestätigt")
            self.assertEqual([c.args for c in limits.call_args_list],[
                (resource.RLIMIT_FSIZE,(1024*1024,1024*1024)),(resource.RLIMIT_CPU,(45,45)),
                (resource.RLIMIT_AS,(1024*1024*1024,1024*1024*1024))])
            self.assertIn("memory_limit=128M",scope["PHP_FLAGS"])
            self.assertEqual(scope["integrity"].call_count,2)

    def test_second_attempt_uses_exact_commit_directory_and_rejects_first_token(self):
        self.assertEqual(driver.run_name(self.commit),"second-live-PNE-DE000A0JBPG2-"+self.commit)
        self.assertNotEqual(driver.run_directory(self.commit),driver.RUN)
        for bad in ("main","../escape","0"*39):
            with self.assertRaises(ValueError):driver.run_directory(bad)
        env=self.env();env["MOSA_PNE_AUTHORIZATION"]="MOSA2-PNE-FIRST-LIVE-20261021:"+self.commit
        with self.assertRaises(PermissionError):driver.authorize(env)
        source=driver.php_source(run_root=driver.run_directory(self.commit))
        self.assertIn("const RUN='"+driver.run_directory(self.commit)+"';",source)
        self.assertIn("RUN.'/preflight.json'",source)
        self.assertLess(source.index("$r['baseline']="),source.index("runtimeRun(RUN"))

    def test_first_attempt_files_survive_second_attempt_and_second_attempt_cannot_repeat(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(resource,"setrlimit"),patch.dict(os.environ,{}):
            scope,root,data=self.fixture(tmp)
            first=root/"runs"/driver.ONCE;first.mkdir(mode=0o700)
            (first/"result.json").write_bytes(b'{"status":"OUTCOME_UNKNOWN"}')
            (first/"retained-marker").write_bytes(b"first-attempt-evidence")
            before={p.name:p.read_bytes() for p in first.iterdir()}
            scope["child"]=Mock(return_value=dict(ok=True,status="COMPLETE",result=dict(committed=True)))
            self.assertTrue(scope["run_once"](data)["ok"])
            self.assertEqual(scope["run_once"](data)["failure_code"],"RUN_ALREADY_EXISTS")
            self.assertEqual(scope["child"].call_count,1)
            self.assertEqual(before,{p.name:p.read_bytes() for p in first.iterdir()})

if __name__=="__main__":unittest.main()
