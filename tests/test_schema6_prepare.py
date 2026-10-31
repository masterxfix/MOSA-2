"""Focused offline guards for the one readonly Dogado preparation; no network/DB."""
import json,subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class PrepareTests(unittest.TestCase):
    def php(self,body):
        p=subprocess.run(['php','-r',"require 'scripts/market_collector/schema6_prepare.php';"+body],cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(p.returncode,0,p.stderr);return json.loads(p.stdout)
    def test_exact_historical_schema_and_real_ledger_hashes(self):
        r=self.php(r"""
        $files=glob('docs/database/migrations/000[1-4]_*.sql');sort($files);$rows=[];
        foreach($files as $i=>$f)$rows[]=['version'=>(string)($i+1),'migration_key'=>basename($f,'.sql'),'checksum'=>hash_file('sha256',$f)];
        \Mosa2\Schema6Prepare\ledger($rows,getcwd());$rejected=0;
        foreach(['version','migration_key','checksum'] as $k){$bad=$rows;$bad[0][$k]='WRONG';
            try{\Mosa2\Schema6Prepare\ledger($bad,getcwd());}catch(Throwable){$rejected++;}}
        $bad=$rows;$bad[]=$rows[0];try{\Mosa2\Schema6Prepare\ledger($bad,getcwd());}catch(Throwable){$rejected++;}
        $blocked=0;foreach([4,5] as $v){if(count(\Mosa2\CollectorSchema5\envelope($v)['tables'])!==26)$blocked++;}
        try{\Mosa2\CollectorSchema5\selected(['state_contract'=>['schema_version'=>6]]);}catch(Throwable){$blocked++;}
        echo json_encode([$rejected,$blocked]);
        """);self.assertEqual(r,[4,3])
    def test_empty_process_list_never_proves_quiescence_or_permits_export(self):
        r=self.php(r"""
        echo json_encode(\Mosa2\Schema6Prepare\exportGate(
            ['complete_object_visibility'=>'JA','objects'=>['ROUTINE'=>['visible_count'=>0]]],
            ['SELECT'=>true,'SHOW VIEW'=>true,'TRIGGER'=>true,'EVENT'=>true],[]));
        """)
        self.assertEqual(r['status'],'BLOCKED_BEFORE_EXPORT');self.assertEqual(r['exports'],0)
        self.assertIn('WRITE_DDL_QUIESCENCE_NOT_PROVEN',r['blockers'])
        self.assertEqual(r['writer_visibility'],'CURRENT_ACCOUNT_ONLY')
    def test_incomplete_visibility_routines_and_sessions_block(self):
        r=self.php(r"""
        echo json_encode(\Mosa2\Schema6Prepare\exportGate(
            ['complete_object_visibility'=>'NICHT NACHWEISBAR','objects'=>['ROUTINE'=>['visible_count'=>1]]],[],[['COMMAND'=>'Query']]));
        """)
        for code in ['OBJECT_VISIBILITY_NOT_PROVEN','ROUTINES_UNSUPPORTED','OTHER_TEST_DATABASE_SESSIONS_VISIBLE','EXPORT_SCHEMA_RIGHT_MISSING']:
            self.assertIn(code,r['blockers'])
    def test_no_private_values_in_public_evidence_and_mismatch_rejected(self):
        r=self.php(r"""
        $item=['status'=>'stale','price'=>'SECRET_DECIMAL','currency'=>'EUR','market_at'=>'market','observed_at'=>'observed'];
        $published=[];$obs=[];for($i=0;$i<5;$i++){
            $route=['display_name'=>'Synthetic '.$i,'isin'=>'SYNTHETIC'.$i,'enabled'=>'0','source_key'=>\Mosa2\TradegateQuote\SOURCE_VALUES['source_key']];
            $published[]=['route'=>$route,'item'=>$item];$obs[]=$item+['isin'=>$route['isin']];}
        $result=\Mosa2\Schema6Prepare\publications($published,$obs);$bad=$obs;$bad[0]['price']='DIFFERENT';
        try{\Mosa2\Schema6Prepare\publications($published,$bad);$blocked=false;}catch(Throwable){$blocked=true;}
        echo json_encode(['safe'=>!str_contains(json_encode($result),'SECRET_DECIMAL'),'blocked'=>$blocked,'n'=>count($result)]);
        """)
        self.assertEqual(r,dict(safe=True,blocked=True,n=5))
    def test_readonly_and_scope_guards_remain_before_inventory(self):
        p=(ROOT/'scripts/backup_permissions.php').read_text()
        self.assertLess(p.index("SELECT @@session.transaction_read_only"),p.index('Schema6Prepare\\inspect'))
        h=(ROOT/'scripts/market_collector/schema6_prepare.php').read_text()
        self.assertIn('WHERE DB=DATABASE() AND ID<>CONNECTION_ID()',h)
        self.assertNotIn('FLUSH TABLES',h);self.assertNotIn('FOR UPDATE',h)
        self.assertNotIn('GET_LOCK(',h)
        self.assertIn("ini_set('display_errors','0')",p)
    def test_remote_secret_only_in_stdin_and_no_retry(self):
        import sys
        sys.path.insert(0,str(ROOT/'scripts'))
        import backup_permissions_remote as remote
        self.assertEqual(remote.execute({'GITHUB_RUN_ATTEMPT':'2'},None),{'status':'FIRST_ATTEMPT_ONLY'})
        source=(ROOT/'scripts/backup_permissions_remote.py').read_text()
        self.assertIn('input=json.dumps(request)',source)
        self.assertNotIn("child.update",source)
        self.assertNotIn("mysqldump --",source)
if __name__=='__main__':unittest.main()
