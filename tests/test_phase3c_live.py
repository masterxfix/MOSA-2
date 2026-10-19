"""Offline guards for the test-only MySQL adapter; never creates a connection."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT/'scripts/phase3c/live_test.php'
FAKE = r'''
class FakeStatement extends PDOStatement {
 public function __construct(public FakeDb $db,public string $sql){}
 public function execute(?array $params=null):bool {
  $this->db->calls[]=$this->sql;
  if(str_starts_with($this->sql,'INSERT INTO m2_market_observations')){
   $this->db->key=bin2hex($params[10]);$this->db->payload=array_slice($params,0,10);
   if(isset($this->db->config['errno'])){$e=new PDOException('not logged');$e->errorInfo=[$this->db->config['state']??'23000',$this->db->config['errno'],$this->db->config['constraint']??'uq_market_observations_dedupe'];throw $e;}
  }return true;
 }
 public function fetch(int $mode=PDO::FETCH_DEFAULT,int $cursorOrientation=PDO::FETCH_ORI_NEXT,int $cursorOffset=0):mixed {
  return ['db'=>$this->db->config['target']??'h29077_mosa2_test','account'=>'h29077_mosa2_test@localhost','version'=>'8.0.26-16','port'=>3307];
 }
 public function fetchAll(int $mode=PDO::FETCH_DEFAULT,mixed ...$args):array {
  $c=$this->db->config;
  if(str_starts_with($this->sql,'SELECT entity_id'))return [['entity_id'=>101]];
  if(str_starts_with($this->sql,'SELECT id FROM m2_sources'))return [['id'=>201]];
  if(str_starts_with($this->sql,'SELECT asset_id,source_id FROM m2_asset_source_routes'))return [['asset_id'=>101,'source_id'=>$c['route_source']??201]];
  if(str_starts_with($this->sql,'SELECT * FROM m2_market_current'))return isset($c['current'])?[$c['current']]:[];
  if(str_contains($this->sql,'WHERE dedupe_key='))return [$c['stored']??\Mosa2\Phase3C\normalizeObservation(\Mosa2\Phase3C\fixtureObservation())];
  throw new RuntimeException('unexpected_fake_select');
 }
}
class FakeDb extends PDO {
 public array $calls=[];public ?string $key=null;public array $payload=[];
 public function __construct(public array $config){}
 public function inTransaction():bool{return $this->config['transaction']??true;}
 public function query(string $query,?int $fetchMode=null,mixed ...$args):PDOStatement|false{return new FakeStatement($this,$query);}
 public function prepare(string $query,array $options=[]):PDOStatement|false{return new FakeStatement($this,$query);}
 public function exec(string $statement):int|false{$this->calls[]=$statement;return 0;}
}
'''


class Phase3CLiveGuardTests(unittest.TestCase):
    def php(self, code, data=None):
        r=subprocess.run(['php','-r','require $argv[1];'+code,str(MODULE),json.dumps(data or {})],capture_output=True,text=True,check=True)
        return json.loads(r.stdout)

    def writer(self, config=None):
        return self.php(FAKE+r'''
$c=json_decode($argv[2],true);$p=new FakeDb($c);$result=null;$error=null;$errno=null;
try{$w=new \Mosa2\Phase3C\LiveTestWriter($p);$row=\Mosa2\Phase3C\fixtureObservation($c['changes']??[]);
$hook=($c['fail']??false)?function(){throw new RuntimeException('injected_offline');}:null;$result=$w->write($row,$hook);
}catch(Throwable $e){$error=$e->getMessage();$errno=$e instanceof PDOException?(int)$e->errorInfo[1]:null;}
echo json_encode(['result'=>$result,'error'=>$error,'errno'=>$errno,'calls'=>$p->calls,'key'=>$p->key,'payload'=>$p->payload]);
''', config)

    def test_adapter_uses_exact_reference_payload_and_raw_hash(self):
        r=self.writer()
        self.assertIsNone(r['error'])
        expected=self.php(r'''$r=\Mosa2\Phase3C\fixtureObservation();echo json_encode(['key'=>bin2hex(\Mosa2\Phase3C\dedupeKey($r)),'payload'=>array_values(\Mosa2\Phase3C\normalizeObservation($r))]);''')
        self.assertEqual(r['key'],expected['key'])
        self.assertEqual(r['payload'],expected['payload'])
        self.assertEqual(r['result']['current'],'updated')
        self.assertEqual(r['calls'][-1],'RELEASE SAVEPOINT m2_observation_write')

    def test_only_exact_dedupe_unique_error_becomes_replay(self):
        r=self.writer(dict(errno=1062))
        self.assertIsNone(r['error'])
        self.assertEqual(r['result']['duplicate_errno'],1062)
        self.assertEqual(r['result']['history'],'duplicate')
        self.assertFalse(any(s.startswith(('INSERT INTO m2_market_current','UPDATE m2_market_current')) for s in r['calls']))
        self.assertEqual(r['calls'][-2:],['ROLLBACK TO SAVEPOINT m2_observation_write','RELEASE SAVEPOINT m2_observation_write'])
        for config in (dict(errno=1452),dict(errno=1062,constraint='PRIMARY'),dict(errno=1062,state='HY000'),
                       dict(errno=1062,constraint='uq_market_observations_dedupe_other')):
            with self.subTest(config=config):
                rejected=self.writer(config)
                self.assertEqual(rejected['errno'],config['errno'])
                self.assertIsNone(rejected['result'])
                self.assertEqual(rejected['calls'][-2:][0],'ROLLBACK TO SAVEPOINT m2_observation_write')

    def test_duplicate_payload_conflict_is_not_suppressed(self):
        row=self.php(r'''echo json_encode(\Mosa2\Phase3C\fixtureObservation(['price'=>'11']));''')
        r=self.writer(dict(errno=1062,stored=row))
        self.assertEqual(r['error'],'dedupe_conflict')
        self.assertIsNone(r['result'])

    def test_wrong_target_and_missing_outer_transaction_fail_closed(self):
        for config,error in ((dict(target='other'),'target_identity'),(dict(transaction=False),'outer_transaction_required')):
            r=self.writer(config)
            self.assertEqual(r['error'],error)
            self.assertEqual(r['calls'],[])
        r=self.writer(dict(route_source=202))
        self.assertEqual(r['error'],'route_source')
        self.assertFalse(any(s.startswith('INSERT') for s in r['calls']))

    def test_fault_after_history_causes_real_savepoint_commands(self):
        r=self.writer(dict(fail=True))
        self.assertEqual(r['error'],'injected_offline')
        self.assertTrue(any(s.startswith('INSERT INTO m2_market_observations') for s in r['calls']))
        self.assertFalse(any(s.startswith(('INSERT INTO m2_market_current','UPDATE m2_market_current')) for s in r['calls']))
        self.assertEqual(r['calls'][-2:],['ROLLBACK TO SAVEPOINT m2_observation_write','RELEASE SAVEPOINT m2_observation_write'])

    def test_current_decision_is_shared_and_older_write_has_no_update(self):
        current=self.php(r'''echo json_encode(\Mosa2\Phase3C\normalizeObservation(\Mosa2\Phase3C\fixtureObservation(['market_at'=>'2026-01-02 12:00:00'])));''')
        r=self.writer(dict(current=current))
        self.assertIsNone(r['error'])
        self.assertEqual(r['result']['current'],'unchanged')
        self.assertFalse(any(s.startswith('UPDATE') for s in r['calls']))
        r=self.writer(dict(current=current,changes=dict(market_at='2026-01-03 12:00:00')))
        self.assertIsNone(r['error'])
        self.assertEqual(r['result']['current'],'updated')
        self.assertTrue(any(s.startswith('UPDATE m2_market_current') for s in r['calls']))

    def test_latency_statistics_and_exact_ledger_baseline(self):
        r=self.php(r'''echo json_encode([\Mosa2\Phase3C\latencyStats(range(1,20)),\Mosa2\Phase3C\expectedLedger()]);''')
        self.assertEqual(r[0],dict(measurements=20,median_ms=10.5,p95_ms=19,max_ms=20))
        self.assertEqual([v['version'] for v in r[1]],[1,2])
        self.assertEqual(r[1][1]['applied_at'],'2026-10-19 08:02:39.939576')

    def test_no_schema_ledger_or_commit_path_and_independent_readback(self):
        source=MODULE.read_text()
        self.assertNotIn('->commit(',source)
        self.assertNotRegex(source,r'(?i)\b(?:CREATE|ALTER|DROP|TRUNCATE)\s+(?:TABLE|DATABASE)\b')
        self.assertNotRegex(source,r'(?i)(?:INSERT INTO|UPDATE|DELETE FROM) m2_schema_migrations')
        self.assertNotIn('INSERT IGNORE',source)
        self.assertNotIn('ON DUPLICATE',source)
        run=source.split('function runLiveTest(')[1]
        self.assertLess(run.index('liveState($p,$root)'),run.index('$p->beginTransaction()'))
        self.assertIn("$p=null;\n        $p=connection($password);$r['independent_final']=liveState",run)
        self.assertIn("fopen($root.'/started.lock','x')",run)
        self.assertIn("unlink($root.'/secret.php')",run)
        r=subprocess.run(['php',str(MODULE)],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0)
        self.assertEqual(json.loads(r.stdout),dict(ok=False,error='guard_failure'))

    def test_gateway_probe_precedes_connection_and_token_lifetime_is_bounded(self):
        source=(ROOT/'scripts/phase3c/password_gateway.php').read_text()
        self.assertLess(source.index("$_POST['probe']"),source.index('connection($password)'))
        self.assertIn("Phase3C\\liveState($pdo, __DIR__)",source)
        self.assertIn('time()-3600',source)
        self.assertIn("min(time()+3600, $config['expires'])",source)
        for guard in ('HTTP_ORIGIN','httponly','Strict','no-store','noindex',"fopen(__DIR__.'/secret.php', 'x')"):
            self.assertIn(guard,source)
        for path in (MODULE,ROOT/'scripts/phase3c/password_gateway.php',ROOT/'scripts/phase3c/market_flow.php'):
            r=subprocess.run(['php','-l',str(path)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)


if __name__=='__main__':
    unittest.main()
