from contextlib import nullcontext
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts import fundamentals_history as worker
from scripts.fundamentals import history
from test_collector_private_directories import FakeOS
from test_fundamentals_esef import plan

ROOT = Path(__file__).resolve().parents[1]
SCOPE = {'start': 2025, 'end': 2025, 'kind': 'fy'}
ISIN = 'NO0010081235'
REPORT = next(r for r in history.catalog(ISIN) if r.period == ('fy', 2025, None))
JOB = dict(SCOPE, id='e' * 64, name='NEL ASA', isin=ISIN)
ENV = {'GITHUB_SHA': 'a' * 40}


def stored(row, source_unit):
    return dict(row, **{k: source_unit[k] for k in ('monetary_currency_code', 'scale_numerator', 'scale_denominator')})


def setup_env():
    return dict(ENV, GITHUB_REPOSITORY='masterxfix/MOSA-2', GITHUB_REF='refs/heads/main',
                GITHUB_WORKFLOW_REF=worker.WORKFLOW, GITHUB_RUN_ATTEMPT='1', GITHUB_EVENT_NAME='workflow_dispatch',
                HISTORY_OPERATION='setup', HISTORY_REQUEST_ID='', EXPECTED_COMMIT=ENV['GITHUB_SHA'],
                AUTHORIZATION=f"MOSA2-HISTORY-setup:{ENV['GITHUB_SHA']}:")


class QueueSetupTests(unittest.TestCase):
    def remote_library(self):
        library = worker.shared.directories.REMOTE_SOURCE.split('\nif __name__=="__main__":')[0]
        source = (history.ROOT / 'history_queue_remote.py').read_text(encoding='utf-8')
        scope = {'__name__': 'fixture'}
        exec(compile(library + '\n' + source, '<history-queue>', 'exec'), scope)
        return scope

    def test_current_device_is_bound_and_a_change_during_open_is_rejected(self):
        remote = self.remote_library()
        api = FakeOS(remote)
        api.umask(0o077)
        for path in (remote['TARGETS'][0], remote['PARENT'], remote['QUEUE']):
            parent, name = path.rsplit('/', 1)
            fd = api.open(parent, api.O_DIRECTORY | api.O_NOFOLLOW)
            try:
                api.mkdir(name, 0o700, dir_fd=fd)
            finally:
                api.close(fd)
        for row in api.nodes.values():
            row.st_dev = 64769
        api.writes.clear()
        api.listdir = lambda fd: []
        remote['os'] = api
        with self.assertRaisesRegex(remote['Stop'], 'BASE_IDENTITY_CHANGED'):
            remote['checked_fd'](api, remote['PARENT'])
        self.assertEqual(remote['queue_operation']({'action': 'claim', 'run': '1', 'id': None}), {'job': None})
        self.assertEqual(api.writes, [])
        api.mutate_inode = True
        with self.assertRaisesRegex(remote['Stop'], 'PATH_CHANGED'):
            remote['queue_operation']({'action': 'claim', 'run': '1', 'id': None})

    @unittest.skipUnless(os.name == 'posix', 'Requires POSIX modes and directory descriptors')
    def test_setup_creates_and_reads_back_permissions_then_rejects_unsafe_lock(self):
        remote = self.remote_library()
        # Use the real POSIX operations in a temporary tree. The production
        # no-follow ancestor checker is covered separately by the FakeOS test.
        uid, gid = os.getuid(), os.getgid()
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'history'
            remote.update(BASE=tmp, PARENT=tmp, QUEUE=str(directory), UID=uid, GID=gid)
            remote['checked_fd'] = lambda api, path, **kw: api.open(path, api.O_RDONLY | api.O_DIRECTORY | api.O_NOFOLLOW)
            old_mask = os.umask(0o077)
            try:
                first = remote['queue_operation']({'action': 'setup'})
                self.assertTrue(first['ready'] and first['directory_created'] and first['lock_created'])
                lock = directory / '.queue-lock'
                self.assertEqual((stat.S_IMODE(directory.stat().st_mode), stat.S_IMODE(lock.stat().st_mode)), (0o700, 0o600))
                second = remote['queue_operation']({'action': 'setup'})
                self.assertTrue(second['owner_group_verified'])
                self.assertFalse(second['directory_created'] or second['lock_created'])
                lock.chmod(0o640)
                with self.assertRaisesRegex(remote['Stop'], 'QUEUE_FILE'):
                    remote['queue_operation']({'action': 'setup'})
            finally:
                os.umask(old_mask)

    def test_setup_has_no_db_dependency_and_redacts_remote_error_details(self):
        setup = setup_env()
        with patch.object(worker.shared, 'no_other_runs'), \
             patch.object(worker.shared.access.profile, 'configuration', return_value={}), \
             patch.object(worker.shared.access, 'configuration', side_effect=AssertionError('database configuration')), \
             patch.object(worker.shared.access, 'tunnel', side_effect=AssertionError('database tunnel')), \
             patch.object(worker.shared.access, 'ssh_client', return_value=nullcontext(Mock())), \
             patch.object(worker.shared.remote, 'remote_call') as call:
            receipt = dict(ready=True, directory_mode='0700', lock_mode='0600', owner_group_verified=True)
            call.return_value = (0, json.dumps(dict(ok=True, result=receipt)).encode(), False, 1)
            self.assertEqual(worker.execute(setup), receipt)
            call.return_value = (0, b'{"ok":true,"result":{"ready":true}}', False, 1)
            self.assertEqual(worker.execute(setup)['code'], 'QUEUE_SETUP_READBACK')
            call.return_value = (1, b'{"ok":false,"code":"EACCES","details":"private-token"}', True, 1)
            self.assertEqual(worker.execute(setup), dict(status='failed', stage='QUEUE_SETUP', code='EACCES',
                                                        message='Dogado denied filesystem access.'))
            call.return_value = (1, b'{"ok":false,"code":"private-token"}', True, 1)
            self.assertNotIn('private-token', json.dumps(worker.execute(setup)))
            call.reset_mock()
            self.assertEqual(worker.execute(dict(setup, HISTORY_ENABLED='true'))['code'], 'BACKGROUND_ENABLED')
            call.assert_not_called()


class HistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report_plan = plan(execution='fundamentals-history-' + 'e' * 32)
        cls.facts = [stored(r, cls.report_plan['units'][0]) for r in cls.report_plan['observations'] if r['fiscal_year'] == '2025']

    def test_full_partial_and_no_source_plans(self):
        reports, missing = history.candidates(SCOPE, [REPORT], history.inventory(self.facts))
        self.assertEqual(reports, [(REPORT, set())])
        self.assertEqual(missing, set())
        reports, missing = history.candidates(dict(SCOPE, kind='both'), [REPORT], history.inventory(self.facts[:1]))
        self.assertEqual(reports[0][1], REPORT.metrics - {self.facts[0]['metric_key']})
        self.assertEqual(missing, {('fq', 2025, quarter) for quarter in range(1, 5)})
        self.assertEqual(history.candidates(SCOPE, [], {}), ([], {('fy', 2025, None)}))

    def test_filter_comparative_scope_evidence_and_exact_scales(self):
        same = dict(self.facts[0], value_decimal='120', scale_numerator='1000000', unit_key='NOK_MILLION')
        filtered = history.select_facts(self.report_plan, REPORT, history.inventory([same]), SCOPE)
        self.assertIs(filtered['publish_current'], False)
        self.assertEqual(len(filtered['observations']), 4)
        self.assertTrue(all(r['fiscal_year'] == '2025' for r in filtered['observations']))
        self.assertEqual(len(json.loads(filtered['evidence_json'])['facts']), 4)
        self.assertTrue(filtered['observations'][0]['field_path'].startswith('evidence:facts/0;'))
        self.assertIsNone(history.select_facts(self.report_plan, REPORT, history.inventory(self.facts), SCOPE))

    def test_conflicts_duplicates_and_structural_breaks(self):
        for wrong in ({'value_decimal': '99'}, {'period_start': '2025-02-01'}, {'monetary_currency_code': 'EUR'}):
            with self.assertRaisesRegex(ValueError, 'HISTORY_CONFLICT'):
                history.select_facts(self.report_plan, REPORT, history.inventory([dict(self.facts[0], **wrong)]), SCOPE)
        with self.assertRaisesRegex(ValueError, 'HISTORY_CONFLICT'):
            history.inventory([self.facts[0], self.facts[0]])
        with self.assertRaisesRegex(ValueError, 'HISTORY_CONFLICT'):
            history.candidates(SCOPE, [REPORT, REPORT], {})

    def test_no_get_for_repeats_or_absent_sources(self):
        for job, rows, status in [(JOB, self.facts, 'complete'), (dict(JOB, isin='DE0000000001'), [], 'unavailable')]:
            with patch.object(worker.shared, 'database', return_value=({'inventory': rows}, 0)), \
                 patch.object(worker, 'qualify', side_effect=AssertionError('unexpected provider call')) as fetch:
                result = worker.process(ENV, None, 0, job)
            self.assertEqual(result['status'], status)
            self.assertEqual(result['inserted'], 0)
            fetch.assert_not_called()

    def test_unknown_apply_stops_without_retry(self):
        inspection = {'inventory': [], 'baseline': {}, 'protected': {}, 'asset_id': '42'}
        with patch.object(worker.shared, 'database', side_effect=[(inspection, 0), (inspection, 0), RuntimeError('INDEPENDENT_READBACK')]) as db, \
             patch.object(worker, 'qualify', side_effect=lambda report, identity, meta, item:
                          (meta.update(self.report_plan['metadata']) or self.report_plan, b'')) as fetch, \
             patch.object(worker.shared, 'archive', return_value={'identity': {}}):
            result = worker.process(ENV, None, 0, JOB)
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(result['reports'][0]['database_stage'], 'INDEPENDENT_READBACK')
        self.assertEqual(db.call_count, 3)
        fetch.assert_called_once()

    def test_history_writer_keeps_current_and_independent_receipt(self):
        old_plan = history.select_facts(self.report_plan, REPORT, {}, SCOPE)
        old_plan['archive'].update(sha256=old_plan['stored_evidence']['sha256'], bytes=old_plan['stored_evidence']['bytes'])
        # Populate Current independently of the incoming history from a separate fixture.
        program = r'''
        require 'tests/fundamentals_offline.php';
        use function Mosa2\Fundamentals\{transaction,readback,fundamentalBaseline};
        $history=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);
        $db=new MemoryPDO();
        $db->data['m2_fundamental_current'][]=['asset_id'=>'42','metric_key'=>'revenue','period_type'=>'fy','observation_id'=>'999'];
        $before=$db->data['m2_fundamental_current'];
        $base=fundamentalBaseline($db,4096);
        $receipt=transaction($db,$history,'42',fn()=>null,$base,4096);
        $reader=new MemoryPDO();$reader->data=$db->data;
        $facts=readback($reader,$receipt,$base,4096);
        if(count($facts)!==5||$receipt['current']!==0||$receipt['current_updates']!==0||
           $db->data['m2_fundamental_current']!==$before)exit(2);
        $reader->data['m2_fundamental_observations'][0]['value_decimal']='999';
        try{readback($reader,$receipt,$base,4096);}catch(Throwable){exit(0);}
        exit(3);
        '''
        result = subprocess.run(['php', '-r', program], input=json.dumps(old_plan), text=True, capture_output=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_stichtag_and_ytd_are_not_quarter_slots(self):
        snapshot = {'period_type': 'snapshot', 'as_of_at': '2025-03-25 00:00:00.000000'}
        self.assertEqual(history.slot(snapshot), ('snapshot', snapshot['as_of_at'], None))
        self.assertNotIn(('ytd', 2025, 1), set(history.periods(dict(SCOPE, kind='fq'))))

    def test_issuer_table_qualifies_exact_quarter_and_ignores_adjusted_values(self):
        report = next(r for r in history.catalog('DE0005936124') if r.period == ('fq', 2025, 1))
        adapter = report.adapter
        html = b'''<h1>OHB SE Releases Its 2025 Quarterly Report</h1>
        <p>The OHB Group (ISIN: DE0005936124, Prime Standard)</p>
        <h2>Key performance indicators at a glance</h2>
        <table><tr><th>in EUR 000</th><th>Q1 2024</th><th>Q1 2025</th></tr>
        <tr><td>Revenue</td><td>5,000</td><td>7,500</td></tr>
        <tr><td>Adjusted EBITDA</td><td>8,000</td><td>9,000</td></tr>
        <tr><td>EBIT</td><td>1,000</td><td>-50</td></tr>
        <tr><td>EBITDA</td><td>2,000</td><td></td></tr></table>'''
        identity = {'name': 'OHB SE', 'isin': adapter.ISIN}
        metadata = dict(self.report_plan['metadata'], url=adapter.URL, content_type='text/html')
        parsed = adapter.parse(html, metadata, identity)
        rows = parsed['observations']
        self.assertEqual([(r['metric_key'], r['value_decimal']) for r in rows], [('revenue', '7500'), ('ebit', '-50')])
        self.assertTrue(all(r['period_end'] == '2025-03-31' and r['period_type'] == 'fq' for r in rows))
        raw, evidence = adapter.evidence(parsed, metadata, identity)
        self.assertIn(b'official_issuer_release', raw)
        parsed.update(metadata=metadata, stored_evidence=evidence,
                      archive=dict(storage_key='/private/synthetic/evidence.json', durable=True,
                                   sha256=evidence['sha256'], bytes=evidence['bytes']))
        filtered = history.select_facts(parsed, report, {}, dict(SCOPE, kind='fq'))
        result = subprocess.run(['php', '-r', "require 'scripts/fundamentals/core.php'; "
                                 "\\Mosa2\\Fundamentals\\storedFile(json_decode(stream_get_contents(STDIN),true));"],
                                input=json.dumps(filtered), text=True, capture_output=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with self.assertRaisesRegex(ValueError, 'ISSUER_TABLE_STRUCTURE'):
            adapter.parse(html.replace(b'Q1 2025', b'YTD 2025'), metadata, identity)

    def test_worker_requires_exact_main_and_fresh_execution(self):
        env = dict(ENV, GITHUB_REPOSITORY='masterxfix/MOSA-2', GITHUB_REF='refs/heads/main',
                   GITHUB_WORKFLOW_REF=worker.WORKFLOW, GITHUB_RUN_ATTEMPT='1', GITHUB_EVENT_NAME='workflow_dispatch',
                   HISTORY_OPERATION='process', HISTORY_REQUEST_ID=JOB['id'], EXPECTED_COMMIT=ENV['GITHUB_SHA'],
                   AUTHORIZATION=f"MOSA2-HISTORY-process:{ENV['GITHUB_SHA']}:{JOB['id']}")
        self.assertEqual(worker.guard(env), ('process', JOB['id']))
        for override in [{'GITHUB_RUN_ATTEMPT': '2'}, {'EXPECTED_COMMIT': 'b' * 40}, {'HISTORY_REQUEST_ID': 'f' * 64}]:
            with self.assertRaises(ValueError):
                worker.guard(dict(env, **override))


if __name__ == '__main__':
    unittest.main()
