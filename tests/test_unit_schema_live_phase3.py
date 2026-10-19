"""Database-free checks of the production Phase-3K parser, guards and DDL order."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_core_schema_phase2 import ROOT, split_sql
from market_units_schema_fixture import parse_schema

MODULE = ROOT / 'scripts/phase3k/live_apply.php'
GATEWAY = ROOT / 'scripts/phase3k/password_gateway.php'
MIGRATIONS = ROOT / 'docs/database/migrations'


class UnitSchemaLiveTests(unittest.TestCase):
    def compare_foreign_keys(self, show, expected):
        return self.php(r'try{\Mosa2\Phase3K\compareShowForeignKeys($v[0],$v[1],"test");echo "true";}catch(Throwable $e){echo "false";}', [show, expected])

    def test_show_foreign_keys_external_and_self_single_and_composite(self):
        for parent in ('m2_parent', 'm2_child'):
            for count in (1, 3):
                columns = ['parent_key', 'parent_version', 'contract'][:count]
                targets = ['unit_key', 'unit_version', 'contract'][:count]
                expected = {'fk_test': dict(columns=columns, table=parent, targets=targets, delete='RESTRICT')}
                for separator in (',', ', ', ',  '):
                    identifiers = lambda names: separator.join('`' + name + '`' for name in names)
                    show = ('CREATE TABLE `m2_child` (\n  CONSTRAINT `fk_test` FOREIGN KEY (' + identifiers(columns)
                            + ') REFERENCES `' + parent + '` (' + identifiers(targets) + ') ON DELETE RESTRICT\n)')
                    with self.subTest(parent=parent, count=count, separator=separator):
                        self.assertTrue(self.compare_foreign_keys(show, expected))

    def test_show_foreign_keys_wrong_column_order_rejected(self):
        expected = {'fk_test': dict(columns=['a', 'b', 'c'], table='m2_child', targets=['x', 'y', 'z'], delete='RESTRICT')}
        for local, target in [('`b`, `a`, `c`', '`x`, `y`, `z`'), ('`a`, `b`, `c`', '`x`, `z`, `y`')]:
            self.assertFalse(self.compare_foreign_keys('  CONSTRAINT `fk_test` FOREIGN KEY (' + local + ') REFERENCES `m2_child` (' + target + ') ON DELETE RESTRICT', expected))

    def test_show_foreign_keys_wrong_target_rejected(self):
        expected = {'fk_test': dict(columns=['a'], table='m2_parent', targets=['x'], delete='RESTRICT')}
        self.assertFalse(self.compare_foreign_keys('  CONSTRAINT `fk_test` FOREIGN KEY (`a`) REFERENCES `m2_wrong` (`x`) ON DELETE RESTRICT', expected))

    def test_show_foreign_keys_missing_or_extra_rejected(self):
        expected = {'fk_test': dict(columns=['a'], table='m2_parent', targets=['x'], delete='RESTRICT')}
        self.assertFalse(self.compare_foreign_keys('CREATE TABLE `m2_child` (`a` int)', expected))
        show = '  CONSTRAINT `fk_test` FOREIGN KEY (`a`) REFERENCES `m2_parent` (`x`) ON DELETE RESTRICT'
        self.assertFalse(self.compare_foreign_keys(show + '\n' + show.replace('fk_test', 'fk_extra'), expected))

    def test_show_foreign_keys_actions_duplicates_and_unknown_syntax_rejected(self):
        expected = {'fk_test': dict(columns=['a'], table='m2_parent', targets=['x'], delete='RESTRICT')}
        show = '  CONSTRAINT `fk_test` FOREIGN KEY (`a`) REFERENCES `m2_parent` (`x`) ON DELETE RESTRICT'
        for bad in (show.replace('RESTRICT', 'NO ACTION'), show.replace('RESTRICT', 'CASCADE'),
                    show + ' ON UPDATE CASCADE', show + ' UNKNOWN', show + '\n' + show,
                    show.replace('(`a`)', '(`a`, `a`)'), show.replace('(`x`)', '(`x`, `y`)')):
            self.assertFalse(self.compare_foreign_keys(bad, expected), bad)

    def php(self, body, payload=None):
        code = 'require $argv[1]; $v=json_decode(stream_get_contents(STDIN),true);' + body
        result = subprocess.run(['php', '-d', 'display_errors=stderr', '-r', code, str(GATEWAY)],
                                input=json.dumps(payload), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_php_sources_lint(self):
        for name in ('unit_schema.php', 'live_apply.php', 'password_gateway.php'):
            subprocess.run(['php', '-l', str(MODULE.parent / name)], check=True, capture_output=True)

    def test_all_six_schema_stages_match_independent_offline_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            for number, name in enumerate(('0001_core_asset_identity.sql', '0002_market_current_history.sql', '0003_market_units.sql'), 1):
                shutil.copyfile(MIGRATIONS / name, Path(directory) / f'{number:04}.sql')
            result = self.php('$r=[];for($i=0;$i<=5;$i++)$r[]=\\Mosa2\\Phase3K\\schemas($v,$i);echo json_encode($r,JSON_THROW_ON_ERROR);', directory)
        base = ''.join((MIGRATIONS / name).read_text(encoding='utf-8') for name in ('0001_core_asset_identity.sql', '0002_market_current_history.sql'))
        sql = (MIGRATIONS / '0003_market_units.sql').read_text(encoding='utf-8')
        import re
        parts = split_sql(re.sub(r'^\s*--[^\n]*$', '', sql, flags=re.M), ';')[:-1]
        for stage, actual in enumerate(result):
            expected = parse_schema(base + ';'.join(parts[:stage]) + (';' if stage else ''))
            self.assertEqual(set(actual), set(expected))
            for name, table in expected.items():
                got = actual[name]
                self.assertEqual(list(got['columns']), list(table['columns']))
                for field, (kind, nullable, collation, auto, default) in table['columns'].items():
                    text = kind.startswith(('VARCHAR', 'CHAR('))
                    self.assertEqual(got['columns'][field], dict(type=kind.lower(), nullable='YES' if nullable else 'NO',
                                     collation=(collation or 'utf8mb4_0900_ai_ci') if text else None,
                                     charset='utf8mb4' if text else None, extra='auto_increment' if auto else '',
                                     default='' if default == "''" else default), (stage, name, field))
                keys = {key: (tuple(value['columns']), value['unique']) for key, value in got['indexes'].items()}
                self.assertEqual(keys, dict(table['indexes'], PRIMARY=(table['pk'], True)))
                fks = {key: (tuple(value.get('columns', [value.get('column')])), value['table'],
                             tuple(value.get('targets', [value.get('target')])), value['delete']) for key, value in (got['fks'] or {}).items()}
                self.assertEqual(fks, table['fks'])
                self.assertEqual(dict(got['checks'] or {}), table['checks'])

    def test_exact_migration_hash_and_tampering_rejected(self):
        sql = (MIGRATIONS / '0003_market_units.sql').read_bytes()
        self.assertEqual(hashlib.sha256(sql).hexdigest(), '199933884802bd139b706e50e57e04687e9cbe5f8bd1366e98e302af7d47b8ee')
        for extra in ('\n', ' SELECT 1;', ' INSERT INTO m2_units VALUES (1);'):
            self.assertTrue(self.php('try{\\Mosa2\\Phase3K\\statements($v);echo "false";}catch(Throwable $e){echo "true";}', sql.decode() + extra))

    def test_stop_at_every_precheck_ddl_or_postcheck_failure(self):
        body = r'''
        $r=[];foreach(['before','execute','after'] as $phase)for($fail=0;$fail<5;$fail++){
            $events=[];$operation=function($name,$i)use(&$events,$phase,$fail){$events[]=[$name,$i];if($name===$phase&&$i===$fail)throw new RuntimeException('injected');};
            try{\Mosa2\Phase3K\applyStatements(['a','b','c','d','e'],fn($i)=>$operation('before',$i),fn($s,$i)=>$operation('execute',$i),fn($i)=>$operation('after',$i));$events[]=['ledger',3];}catch(Throwable $e){}
            $r[]=[$phase,$fail,$events];
        }echo json_encode($r);
        '''
        for phase, fail, events in self.php(body):
            expected = [[name, i] for i in range(fail) for name in ('before', 'execute', 'after')]
            for name in ('before', 'execute', 'after'):
                expected.append([name, fail])
                if name == phase:
                    break
            self.assertEqual(events, expected)

    def test_success_has_exactly_five_ddl_executions_in_order(self):
        got = self.php(r'$r=[];\Mosa2\Phase3K\applyStatements([1,2,3,4,5],function($i)use(&$r){$r[]="before$i";},function($s,$i)use(&$r){$r[]="ddl$s";},function($i)use(&$r){$r[]="after$i";});echo json_encode($r);')
        self.assertEqual(got, [value for i in range(5) for value in (f'before{i}', f'ddl{i+1}', f'after{i}')])

    def test_resume_executes_only_ddl_two_to_five_and_stops_on_each_failure(self):
        body = r'''
        $r=[];foreach(['success','before','execute','after'] as $phase)for($fail=1;$fail<5;$fail++){
            $events=[];$operation=function($name,$i)use(&$events,$phase,$fail){$events[]=[$name,$i];if($name===$phase&&$i===$fail)throw new RuntimeException('injected');};
            try{\Mosa2\Phase3K\applyStatements(['CREATE','ALTER2','ALTER3','ALTER4','ALTER5'],fn($i)=>$operation('before',$i),fn($s,$i)=>$operation('execute',$i),fn($i)=>$operation('after',$i),1);$events[]=['ledger',3];}catch(Throwable $e){}
            $r[]=[$phase,$fail,$events];
        }echo json_encode($r);
        '''
        for phase, fail, events in self.php(body):
            end = 5 if phase == 'success' else fail
            expected = [[name, i] for i in range(1, end) for name in ('before', 'execute', 'after')]
            if phase == 'success':
                expected.append(['ledger', 3])
            else:
                for name in ('before', 'execute', 'after'):
                    expected.append([name, fail])
                    if name == phase:
                        break
            self.assertEqual(events, expected)

    def test_current_resume_never_replays_ddl_one_to_three(self):
        body = r'''
        $out=[];foreach(['success','before','execute','after'] as $phase)foreach([3,4] as $fail){
            $events=[];$operation=function($name,$i)use(&$events,$phase,$fail){$events[]=[$name,$i];if($name===$phase&&$i===$fail)throw new RuntimeException('injected');};
            try{\Mosa2\Phase3K\resumeStatements(['CREATE','ALTER2','ALTER3','ALTER4','ALTER5'],fn($i)=>$operation('before',$i),fn($s,$i)=>$operation('execute',$i),fn($i)=>$operation('after',$i));$events[]=['ledger',3];}catch(Throwable $e){}
            $out[]=[$phase,$fail,$events];
        }echo json_encode($out);
        '''
        for phase, fail, events in self.php(body):
            expected = [[step, i] for i in range(3, 5 if phase == 'success' else fail) for step in ('before', 'execute', 'after')]
            if phase == 'success':
                expected.append(['ledger', 3])
            else:
                for step in ('before', 'execute', 'after'):
                    expected.append([step, fail])
                    if step == phase:
                        break
            self.assertEqual(events, expected)

    def test_resume_after_ddl_three_requires_unchanged_prior_evidence_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for number, name in enumerate(('0001_core_asset_identity.sql', '0002_market_current_history.sql', '0003_market_units.sql'), 1):
                shutil.copyfile(MIGRATIONS / name, path / f'{number:04}.sql')
            body = r'''
            $p=$v;$parts=\Mosa2\Phase3K\statements(file_get_contents($p.'/0003.sql'));
            $original=['structure'=>['counts'=>\Mosa2\Phase3K\totals(\Mosa2\Phase3K\schemas($p,0))],'environment'=>['strict'=>true],'rows'=>['synthetic'=>[]],'ledger'=>[1,2]];
            $original['row_hash']=\Mosa2\Phase3K\dataHash($original['rows']);$bytes=json_encode($original);
            file_put_contents($p.'/original-pre-state.json',$bytes);file_put_contents($p.'/original-restore.sql','old-backup');
            $first=['migration_sha256'=>\Mosa2\Phase3K\DIGEST,'ok'=>false,'stage'=>'ddl_1','failure'=>['kind'=>'guard','reason'=>'show_fk:m2_units'],'restore_ready'=>true,
                'ddl'=>[['table'=>'m2_units','status'=>'executing','sha256'=>hash('sha256',$parts[0])]],'pre_state_sha256'=>hash('sha256',$bytes),'restore_sha256'=>hash('sha256','old-backup')];
            file_put_contents($p.'/original-report.json',json_encode($first));
            $prior=$original;$prior['structure']['counts']=\Mosa2\Phase3K\totals(\Mosa2\Phase3K\schemas($p,1));
            $report=['migration_sha256'=>\Mosa2\Phase3K\DIGEST,'ok'=>false,'stage'=>'ddl_3','failure'=>['kind'=>'guard','reason'=>'unit_check_expression:ck_market_observations_volume'],'restore_ready'=>true,'resume_from_ddl'=>2,
                'ddl'=>[1=>['table'=>'m2_asset_source_routes','status'=>'validated','sha256'=>hash('sha256',$parts[1])],2=>['table'=>'m2_market_observations','status'=>'executing','sha256'=>hash('sha256',$parts[2])]],'restore_sha256'=>hash('sha256','prior-backup')];
            file_put_contents($p.'/prior-restore.sql','prior-backup');$out=[];
            foreach(['valid','wrong_stage','wrong_constraint','extra_ddl','wrong_ddl','wrong_pre_hash','wrong_restore_hash','changed_legacy','changed_ledger','wrong_resume_start'] as $case){
                $r=$report;$b=$prior;
                if($case==='wrong_stage')$r['stage']='ddl_4';if($case==='wrong_constraint')$r['failure']['reason']='other';
                if($case==='extra_ddl')$r['ddl'][3]=$r['ddl'][2];if($case==='wrong_ddl')$r['ddl'][2]['sha256']=str_repeat('0',64);
                if($case==='wrong_restore_hash')$r['restore_sha256']=str_repeat('0',64);if($case==='wrong_resume_start')$r['resume_from_ddl']=1;
                if($case==='changed_legacy'){$b['rows']['synthetic'][]=['changed'=>1];$b['row_hash']=\Mosa2\Phase3K\dataHash($b['rows']);}
                if($case==='changed_ledger')$b['ledger']=[1,3];
                $bytes=json_encode($b);file_put_contents($p.'/prior-pre-state.json',$bytes);$r['pre_state_sha256']=hash('sha256',$bytes);
                if($case==='wrong_pre_hash')$r['pre_state_sha256']=str_repeat('0',64);file_put_contents($p.'/prior-report.json',json_encode($r));
                try{\Mosa2\Phase3K\priorEvidence($p);$out[$case]=true;}catch(Throwable $e){$out[$case]=false;}
            }echo json_encode($out);
            '''
            got = self.php(body, directory)
        self.assertTrue(got.pop('valid'))
        self.assertFalse(any(got.values()), got)

    def test_resume_requires_hash_bound_original_stop_and_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for number, name in enumerate(('0001_core_asset_identity.sql', '0002_market_current_history.sql', '0003_market_units.sql'), 1):
                shutil.copyfile(MIGRATIONS / name, path / f'{number:04}.sql')
            body = r'''
            $root=$v;$before=['structure'=>['counts'=>\Mosa2\Phase3K\totals(\Mosa2\Phase3K\schemas($root,0))],'rows'=>['synthetic'=>[]],'ledger'=>[1,2]];
            $before['row_hash']=\Mosa2\Phase3K\dataHash($before['rows']);$bytes=json_encode($before);$restore='synthetic-backup';
            file_put_contents($root.'/original-pre-state.json',$bytes);file_put_contents($root.'/original-restore.sql',$restore);
            $report=['migration_sha256'=>\Mosa2\Phase3K\DIGEST,'ok'=>false,'stage'=>'ddl_1','failure'=>['kind'=>'guard','reason'=>'show_fk:m2_units'],'restore_ready'=>true,
                'ddl'=>[['table'=>'m2_units','status'=>'executing','sha256'=>hash('sha256',\Mosa2\Phase3K\statements(file_get_contents($root.'/0003.sql'))[0])]],
                'pre_state_sha256'=>hash('sha256',$bytes),'restore_sha256'=>hash('sha256',$restore)];
            $out=[];foreach(['valid','wrong_stage','wrong_digest','wrong_ddl','wrong_pre_hash','wrong_restore_hash','extra_ddl','changed_rows'] as $case){
                $r=$report;
                if($case==='wrong_stage')$r['stage']='ddl_2';if($case==='wrong_digest')$r['migration_sha256']=str_repeat('0',64);
                if($case==='wrong_ddl')$r['ddl'][0]['sha256']=str_repeat('0',64);if($case==='wrong_pre_hash')$r['pre_state_sha256']=str_repeat('0',64);
                if($case==='wrong_restore_hash')$r['restore_sha256']=str_repeat('0',64);if($case==='extra_ddl')$r['ddl'][]=$r['ddl'][0];
                file_put_contents($root.'/original-pre-state.json',$case==='changed_rows'?$bytes.' ':$bytes);file_put_contents($root.'/original-report.json',json_encode($r));
                try{\Mosa2\Phase3K\originalEvidence($root);$out[$case]=true;}catch(Throwable $e){$out[$case]=false;}
            }echo json_encode($out);
            '''
            got = self.php(body, directory)
        self.assertTrue(got.pop('valid'))
        self.assertFalse(any(got.values()), got)

    def test_legacy_guard_rejects_each_kind_of_change(self):
        before = {'environment': {'grants': ['isolated'], 'utc': True}, 'rows': {'observations': [{'dedupe': 'ab', 'price': '1.23'}]}, 'row_hash': 'abc'}
        for key, value in (('environment', {}), ('rows', {}), ('row_hash', 'changed')):
            changed = dict(before, **{key: value})
            self.assertTrue(self.php('try{\\Mosa2\\Phase3K\\preserve($v[0],$v[1]);echo "false";}catch(Throwable $e){echo "true";}', [before, changed]))

    def test_origin_https_method_host_expiry_query_and_size_guards(self):
        config = {'host': 'mosa2-test.scharwerk.de', 'expires': 1001}
        server = {'HTTPS': 'on', 'HTTP_HOST': config['host'], 'REQUEST_METHOD': 'POST',
                  'HTTP_ORIGIN': 'https://' + config['host'], 'CONTENT_LENGTH': '100', 'QUERY_STRING': ''}
        cases = [server] + [dict(server, **{key: value}) for key, value in
                           [('HTTPS', 'off'), ('HTTP_HOST', 'mosa.scharwerk.de'), ('REQUEST_METHOD', 'PUT'),
                            ('HTTP_ORIGIN', 'https://elsewhere.invalid'), ('CONTENT_LENGTH', '4097'),
                            ('CONTENT_LENGTH', '-1'), ('QUERY_STRING', 'password=not-a-secret')]]
        result = self.php('$r=[];foreach($v[0] as $s)$r[]=\\Mosa2\\Phase3K\\requestAllowed($s,$v[1],1000);echo json_encode($r);', [cases, config])
        self.assertEqual(result, [True] + [False] * (len(cases) - 1))
        self.assertFalse(self.php('echo json_encode(\\Mosa2\\Phase3K\\requestAllowed($v[0],$v[1],1002));', [server, config]))

    def test_csrf_cookie_signature_age_and_future_guards(self):
        body = r'''$key='synthetic-key';$nonce='1000.'.str_repeat('a',64);$token=$nonce.'.'.hash_hmac('sha256',$nonce,$key);
        echo json_encode([\Mosa2\Phase3K\tokenValid($token,$token,$key,1000),\Mosa2\Phase3K\tokenValid($token,$token,$key,1601),\Mosa2\Phase3K\tokenValid($token,$token,$key,999),\Mosa2\Phase3K\tokenValid($token,'different',$key,1000),\Mosa2\Phase3K\tokenValid($token,$token,'wrong',1000)]);'''
        self.assertEqual(self.php(body), [True, False, False, False, False])

    def test_practical_probes_rollback_success_and_unexpected_failure(self):
        body = r'''
        require $v;$r=[];
        foreach([null,'12.50000000'] as $volume)foreach([false,true] as $failure){
            $p=new UnitProbePDO($failure);$result=null;
            try{$result=\Mosa2\Phase3K\practical($p,['rows'=>['m2_market_observations'=>[['id'=>11,'route_id'=>22,'volume'=>$volume]]]]);}catch(RuntimeException $e){if($e->getMessage()!=='injected_insert_failure')throw $e;}
            $r[]=['failed'=>$failure,'rolled_back'=>$p->rolledBack,'active'=>$p->active,'insertions'=>count($p->insertions),'updates'=>count($p->updates),'negative'=>count($result['negative']??[])];
        }echo json_encode($r);
        '''
        for row in self.php(body, str(ROOT / 'tests/phase3k_probe_fixture.php')):
            self.assertTrue(row['rolled_back'])
            self.assertFalse(row['active'])
            self.assertEqual(row['insertions'], 0 if row['failed'] else 4)
            self.assertEqual(row['updates'], 0 if row['failed'] else 3)
            self.assertEqual(row['negative'], 0 if row['failed'] else 10)

    def test_restore_export_encodes_all_scalar_and_binary_bytes_without_credentials(self):
        body = r'''
        require $v;$p=new UnitProbePDO();
        $schema=['m2_test'=>['columns'=>['id'=>['type'=>'bigint unsigned'],'name'=>['type'=>'varchar(64)'],'digest'=>['type'=>'binary(32)'],'optional'=>['type'=>'varchar(64)']]]];
        $before=['structure'=>['metadata'=>['m2_test'=>['show_create'=>'CREATE TABLE `m2_test` (`id` bigint unsigned)']]],'rows'=>['m2_test'=>[['id'=>7,'name'=>"A'B\\C\nD",'digest'=>'00FF','optional'=>null]]]];
        echo json_encode(\Mosa2\Phase3K\restoreArtifact($p,$before,$schema));
        '''
        sql = self.php(body, str(ROOT / 'tests/phase3k_probe_fixture.php'))
        self.assertIn('CREATE TABLE `m2_test`', sql)
        self.assertIn("CONVERT(UNHEX('37') USING utf8mb4)", sql)
        self.assertIn("CONVERT(UNHEX('" + "A'B\\C\nD".encode().hex() + "') USING utf8mb4)", sql)
        self.assertIn("UNHEX('00FF'),NULL", sql)
        self.assertNotIn('DROP', sql)

    def test_secrets_are_not_serialized_or_saved(self):
        gateway = GATEWAY.read_text(encoding='utf-8')
        runner = MODULE.read_text(encoding='utf-8')
        self.assertNotIn('secret.php', gateway + runner)
        self.assertNotIn('var_export($password', gateway + runner)
        self.assertIn('unset($password,$_POST)', gateway)
        for protection in ("'secure'=>true", "'httponly'=>true", "'samesite'=>'Strict'", 'no-store', 'noindex', 'maxlength="1024"'):
            self.assertIn(protection, gateway)
        self.assertLess(gateway.index("$_POST['probe']"), gateway.index("$_POST['password']??null"))
        self.assertIn('if($p->inTransaction())$p->rollBack()', runner)
        self.assertLess(runner.index("$report['practical']=practical"), runner.index("$report['stage']='ledger_transaction'"))
        self.assertNotIn('DROP TABLE', runner)

    def test_new_check_ast_matches_qualified_server_rendering(self):
        from test_check_expression import CheckExpressionTests
        compare = CheckExpressionTests().compare
        expression = "((unit_contract_version = 'mosa2-market-unit-v1' AND quote_unit_key IS NOT NULL) OR quote_unit_version IS NULL) IS TRUE"
        actual = expression.replace("'mosa2-market-unit-v1'", "_utf8mb4'mosa2-market-unit-v1'")
        show = 'CREATE TABLE test (\n  CONSTRAINT `ck_test` CHECK (' + actual.lower() + ')\n)'
        # Identifier and literal bytes remain significant; only keywords normalize.
        information = actual.replace("'", "\\'")
        self.assertTrue(compare(expression, information, show, True)['equal'])
        self.assertFalse(compare(expression, information.replace('IS NOT NULL', 'IS NULL'), show, True)['equal'])


if __name__ == '__main__':
    unittest.main()
