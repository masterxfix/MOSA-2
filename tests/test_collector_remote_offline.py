"""Focused guards and comparisons; all writes stay in local test fixtures."""
import ast
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import Mock,patch
from scripts import collector_remote_offline as driver
from scripts import collector_remote_offline_probe as probe
ROOT=Path(__file__).resolve().parents[1]

class OfflineProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=driver.request()

    def setUp(self):
        probe.COUNTERS.update(php_processes=0,blocked_network=0,blocked_writes=0)

    def test_existing_fixtures_canonical_native_units_insert_and_replay(self):
        results=self.data["expected"]
        self.assertEqual(len(results),2)
        for result in results:
            self.assertEqual(result["insert"],"INSERT")
            self.assertEqual(result["replay"],"DUPLICATE_UNCHANGED")
            self.assertEqual(hashlib.sha256(bytes.fromhex(result["canonical_hex"])).hexdigest(),result["dedupe_hex"])
        self.assertEqual(results[0]["normalized"]["price"],"173.8125000000")
        self.assertEqual((results[1]["normalized"]["price"],results[1]["normalized"]["quote_unit_key"]),("246.8000000000","GBX"))
        import test_market_collector_v1 as reference
        for case,result in zip((reference.FrankfurtCollectorTests(),reference.MarketCollectorTests()),results):
            case.setUp()
            expected=case.run_pipeline() if isinstance(case,reference.FrankfurtCollectorTests) else case.run_pipeline(case.inputs("GBX"))
            self.assertEqual(expected["canonical_bytes"].hex(),result["canonical_hex"])
            self.assertEqual(expected["dedupe_key"].hex(),result["dedupe_hex"])

    def materialize(self,root):
        archive,_=driver.release.build(ROOT,probe.RELEASE_COMMIT)
        root.mkdir(mode=0o700)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            for item in tar:
                p=root/item.name
                for directory in reversed(p.parents):
                    if directory==root or root in directory.parents:directory.mkdir(mode=0o700,exist_ok=True)
                p.write_bytes(tar.extractfile(item).read());p.chmod(0o600)
        return root

    def test_hash_set_symlink_and_mode_guards_on_local_fixture(self):
        for case in ("clean","hash","unknown","missing","symlink","mode"):
            with self.subTest(case=case),tempfile.TemporaryDirectory() as tmp:
                root=self.materialize(Path(tmp)/"release")
                p=root/self.data["manifest"]["files"][0]["path"]
                if case=="hash":p.write_bytes(b"changed")
                elif case=="unknown":(root/"unknown").write_text("synthetic")
                elif case=="missing":p.unlink()
                elif case=="symlink":p.unlink();p.symlink_to(root/"scripts/market_collector/normalizer.py")
                elif case=="mode":p.chmod(0o644)
                if case=="clean":self.assertEqual(probe.integrity(root,self.data["manifest"],remote=False),"PASS")
                else:
                    with self.assertRaises(ValueError):probe.integrity(root,self.data["manifest"],remote=False)

    def test_network_write_and_unapproved_process_guards(self):
        for event,args in (("socket.connect",()),("sqlite3.connect",()),("os.mkdir",()),
                           ("open",("/tmp/forbidden","w",os.O_WRONLY)),("os.rename",()),
                           ("subprocess.Popen",("bad",["bad"],None,None))):
            with self.subTest(event=event),self.assertRaises((PermissionError,ValueError)):
                probe.audit(event,args)
        probe.audit("open",("normative-seed","r",os.O_RDONLY))

    def test_php_pin_flags_operations_and_process_budget(self):
        probe.PHP_BINARY=probe.PHP;probe.VALUE_ADAPTER=probe.RELEASE+"/scripts/phase3n/value_adapter.php"
        with patch.object(probe,"php_run",return_value=b'{"ok":true}') as php:
            r=probe.pinned_run(["php",probe.VALUE_ADAPTER],input=b'{"operation":"identity"}')
            self.assertEqual(r.returncode,0)
            self.assertEqual(php.call_args.args[0],probe.PHP)
            self.assertIn("proc_open",php.call_args.args[1][1])
            probe.COUNTERS["php_processes"]=256
            with self.assertRaises(ValueError):probe.pinned_run(["php",probe.VALUE_ADAPTER],input=b'{"operation":"identity"}')
        with self.assertRaises(ValueError):probe.pinned_run(["php","/other/value_adapter.php"],input=b"{}")
        for option in ("log_errors=0","opcache.enable_cli=0","opcache.file_cache=","allow_url_fopen=0"):
            self.assertIn(option,probe.PHP_OPTIONS)
        for function in ("fopen","file_put_contents","curl_exec","fsockopen","error_log","system"):
            self.assertIn(function,probe.DENY.split(","))

    def test_php_include_closure_without_running_collector_main(self):
        php=driver.shutil.which("php")
        libraries=[r["path"] for r in self.data["manifest"]["files"] if r["path"].endswith(".php")
                   and not r["path"].endswith("frankfurt_request.php")]
        code=("foreach(json_decode("+json.dumps(json.dumps(libraries))+",true) as $p)require_once "+
              json.dumps(str(ROOT)+"/")+".$p;echo json_encode(get_included_files());")
        included=json.loads(probe.php_run(php,["-r",code]))
        self.assertEqual({str(Path(p).relative_to(ROOT)) for p in included},set(libraries))

    def test_driver_never_retries_or_uses_db_secret_or_tunnel(self):
        source=(ROOT/"scripts/collector_remote_offline.py").read_text()
        self.assertEqual(source.count("remote.remote_call("),1)
        self.assertNotIn("MOSA_TEST_DB_PASSWORD",source)
        self.assertNotIn("shared.tunnel",source)
        self.assertNotIn("upload(",source)
        with self.assertRaises(PermissionError):driver.execute({"GITHUB_RUN_ATTEMPT":"2"},Mock())
        args=shlex.split(driver.command())
        self.assertEqual(args[:4],[probe.PYTHON,"-I","-B","-c"])
        self.assertNotIn("password",args[-1].lower())


    def test_stdio_pipe_descriptor_allowed_but_regular_file_write_blocked(self):
        readfd,writefd=os.pipe()
        try:
            probe.audit("open",(writefd,"w",os.O_WRONLY))
            probe.audit("open",(readfd,"r",os.O_RDONLY))
        finally:os.close(readfd);os.close(writefd)
        with tempfile.TemporaryFile() as file:
            with self.assertRaises(PermissionError):
                probe.audit("open",(file.fileno(),"w",os.O_WRONLY))

    def test_actual_guarded_php_stdio_normalizer_and_replay_in_child(self):
        source="""import sys
sys.path.insert(0,ROOT)
from scripts import collector_remote_offline as driver
from scripts import collector_remote_offline_probe as probe
data=driver.request()
probe.COUNTERS.update(php_processes=0,blocked_network=0,blocked_writes=0)
sys.addaudithook(probe.audit)
probe.subprocess.run=probe.pinned_run
result=probe.evaluate(driver.ROOT,data["cases"])
assert result==data["expected"]
assert probe.COUNTERS["blocked_network"]==probe.COUNTERS["blocked_writes"]==0
print("GUARDED_STDIO_REFERENCE_PASS")
""".replace("ROOT",repr(str(ROOT)),1)
        result=subprocess.run([sys.executable,"-I","-B","-c",source],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),"GUARDED_STDIO_REFERENCE_PASS")

    def test_remote_probe_has_no_write_or_network_or_productive_main_calls(self):
        source=(ROOT/"scripts/collector_remote_offline_probe.py").read_text()
        tree=ast.parse(source)
        calls={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertFalse(calls & {"write_bytes","write_text","mkdir","unlink","rename","chmod","connect","fetch","live_request"})
        self.assertNotIn("MarketLive",source)
        self.assertNotIn("live_bridge.run",source)
        self.assertIn("sys.dont_write_bytecode=True",source)
        self.assertIn("sys.addaudithook(audit)",source)
        self.assertIn("RLIMIT_FSIZE",source)
        self.assertIn("signal.alarm(55)",source)

if __name__=="__main__":unittest.main()
