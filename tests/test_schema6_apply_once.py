"""Offline failure injection for the one authorized path; no DB or provider."""
import json
import subprocess
import unittest
from scripts import schema6_apply_once as a

class OnceTests(unittest.TestCase):
    def env(self):
        sha = 'a' * 40
        return dict(GITHUB_REPOSITORY='masterxfix/MOSA-2', GITHUB_REF='refs/heads/main',
                    GITHUB_EVENT_NAME='workflow_dispatch', GITHUB_RUN_ATTEMPT='1', GITHUB_RUN_NUMBER='1',
                    EXECUTION_ID=a.EXECUTION, GITHUB_SHA=sha, EXPECTED_COMMIT=sha,
                    AUTHORIZATION=a.EXECUTION + ':' + sha, GITHUB_RUN_ID='123')

    def test_binding_and_replay_guards(self):
        env = self.env()
        a.guard(env)
        for field in env:
            if field == 'GITHUB_RUN_ID':
                continue
            with self.subTest(field=field), self.assertRaises(ValueError):
                a.guard(env | {field: 'other'})

    def test_other_actions_fail_closed(self):
        a.no_other_runs(self.env(), lambda status: dict(total_count=1, workflow_runs=[dict(id=123)]))
        for result in (dict(total_count=101, workflow_runs=[]), dict(total_count=1, workflow_runs=[dict(id=999)])):
            with self.assertRaises(ValueError):
                a.no_other_runs(self.env(), lambda status: result)

    def php(self, body):
        p = subprocess.run(['php', '-r', "require 'scripts/schema6_apply.php';" + body],
                           cwd=a.ROOT, text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(p.stderr, '')
        return json.loads(p.stdout)

    def test_all_ddl_and_commit_failures_stop_without_retry(self):
        result = self.php(r'''
        class S extends PDOStatement {
            public function __construct(){}
            public function execute(?array $params=null):bool{return true;}
        }
        class P extends PDO {
            public array $sql=[];public int $commits=0;public int $begins=0;
            public function __construct(public int $failExec=0,public int $failCommit=0){}
            public function exec(string $sql):int|false{
                $this->sql[]=$sql;if(count($this->sql)===$this->failExec)throw new RuntimeException('injected');return 1;
            }
            public function prepare(string $query,array $options=[]):PDOStatement|false{return new S();}
            public function beginTransaction():bool{$this->begins++;return true;}
            public function commit():bool{$this->commits++;if($this->commits===$this->failCommit)throw new RuntimeException('unknown');return true;}
        }
        $schema=\Mosa2\CollectorSchema6\schemas();$out=[];
        foreach(array_merge([[0,0]],array_map(fn($i)=>[$i,0],range(1,13)),[[0,1],[0,2]]) as [$e,$c]){
            $p=new P($e,$c);$events=[];$checks=[];$ok=false;
            try{\Mosa2\Schema6Apply\migrate($p,$schema,
                function($v)use(&$checks){$checks[]=$v;},function($s)use(&$events){$events[]=$s;});$ok=true;}catch(Throwable){}
            $out[]=['ok'=>$ok,'exec'=>count($p->sql),'commits'=>$p->commits,'checks'=>$checks,'events'=>$events,
                'creates'=>count(array_filter($p->sql,fn($s)=>str_starts_with($s,'CREATE TABLE')))];
        }echo json_encode($out);
        ''')
        self.assertTrue(result[0]['ok'])
        self.assertEqual(result[0]['exec'], 13)
        self.assertEqual(result[0]['creates'], 9)
        self.assertEqual(result[0]['checks'], [5, 0, 6])
        for i, entry in enumerate(result[1:14], 1):
            self.assertFalse(entry['ok'])
            self.assertEqual(entry['exec'], i)
            self.assertNotIn('SCHEMA6_PASS', entry['events'])
        self.assertEqual(result[14]['exec'], 8)
        self.assertEqual(result[14]['commits'], 1)
        self.assertNotIn('BOOTSTRAP5_CONFIRMED', result[14]['events'])
        self.assertEqual(result[15]['commits'], 2)
        self.assertNotIn('LEDGER6_CONFIRMED', result[15]['events'])

    def test_metadata_rejection_prevents_later_steps(self):
        result = self.php(r'''
        class S extends PDOStatement {public function __construct(){}public function execute(?array $params=null):bool{return true;}}
        class P extends PDO {
            public int $n=0;public int $commits=0;public function __construct(){}
            public function exec(string $sql):int|false{$this->n++;return 1;}
            public function prepare(string $query,array $options=[]):PDOStatement|false{return new S();}
            public function beginTransaction():bool{return true;}
            public function commit():bool{$this->commits++;return true;}
        }
        $schema=\Mosa2\CollectorSchema6\schemas();$out=[];
        foreach([5,0,6] as $fail){$p=new P();$events=[];
            try{\Mosa2\Schema6Apply\migrate($p,$schema,function($v)use($fail){if($v===$fail)throw new RuntimeException();},function($v)use(&$events){$events[]=$v;});}catch(Throwable){}
            $out[]=[$p->n,$p->commits,in_array('SCHEMA6_PASS',$events)];}
        echo json_encode($out);
        ''')
        self.assertEqual(result, [[8, 1, False], [13, 1, False], [13, 2, False]])

    def test_input_fails_before_connection(self):
        p = subprocess.run(['php', 'scripts/schema6_apply.php'], input='{}', cwd=a.ROOT,
                           text=True, capture_output=True)
        self.assertEqual(p.returncode, 1)
        self.assertEqual(json.loads(p.stdout), dict(stage='STOP', at='INPUT', outcome='NO_SCHEMA_WRITES'))
        self.assertEqual(p.stderr, '')

    def test_fingerprints_detect_binary_null_and_value_drift(self):
        result = self.php(r'''
        class S extends PDOStatement {
            public function __construct(public array $rows){}
            public function fetchAll(int $mode=PDO::FETCH_DEFAULT,mixed ...$args):array{return $this->rows;}
        }
        class P extends PDO {
            public function __construct(public int $variant){}
            public function query(string $sql,?int $fetchMode=null,mixed ...$args):PDOStatement|false{
                $rows=[];
                if(str_contains($sql,'`m2_market_current`'))$rows=array_fill(0,5,['value'=>'1.2300','binary'=>"\x00\xff",'optional'=>null]);
                if(str_contains($sql,'`m2_market_observations`'))$rows=array_fill(0,28,['value'=>'1.2300']);
                if($rows&&$this->variant===1)$rows[0]['value']='1.2301';
                if($rows&&$this->variant===2)$rows[0]['optional']='';
                if($rows&&$this->variant===3)$rows[0]['binary']="\x00\xfe";
                if($rows&&$this->variant===4)$rows=array_fill(0,129,[]);
                return new S($rows);
            }
        }
        $baseline=\Mosa2\Schema6Apply\fingerprints(new P(0));$out=[];
        foreach([1,2,3] as $v)$out[]=\Mosa2\Schema6Apply\fingerprints(new P($v))!==$baseline;
        try{\Mosa2\Schema6Apply\fingerprints(new P(4));$out[]=false;}catch(Throwable){$out[]=true;}
        $out[]=\Mosa2\Schema6Apply\fingerprints(new P(0),true)===$baseline;
        echo json_encode($out);
        ''')
        self.assertEqual(result, [True] * 5)

    def test_output_and_original_artifacts(self):
        self.assertEqual(a.validated_output('{"stage":"DDL5_1_START"}\n')[0]['stage'], 'DDL5_1_START')
        with self.assertRaises(ValueError):
            a.validated_output('{"stage":"PRIVATE_SECRET"}')
        result = self.php(r'echo json_encode(\Mosa2\CollectorSchema5\envelope(6));')
        self.assertEqual(len(result['tables']), 26)
        self.assertEqual(result['versions'], list('123456'))

if __name__ == '__main__':
    unittest.main()
