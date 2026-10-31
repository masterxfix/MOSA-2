"""Schema6 opt-in, exact parser, locked acquisition and closed release dependencies; offline."""
import hashlib,json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from scripts import collector_release as r
from scripts import collector_migration5 as m
import test_fundamentals_schema as fund
ROOT=m.ROOT

class Schema6Tests(unittest.TestCase):
    def php(self,body):
        p=subprocess.run(['php','-r',"require 'scripts/market_collector/schema6.php';"+body],
            cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr);self.assertEqual(p.stderr,'');return json.loads(p.stdout)
    def test_exact_26_table_structure_matches_previously_qualified_0006(self):
        schema=self.php(r'echo json_encode(\Mosa2\CollectorSchema6\schemas());')
        self.assertEqual(len(schema),26)
        for name in fund.NEW:
            actual=schema[name];expected=fund.AFTER[name]
            self.assertEqual(list(actual['columns']),list(expected['columns']))
            for field,(typ,nullable,collation,auto,default) in expected['columns'].items():
                text=typ.startswith(('VARCHAR','CHAR'))
                self.assertEqual(actual['columns'][field],dict(type=typ.lower(),nullable='YES' if nullable else 'NO',
                    extra='auto_increment' if auto else '',collation=(collation or 'utf8mb4_0900_ai_ci') if text else None,
                    charset='utf8mb4' if text else None,default=default),(name,field))
            self.assertEqual(actual['indexes'],{k:dict(columns=list(cols),unique=unique) for k,(cols,unique) in expected['indexes'].items()}|
                {'PRIMARY':dict(columns=list(expected['pk']),unique=True)})
            self.assertEqual(actual['fks'] or {},{k:dict(columns=list(cols),table=parent,targets=list(target),delete=rule) for k,(cols,parent,target,rule) in expected['fks'].items()})
            self.assertEqual(actual['checks'],expected['checks'])
    def test_explicit_selection_old_envelopes_and_closed_acquisition(self):
        result=self.php(r"""
        $out=['default'=>\Mosa2\MarketCurrent\stateContract([]),'selected'=>\Mosa2\MarketCurrent\stateContract(['state_contract'=>['schema_version'=>6]]),'counts'=>[]];
        foreach([3,4,5,6] as $v)$out['counts'][]=count(\Mosa2\CollectorSchema5\envelope($v)['tables']);
        $out['blocked']=[];foreach([5,6,7,'6',null] as $v){try{\Mosa2\CollectorSchema5\acquisitionAllowed(['schema_version'=>$v]);$out['blocked'][]=false;}catch(Throwable){$out['blocked'][]=true;}}
        $out['invalid']=[];foreach(['6',true,7] as $v){try{\Mosa2\CollectorSchema5\selected(['state_contract'=>['schema_version'=>$v]]);$out['invalid'][]=false;}catch(Throwable){$out['invalid'][]=true;}}
        echo json_encode($out);
        """)
        self.assertEqual(result['default'],dict(schema_version=4,allow_current=True))
        self.assertEqual(result['selected'],dict(schema_version=6,allow_current=True))
        self.assertEqual(result['counts'],[17,17,21,26])
        self.assertEqual(result['blocked'],[True,True,True,True,False])
        self.assertTrue(all(result['invalid']))
    def test_old_contracts_and_six_original_migrations_unchanged(self):
        result=self.php(r'echo json_encode(\Mosa2\CollectorSchema5\envelope(6));')
        self.assertEqual(result['versions'],list('123456'));self.assertEqual(len(result['digests']),6)
        expected=dict(fund.OLD);expected[fund.PATH.name]='55457063c72d20498a097d273b5465d34cfd8aba5b2c7c229a9673bfc0c4a60c'
        self.assertEqual(result['digests'],list(expected.values()))
        for name,digest in expected.items():self.assertEqual(hashlib.sha256((fund.MIGRATIONS/name).read_bytes()).hexdigest(),digest)
    def test_schema6_release_closed_dependencies_and_materialized_runtime(self):
        # Offline object map; real Git-commit build/verify runs once on Linux.
        paths=[x['path'] for x in json.loads((ROOT/r.SCHEMA6_CONTRACT).read_text())['files']]
        all_paths=paths+[r.SCHEMA6_CONTRACT,r.CONTRACT]
        raw={p:(ROOT/p).read_bytes() for p in all_paths}
        objects={p:('100644','blob',hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()) for p,b in raw.items()}
        with patch.object(r,'repository',return_value=(objects,raw.__getitem__)):
            archive,manifest=r.build(ROOT,'a'*40,'schema6')
            self.assertEqual((archive,manifest),r.build(ROOT,'a'*40,'schema6'))
            meta=r.verify(ROOT,'a'*40,archive,manifest,'schema6')
            with self.assertRaises(ValueError):r.verify(ROOT,'a'*40,archive,manifest.replace(b'a'*40,b'b'*40),'schema6')
        self.assertEqual(len(meta['files']),len(paths))
        self.assertFalse(any('remote' in p or p.startswith('tests/') for p in paths))
        import io,tarfile
        with tempfile.TemporaryDirectory() as tmp:
            with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
                for member in bundle:
                    target=Path(tmp)/member.name;target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(bundle.extractfile(member).read())
            p=subprocess.run(['php','-r',r"require $argv[1]; echo count(\Mosa2\CollectorSchema6\schemas());",str(Path(tmp)/'scripts/market_collector/schema6.php')],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr);self.assertEqual(p.stdout,'26');self.assertEqual(p.stderr,'')
        legacy=json.loads((ROOT/r.CONTRACT).read_text());self.assertEqual(len(legacy['files']),33)
if __name__=='__main__':unittest.main()
