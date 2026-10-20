"""Phase-3M production plan/readback/replay tests; no database connection."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'scripts/phase3m/unit_seed.py'
spec = importlib.util.spec_from_file_location('phase3m_units', MODULE)
units = importlib.util.module_from_spec(spec)
spec.loader.exec_module(units)
CREATED = '2026-01-01 01:02:03.456789'  # Synthetic, never used for live insert.


class LiveUnitSeedTests(unittest.TestCase):
    def setUp(self):
        self.manifest = units.load_approved()
        self.resolved = units.resolve_plan(self.manifest, CREATED)
        self.rows = copy.deepcopy(self.resolved['rows'])

    def test_source_manifest_exact_bytes_and_hashes(self):
        self.assertEqual(hashlib.sha256(units.seed.DEFAULT.read_bytes()).hexdigest(), units.MANIFEST_BYTES)
        self.assertEqual(units.seed.package_sha256(self.manifest), units.APPROVED)
        for row, canonical in zip(self.resolved['definitions'], self.resolved['canonical_definitions']):
            self.assertEqual(hashlib.sha256(canonical.encode()).hexdigest(), row['definition_sha256'])

    def test_deterministic_insert_plan_and_single_frozen_time(self):
        self.assertEqual(units.insert_plan(self.manifest), units.insert_plan(self.manifest))
        self.assertNotIn('created_at', units.insert_plan(self.manifest))
        self.assertEqual([r['unit_key'] for r in self.rows], ['EUR', 'GBP', 'POINT', 'GBX'])
        self.assertEqual({r['created_at'] for r in self.rows}, {CREATED})

    def test_complete_readback_rebuilds_approved_package(self):
        result = units.verify_readback(self.manifest, self.rows[::-1], CREATED)
        self.assertEqual(result['package_sha256'], units.APPROVED)
        self.assertEqual(result['unit_rows'], 4)
        self.assertEqual([result['replay'][k] for k in ('duplicates','inserts','updates','conflicts')], [4,0,0,0])
        self.assertTrue(all(r['classification'] == 'duplicate / unchanged' for r in result['replay']['rows']))

    def test_raw_binary_32_byte_hash_readback(self):
        for row in self.rows:
            row['definition_sha256'] = bytes.fromhex(row['definition_sha256'])
        self.assertEqual(units.verify_readback(self.manifest, self.rows, CREATED)['unit_rows'], 4)
        self.rows[0]['definition_sha256'] = b'x' * 31
        with self.assertRaises(ValueError):
            units.verify_readback(self.manifest, self.rows, CREATED)

    def test_missing_extra_duplicate_rows_rejected(self):
        cases = [self.rows[:-1], self.rows + [self.rows[0]], []]
        extra = dict(self.rows[0], unit_key='EXTRA', base_unit_key='EXTRA')
        extra['definition_sha256'] = units.seed.definition_sha256(extra)
        cases.append(self.rows + [extra])
        for rows in cases:
            with self.subTest(count=len(rows)), self.assertRaises(ValueError):
                units.verify_readback(self.manifest, rows, CREATED)

    def test_replay_classifies_missing_without_executing(self):
        result = units.replay_plan(self.manifest, [], CREATED)
        self.assertEqual([result[k] for k in ('duplicates','inserts','updates','conflicts')], [0,4,0,0])
        self.assertEqual(units.replay_plan(self.manifest, self.rows[:2], CREATED)['inserts'], 2)

    def test_each_semantic_field_conflicts_even_with_new_digest(self):
        for field, value in [('unit_version','2'), ('unit_contract_version','wrong'),
                             ('base_unit_key','EUR'), ('base_unit_version','2'),
                             ('dimension_key','quantity'), ('monetary_currency_code','EUR'),
                             ('scale_numerator','3'), ('scale_denominator','101'), ('status','draft')]:
            rows = copy.deepcopy(self.rows); rows[-1][field] = value
            if field == 'dimension_key':
                rows[-1]['monetary_currency_code'] = None
            try:
                rows[-1]['definition_sha256'] = units.seed.definition_sha256(rows[-1])
            except ValueError:
                pass
            with self.subTest(field=field), self.assertRaises(ValueError):
                units.verify_readback(self.manifest, rows, CREATED)

    def test_created_at_never_changes_on_replay(self):
        original = copy.deepcopy(self.rows)
        units.replay_plan(self.manifest, self.rows, CREATED)
        self.assertEqual(self.rows, original)
        self.rows[0]['created_at'] = '2026-01-02 01:02:03.456789'
        with self.assertRaisesRegex(ValueError, 'CONFLICT'):
            units.verify_readback(self.manifest, self.rows, CREATED)

    def test_bad_times_rejected(self):
        for value in (None, 1.5, 'now', '2026-01-01T00:00:00Z', '2026-02-30 00:00:00.000000',
                      '2026-01-01 00:00:00', '0999-01-01 00:00:00.000000'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                units.resolve_plan(self.manifest, value)

    def test_unknown_db_fields_floats_and_hash_mismatch_rejected(self):
        for field, value in [('provider','forbidden'), ('scale_denominator',100.0),
                             ('definition_sha256','0'*64), ('definition_sha256','F'*64)]:
            rows=copy.deepcopy(self.rows); rows[-1][field]=value
            with self.subTest(field=field), self.assertRaises(ValueError):
                units.verify_readback(self.manifest, rows, CREATED)

    def test_manifest_mutation_fails_before_plan(self):
        for field, value in [('package_sha256','0'*64), ('package_key','other')]:
            changed=copy.deepcopy(self.manifest); changed[field]=value
            with self.assertRaises(ValueError):
                units.insert_plan(changed)

    def test_transport_and_readback_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'transport.json'
            result = subprocess.run([sys.executable,str(MODULE),'--transport',str(target)],
                                    check=True,capture_output=True,text=True)
            transport = json.loads(target.read_text(encoding='utf-8'))
            self.assertEqual(transport,units.insert_plan(self.manifest))
            self.assertEqual(json.loads(result.stdout)['package_sha256'], units.APPROVED)
            readback = Path(directory) / 'readback.json'
            readback.write_text(json.dumps(self.rows),encoding='utf-8')
            result = subprocess.run([sys.executable,str(MODULE),'--readback',str(readback),'--created-at',CREATED],
                                    check=True,capture_output=True,text=True)
            self.assertEqual(json.loads(result.stdout)['replay']['duplicates'],4)
            # Transport cannot overwrite an already frozen file.
            self.assertNotEqual(subprocess.run([sys.executable,str(MODULE),'--transport',str(target)],
                                              capture_output=True).returncode,0)

    def test_no_unit_special_logic_or_database_in_offline_module(self):
        source = MODULE.read_text(encoding='utf-8')
        for text in ('GBX','POINT','GBP','EUR','connect(', 'execute(', 'PDO', 'mysqli',
                     'INSERT INTO', 'UPDATE ', 'UPSERT', 'datetime.now', 'utcnow'):
            self.assertNotIn(text, source)

    def test_no_protected_source_changes(self):
        expected = {
            'scripts/phase3c/market_flow.php':'ab2b9510da0a76b549b587e10db5d768f079b57cd1d4e0d6542b46f805cd33af',
            'docs/database/migrations/0003_market_units.sql':'199933884802bd139b706e50e57e04687e9cbe5f8bd1366e98e302af7d47b8ee',
            'index.html':'f271e50a25fe7dadac9f4e76f0dfb1ce0264d21476e6cb09125ad5deb6c2f4d6'}
        for path,digest in expected.items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),digest)


FAKE_PDO = r'''
class UnitStatement extends PDOStatement {
    public function __construct(public UnitPDO $owner,public string $sql){}
    public function execute(?array $params=null): bool {
        $this->owner->trace[]='insert';
        $fields=array_merge(\Mosa2\Phase3M\FIELDS,['definition_sha256','created_at']);
        $row=array_combine($fields,$params);$row['definition_sha256']=bin2hex($row['definition_sha256']);
        if($row['base_unit_key']==='SEED_PROBE_MISSING'){
            $e=new PDOException('synthetic_fk');$e->errorInfo=['23000',1452,'fk_units_base'];throw $e;
        }
        $this->owner->rows[]=$row;return true;
    }
    public function rowCount(): int {return 1;}
    public function fetchAll(int $mode=PDO::FETCH_DEFAULT,mixed ...$args): array {return $this->owner->rows;}
}
class UnitPDO extends PDO {
    public array $trace=[];public array $rows=[];public bool $active=false;public bool $badCommit=false;
    public function __construct(){}
    public function beginTransaction(): bool {$this->trace[]='begin';$this->active=true;return true;}
    public function commit(): bool {$this->trace[]='commit';if($this->badCommit)throw new RuntimeException('commit_error');$this->active=false;return true;}
    public function rollBack(): bool {$this->trace[]='rollback';$this->active=false;$this->rows=[];return true;}
    public function inTransaction(): bool {return $this->active;}
    public function prepare(string $query,array $options=[]): PDOStatement|false {return new UnitStatement($this,$query);}
    public function query(string $query,?int $fetchMode=null,mixed ...$args): PDOStatement|false {
        $this->trace[]=str_contains($query,'FOR UPDATE')?'range_lock':'read';return new UnitStatement($this,$query);
    }
}
'''


class UnitSeedGatewayTests(unittest.TestCase):
    def php(self, code, payload=None, fake=False):
        prefix = 'require $argv[1];$v=json_decode(stream_get_contents(STDIN),true);'
        result = subprocess.run(['php','-r',prefix+(FAKE_PDO if fake else '')+code,
                                 str(ROOT/'scripts/phase3m/password_gateway.php')],
                                input=json.dumps(payload),capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        return json.loads(result.stdout)

    def test_php_lint(self):
        for path in (ROOT/'scripts/phase3m').glob('*.php'):
            result=subprocess.run(['php','-l',str(path)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr+result.stdout)

    def test_https_origin_expiry_method_query_size_guards(self):
        config={'host':'mosa2-test.scharwerk.de','expires':1000}
        valid=dict(HTTPS='on',HTTP_HOST=config['host'],QUERY_STRING='',REQUEST_METHOD='POST',
                   HTTP_ORIGIN='https://mosa2-test.scharwerk.de',CONTENT_LENGTH='100')
        cases=[valid]
        for field,value in [('HTTPS','off'),('HTTP_HOST','wrong.example'),('QUERY_STRING','password=x'),
                            ('REQUEST_METHOD','PUT'),('HTTP_ORIGIN','https://wrong.example'),
                            ('HTTP_ORIGIN','null'),('CONTENT_LENGTH','4097'),('CONTENT_LENGTH','-1')]:
            cases.append(dict(valid,**{field:value}))
        result=self.php(r'echo json_encode(array_map(fn($s)=>\Mosa2\Phase3M\requestAllowed($s,$v[1],999),$v[0]));',[cases,config])
        self.assertEqual(result,[True]+[False]*8)
        self.assertFalse(self.php(r'echo json_encode(\Mosa2\Phase3M\requestAllowed($v[0],$v[1],1001));',[valid,config]))

    def test_csrf_signature_cookie_age_guards(self):
        result=self.php(r'''
        $n='1000.'.str_repeat('a',64);$t=$n.'.'.hash_hmac('sha256',$n,'test-only');
        echo json_encode([\Mosa2\Phase3M\tokenValid($t,$t,'test-only',1000),
            \Mosa2\Phase3M\tokenValid($t,$t,'wrong',1000),\Mosa2\Phase3M\tokenValid($t,'wrong','test-only',1000),
            \Mosa2\Phase3M\tokenValid($t,$t,'test-only',1601),\Mosa2\Phase3M\tokenValid($t,$t,'test-only',999)]);
        ''')
        self.assertEqual(result,[True,False,False,False,False])

    def transaction(self, fail):
        return self.php(r'''
        $p=new UnitPDO();$p->badCommit=$v[1]==='commit';$failed=false;
        try{\Mosa2\Phase3M\applyTransaction($p,$v[0],$v[2],
            function($i)use($p,$v){$p->trace[]='pre'.$i;if($v[1]==='pre2'&&$i===2)throw new RuntimeException('preflight');},
            function()use($p,$v){$p->trace[]='readback';if($v[1]==='readback')throw new RuntimeException('mismatch');});}
        catch(Throwable $e){$failed=true;}
        echo json_encode(['failed'=>$failed,'trace'=>$p->trace,'rows'=>$p->rows,'active'=>$p->active]);
        ''',[units.insert_plan(units.load_approved())['definitions'],fail,CREATED],True)

    def test_one_transaction_exact_four_binary_hashes_before_commit(self):
        result=self.transaction('')
        self.assertFalse(result['failed']);self.assertFalse(result['active'])
        self.assertEqual(result['trace'],['begin','range_lock','pre0','insert','pre1','insert','pre2','insert','pre3','insert','readback','commit'])
        self.assertEqual(len(result['rows']),4)
        self.assertEqual([r['definition_sha256'] for r in result['rows']],
                         [r['definition_sha256'] for r in units.load_approved()['definitions']])
        self.assertEqual({r['created_at'] for r in result['rows']},{CREATED})

    def test_fail_closed_rollback_without_retry(self):
        for stage,inserts in [('pre2',2),('readback',4),('commit',4)]:
            result=self.transaction(stage)
            self.assertTrue(result['failed']);self.assertFalse(result['active'])
            self.assertEqual(result['trace'].count('begin'),1)
            self.assertEqual(result['trace'].count('insert'),inserts)
            self.assertEqual(result['trace'][-1],'rollback');self.assertEqual(result['rows'],[])
            self.assertEqual(result['trace'].count('commit'),int(stage=='commit'))

    def test_self_fk_probe_always_rolls_back(self):
        result=self.php(r'''
        $p=new UnitPDO();$r=\Mosa2\Phase3M\selfFk($p,$v,'2000-01-01 00:00:00.000000');
        echo json_encode([$r,$p->trace,$p->rows,$p->active]);
        ''',units.insert_plan(units.load_approved())['synthetic_probe'],True)
        self.assertTrue(all(result[0].values()));self.assertEqual(result[1][-1],'rollback')
        self.assertEqual(result[1].count('commit'),0);self.assertEqual(result[2],[]);self.assertFalse(result[3])

    def test_live_scope_and_password_storage_guards(self):
        source=(ROOT/'scripts/phase3m/live_seed.php').read_text(encoding='utf-8')
        gateway=(ROOT/'scripts/phase3m/password_gateway.php').read_text(encoding='utf-8')
        for forbidden in ('UPDATE ', 'DELETE ', 'INSERT IGNORE', 'ON DUPLICATE', 'CREATE TABLE', 'ALTER TABLE',
                          'SET FOREIGN_KEY_CHECKS', 'INSERT INTO m2_schema_migrations','GBX','GBP','POINT','EUR'):
            self.assertNotIn(forbidden,source)
        self.assertIn("fopen($root.'/started.lock','x')",source)
        self.assertIn('compareState($baseline,$state,$unitCount)',source)
        self.assertIn("'commit_requested'=>false,'commit_confirmed'=>false",source)
        self.assertLess(source.index("$plan=plan($root)"),source.index('$p=connection($password)'))
        self.assertIn("'httponly'=>true,'samesite'=>'Strict'",gateway)
        self.assertIn("unset($password,$_POST)",gateway)
        self.assertNotRegex(source+gateway,r'(?:save|file_put_contents|privateFile)\([^;]*\$password')

    def state_fixture(self, ids=(1,), next_id='10'):
        rows={'sample':[{'id':i,'value':'synthetic'} for i in ids]}
        digest=lambda value: hashlib.sha256(json.dumps(value,separators=(',',':')).encode()).hexdigest()
        keys=list(map(str,ids))
        result={'environment':{'grants':['synthetic'],'utc':True},'rows':rows,'row_hash':digest(rows),
                'ledger':[{'version':1,'checksum':'synthetic'}], 'units':[],
                'structure':{'counts':{'tables':1},'metadata':{'sample':{
                    'table':{'AUTO_INCREMENT':next_id,'ENGINE':'InnoDB'},
                    'show_create':'CREATE TABLE sample (id BIGINT PRIMARY KEY, value TEXT) ENGINE=InnoDB AUTO_INCREMENT='+next_id,
                    'columns':[{'COLUMN_NAME':'id','COLUMN_TYPE':'bigint','EXTRA':'auto_increment'}]}}},
                'counter_diagnostics':{'sample':{'column':'id','value':next_id,'count':len(ids),
                    'min_pk':str(min(ids)) if ids else None,'max_pk':str(max(ids)) if ids else None,
                    'pk_set':keys,'pk_sha256':digest(keys),'row_hash':digest(rows['sample'])}}}
        return result

    def compare_state(self, before, after):
        return self.php(r'''
        require_once dirname($argv[1]).'/state_integrity.php';
        try{$r=\Mosa2\Phase3M\compareState($v[0],$v[1]);echo json_encode(['ok'=>true,'result'=>$r]);}
        catch(Throwable $e){echo json_encode(['ok'=>false,'reason'=>$e->getMessage()]);}
        ''',[before,after])

    def test_state_identical_rows_identical_counter(self):
        base=self.state_fixture();result=self.compare_state(base,base)
        self.assertTrue(result['ok']);self.assertEqual(result['result']['affected_tables'],0)

    def test_state_identical_rows_higher_counter(self):
        result=self.compare_state(self.state_fixture(),self.state_fixture(next_id='100'))
        self.assertTrue(result['ok']);self.assertEqual(result['result']['affected_tables'],1)
        self.assertEqual(result['result']['classification'],'CHECKER_BASELINE_BUG')

    def test_state_pk_gap_and_higher_counter(self):
        self.assertTrue(self.compare_state(self.state_fixture((1,7)),self.state_fixture((1,7),'999'))['ok'])

    def test_state_changed_pk_set_rejected(self):
        self.assertFalse(self.compare_state(self.state_fixture(),self.state_fixture((2,)))['ok'])

    def test_state_changed_value_with_same_pk_rejected(self):
        base=self.state_fixture();after=copy.deepcopy(base);after['rows']['sample'][0]['value']='changed'
        self.assertFalse(self.compare_state(base,after)['ok'])

    def test_state_changed_count_or_extra_row_rejected(self):
        self.assertFalse(self.compare_state(self.state_fixture(),self.state_fixture((1,2)))['ok'])

    def test_state_counter_is_never_release_condition(self):
        for value in ('0','1','999999999999999999999999999999999999'):
            with self.subTest(counter=value):
                self.assertTrue(self.compare_state(self.state_fixture(),self.state_fixture(next_id=value))['ok'])

    def test_state_row_hash_change_rejected(self):
        base=self.state_fixture();after=copy.deepcopy(base);after['row_hash']='0'*64
        self.assertFalse(self.compare_state(base,after)['ok'])

    def test_state_unknown_table_schema_or_column_change_rejected(self):
        base=self.state_fixture()
        for field in ('table','column','show'):
            after=copy.deepcopy(base)
            if field=='table': after['structure']['metadata']['unexpected']=copy.deepcopy(after['structure']['metadata']['sample'])
            if field=='column': after['structure']['metadata']['sample']['columns'][0]['COLUMN_TYPE']='int'
            if field=='show': after['structure']['metadata']['sample']['show_create']+=' COLLATE=unexpected'
            self.assertFalse(self.compare_state(base,after)['ok'])

    def test_state_ledger_grants_and_nonempty_units_rejected(self):
        base=self.state_fixture()
        for field in ('ledger','environment','units'):
            after=copy.deepcopy(base);after[field].append({'unexpected':True}) if isinstance(after[field],list) else after[field].update(utc=False)
            self.assertFalse(self.compare_state(base,after)['ok'])

    def test_state_bigint_counter_and_empty_table(self):
        self.assertTrue(self.compare_state(self.state_fixture(),self.state_fixture(next_id='18446744073709551614'))['ok'])
        self.assertTrue(self.compare_state(self.state_fixture(()),self.state_fixture((),'100'))['ok'])

    def test_state_counter_pk_evidence_tampering_rejected(self):
        base=self.state_fixture()
        for field,value in [('count',3),('pk_set',['2']),('pk_sha256','0'*64),('row_hash','0'*64),('max_pk','2'),('min_pk','0')]:
            after=copy.deepcopy(base);after['counter_diagnostics']['sample'][field]=value
            self.assertFalse(self.compare_state(base,after)['ok'])

    def test_phase3c_contract_and_no_counter_reset(self):
        contract=(ROOT/'docs/database/PHASE3C_MARKET_FLOW.md').read_text(encoding='utf-8')
        self.assertIn('nicht identische\nAUTO_INCREMENT-Zähler',contract.replace('\r\n','\n'))
        self.assertIn('Kein Zähler-Reset',contract)
        source='\n'.join(p.read_text(encoding='utf-8') for p in (ROOT/'scripts/phase3m').glob('*.php'))
        self.assertNotRegex(source,r'(?i)ALTER\s+TABLE[^;]*AUTO_INCREMENT')
        self.assertNotRegex(source,r'(?i)(?:DELETE\s+FROM|TRUNCATE\s+TABLE)')
        diagnostic=(ROOT/'scripts/phase3m/state_integrity.php').read_text(encoding='utf-8')
        self.assertIn('SET TRANSACTION READ ONLY',diagnostic)
        self.assertIn('information_schema.columns',diagnostic)
        self.assertIn("$root.'/latest-capture.json'",diagnostic)
        self.assertNotIn("'counter_not_above_max'",diagnostic)
        self.assertNotIn("decimalCompare($d['value']",diagnostic)
        self.assertNotIn('auto_increments_changed',(ROOT/'scripts/phase3m/live_seed.php').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
