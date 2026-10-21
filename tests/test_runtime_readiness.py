"""Harmless readiness-probe security and process tests; no DB or HTTP."""
from contextlib import contextmanager
import ast
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import collector_runtime_readiness as readiness


def php(**data):
    p=subprocess.run(['php',str(ROOT/'tests/runtime_readiness_fixture.php')],
                     input=json.dumps(data),text=True,capture_output=True,check=True)
    if p.stderr:
        raise AssertionError('fixture stderr')
    return json.loads(p.stdout)


class ReadinessTests(unittest.TestCase):
    def test_bounded_fixed_candidates_and_early_success(self):
        report=php(action='assess')
        self.assertTrue(report['report']['assessment_complete'])
        self.assertFalse(report['report']['ok'])
        self.assertEqual(len(report['calls']),3)
        self.assertEqual([r['command'][0] for r in report['calls']],['/usr/bin/python3','python3','/usr/local/bin/python3'])
        for c in report['calls']:
            self.assertEqual(c['command'][1:4],['-I','-B','-c'])
            self.assertEqual(set(c['input']),{'php_binary','php_flags'})
        success=php(action='assess',succeed_at=1)
        self.assertTrue(success['report']['ok'])
        self.assertEqual(len(success['calls']),1)

    def test_php_starts_harmless_child_and_closes_successfully(self):
        r=php(action='normal')
        self.assertTrue(r['started']);self.assertEqual(r['exit_code'],0)
        self.assertEqual(r['result'],dict(marker='harmless'))

    def test_stderr_and_excess_output_not_published(self):
        stderr=php(action='stderr')
        self.assertTrue(stderr['stderr_suppressed'])
        self.assertNotIn('synthetic-private-error',json.dumps(stderr))
        overflow=php(action='overflow')
        self.assertTrue(overflow['output_limit'])
        self.assertNotIn('xxxx',json.dumps(overflow))

    def test_python_modules_and_own_process_group_cleanup_locally(self):
        data=dict(php_binary=subprocess.check_output(['php','-r','echo PHP_BINARY;'],text=True),
                  php_flags=['-d','display_errors=0','-d','log_errors=0'])
        p=subprocess.run([sys.executable,'-I','-B',str(ROOT/'scripts/market_collector/runtime_readiness_probe.py')],
                         input=json.dumps(data),text=True,capture_output=True,check=True,timeout=15)
        self.assertEqual(p.stderr,'')
        r=json.loads(p.stdout)
        self.assertTrue(r['ok'],r)
        self.assertEqual(r['collector_syntax'],'PASS')
        self.assertTrue(all(x=='PASS' for x in r['modules'].values()))
        self.assertEqual(r['own_process_group_termination'],'PASS')
        self.assertTrue(r['python_to_php']['pinned_path']['ok'])
        self.assertEqual(r['provider_requests'],0);self.assertEqual(r['database_connections'],0)

    def run_mock(self,probe):
        @contextmanager
        def ssh(*args):
            yield Mock()
        env={name:'synthetic-private-secret' for name in readiness.shared.SECRETS}
        with patch.object(readiness.shared,'configuration',return_value={}), \
             patch.object(readiness.shared,'ssh_client',ssh), \
             patch.object(readiness.remote,'capability',return_value=('php',[])), \
             patch.object(readiness.remote,'remote_call',return_value=(0,json.dumps(probe).encode(),False,1)) as remote:
            result=readiness.execute(env,paramiko=Mock())
        return result,remote

    def test_no_secret_or_database_input_in_remote_payload(self):
        result,remote=self.run_mock(dict(ok=True,assessment_complete=True))
        self.assertTrue(result['collector_runtime_ready'])
        data=json.loads(remote.call_args.args[2])
        self.assertEqual(set(data),{'source','python_source'})
        self.assertNotIn('synthetic-private-secret',json.dumps(data))
        self.assertEqual(remote.call_args.kwargs['timeout'],75)
        self.assertEqual(result['database_connections'],0)
        self.assertEqual(result['remote_file_operations'],0)

    def test_negative_readiness_is_completed_assessment_not_a_false_pass(self):
        result,remote=self.run_mock(dict(ok=False,assessment_complete=True,blocker='missing interpreter'))
        self.assertTrue(result['ok'])
        self.assertFalse(result['collector_runtime_ready'])
        self.assertEqual(result['probe']['blocker'],'missing interpreter')

    def test_missing_secrets_stop_before_ssh(self):
        with patch.object(readiness.shared,'ssh_client') as ssh:
            r=readiness.execute({},paramiko=Mock())
        ssh.assert_not_called();self.assertFalse(r['ok'])

    def test_exec_rejection_has_no_alternative_route(self):
        @contextmanager
        def ssh(*args):
            yield Mock()
        with patch.object(readiness.shared,'configuration',return_value={}), \
             patch.object(readiness.shared,'ssh_client',ssh), \
             patch.object(readiness.remote,'capability',side_effect=readiness.remote.ProbeError('SSH_EXEC_REQUEST_REJECTED')), \
             patch.object(readiness.remote,'remote_call') as remote:
            r=readiness.execute({},paramiko=Mock())
        remote.assert_not_called()
        self.assertEqual(r['failure'],'SSH_EXEC_REQUEST_REJECTED')

    def test_manual_only_workflow_and_no_mutating_or_network_probe(self):
        text=(ROOT/'.github/workflows/collector-runtime-readiness.yml').read_text()
        self.assertIn('workflow_dispatch:',text)
        self.assertNotIn('  push:',text);self.assertNotIn('  schedule:',text)
        self.assertNotIn('upload-artifact',text)
        self.assertIn('persist-credentials: false',text)
        for path in ('scripts/market_collector/runtime_readiness_probe.php','scripts/collector_runtime_readiness.py'):
            source=(ROOT/path).read_text()
            for forbidden in ('open_sftp(', 'file_put_contents(', 'mkdir(', 'new PDO(', 'executePlan(', 'runtimeRun(', "['action'=>'fetch'"):
                self.assertNotIn(forbidden,source)
        source=(ROOT/'scripts/market_collector/runtime_readiness_probe.py').read_text()
        parsed=ast.parse(source)
        banned={'urlopen','getaddrinfo','create_connection','fetch','connect','write_text','write_bytes','mkdir','makedirs'}
        calls=[n.func.attr for n in ast.walk(parsed) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
        self.assertFalse(banned.intersection(calls))

    def test_existing_secret_output_guard(self):
        for name in readiness.shared.SECRETS:
            result=readiness.shared.public_text(dict(ok=True,data='synthetic-sensitive'),{name:'synthetic-sensitive'})
            self.assertFalse(json.loads(result)['ok'])
            self.assertNotIn('synthetic-sensitive',result)

if __name__=='__main__':
    unittest.main()
