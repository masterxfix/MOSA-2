"""New candidate and unchanged historical contract; no remote or provider capability."""
import copy, hashlib, io, json, os, socket, subprocess, sys, tarfile, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from scripts import collector_release as r
import test_market_current as current_fixtures

ROOT=Path(__file__).resolve().parents[1]
HISTORICAL='6fa0655088f5ae2b37b7043b10a568d4aa2f14fb'

class Schema5ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.commit=r.git(ROOT,'rev-parse','HEAD').decode().strip()
        cls.archive,cls.manifest=r.build(ROOT,cls.commit,'schema5')
        cls.metadata=r.verify(ROOT,cls.commit,cls.archive,cls.manifest,'schema5')
    def test_reproducible_and_fully_pinned_disabled_candidate(self):
        self.assertEqual((self.archive,self.manifest),r.build(ROOT,self.commit,'schema5'))
        contract=json.loads((ROOT/r.SCHEMA5_CONTRACT).read_text(encoding='utf-8'))
        self.assertEqual(len(self.metadata['files']),len(contract['files']))
        self.assertTrue(all(x['source_blob'] for x in contract['files']))
        self.assertEqual(contract['candidate'],dict(schema_versions=[4,5],default_schema=4,execution_enabled=False,upload_enabled=False))
        self.assertEqual(contract['entrypoints'],json.loads((ROOT/r.CONTRACT).read_text())['entrypoints'])
        required={'scripts/market_collector/schema_contract.php','scripts/market_current/refresh.php','scripts/market_current/planner.py',
            'scripts/market_current/selection.php','api/market_core/selection.php','api/market_core/values.php','api/market_core/primitives.php',
            'api/market_core/units.json','docs/database/migrations/0005_collector_reservations.sql'}
        self.assertTrue(required<={x['path'] for x in self.metadata['files']})
    def test_historical_contract_is_byte_identical_and_cannot_be_replaced_by_candidate(self):
        self.assertEqual((ROOT/r.CONTRACT).read_bytes(),r.git(ROOT,'show',HISTORICAL+':'+r.CONTRACT))
        self.assertEqual(len(json.loads((ROOT/r.CONTRACT).read_text())['files']),33)
        with self.assertRaises(ValueError):r.verify(ROOT,self.commit,self.archive,self.manifest)
        # Its qualified source pins intentionally reject today's changed modules.
        with self.assertRaises(ValueError):r.build(ROOT,self.commit)
    def rewrite(self,change):
        out=io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(self.archive),mode='r:') as source,tarfile.open(fileobj=out,mode='w',format=tarfile.USTAR_FORMAT) as target:
            for i,item in enumerate(source):
                raw=source.extractfile(item).read();edited=change(i,item,raw)
                if edited:
                    item,raw=edited;target.addfile(item,io.BytesIO(raw) if item.isfile() else None)
        return out.getvalue()
    def test_missing_corrupt_foreign_symlink_and_forged_commit_rejected(self):
        def foreign(i,item,raw):
            if i==0:item.name='foreign.php'
            return item,raw
        def link(i,item,raw):
            if i==0:item.type=tarfile.SYMTYPE;item.linkname='target'
            return item,raw
        for change in [lambda i,item,raw:None if i==0 else (item,raw),
            lambda i,item,raw:(item,bytes([raw[0]^1])+raw[1:]) if i==0 else (item,raw),foreign,link]:
            with self.assertRaises(ValueError):r.verify(ROOT,self.commit,self.rewrite(change),self.manifest,'schema5')
        for key,value in [('commit','a'*40),('contract_sha256','0'*64),('unknown',True)]:
            meta=copy.deepcopy(self.metadata);meta[key]=value
            with self.assertRaises(ValueError):r.verify(ROOT,self.commit,self.archive,r.canonical(meta),'schema5')
    def test_removed_or_unrecorded_dependency_blocks_build(self):
        objects,read=r.repository(ROOT,self.commit)
        original=read(r.SCHEMA5_CONTRACT)
        for change in ('remove','edge','source'):
            c=json.loads(original)
            if change=='remove':c['files']=[x for x in c['files'] if x['path']!='scripts/market_collector/schema_contract.php']
            elif change=='edge':
                row=next(x for x in c['files'] if x['path']=='scripts/market_collector/live_persistence.php')
                row['requires'].remove('scripts/market_collector/schema_contract.php')
            else:c['files'][0]['source_blob']='0'*40
            def fake(path):return r.canonical(c) if path==r.SCHEMA5_CONTRACT else read(path)
            with patch.object(r,'repository',return_value=(objects,fake)),self.assertRaises(ValueError):r.build(ROOT,self.commit,'schema5')
    def test_no_secrets_provider_or_remote_files_and_no_configuration_activation(self):
        sentinel='SYNTHETIC-SECRET-DO-NOT-PACKAGE'
        with patch.dict(os.environ,{'MOSA_TEST_DB_PASSWORD':sentinel}),patch.object(socket,'socket',side_effect=AssertionError('network forbidden')):
            archive,manifest=r.build(ROOT,self.commit,'schema5')
        self.assertNotIn(sentinel.encode(),archive+manifest)
        names={x['path'] for x in self.metadata['files']}
        self.assertFalse(any('deploy' in p or 'remote' in p or 'tests/' in p for p in names))
        for p in ['config/collector-operation.json','config/collector-provider-budget.json']:
            c=json.loads((ROOT/p).read_text());self.assertFalse(c['execution_enabled'])
        c=json.loads((ROOT/'config/collector-provider-budget.json').read_text())
        self.assertFalse(any(p['rights_confirmed'] for p in c['providers'].values()))
    def test_materialized_candidate_php_and_real_stored_fact_planner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'candidate';root.mkdir(mode=0o700)
            with tarfile.open(fileobj=io.BytesIO(self.archive),mode='r:') as bundle:
                for member in bundle:
                    dest=root/member.name;dest.parent.mkdir(parents=True,exist_ok=True)
                    dest.write_bytes(bundle.extractfile(member).read());dest.chmod(0o600)
            for module in ('scripts/market_current/refresh.php','scripts/collector_release/runtime.php'):
                code='require $argv[1]; echo json_encode(\\Mosa2\\MarketCurrent\\stateContract([]));' if 'refresh' in module else 'require $argv[1]; echo "OK";'
                p=subprocess.run(['php','-r',code,str(root/module)],capture_output=True,text=True,check=True)
                self.assertEqual(p.stderr,'')
            f=current_fixtures.CurrentTests();f.setUp();f.previous()
            p=subprocess.run([sys.executable,'-B',str(root/'scripts/market_current/planner.py')],
                input=json.dumps(dict(items=[f.data])),capture_output=True,text=True,check=True)
            self.assertEqual(p.stderr,'');self.assertEqual(json.loads(p.stdout)['plans'][0]['decision'],'UNCHANGED')

class SelectionTests(unittest.TestCase):
    def php(self,value):
        code='require $argv[1];try{echo json_encode(\\Mosa2\\MarketCurrent\\stateContract(json_decode($argv[2],true)));}catch(Throwable $e){echo $e->getMessage();}'
        p=subprocess.run(['php','-r',code,str(ROOT/'scripts/market_current/refresh.php'),json.dumps(value)],capture_output=True,text=True,check=True)
        self.assertEqual(p.stderr,'');return p.stdout
    def test_default4_explicit5_and_no_fallback(self):
        self.assertEqual(json.loads(self.php({})),dict(schema_version=4,allow_current=True))
        self.assertEqual(json.loads(self.php(dict(state_contract=dict(schema_version=5)))),dict(schema_version=5,allow_current=True))
        for value in (None,3,6,'5',True):
            self.assertEqual(self.php(dict(state_contract=dict(schema_version=value))),'schema_contract')
    def test_consumed_historical_authorization_is_still_permanently_blocked(self):
        from scripts.market_current.takeover import CONSUMED_RUN_IDS
        self.assertIn('current-once-39634298612',CONSUMED_RUN_IDS)

if __name__=='__main__':unittest.main()
