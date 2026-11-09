import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from scripts import fundamentals_history as worker
from scripts.fundamentals import history
from test_fundamentals_esef import plan

ROOT = Path(__file__).resolve().parents[1]
SCOPE = {'start': 2025, 'end': 2025, 'kind': 'fy'}
ISIN = 'NO0010081235'
REPORT = next(r for r in history.catalog(ISIN) if r.period == ('fy', 2025, None))
JOB = dict(SCOPE, id='e' * 64, name='NEL ASA', isin=ISIN)
ENV = {'GITHUB_SHA': 'a' * 40}


def stored(row, source_unit):
    return dict(row, **{k: source_unit[k] for k in ('monetary_currency_code', 'scale_numerator', 'scale_denominator')})


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
        for job, rows, status in [(JOB, self.facts, 'complete'), (dict(JOB, isin='DE0005936124'), [], 'unavailable')]:
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
