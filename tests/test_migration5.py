"""No database access: PREPARE boundaries, frozen artifacts and exact expression checks."""
import hashlib,json,subprocess,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from scripts import collector_migration5 as m,collector_migration5_remote as remote
ROOT=m.ROOT
class Migration5Tests(unittest.TestCase):
    def test_bounded_compressed_metadata_integrity_and_unknown_encoding(self):
        import gzip,base64
        raw=b'{"synthetic":true}'
        e=dict(encoding='gzip-base64-v1',payload=base64.b64encode(gzip.compress(raw)).decode(),sha256=hashlib.sha256(raw).hexdigest(),length=len(raw))
        self.assertEqual(m.unpack(e),dict(synthetic=True))
        for change in (dict(length=2000001),dict(sha256='0'*64),dict(payload='invalid'),dict(encoding='unknown')):
            with self.assertRaises(Exception):m.unpack(e|change)
    def test_current_baseline_binds_facts_but_not_inspection_clock(self):
        import copy
        entry=dict(isin='SYNTHETIC',scope_rows=[{'route_id':'1'}],input=dict(now='old',approval=None,current={'price':'2.0000000000'}))
        a=dict(items=[entry]);b=copy.deepcopy(a);b['items'][0]['input']['now']='new'
        self.assertEqual(m.digest(m.current_binding(a)),m.digest(m.current_binding(b)))
        b['items'][0]['input']['current']['price']='3.0000000000'
        self.assertNotEqual(m.digest(m.current_binding(a)),m.digest(m.current_binding(b)))
    def test_unchanged_migrations_and_explicit_contracts(self):
        c=m.contract();self.assertEqual(len(c['statements']),8)
        self.assertEqual(set(c['envelope5']['tables'])-set(c['envelope4']['tables']),set(m.TABLES))
        self.assertEqual(c['envelope4']['versions'],['1','2','3','4']);self.assertEqual(c['envelope5']['versions'],['1','2','3','4','5'])
        self.assertEqual(c['envelope4']['digests'],c['envelope5']['digests'][:4])
        for i,digest in enumerate(c['envelope5']['digests'],1):
            p=next((ROOT/'docs/database/migrations').glob(f'{i:04d}_*.sql'));self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),digest)
    def test_preserves_existing_tables_and_all_old_column_contracts(self):
        c=m.contract()
        for name,table in c['schemas4'].items():self.assertEqual(table,c['schemas5'][name])
        new=[c['schemas5'][t] for t in m.TABLES]
        self.assertEqual(sum(len(t['fks']) for t in new),9)
        self.assertEqual(sum(sum(x['unique'] for x in t['indexes'].values()) for t in new),7)
    def test_no_apply_or_unsafe_recovery_in_prepare(self):
        for file in ('scripts/collector_migration5.py','scripts/collector_migration5_remote.py','scripts/market_collector/migration5_capture.php'):
            source=(ROOT/file).read_text(encoding='utf8')
            for text in ('DROP TABLE','DROP DATABASE','MOSA_TEST_DB_PASSWORD','CREATE USER','writer_call('):self.assertNotIn(text,source)
        self.assertIn("const CONTRACT=['schema_version'=>4",(ROOT/'scripts/market_current/refresh.php').read_text())
    def test_callback_reuses_exactly_one_existing_read_only_reader(self):
        with patch.object(remote.historical,'original_plan',side_effect=ValueError),patch.object(remote.reader,'execute',return_value={}) as read:
            remote.execute({'GITHUB_RUN_ATTEMPT':'1'},Mock())
        self.assertEqual(read.call_count,1);self.assertEqual(read.call_args.kwargs['bundle_script'].name,'collector_migration5_bundle.php')
        with patch.object(remote.reader,'execute') as read:remote.execute({'GITHUB_RUN_ATTEMPT':'2'},Mock())
        read.assert_not_called()
    def test_missing_corrupt_or_unknown_metadata_blocks(self):
        for value in ({},{'inventory':[]},{'inventory':[{'sql':'secret','args':[],'rows':[]}]}):
            self.assertEqual(m.assess(value)['status'],'UNKNOWN_OR_DRIFT')
        with self.assertRaises(ValueError):m.prepare({},'a'*40,'synthetic',{})
    def test_partial_table_anchor_ledger_masks_never_resume(self):
        c=m.contract()
        for count in range(1,5):
            names=sorted(c['envelope4']['tables']+m.TABLES[:count])
            data=dict(inventory=[dict(sql='SELECT TABLE_NAME FROM information_schema.tables WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME',args=[],rows=[{'TABLE_NAME':n} for n in names])],jobs=[],modules=[],collector={},ledger=[],properties=dict(db='h29077_mosa2_test',version='8.0.26',fk_checks='1'))
            r=m.assess(data);self.assertFalse(r['apply_allowed']);self.assertEqual(r['status'],'PARTIAL_OR_CONFLICT')
    def test_new_check_syntax_remains_exact_and_rejects_drift(self):
        code=r'''require $argv[1];$a="JSON_TYPE(selection_json) = 'ARRAY' AND JSON_LENGTH(selection_json) = 5";$b="(json_type(`selection_json`) = 'ARRAY') AND (json_length(`selection_json`) = 5)";
        $parse=fn($s)=>\Mosa2\Phase2\canonicalCheckTree((new \Mosa2\Phase2\CheckExpression($s))->parse());
        echo json_encode([$parse($a)===$parse($b),$parse($a)!==$parse(str_replace('= 5','= 4',$b)),$parse('ordinal_no BETWEEN 1 AND 5')!==$parse('ordinal_no BETWEEN 1 AND 6')]);'''
        p=subprocess.run(['php','-r',code,str(ROOT/'scripts/phase2/postcheck.php')],capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(p.stdout),[True]*3)
if __name__=='__main__':unittest.main()
