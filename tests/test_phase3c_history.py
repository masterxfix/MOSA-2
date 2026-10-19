"""Offline fixture/EXPLAIN policy tests: no PDO instance or DB connection."""
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'scripts/phase3c/live_test.php'
KEY = 'ix_market_observations_asset_time'


class Phase3CHistoryTests(unittest.TestCase):
    def php(self, code, data=None):
        result = subprocess.run(['php', '-r', 'require $argv[1];' + code,
                                 str(MODULE), json.dumps(data or {})],
                                capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def policy(self, plans, second_query=False):
        return self.php(r'''
$c=json_decode($argv[2],true);$queue=$c['plans'];$calls=0;$expansions=0;$expanded=false;$report=[];$events=[];
$file=tempnam(sys_get_temp_dir(),'m2-plan-');$error=null;
$persist=function()use(&$report,&$events,$file){\Mosa2\Phase2\save($file,$report);$events[]=json_decode(file_get_contents($file),true);};
$explain=function($sql,$parameters)use(&$queue,&$calls){$calls++;return [array_shift($queue)];};
$expand=function()use(&$expansions,&$events,&$report){$events[]=['before_expansion'=>$report];$expansions++;};
$fixture=function()use(&$expansions){return ['total_observations'=>$expansions?3080:776,
 'per_asset'=>[['asset_id'=>101,'observations'=>$expansions?1030:262,'sources'=>2,'routes'=>2,'window_rows'=>35]]];};
try{
 \Mosa2\Phase3C\guardedReadPlan('history',\Mosa2\Phase3C\HISTORY_SQL,[101,'2026-01-02','2026-01-03'],
 'ix_market_observations_asset_time',$expanded,$report,$explain,$expand,$fixture,$persist);
 if($c['second_query'])\Mosa2\Phase3C\guardedReadPlan('later',\Mosa2\Phase3C\HISTORY_SQL,[102,'2026-01-02','2026-01-03'],
 'ix_market_observations_asset_time',$expanded,$report,$explain,$expand,$fixture,$persist);
}catch(Throwable $e){$error=$e->getMessage();}
$disk=json_decode(file_get_contents($file),true);unlink($file);
echo json_encode(compact('calls','expansions','error','report','disk','events'));
''', dict(plans=plans, second_query=second_query))

    @staticmethod
    def plan(key=KEY, kind='range', extra='Using where; Using index'):
        return dict(key=key, type=kind, rows=32, Extra=extra)

    def test_same_multisource_multiday_distribution_for_every_asset(self):
        rows = self.php(r'''echo json_encode(iterator_to_array(\Mosa2\Phase3C\performanceObservations(0,8)));''')
        self.assertEqual(len(rows), 768)
        distributions = []
        for asset in ('101', '102', '103'):
            selected = [r for r in rows if r['asset_id'] == asset]
            self.assertEqual(len(selected), 256)
            self.assertEqual({r['source_id'] for r in selected}, {'201', '202'})
            self.assertEqual(len({r['route_id'] for r in selected}), 2)
            per_source = []
            for source in ('201', '202'):
                times = [r['market_at'] for r in selected if r['source_id'] == source]
                self.assertEqual(len({t[:10] for t in times}), 8)
                window = [t for t in times if '2026-01-02' <= t < '2026-01-03']
                self.assertEqual(len(window), 16)
                self.assertEqual(len(window) / len(times), 1/8)
                per_source.append(times)
            self.assertEqual(*per_source)
            distributions.append(per_source)
        self.assertEqual(distributions[0], distributions[1])
        self.assertEqual(distributions[1], distributions[2])

    def test_expansion_is_bounded_disjoint_and_uses_reference_dedupe(self):
        result = self.php(r'''
$keys=[];$counts=[];foreach([[0,8],[8,24]] as [$first,$days]){
 $batch=[];foreach(\Mosa2\Phase3C\performanceObservations($first,$days) as $r){
 $key=bin2hex(\Mosa2\Phase3C\dedupeKey($r));if(isset($keys[$key]))throw new RuntimeException('duplicate');$keys[$key]=true;$batch[]=$r;
 }$counts[]=count($batch);}
echo json_encode(['batches'=>$counts,'total'=>count($keys)]);
''')
        self.assertEqual(result, dict(batches=[768, 2304], total=3072))

    def test_wrong_ref_key_expands_exactly_once_and_keeps_both_plans_on_disk(self):
        wrong = self.plan('ix_market_observations_asset_source', 'ref', 'Using where; Using index; Using filesort')
        r = self.policy([wrong, self.plan()])
        self.assertIsNone(r['error'])
        self.assertEqual((r['calls'], r['expansions']), (2, 1))
        plans = r['disk']['plans']['history']
        self.assertEqual([p['attempt'] for p in plans], [1, 2])
        self.assertEqual([p['explain'][0] for p in plans], [wrong, self.plan()])
        self.assertEqual(plans[0]['fixture']['total_observations'], 776)
        self.assertEqual(plans[1]['fixture']['total_observations'], 3080)
        self.assertEqual(r['events'][0]['plans']['history'], [plans[0]])
        self.assertEqual(r['events'][2]['before_expansion']['plans']['history'], [plans[0]])
        for plan in plans:
            for key in ('query_id', 'sql', 'parameters', 'expected_key', 'key', 'type', 'rows', 'extra', 'fixture', 'attempt'):
                self.assertIn(key, plan)

    def test_all_expands_even_with_expected_key(self):
        r = self.policy([self.plan(kind='ALL'), self.plan()])
        self.assertEqual((r['calls'], r['expansions']), (2, 1))
        self.assertIsNone(r['error'])

    def test_correct_index_never_expands(self):
        r = self.policy([self.plan()])
        self.assertEqual((r['calls'], r['expansions']), (1, 0))
        self.assertIsNone(r['error'])

    def test_wrong_second_plan_survives_strict_guard_failure(self):
        wrong = self.plan('ix_market_observations_asset_source', 'ref')
        r = self.policy([wrong, wrong])
        self.assertEqual((r['calls'], r['expansions']), (2, 1))
        self.assertEqual(r['error'], 'plan_key:history')
        self.assertEqual(len(r['disk']['plans']['history']), 2)
        self.assertEqual(r['disk']['plans']['history'][1]['explain'], [wrong])

    def test_all_after_expansion_fails_without_third_attempt(self):
        r = self.policy([self.plan(kind='ALL'), self.plan(kind='ALL')])
        self.assertEqual((r['calls'], r['expansions']), (2, 1))
        self.assertEqual(r['error'], 'unbounded_plan:history')
        self.assertEqual(len(r['disk']['plans']['history']), 2)

    def test_expansion_budget_is_shared_across_read_paths(self):
        r = self.policy([self.plan('other', 'ref'), self.plan(), self.plan('other', 'ref')], second_query=True)
        self.assertEqual((r['calls'], r['expansions']), (3, 1))
        self.assertEqual(r['error'], 'plan_key:later')
        self.assertEqual(len(r['disk']['plans']['later']), 1)

    def test_filesort_is_not_accepted_with_expected_key(self):
        r = self.policy([self.plan(extra='Using filesort')])
        self.assertEqual(r['error'], 'filesort:history')
        self.assertEqual(r['expansions'], 0)

    def test_query_and_migrations_unchanged_without_index_hints(self):
        query = self.php(r'''echo json_encode(\Mosa2\Phase3C\HISTORY_SQL);''')
        self.assertEqual(query, 'SELECT id,market_at FROM m2_market_observations WHERE asset_id=? AND market_at>=? AND market_at<? ORDER BY market_at,id LIMIT 5')
        source = MODULE.read_text()
        self.assertNotRegex(source.upper(), r'\b(?:FORCE|USE|IGNORE)\s+INDEX\b')
        self.assertLess(source.index("$record('atomicity','savepoint_rollback')"), source.index('appendPerformanceObservations($p,0,8)'))
        generator = source.split('function performanceObservations(')[1].split('function appendPerformanceObservations(')[0]
        self.assertNotIn('101', generator)
        for name, digest in [('0001_core_asset_identity.sql', '9c3ac21f02fc242e9561d94aaa4a4c4fe6a430d11aa5f0681f0c9eace81446dd'),
                             ('0002_market_current_history.sql', '205bea42cfc93a64f76eb61c10377e47dceae38815c4351817a17aced00a75ee')]:
            self.assertEqual(hashlib.sha256((ROOT/'docs/database/migrations'/name).read_bytes()).hexdigest(), digest)

    def test_rollback_endcheck_accepts_only_counter_change(self):
        result = self.php(r'''
$base=['ledger'=>[1,2],'grants'=>['same'],'empty'=>array_fill_keys(range(1,15),0),
 'structure'=>['counts'=>['tables'=>16],'metadata'=>['t'=>['show_create'=>'CREATE TABLE `t` (`id` bigint NOT NULL AUTO_INCREMENT, PRIMARY KEY (`id`)) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4','columns'=>['unchanged']]]]];
$after=$base;$after['structure']['metadata']['t']['show_create']=str_replace('AUTO_INCREMENT=1 ','AUTO_INCREMENT=100 ',$after['structure']['metadata']['t']['show_create']);
$ok=\Mosa2\Phase3C\confirmFinalState($base,$after);$errors=[];
foreach(['data','column','ddl','ledger','grant'] as $case){$bad=$after;
 if($case==='data')$bad['empty'][1]=1;
 if($case==='column')$bad['structure']['metadata']['t']['columns']=['changed'];
 if($case==='ddl')$bad['structure']['metadata']['t']['show_create']=str_replace('bigint','int',$bad['structure']['metadata']['t']['show_create']);
 if($case==='ledger')$bad['ledger']=[1];if($case==='grant')$bad['grants']=[];
 try{\Mosa2\Phase3C\confirmFinalState($base,$bad);$errors[$case]=null;}catch(Throwable $e){$errors[$case]=$e->getMessage();}
}echo json_encode(compact('ok','errors'));
''')
        self.assertTrue(result['ok']['schema_contract_same'])
        self.assertFalse(result['ok']['auto_increment_equal'])
        self.assertFalse(result['ok']['auto_increment_reset_required'])
        self.assertEqual(result['errors'], dict(data='facts_remaining', column='structure_changed', ddl='structure_changed', ledger='ledger_changed', grant='grants_changed'))


if __name__ == '__main__':
    unittest.main()
