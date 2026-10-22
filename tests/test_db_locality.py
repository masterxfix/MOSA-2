"""Relevant locality-probe safety checks, all offline."""
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import collector_db_locality as probe


def php(**data):
    p=subprocess.run(['php',str(ROOT/'tests/db_locality_fixture.php')],input=json.dumps(data),
                     text=True,capture_output=True,check=True)
    if p.stderr:
        raise AssertionError('fixture stderr')
    return json.loads(p.stdout)


class LocalityTests(unittest.TestCase):
    def test_exactly_ten_fixed_selects_and_readonly_transaction(self):
        r=php();result=r['result']
        self.assertTrue(result['ok'],result)
        self.assertEqual(result['select1_executions'],10)
        self.assertEqual(r['sql'].count('SELECT 1 AS probe'),10)
        self.assertEqual([x['mode'] for x in result['samples']],['direct']*5+['native']*5)
        self.assertEqual(r['sql'][0],'SET SESSION TRANSACTION READ ONLY')
        self.assertEqual(r['writes'],0);self.assertEqual(r['rollbacks'],1)
        self.assertEqual(result['target_identity'],'PASS')
        for key in ('direct','native','all_selects'):
            s=result[key]
            self.assertAlmostEqual(s['mean_ms'],sum(s['samples_ms'])/len(s['samples_ms']))
            self.assertLessEqual(s['min_ms'],s['mean_ms'])
            self.assertLessEqual(s['mean_ms'],s['max_ms'])
        self.assertGreaterEqual(result['total_sequence_ms'],result['select_sequence_ms'])

    def test_identity_and_wrong_values_fail_closed_and_rollback(self):
        for fault in ('identity','value'):
            r=php(fault=fault)
            self.assertFalse(r['result']['ok'])
            self.assertLess(r['result']['select1_executions'],10)
            self.assertEqual(r['rollbacks'],1);self.assertEqual(r['writes'],0)
        self.assertEqual(php(fault='identity')['result']['select1_executions'],0)

    def test_invalid_endpoint_or_missing_password_never_connects(self):
        for data in (dict(port=0),dict(port=65536),dict(port='3307'),dict(password='')):
            r=php(**data)
            self.assertFalse(r['result']['ok']);self.assertEqual(r['factory_calls'],0)

    def test_exception_text_is_never_published(self):
        r=php(fault='exception')
        self.assertFalse(r['result']['ok'])
        self.assertNotIn('synthetic-secret-from-exception',json.dumps(r))
        self.assertEqual(r['result']['failure'],'DATABASE_OPERATION_FAILED')
        self.assertEqual(r['rollbacks'],1)

    def test_secret_and_source_only_in_stdin_never_command_or_environment(self):
        source=probe.source();env={'MOSA_TEST_DB_PASSWORD':'synthetic-db-secret','PATH':'/bin'}
        encoded=probe.payload(3307,env,source)
        cmd=probe.command('php',probe.BOOTSTRAP)
        self.assertNotIn(env['MOSA_TEST_DB_PASSWORD'],cmd)
        self.assertNotIn(source,cmd)
        self.assertEqual(json.loads(encoded)['source'],source)
        completed=subprocess.CompletedProcess([],0,stdout=b'{"ok":true}',stderr=b'')
        with patch.object(probe.subprocess,'run',return_value=completed) as run:
            probe.local_probe(3307,env,source)
        args,kwargs=run.call_args
        self.assertNotIn(env['MOSA_TEST_DB_PASSWORD'],repr(args))
        self.assertNotIn('MOSA_TEST_DB_PASSWORD',kwargs['env'])
        self.assertEqual(json.loads(kwargs['input'])['password'],env['MOSA_TEST_DB_PASSWORD'])
        self.assertEqual(kwargs['timeout'],90)
        with self.assertRaises(probe.ProbeError):
            probe.command('/unapproved/php',probe.BOOTSTRAP)

    def test_remote_channel_has_no_pty_closes_and_keeps_payload_on_stdin(self):
        channel=Mock()
        channel.recv_ready.side_effect=[True,False,False]
        channel.recv.return_value=b'{"ok":true}'
        channel.recv_stderr_ready.return_value=False
        channel.exit_status_ready.return_value=True
        channel.recv_exit_status.return_value=0
        transport=Mock();transport.open_session.return_value=channel
        cmd=probe.command('php',probe.BOOTSTRAP)
        code,output,errors,elapsed=probe.remote_call(transport,cmd,b'private-stdin')
        self.assertEqual(code,0);self.assertEqual(json.loads(output),{'ok':True})
        self.assertFalse(errors)
        channel.exec_command.assert_called_once_with(cmd)
        channel.sendall.assert_called_once_with(b'private-stdin')
        channel.shutdown_write.assert_called_once()
        channel.get_pty.assert_not_called();channel.close.assert_called_once()

    def test_exec_rejection_stops_before_password_or_database(self):
        channel=Mock();channel.exec_command.side_effect=RuntimeError('private remote text')
        transport=Mock();transport.open_session.return_value=channel
        with self.assertRaisesRegex(probe.ProbeError,'SSH_EXEC_REQUEST_REJECTED'):
            probe.capability(transport)
        channel.sendall.assert_not_called();channel.close.assert_called_once()

    def test_unavailable_php_has_only_fixed_bounded_capability_commands(self):
        with patch.object(probe,'remote_call',return_value=(127,b'',True,1)) as call:
            with self.assertRaisesRegex(probe.ProbeError,'NO_PHP84_CLI'):
                probe.capability(Mock())
        self.assertEqual(call.call_count,3)
        for c in call.call_args_list:
            self.assertEqual(c.kwargs['timeout'],25)
            self.assertEqual(len(c.args),2)

    def test_capability_failure_stops_execute_before_tunnel_or_password_payload(self):
        @contextmanager
        def ssh(*args):
            yield Mock()
        with patch.object(probe.shared,'configuration',return_value={}), \
             patch.object(probe.shared,'ssh_client',ssh), \
             patch.object(probe,'capability',side_effect=probe.ProbeError('SSH_EXEC_REQUEST_REJECTED')), \
             patch.object(probe.shared,'tunnel') as tunnel, \
             patch.object(probe,'payload') as payload:
            result=probe.execute({},paramiko=Mock())
        self.assertFalse(result['ok']);self.assertEqual(result['dogado_php84_cli'],'FAIL')
        tunnel.assert_not_called();payload.assert_not_called()

    def test_output_bounds_and_secret_guard(self):
        channel=Mock();channel.recv_ready.return_value=True
        channel.recv.return_value=b'x'*(probe.MAX_OUTPUT+1)
        transport=Mock();transport.open_session.return_value=channel
        with self.assertRaisesRegex(probe.ProbeError,'SSH_OUTPUT_LIMIT'):
            probe.remote_call(transport,'fixed')
        channel.close.assert_called_once()
        for name in probe.shared.SECRETS:
            output=probe.shared.public_text({'ok':True,'data':'synthetic-private'}, {name:'synthetic-private'})
            self.assertFalse(json.loads(output)['ok'])
            self.assertNotIn('synthetic-private',output)

    def test_ratios_and_reductions(self):
        def report(value):
            return dict(pdo_connect_ms=value,total_sequence_ms=value,
                        all_selects=dict(mean_ms=value),direct=dict(mean_ms=value),native=dict(mean_ms=value))
        result=probe.ratios(report(400),report(2))
        self.assertEqual(result['direct']['tunnel_over_local'],200)
        self.assertEqual(result['direct']['reduction_percent'],99.5)

    def test_workflow_manual_and_probe_has_no_business_write_or_provider_path(self):
        workflow=(ROOT/'.github/archived-workflows/collector-db-locality.yml').read_text()
        self.assertIn('workflow_dispatch:',workflow)
        self.assertNotIn('  push:',workflow);self.assertNotIn('  schedule:',workflow)
        self.assertIn('persist-credentials: false',workflow)
        self.assertNotIn('upload-artifact',workflow)
        text=(ROOT/'scripts/collector_db_locality.py').read_text()
        for forbidden in ('open_sftp','get_pty(', 'request_pty(', 'mkdtemp(', 'exec_command("mkdir'):
            self.assertNotIn(forbidden,text)
        php_text=probe.source()
        for forbidden in ('INSERT ', 'UPDATE ', 'DELETE ', 'file_put_contents(', 'fopen(', 'runtimeRun(', 'executePlan('):
            self.assertNotIn(forbidden,php_text)

if __name__=='__main__':
    unittest.main()
