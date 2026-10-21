"""Synthetic exact takeover and existing Current transaction tests. No live DB."""
import copy
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from scripts.market_current import takeover, planner, sealed
import test_current_preview as preview_fixtures
from test_observation_v2_writer_phase3 import row, CREATED
ROOT=Path(__file__).resolve().parents[1]

class CurrentTakeoverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        builder=preview_fixtures.CurrentPreviewTests();builder.setUp()
        cls.entries=builder.snapshot()
        for i,entry in enumerate(cls.entries[:2]):
            data=entry['input'];r=data['route']
            raw=row(asset_id=r['asset_id'],route_id=r['id'],market_at='2025-12-31 23:59:00',observed_at='2025-12-31 23:59:01')
            old=builder.builder.fact(raw,str(8000+i))
            data['current']=planner.plan_facts(dict(data,facts=[old]))['values'];data['current_fact']=old
        cls.snapshot=dict(items=cls.entries,as_of=CREATED)
        cls.plan=takeover.prepare(cls.snapshot,'current-once-12345','a'*40)

    def items(self):
        return [copy.deepcopy(e['input'])|dict(qualified_scope={k:copy.deepcopy(e[k]) for k in ('isin','name','scope_rows')}) for e in self.entries]

    def validate(self,items=None,plan=None,auth=None):
        plan=plan or self.plan
        return takeover.validate(items or self.items(),dict(plan=plan,authorization=auth if auth is not None else takeover.phrase(plan)))

    def test_exact_five_pending_plan_two_updates_three_inserts(self):
        self.assertIsNone(self.plan['authorization']);self.assertEqual(len(self.plan['items']),5)
        self.assertEqual([p['decision'] for p in self.validate()],['UPDATE']*2+['INSERT']*3)
        for entry,item in zip(self.entries,self.plan['items']):
            self.assertEqual(item['route_sha256'],planner.route_hash(entry['input']['route']))
            self.assertEqual(item['observation_id'],entry['input']['facts'][0]['id'])
            self.assertTrue(item['disabled_projection_required'])

    def test_authorization_and_disabled_permission_are_explicit(self):
        for auth in ('',takeover.phrase(self.plan).replace(':ALLOW_DISABLED_ROUTE_PROJECTION','')):
            with self.assertRaises(ValueError):self.validate(auth=auth)
        plan=copy.deepcopy(self.plan);plan['items'][0]['disabled_projection_required']=False
        with self.assertRaises(ValueError):self.validate(plan=plan)

    def test_route_hash_and_physical_route_drift_block(self):
        plan=copy.deepcopy(self.plan);plan['items'][0]['route_sha256']='0'*64
        with self.assertRaises(ValueError):self.validate(plan=plan)
        for key,value in [('id','99999'),('route_revision','99'),('enabled','1')]:
            items=self.items();items[0]['route'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate(items)

    def test_database_current_and_observation_drift_block(self):
        for key,value in [('price','9.0000000000'),('updated_at','2026-01-01 00:00:03.000000')]:
            items=self.items();items[0]['current'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate(items)
        items=self.items();items[0]['facts'][0]['id']='99999'
        with self.assertRaises(ValueError):self.validate(items)

    def test_unqualified_observation_and_equal_time_conflicts_block(self):
        # Even a newly authorized plan cannot bypass existing fact safety checks.
        for field,value in [('observation_format_version','1'),('dedupe_key','0'*64),('quote_unit_key','GBP')]:
            items=self.items();items[0]['facts'][0][field]=value
            plan=copy.deepcopy(self.plan);plan['items'][0]['reference']['input']['facts']=copy.deepcopy(items[0]['facts'])
            with self.subTest(field=field),self.assertRaises(ValueError):self.validate(items,plan)
        items=self.items();bad=copy.deepcopy(items[0]['facts'][0]);bad['id']='99998';bad['price']='1.0000000000'
        payload={k:bad[k] for k in planner.CORE+planner.UNITS}
        import hashlib
        bad['dedupe_key']=hashlib.sha256(b'mosa2-observation-v2\n'+json.dumps(payload,separators=(',',':')).encode()).hexdigest()
        items[0]['facts'].append(bad);plan=copy.deepcopy(self.plan);plan['items'][0]['reference']['input']['facts']=copy.deepcopy(items[0]['facts'])
        with self.assertRaises(ValueError):self.validate(items,plan)

    def test_missing_duplicate_and_extra_scope_rejected(self):
        for items in (self.items()[:-1],self.items()+self.items()[:1],self.items()[:4]+self.items()[:1]):
            with self.assertRaises(ValueError):self.validate(items)

    def test_expired_plan_rejected(self):
        items=self.items();items[0]['now']='2026-01-03 00:00:00.000000'
        with self.assertRaises(ValueError):self.validate(items)

    def memory(self,fault=''):
        plans=self.validate()
        before=dict(m2_market_current=[copy.deepcopy(e['input']['current']) for e in self.entries if e['input']['current']],
            m2_market_observations=[dict(synthetic='unchanged')],m2_market_bars=[],m2_asset_source_routes=[dict(enabled='0')])
        p=subprocess.run(['php',str(ROOT/'tests/fixtures/current_takeover.php'),str(ROOT)],
            input=json.dumps(dict(before=before,plans=plans,fault=fault)),capture_output=True,text=True,check=True)
        self.assertEqual(p.stderr,'');return before,json.loads(p.stdout)

    def test_existing_writer_one_atomic_transaction_and_other_tables_unchanged(self):
        before,result=self.memory();self.assertTrue(result['ok']);self.assertEqual(result['writes'],5)
        self.assertEqual(result['events'],['LOCK','SET TRANSACTION ISOLATION LEVEL REPEATABLE READ','BEGIN','COMMIT','UNLOCK'])
        self.assertEqual(result['readback'],'PASS')
        for table in before:
            if table!='m2_market_current':self.assertEqual(result['state'][table],before[table])

    def test_locked_fresh_binding_and_existing_php_planner_bridge(self):
        p=subprocess.run(['php',str(ROOT/'tests/fixtures/current_preview.php'),str(ROOT)],
            input=json.dumps(dict(action='fresh',items=self.entries,now=CREATED)),capture_output=True,text=True,check=True)
        self.assertEqual(p.stderr,'');fresh=json.loads(p.stdout);self.assertTrue(fresh['unchanged'])
        self.assertTrue(all(q['sql'].endswith(' FOR UPDATE') for q in fresh['calls']))
        self.assertEqual(len(fresh['calls']),27)
        code=r'''require $argv[1];$in=json_decode(stream_get_contents(STDIN),true);echo json_encode(\Mosa2\MarketCurrent\plans($in['config'],$in['items'],$in['takeover']));'''
        request=dict(config=dict(python=__import__('sys').executable,project=str(ROOT),runtime_path=os.environ['PATH']),
            items=fresh['items'],takeover=dict(plan=self.plan,authorization=takeover.phrase(self.plan)))
        p=subprocess.run(['php','-r',code,str(ROOT/'scripts/market_current/refresh.php')],
            input=json.dumps(request),capture_output=True,text=True,check=True)
        self.assertEqual(p.stderr,'');self.assertEqual([x['decision'] for x in json.loads(p.stdout)],['UPDATE']*2+['INSERT']*3)

    def test_write_failure_rolls_back_every_change(self):
        before,result=self.memory('write');self.assertFalse(result['ok']);self.assertEqual(result['state'],before)
        self.assertIn('ROLLBACK',result['events']);self.assertNotIn('COMMIT',result['events'])

    def test_failed_transaction_start_never_writes(self):
        before,result=self.memory('begin');self.assertFalse(result['ok']);self.assertEqual(result['writes'],0)
        self.assertEqual(result['state'],before);self.assertNotIn('COMMIT',result['events'])

    def test_commit_or_rowcount_failure_rolls_back_every_change(self):
        for fault in ('commit','rowcount'):
            before,result=self.memory(fault)
            with self.subTest(fault=fault):
                self.assertFalse(result['ok']);self.assertEqual(result['state'],before);self.assertIn('ROLLBACK',result['events'])

    def test_other_table_delta_blocks_and_rolls_back(self):
        before,result=self.memory('other');self.assertFalse(result['ok']);self.assertEqual(result['state'],before)
        self.assertIn('ROLLBACK',result['events'])

    def test_failed_independent_readback_is_post_commit_failure(self):
        before,result=self.memory('readback');self.assertFalse(result['ok']);self.assertIn('COMMIT',result['events'])
        self.assertNotIn('ROLLBACK',result['events']);self.assertNotEqual(result['state'],before)

    def test_replay_is_unchanged_and_second_apply_fails_before_writes(self):
        items=self.items();plans=self.validate(items)
        for data,plan in zip(items,plans):
            data['current']=plan['values'];data['current_fact']=data['facts'][0]
            data['approval']=dict(route_sha256=planner.route_hash(data['route']),approved_at=CREATED,allow_disabled_projection=True)
            self.assertEqual(planner.plan(data)['decision'],'UNCHANGED')
        with self.assertRaises(ValueError):self.validate(items)

    def test_attempt_claim_blocks_repeated_or_missing_claim(self):
        from scripts import current_takeover_remote as remote
        env=dict(TAKEOVER_PLAN_SOURCE_RUN='12345',GITHUB_RUN_ID='67890')
        for claims in ([],[dict(workflow_run=dict(id=100),expired=False)]):
            with patch.object(remote,'api',return_value=json.dumps(dict(artifacts=claims)).encode()),self.assertRaises(ValueError):remote.no_previous_claim(env)
        with patch.object(remote,'api',return_value=json.dumps(dict(artifacts=[dict(workflow_run=dict(id=67890),expired=False)])).encode()):remote.no_previous_claim(env)

    def test_encrypted_evidence_both_existing_secret_and_recipient_roundtrip(self):
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        private=rsa.generate_private_key(public_exponent=65537,key_size=3072)
        public=sealed.b64(private.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo))
        envelope=sealed.seal(self.plan,public,'synthetic-existing-secret')
        self.assertEqual(sealed.open_plan(envelope,password='synthetic-existing-secret'),self.plan)
        self.assertEqual(sealed.open_plan(envelope,private_key=private),self.plan)
        encoded=json.dumps(envelope)
        for value in ('123.4500000000','scope_rows','observation_id','synthetic-existing-secret'):self.assertNotIn(value,encoded)
        envelope['ciphertext']=envelope['ciphertext'][:-4]+'AAAA'
        with self.assertRaises(Exception):sealed.open_plan(envelope,private_key=private)

    def test_lock_prepare_accepts_only_exact_readonly_barrier_and_keeps_proof(self):
        code=r'''require $argv[1];
        class LockScalar extends PDOStatement {public function __construct(private string $v){}public function fetchColumn(int $column=0):mixed{return $this->v;}}
        class LockProof extends PDO {
            public function __construct(private string $fault){}
            public function inTransaction():bool{return $this->fault!=='inactive';}
            public function query(string $q,?int $m=null,mixed ...$args):PDOStatement|false{return new LockScalar($this->fault==='state'?'0':'1');}
            public function prepare(string $q,array $options=[]):PDOStatement|false {
                if($this->fault==='prepared')return new LockScalar('1');
                $e=new PDOException('private SQL password data');$e->errorInfo=$this->fault==='syntax'?['42000',1064,'private']:['25006',1792,'private'];throw $e;
            }
        }
        try{echo \Mosa2\CurrentTakeover\lockQueryReadOnlyProof(new LockProof($argv[2]));}catch(Throwable){echo 'REJECTED';}'''
        for fault,expected in [('readonly','READONLY_LOCK_QUERY_REJECTION_CONFIRMED'),('prepared','LOCK_QUERY_NATIVE_PREPARE_CONFIRMED'),
                ('syntax','REJECTED'),('state','REJECTED'),('inactive','REJECTED')]:
            p=subprocess.run(['php','-r',code,str(ROOT/'scripts/market_current/takeover.php'),fault],capture_output=True,text=True,check=True)
            self.assertEqual(p.stderr,'');self.assertEqual(p.stdout,expected)

    def test_preparation_does_not_call_current_refresh(self):
        code=(ROOT/'scripts/current_takeover_remote.py').read_text()
        prep=code[code.index('def prepare('):code.index('def api(')]
        self.assertNotIn("'apply'",prep);self.assertIn("'readiness'",prep)
        php=(ROOT/'scripts/market_current/takeover.php').read_text()
        ready=php[php.index('function readiness('):php.index("if(PHP_SAPI")]
        for forbidden in ('INSERT ','UPDATE ','DELETE ','GET_LOCK'):self.assertNotIn(forbidden,ready)

if __name__=='__main__':unittest.main()
