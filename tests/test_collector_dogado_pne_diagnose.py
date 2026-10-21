"""Focused start/diagnostic safety checks; no credentials or network."""
import ast
import json
from pathlib import Path
import stat
import subprocess
import unittest
from unittest.mock import Mock
from scripts import collector_dogado_pne_diagnose as diag

ROOT=Path(__file__).resolve().parents[1]

class DiagnosisTests(unittest.TestCase):
    def test_generated_php_lints_and_starts_without_main_or_database_input(self):
        source=diag.startup_source(str(ROOT))
        lint=subprocess.run(["php","-d","log_errors=0","-l"],input="<?php\n"+source,text=True,capture_output=True,timeout=10)
        self.assertEqual(lint.returncode,0,lint.stderr)
        p=subprocess.run(["php","-d","log_errors=0","-r",source],input="",text=True,capture_output=True,timeout=10)
        self.assertEqual(p.returncode,0,p.stderr);self.assertFalse(p.stderr,p.stderr)
        r=json.loads(p.stdout);self.assertEqual(r["startup"],"PASS")
        self.assertNotIn("\\Mosa2\\DogadoPne\\main();",source)
        self.assertNotIn("MOSA_TEST_DB_PASSWORD",diag.PROBE)

    def test_probe_does_not_receive_secrets_or_call_collector_and_never_writes(self):
        tree=ast.parse(diag.PROBE)
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call)]
        names=[n.func.attr if isinstance(n.func,ast.Attribute) else getattr(n.func,"id","") for n in calls]
        for name in ("open","mkdir","unlink","rename","chmod","chown","connect","run_once","perform"):
            self.assertNotIn(name,names)
        self.assertIn('assert set(d)=={"source","release"}',diag.PROBE)
        self.assertIn('for mib in (256,1024):',diag.PROBE)
        self.assertIn('resource.RLIMIT_FSIZE,(0,0)',diag.PROBE)
        self.assertNotIn("password",diag.PROBE.lower())

    def test_sql_probe_read_only_no_writer_or_provider_and_rollback(self):
        self.assertIn("SET TRANSACTION READ ONLY",diag.DB)
        self.assertIn("$p->rollBack()",diag.DB)
        self.assertIn("LIMIT 1001",diag.DB)
        for word in ("INSERT ","UPDATE ","DELETE ","CREATE ","runtimeRun(","boundedBridge("):
            self.assertNotIn(word,diag.DB)
        source=(ROOT/"scripts/collector_dogado_pne_diagnose.py").read_text()
        self.assertEqual(source.count("remote.remote_call("),2)
        self.assertNotIn("live.execute(",source)

    def test_existing_run_is_only_opened_rb_and_unknown_file_or_symlink_is_rejected(self):
        s=Mock()
        directory=Mock(st_mode=stat.S_IFDIR|0o700,st_uid=10317,st_gid=1003)
        s.lstat.return_value=directory;s.normalize.return_value=diag.live.RUN
        s.listdir.return_value=["unexpected"]
        with self.assertRaises(ValueError):diag.fingerprint(s)
        s.open.assert_not_called()
        s.listdir.return_value=["result.json"]
        s.lstat.side_effect=[directory,Mock(st_mode=stat.S_IFLNK|0o600,st_uid=10317,st_gid=1003,st_size=1)]
        with self.assertRaises(ValueError):diag.fingerprint(s)
        s.open.assert_not_called()
        code=(ROOT/"scripts/collector_dogado_pne_diagnose.py").read_text()
        self.assertIn('sftp.open(p,"rb")',code)
        self.assertNotIn('sftp.open(p,"w',code)

if __name__=="__main__":unittest.main()
