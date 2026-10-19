"""Offline tests of shared Phase-3B guards; never connects to a database."""
import json
import hashlib
from datetime import datetime
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'scripts/phase3b/postcheck.php'


class Phase3BTests(unittest.TestCase):
    def php(self, code, *args):
        result = subprocess.run(['php', '-r', 'require $argv[1];'+code, str(MODULE), *map(str, args)],
                                capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def test_php_lints(self):
        for folder in ('phase2', 'phase3b'):
            for path in (ROOT/'scripts'/folder).glob('*.php'):
                result = subprocess.run(['php', '-l', str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

    def test_both_exact_migrations_parse_with_shared_contract(self):
        result = self.php(r'''
$core=\Mosa2\Phase2\contract(file_get_contents($argv[2]));
$market=\Mosa2\Phase2\contract(file_get_contents($argv[3]),\Mosa2\Phase3B\DIGEST,\Mosa2\Phase3B\MARKET);
$counts=[count($core+$market),0,0,0,0,0,0];
foreach($core+$market as $t){$counts[1]+=count($t['columns']);foreach($t['indexes'] as $k=>$v)$counts[$k==='PRIMARY'?2:($v['unique']?3:4)]++;$counts[5]+=count($t['fks']);$counts[6]+=count($t['checks']);}
echo json_encode($counts);
''', ROOT/'docs/database/migrations/0001_core_asset_identity.sql', ROOT/'docs/database/migrations/0002_market_current_history.sql')
        self.assertEqual(result, [16, 140, 16, 9, 26, 23, 19])

    def test_changed_bytes_fail_before_sql(self):
        self.assertEqual(self.php(r'''
$s=file_get_contents($argv[2]);$r=[];
foreach([$s."\n",str_replace('price > 0','price >= 0',$s)] as $bad){try{\Mosa2\Phase2\contract($bad,\Mosa2\Phase3B\DIGEST,\Mosa2\Phase3B\MARKET);$r[]=false;}catch(RuntimeException $e){$r[]=$e->getMessage()==='migration_digest';}}
echo json_encode($r);
''', ROOT/'docs/database/migrations/0002_market_current_history.sql'), [True, True])

    def test_interval_three_way_checks_fail_closed(self):
        self.assertEqual(self.php(r'''
$e="interval_key IN ('1m','5m','1h','1d')";
$a="(`interval_key` in (_utf8mb4\\'1m\\',_utf8mb4\\'5m\\',_utf8mb4\\'1h\\',_utf8mb4\\'1d\\'))";
$s=" CONSTRAINT `ck` CHECK ((`interval_key` in (_utf8mb4'1m',_utf8mb4'5m',_utf8mb4'1h',_utf8mb4'1d')))";
$r=[];foreach([[$a,$s], [str_replace('1d','1w',$a),$s],[$a,str_replace('1d','1w',$s)], [str_replace('_utf8mb4','_latin1',$a),$s]] as [$actual,$show])$r[]=\Mosa2\Phase2\compareCheck('t','ck',$e,$actual,$show,true)['equal'];
echo json_encode($r);
'''), [True, False, False, False])

    def test_ledger_and_empty_guards_execute_against_fake_pdo(self):
        self.assertEqual(self.php(r'''
class S extends PDOStatement { public array $data=[]; public function fetchAll(int $mode=PDO::FETCH_DEFAULT,mixed ...$args):array{return $this->data;} public function fetchColumn(int $column=0):mixed{return $this->data[0];}}
class P extends PDO {public array $data=[];public function __construct(){} public function query(string $query,?int $fetchMode=null,mixed ...$args):PDOStatement|false{$s=new S();$s->data=$this->data;return $s;}}
$p=new P();$v=['version'=>1,'migration_key'=>'0001_core_asset_identity','checksum'=>\Mosa2\Phase2\DIGEST,'applied_at'=>'2026-10-18 14:10:22.604406'];$p->data=[$v];$r=[\Mosa2\Phase3B\ledger($p,1)==[$v]];
foreach(['version','migration_key','checksum','applied_at'] as $key){$bad=$v;$bad[$key]='invalid';$p->data=[$bad];try{\Mosa2\Phase3B\ledger($p,1);$r[]=false;}catch(RuntimeException){$r[]=true;}}
$p->data=[$v,$v];try{\Mosa2\Phase3B\ledger($p,1);$r[]=false;}catch(RuntimeException){$r[]=true;}
$p->data=[0];$r[]=\Mosa2\Phase3B\emptyFacts($p,['m2_entities'])===['m2_entities'=>0];
$p->data=[1];try{\Mosa2\Phase3B\emptyFacts($p,['m2_entities']);$r[]=false;}catch(RuntimeException){$r[]=true;}
echo json_encode($r);
'''), [True]*8)

    def test_order_and_no_resume_or_forced_index(self):
        source=MODULE.read_text(encoding='utf-8')
        self.assertNotIn('FORCE INDEX', source)
        self.assertNotIn('--resume', source)
        self.assertIn("fopen($root.'/started.lock','x')", source)
        run=source.split('function run(')[1]
        self.assertLess(run.index('before($p,$core)'),run.index("$p->exec($table['ddl'])"))
        self.assertLess(run.index("practical($p,$r['practical'],"),run.index('INSERT INTO m2_schema_migrations'))
        self.assertLess(run.index('emptyFacts($p,array_keys($all))'),run.index('INSERT INTO m2_schema_migrations'))
        self.assertIn('!$committed&&!$commitAttempted',run)
        self.assertIn("check(in_array($name,MARKET,true),'cleanup_scope')",run)
        self.assertIn("$p=null;$p=connection($password)",run)

    def test_failed_plan_evidence_survives_guard_without_extra_fields(self):
        result=self.php(r'''
$e=[];$row=['key'=>'different_index','type'=>'ref','rows'=>8,'Extra'=>'Using filesort','unrelated'=>'must not survive'];
try {\Mosa2\Phase3B\rememberPlan($e,'bars_asset',$row,'ix_market_bars_asset_time',4096,'SELECT synthetic');\Mosa2\Phase2\same($row['key'],'ix_market_bars_asset_time','plan_key:bars_asset');} catch(RuntimeException $error) {$failure=$error->getMessage();}
\Mosa2\Phase3B\rememberPlan($e,'bars_asset',['key'=>null,'type'=>'ALL','rows'=>16384,'Extra'=>''], 'ix_market_bars_asset_time',16384,'SELECT synthetic');
echo json_encode([$failure,$e]);
''')
        self.assertEqual(result[0], 'plan_key:bars_asset')
        attempts=result[1]['explain_attempts']['bars_asset']
        self.assertEqual(len(attempts),2)
        self.assertEqual(attempts[0],dict(sql='SELECT synthetic',expected_key='ix_market_bars_asset_time',key='different_index',type='ref',rows=8,extra='Using filesort',history_rows_per_table=4096,fixture_rows=[]))
        self.assertIsNone(attempts[1]['key'])
        self.assertEqual(result[1]['history_rows_per_table'],16384)
        source=MODULE.read_text(encoding='utf-8')
        self.assertLess(source.index('rememberPlan($evidence,$name,$r'),source.index("same($r['key'],$key"))
        self.assertIn("practical($p,$r['practical'],function()use(&$r,$root):void{save($root.'/report.json',$r);})",source)

    def test_plan_is_written_before_failing_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'diagnostic.json'
            result=self.php(r'''
$report=['practical'=>[]];$path=$argv[2];
$persist=function()use(&$report,$path):void{\Mosa2\Phase2\save($path,$report);};
$sql="SELECT id,starts_at FROM m2_market_bars WHERE asset_id=1 AND interval_key='1m' AND starts_at>='2026-01-01' AND starts_at<'2026-01-02' ORDER BY starts_at,id LIMIT 5";
try {
 \Mosa2\Phase3B\rememberPlan($report['practical'],'bars_asset',['key'=>'different_index','type'=>'ref','rows'=>8,'Extra'=>'Using index'],'ix_market_bars_asset_time',4096,$sql,$persist);
 \Mosa2\Phase2\same('different_index','ix_market_bars_asset_time','plan_key:bars_asset');
} catch(RuntimeException $e) {$failure=$e->getMessage();}
unset($report);echo json_encode([$failure,json_decode(file_get_contents($path),true)]);
''',path)
            self.assertEqual(result[0],'plan_key:bars_asset')
            plan=result[1]['practical']['explain_attempts']['bars_asset'][0]
            self.assertEqual(plan['key'],'different_index')
            self.assertIn("interval_key='1m'",plan['sql'])
            self.assertEqual(plan['rows'],8)
            self.assertEqual(json.loads(path.read_text()),result[1])

    def test_bar_fixture_intervals_alignment_and_bounded_selectivity(self):
        initial, additional = self.php(r"""
echo json_encode([iterator_to_array(\Mosa2\Phase3B\barFixture(0,8),false),iterator_to_array(\Mosa2\Phase3B\barFixture(8,16),false)]);
""")
        self.assertEqual(len(initial), 32)
        self.assertEqual(len(initial + additional), 64)
        identities = set()
        for row in initial + additional:
            identity = (row['interval_key'], row['starts_at'])
            self.assertNotIn(identity, identities)
            identities.add(identity)
            start = datetime.fromisoformat(row['starts_at'])
            end = datetime.fromisoformat(row['ends_at'])
            seconds = {'1m': 60, '5m': 300, '1h': 3600, '1d': 86400}[row['interval_key']]
            self.assertEqual((end-start).total_seconds(), seconds)
            self.assertEqual((start-datetime(2026, 1, 1)).total_seconds() % seconds, 0)
        for rows, per_interval in ((initial, 8), (initial + additional, 16)):
            for interval in ('1m', '5m', '1h', '1d'):
                self.assertEqual(sum(r['interval_key'] == interval for r in rows), per_interval)
            matching_interval = [r for r in rows if r['interval_key'] == '1m']
            matching_window = [r for r in matching_interval if '2026-01-01' <= r['starts_at'] < '2026-01-02']
            self.assertEqual(len(matching_window), 2)
            self.assertLess(len(matching_window), len(matching_interval))
            self.assertLess(len(matching_interval), len(rows))
        source = MODULE.read_text(encoding='utf-8')
        self.assertIn('for($a=1;$a<=512;$a++)foreach($rows as $row)', source)
        generator = source.split('function barFixture(')[1].split('function checkedExplain(')[0]
        self.assertNotIn('$a', generator)

    def explain_case(self, rows, *, expanded=False, second=False):
        return self.php(r"""
class PlanRows extends PDOStatement {public array $row;public function fetchAll(int $mode=PDO::FETCH_DEFAULT,mixed ...$args):array{return [$this->row];}}
class PlanDb extends PDO {public array $rows;public int $queries=0;public function __construct(array $rows){$this->rows=$rows;}public function query(string $query,?int $fetchMode=null,mixed ...$args):PDOStatement|false{if(!str_starts_with($query,'EXPLAIN '))throw new RuntimeException('unexpected_sql');$s=new PlanRows();$s->row=$this->rows[$this->queries++];return $s;}}
$p=new PlanDb(json_decode($argv[2],true));$expanded=$argv[3]==='1';$calls=0;$snapshots=[];
$e=['fixture_rows'=>['m2_market_bars'=>16384],'explain_attempts'=>[]];
$expand=function()use(&$calls,&$e):void{$calls++;$e['fixture_rows']['m2_market_bars']=32768;};
$persist=function()use(&$snapshots,&$e):void{$snapshots[]=$e;};$failure=null;
try {\Mosa2\Phase3B\checkedExplain($p,'bars_asset','SELECT synthetic','ix_market_bars_asset_time','m2_market_bars',$e,$expanded,$expand,$persist);
if($argv[4]==='1')\Mosa2\Phase3B\checkedExplain($p,'bars_asset_next','SELECT synthetic','ix_market_bars_asset_time','m2_market_bars',$e,$expanded,$expand,$persist);
} catch(RuntimeException $error){$failure=$error->getMessage();}
echo json_encode(['failure'=>$failure,'calls'=>$calls,'queries'=>$p->queries,'evidence'=>$e,'snapshots'=>$snapshots]);
""", json.dumps(rows), int(expanded), int(second))

    @staticmethod
    def plan(key='ix_market_bars_asset_time', access='range'):
        return dict(key=key, type=access, rows=2, Extra='Using index')

    def test_expected_plan_needs_no_expansion(self):
        result = self.explain_case([self.plan()])
        self.assertIsNone(result['failure'])
        self.assertEqual((result['calls'], result['queries']), (0, 1))

    def test_wrong_key_ref_and_all_each_expand_once_and_retain_both_attempts(self):
        for first in (self.plan('uq_market_bars_identity', 'ref'), self.plan(None, 'ALL')):
            with self.subTest(first=first):
                result = self.explain_case([first, self.plan()])
                self.assertIsNone(result['failure'])
                self.assertEqual((result['calls'], result['queries']), (1, 2))
                attempts = result['evidence']['explain_attempts']['bars_asset']
                self.assertEqual([a['key'] for a in attempts], [first['key'], 'ix_market_bars_asset_time'])
                self.assertEqual([a['history_rows_per_table'] for a in attempts], [16384, 32768])
                self.assertEqual([a['fixture_rows']['m2_market_bars'] for a in attempts], [16384, 32768])
                self.assertEqual(len(result['snapshots'][0]['explain_attempts']['bars_asset']), 1)
                self.assertEqual(len(result['snapshots'][1]['explain_attempts']['bars_asset']), 2)

    def test_retry_keeps_strict_key_and_access_guards(self):
        for last, failure in ((self.plan('other_index', 'ref'), 'plan_key:bars_asset'),
                              (self.plan(access='ALL'), 'unbounded_plan:bars_asset')):
            result = self.explain_case([self.plan('wrong', 'ref'), last])
            self.assertEqual(result['failure'], failure)
            self.assertEqual((result['calls'], result['queries']), (1, 2))
            self.assertEqual(len(result['snapshots'][-1]['explain_attempts']['bars_asset']), 2)
        source = MODULE.read_text(encoding='utf-8')
        self.assertIn("same($r['key'],$key,'plan_key:'.$name)", source)
        self.assertIn("['const','eq_ref','ref','range']", source)
        self.assertNotIn('FORCE INDEX', source)

    def test_expansion_budget_is_global_across_queries(self):
        result = self.explain_case([self.plan('wrong', 'ref'), self.plan(), self.plan('wrong', 'ref')], second=True)
        self.assertEqual(result['failure'], 'plan_key:bars_asset_next')
        self.assertEqual((result['calls'], result['queries']), (1, 3))
        result = self.explain_case([self.plan('wrong', 'ref')], expanded=True)
        self.assertEqual(result['failure'], 'plan_key:bars_asset')
        self.assertEqual((result['calls'], result['queries']), (0, 1))

    def test_migrations_are_byte_identical(self):
        for name, digest in (
            ('0001_core_asset_identity.sql', '9c3ac21f02fc242e9561d94aaa4a4c4fe6a430d11aa5f0681f0c9eace81446dd'),
            ('0002_market_current_history.sql', '205bea42cfc93a64f76eb61c10377e47dceae38815c4351817a17aced00a75ee')):
            self.assertEqual(hashlib.sha256((ROOT/'docs/database/migrations'/name).read_bytes()).hexdigest(), digest)

    def test_core_state_rejects_all_forbidden_baselines(self):
        result=self.php(r'''
class StateRows extends PDOStatement {
 public array $rows=[];
 public function fetchAll(int $mode=PDO::FETCH_DEFAULT,mixed ...$args):array{return $this->rows;}
 public function fetchColumn(int $column=0):mixed{return $this->rows[0];}
}
class StateDb extends PDO {
 public array $names;public array $ledger;public int $facts=0;
 public function __construct(){ $this->names=\Mosa2\Phase2\TABLES;sort($this->names);$this->ledger=[['version'=>1,'migration_key'=>'0001_core_asset_identity','checksum'=>\Mosa2\Phase2\DIGEST,'applied_at'=>'2026-10-18 14:10:22.604406']];}
 public function query(string $query,?int $fetchMode=null,mixed ...$args):PDOStatement|false {
  $s=new StateRows();
  if(str_contains($query,'information_schema.tables'))$s->rows=$this->names;
  elseif(str_starts_with($query,'SELECT version'))$s->rows=$this->ledger;
  elseif(str_starts_with($query,'SELECT COUNT(*) FROM `m2_'))$s->rows=[$this->facts];
  else throw new RuntimeException('unexpected_sql');
  return $s;
 }
}
$r=[];$p=new StateDb();$state=\Mosa2\Phase3B\coreState($p);$r[]=$state['tables']===13&&count($state['ledger'])===1&&count($state['empty'])===12;
try{\Mosa2\Phase2\preflight($p);$r[]=false;}catch(RuntimeException $e){$r[]=$e->getMessage()==='target_not_empty';}
foreach(['foreign','market','missing_table','missing_ledger','digest','rows'] as $case){
 $p=new StateDb();
 if($case==='foreign')$p->names[]='unexpected_table';
 if($case==='market')$p->names[]='m2_market_current';
 if($case==='missing_table')array_pop($p->names);
 if($case==='missing_ledger')$p->ledger=[];
 if($case==='digest')$p->ledger[0]['checksum']=str_repeat('0',64);
 if($case==='rows')$p->facts=1;
 try{\Mosa2\Phase3B\coreState($p);$r[]=false;}catch(RuntimeException $e){$r[]=true;}
}
echo json_encode($r);
''')
        self.assertEqual(result,[True]*8)

    def test_phase2_gateway_unchanged_and_phase3_store_order(self):
        original=subprocess.run(['git','show','HEAD:scripts/phase2/password_gateway.php'],cwd=ROOT,capture_output=True,check=True).stdout
        self.assertEqual((ROOT/'scripts/phase2/password_gateway.php').read_bytes().replace(b'\r\n',b'\n'),original.replace(b'\r\n',b'\n'))
        gateway=(ROOT/'scripts/phase3b/password_gateway.php').read_text(encoding='utf-8')
        self.assertNotIn('Phase2\\preflight($pdo)',gateway)
        self.assertLess(gateway.index('Phase3B\\before($pdo, $core)'),gateway.index("fopen(__DIR__.'/secret.php', 'x')"))
        self.assertIn('preflight($p,false)',MODULE.read_text(encoding='utf-8'))
        self.assertIn("unset($r['tables'])",MODULE.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
