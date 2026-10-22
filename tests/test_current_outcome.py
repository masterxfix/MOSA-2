"""Synthetic PDO and real local process faults only. No DB/provider/network."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
from scripts.market_current import process, takeover
from scripts import current_takeover_remote as remote

ROOT = Path(__file__).resolve().parents[1]


def event(**changes):
    data = dict(kind='progress', phase='PREFLIGHT', commit='NOT_ATTEMPTED',
                rollback='NOT_ATTEMPTED', cause='NONE', transaction_started=False,
                write_attempted=False, readback_confirmed=False, replay_unchanged=False,
                elapsed_ms=1, phase_ms={'PREFLIGHT': 1})
    return data | changes


class OutcomeTests(unittest.TestCase):
    def memory(self, fault=''):
        before = dict(m2_market_current=[], m2_market_observations=[])
        plans = [dict(decision='INSERT', values=dict(asset_id=str(i), price='123.4500000000')) for i in range(1, 6)]
        result = subprocess.run(['php', str(ROOT/'tests/fixtures/current_takeover.php'), str(ROOT)],
                                input=json.dumps(dict(before=before, plans=plans, fault=fault)),
                                text=True, capture_output=True, timeout=10, check=True)
        self.assertEqual(result.stderr, '')
        data = json.loads(result.stdout)
        wire = '\n'.join(json.dumps(e) for e in data['progress'] +
                         [dict(kind='final', ok=data['ok']) | data['outcome']])
        data['public'] = process.outcome(wire)
        return data

    def test_success_requires_commit_independent_readback_and_unchanged_replay(self):
        result = self.memory()
        self.assertEqual(result['public']['status'], process.SUCCESS)
        self.assertTrue(result['public']['readback_confirmed'])
        self.assertTrue(result['public']['replay_unchanged'])
        self.assertEqual(result['events'].count('COMMIT'), 1)
        self.assertEqual(result['events'].count('UNLOCK'), 1)
        self.assertEqual(result['writes'], 5)
        # The commit event is deliberately not a final success.
        committed = next(e for e in result['progress'] if e['phase'] == 'COMMIT_CONFIRMED')
        self.assertEqual(committed['status'], 'COMMIT_CONFIRMED_READBACK_PENDING')

    def test_timeout_before_commit_rolls_back_with_proof(self):
        result = self.memory('timeout_before_commit')
        self.assertEqual(result['public']['status'], 'ROLLBACK_CONFIRMED')
        self.assertEqual(result['public']['cause'], 'PLANNER_TIMEOUT')
        self.assertNotIn('COMMIT', result['events'])
        self.assertEqual(result['state']['m2_market_current'], [])

    def test_begin_failure_is_proven_no_write_attempt(self):
        result = self.memory('begin')
        self.assertEqual(result['public']['status'], 'PREFLIGHT_FAILED_NO_WRITE')
        self.assertFalse(result['public']['write_attempted'])
        self.assertEqual(result['writes'], 0)

    def test_write_failure_and_successful_rollback(self):
        result = self.memory('write')
        self.assertEqual(result['public']['status'], 'ROLLBACK_CONFIRMED')
        self.assertEqual(result['state']['m2_market_current'], [])
        self.assertEqual(result['events'].count('ROLLBACK'), 1)
        self.assertEqual(result['events'].count('UNLOCK'), 1)

    def test_commit_unknown_even_when_rollback_returns_true(self):
        for fault in ('commit', 'commit_unknown', 'rollback'):
            with self.subTest(fault=fault):
                result = self.memory(fault)
                self.assertEqual(result['public']['status'], 'OUTCOME_UNKNOWN')
                self.assertIn('UNLOCK', result['events'])

    def test_post_commit_readback_replay_and_timeout_failures_never_rollback(self):
        for fault in ('readback', 'replay', 'timeout_after_commit'):
            with self.subTest(fault=fault):
                result = self.memory(fault)
                self.assertEqual(result['public']['status'], 'ERROR_AFTER_COMMIT')
                self.assertEqual(result['public']['commit'], 'CONFIRMED')
                self.assertNotIn('ROLLBACK', result['events'])
                self.assertFalse(result['public']['retry_allowed'])

    def test_missing_or_partial_final_and_unknown_commit(self):
        for wire in ('', json.dumps(event()), json.dumps(event(phase='COMMIT_ATTEMPT', commit='UNKNOWN')),
                     json.dumps(event())+'\n{"kind":'):
            self.assertEqual(process.outcome(wire)['status'], 'OUTCOME_UNKNOWN')
        result = process.outcome(json.dumps(event(phase='COMMIT_CONFIRMED', commit='CONFIRMED')), 'PROCESS_TIMEOUT')
        self.assertEqual(result['status'], 'ERROR_AFTER_COMMIT')
        self.assertEqual(result['commit'], 'CONFIRMED')

    def test_success_label_alone_cannot_pass(self):
        for changes in ({}, dict(commit='CONFIRMED'), dict(commit='CONFIRMED', readback_confirmed=True)):
            result = process.outcome(json.dumps(event(kind='final', ok=True, status=process.SUCCESS, **changes)))
            self.assertNotEqual(result['status'], process.SUCCESS)

    def test_public_diagnostics_never_contain_raw_data(self):
        private = 'password SELECT secret /private/path 123.4500000000'
        for raw in (private, json.dumps(event(secret=private)), json.dumps(event(cause=private))):
            self.assertNotIn(private, json.dumps(process.outcome(raw)))
        self.assertNotIn(private, json.dumps(process.outcome('', cause=private)))
        for fault in ('', 'write', 'commit_unknown', 'rollback', 'readback'):
            text = json.dumps(self.memory(fault)['public'])
            for value in ('123.4500000000', 'private', 'SQL', 'secret', 'password'):
                self.assertNotIn(value, text)

    def test_real_process_timeout_before_transaction_and_no_automatic_retry(self):
        code = 'import time;time.sleep(10)'
        start = time.monotonic()
        with patch.object(process.subprocess, 'Popen', wraps=subprocess.Popen) as spawn:
            result = process.run([sys.executable, '-c', code], {}, os.environ.copy(), ROOT, seconds=.15)
        self.assertEqual(sum(call.args[0][0] == sys.executable for call in spawn.call_args_list), 1)
        self.assertLess(time.monotonic()-start, 8)
        self.assertEqual(result['status'], 'OUTCOME_UNKNOWN')
        self.assertEqual(result['cause'], 'PROCESS_TIMEOUT')

    def test_phase_deadlines_before_begin_and_after_commit(self):
        code = r'''require $argv[1];$out=[];
        foreach(['preflight','before_commit','after_commit'] as $case){
            $o=new \Mosa2\MarketCurrent\Outcome();
            if($case==='before_commit'){$o->transaction=true;$o->phase='TRANSACTION_ACTIVE';}
            if($case==='after_commit'){$o->transaction=true;$o->commit='CONFIRMED';$o->phase='READBACK';}
            (new ReflectionProperty($o,'started'))->setValue($o,hrtime(true)/1e9-211);
            try{$o->budget($case==='before_commit');}catch(Throwable){}
            $out[]=['kind'=>'final','ok'=>false]+$o->report();
        }echo json_encode($out);'''
        result = subprocess.run(['php', '-r', code, str(ROOT/'scripts/market_current/outcome.php')],
                                text=True, capture_output=True, timeout=5, check=True)
        events = json.loads(result.stdout)
        self.assertEqual([process.outcome(json.dumps(e))['status'] for e in events],
                         ['PREFLIGHT_FAILED_NO_WRITE', 'TRANSACTION_FAILED_BEFORE_COMMIT', 'ERROR_AFTER_COMMIT'])
        self.assertTrue(all(e['cause'] == 'PHASE_TIMEOUT' for e in events))

    def test_planner_deadline_and_stderr_are_bounded_and_redacted(self):
        php = r'''require $argv[1];$c=json_decode(stream_get_contents(STDIN),true);
        try{\Mosa2\MarketCurrent\boundedPlanner([$c['python'],'-c',$c['code']],'{}',$c,$c['seconds']);echo 'BAD';}
        catch(Throwable $e){echo $e->getMessage();}'''
        for code, expected in [('import time;time.sleep(10)', 'current_planner_timeout'),
                               ('import sys;sys.stderr.write("password SQL secret")', 'current_planner_failed')]:
            result = subprocess.run(['php', '-r', php, str(ROOT/'scripts/market_current/bounded_process.php')],
                                    input=json.dumps(dict(python=sys.executable, code=code, project=str(ROOT), runtime_path=os.environ['PATH'], seconds=.1 if expected.endswith('timeout') else 2)),
                                    text=True, capture_output=True, timeout=5, check=True)
            self.assertEqual(result.stdout, expected)
            self.assertEqual(result.stderr, '')

    @unittest.skipUnless(os.name == 'posix', 'Linux process group proof')
    def test_hard_timeout_terminates_descendant_before_late_side_effect(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder)/'late'
            child = 'import time,pathlib;time.sleep(1.5);pathlib.Path('+repr(str(marker))+').write_text("bad")'
            code = ('import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",'+repr(child)+']);'
                    'print('+repr(json.dumps(event(elapsed_ms=37)))+',flush=True);time.sleep(10)')
            result = process.run([sys.executable, '-c', code], {}, os.environ.copy(), ROOT, seconds=.5)
            time.sleep(1.7)
            self.assertFalse(marker.exists())
            self.assertEqual(result['elapsed_ms'], 37)  # Parent actually spawned the descendant before termination.
            self.assertEqual(result['status'], 'OUTCOME_UNKNOWN')

    def test_historical_consumed_authorization_is_permanently_denied_without_api_or_writer(self):
        run_id = 'current-once-39634298612'
        with self.assertRaisesRegex(ValueError, 'takeover_consumed'):
            takeover.approvals(dict(run_id=run_id), 'anything', 'anything')
        with patch.object(remote, 'api') as api, self.assertRaises(ValueError):
            remote.no_previous_claim(dict(TAKEOVER_PLAN_SOURCE_RUN='39634298612'))
        api.assert_not_called()
        with patch.object(remote, 'artifact_plan', side_effect=ValueError('secret')), patch.object(remote, 'writer_call') as write:
            result = remote.apply({}, None)
        write.assert_not_called()
        self.assertEqual(result['status'], 'PREFLIGHT_FAILED_NO_WRITE')

    def test_transport_cleanup_cannot_erase_confirmed_commit_or_retry(self):
        from contextlib import contextmanager

        @contextmanager
        def ssh(*unused):
            yield object()

        @contextmanager
        def tunnel(*unused):
            yield 1234
            raise OSError('private secret path')

        env = dict(PATH=os.environ['PATH'], MOSA_TEST_DB_PASSWORD='synthetic-secret', GITHUB_RUN_ATTEMPT='1')
        committed = dict(status=process.SUCCESS, commit='CONFIRMED', retry_allowed=False)
        with patch.object(remote.reader.access, 'configuration', return_value={}), \
                patch.object(remote.reader.access, 'ssh_client', ssh), \
                patch.object(remote.reader.access, 'tunnel', tunnel), \
                patch.object(remote, 'php', return_value=committed) as invoke:
            result = remote.writer_call(env, None, 'apply')
        self.assertEqual(invoke.call_count, 1)
        self.assertEqual(result['status'], 'ERROR_AFTER_COMMIT')
        self.assertEqual(result['commit'], 'CONFIRMED')
        self.assertNotIn('secret', json.dumps(result))


if __name__ == '__main__':
    unittest.main()
