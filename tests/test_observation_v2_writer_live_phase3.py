"""Phase-3O transport/runtime gate; synthetic, no DB executor or connection."""
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'scripts/phase3o/live_plan.py'
spec=importlib.util.spec_from_file_location('phase3o_transport_test',MODULE)
live=importlib.util.module_from_spec(spec);spec.loader.exec_module(live)


class WriterRuntimeGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request=json.loads((ROOT/'tests/fixtures/phase3o_runtime_request.json').read_text(encoding='utf8'))
        cls.expected=json.loads((ROOT/'tests/fixtures/phase3o_runtime_expected.json').read_text(encoding='utf8'))

    def test_actual_writer_four_golden_plans(self):
        result=live.plans(self.request)
        self.assertEqual(result,self.expected)
        self.assertEqual([r['decision'] for r in result],['INSERT']*4)
        catalog=live.writer.observation.catalog_module.normative_catalog()
        planner=live.writer.WriterPlanner(catalog,self.request['routes'])
        for raw,encoded in zip(self.request['observations'],result):
            direct=planner.plan(raw,format_version=2,intent=self.request['intent'],created_at=self.request['created_at'])
            decoded=live.restore(encoded)
            direct['expected_db_columns']=list(direct['expected_db_columns'])
            self.assertEqual(decoded,direct)

    def test_binary_transport_exact_raw_hash_canonical_and_db_columns(self):
        for plan in self.expected:
            decoded=live.restore(plan);key=decoded['dedupe_key'];canonical=decoded['canonical_bytes']
            self.assertEqual(type(key),bytes);self.assertEqual(len(key),32)
            self.assertEqual(hashlib.sha256(canonical).digest(),key)
            self.assertTrue(canonical.startswith(b'mosa2-observation-v2\n'))
            self.assertEqual(len(json.loads(canonical.split(b'\n',1)[1])),18)
            self.assertEqual(decoded['db_values']['dedupe_key'],key)
            self.assertEqual(decoded['db_values']['observation_format_version'],2)
            self.assertEqual(set(decoded['expected_db_columns']),set(decoded['db_values']))
            self.assertEqual(len(decoded['db_values']),21)

    def test_stdio_cli_is_deterministic(self):
        process=subprocess.run([sys.executable,str(MODULE)],input=json.dumps(self.request),text=True,capture_output=True,check=True)
        self.assertEqual(process.stderr,'')
        self.assertEqual(json.loads(process.stdout),dict(ok=True,plans=self.expected))
        self.assertEqual(live.plans(copy.deepcopy(self.request)),self.expected)

    def test_real_readback_shape_duplicate_and_conflict_transport(self):
        req=copy.deepcopy(self.request)
        req['existing']=[dict(format_version=2,payload=copy.deepcopy(p['normalized']),dedupe_key=copy.deepcopy(p['dedupe_key'])) for p in self.expected]
        self.assertEqual([p['decision'] for p in live.plans(req)],['DUPLICATE_UNCHANGED']*4)
        req['existing'][0]['payload']['price']='99.0000000000'
        self.assertEqual(live.plans(req)[0]['decision'],'CONFLICT')

    def test_request_is_bounded_and_credentials_are_not_an_input(self):
        for changes in [dict(password='forbidden'),dict(observations=[]),dict(observations=self.request['observations']*2)]:
            req=copy.deepcopy(self.request);req.update(changes)
            with self.assertRaises(ValueError):live.plans(req)
        with self.assertRaises(Exception):live.restore({'$bytes':'!!bad!!'})
        for value in (b'\x00'*32,b'\xff'*32,b'mosa2-observation-v2\n{}'):
            self.assertEqual(live.restore(live.transport(value)),value)

    def test_only_transport_no_second_semantic_writer_or_db(self):
        python=MODULE.read_text(encoding='utf8');php=(ROOT/'scripts/phase3o/runtime_probe.php').read_text(encoding='utf8')
        self.assertIn('writer.WriterPlanner(',python)
        self.assertNotIn('hashlib',python);self.assertNotIn('canonical_observation',python)
        for forbidden in ('PDO','mysqli','INSERT INTO','UPDATE ','DELETE FROM','ALTER TABLE','CREATE TABLE','commit(','password'):
            self.assertNotIn(forbidden,python+php)
        self.assertIn('probe_already_attempted',php)
        self.assertLess(php.index("if(file_exists($file))"),php.index('$report=runtimeProbe($project)'))
        lint=subprocess.run(['php','-l',str(ROOT/'scripts/phase3o/runtime_probe.php')],capture_output=True,text=True)
        self.assertEqual(lint.returncode,0,lint.stderr+lint.stdout)


class StructuralCounterGuardTests(unittest.TestCase):
    @classmethod
    def php(cls, code, value=None):
        prelude=r"require $argv[1].'/scripts/phase3o/state_integrity.php';$v=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);"
        p=subprocess.run(['php','-r',prelude+code,str(ROOT)],input=json.dumps(value),capture_output=True,text=True)
        if p.returncode:raise AssertionError(p.stdout+p.stderr)
        return json.loads(p.stdout)

    @classmethod
    def setUpClass(cls):
        qualified=cls.php(r'''
        $core=\Mosa2\Phase2\contract(file_get_contents($argv[1].'/docs/database/migrations/0001_core_asset_identity.sql'));
        $market=\Mosa2\Phase2\contract(file_get_contents($argv[1].'/docs/database/migrations/0002_market_current_history.sql'),\Mosa2\Phase3B\DIGEST,\Mosa2\Phase3B\MARKET);
        echo json_encode(['core'=>$core,'market'=>$market,'counts'=>\Mosa2\Phase3K\COUNTS],JSON_THROW_ON_ERROR);
        ''')
        cls.contracts=qualified['core']|qualified['market'];cls.expected_counts=qualified['counts']
        cls.counter_counts=[sum(any(c['extra']=='auto_increment' for c in t['columns'].values()) for t in qualified[k].values()) for k in ('core','market')]

    def state(self):
        digest=lambda x:hashlib.sha256(json.dumps(x,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        rows={name:[dict(id=str(i+1),value='synthetic') for i in range(count)] for name,count in self.expected_counts.items()}
        metadata={};counters={}
        for name,table in self.contracts.items():
            columns=[dict(COLUMN_NAME=k,EXTRA=c['extra']) for k,c in table['columns'].items()]
            automatic=[c['COLUMN_NAME'] for c in columns if c['EXTRA']=='auto_increment']
            metadata[name]=dict(columns=columns,table={'AUTO_INCREMENT':'10' if automatic else None},show_create=table['ddl'])
            if automatic:
                keys=[r['id'] for r in rows[name]]
                counters[name]=dict(column=automatic[0],value='10',count=len(keys),min_pk=keys[0] if keys else None,
                    max_pk=keys[-1] if keys else None,pk_set=keys,pk_sha256=digest(keys),row_hash=digest(rows[name]))
        metadata['m2_units']=dict(columns=[dict(COLUMN_NAME='unit_key',EXTRA='')],table={'AUTO_INCREMENT':None},show_create='synthetic non-counter table')
        return dict(environment={'grants':['synthetic'],'utc':True},structure=dict(metadata=metadata),rows=rows,
                    row_hash=digest(rows),ledger=[dict(version=i,checksum='synthetic') for i in (1,2,3)],
                    units=[dict(unit_key='SYNTH_'+str(i),definition='fixed') for i in range(4)],counter_diagnostics=counters)

    def compare(self, before, after):
        return self.php(r'''
        try{$r=\Mosa2\Phase3O\compareBusinessState($v[0],$v[1]);echo json_encode(['ok'=>true,'counter_tables'=>count(\Mosa2\Phase3M\counterColumns($v[1]['structure'])),'diagnostics'=>$r]);}
        catch(Throwable $e){echo json_encode(['ok'=>false,'reason'=>$e->getMessage()]);}
        ''',[before,after])

    def test_actual_schema_twelve_is_ten_core_plus_two_market(self):
        self.assertEqual(self.counter_counts,[10,2])
        result=self.compare(self.state(),self.state());self.assertTrue(result['ok'],result)
        self.assertEqual(result['counter_tables'],12)

    def test_nine_materialized_historical_values_still_expect_twelve(self):
        before=self.state();after=copy.deepcopy(before)
        for name in list(before['counter_diagnostics'])[:3]:
            before['structure']['metadata'][name]['table']['AUTO_INCREMENT']=None
        self.assertEqual(sum(t['table']['AUTO_INCREMENT'] is not None for t in before['structure']['metadata'].values()),9)
        result=self.compare(before,after);self.assertTrue(result['ok'],result);self.assertEqual(result['counter_tables'],12)

    def test_changed_counters_including_below_max_pk_are_only_diagnostic(self):
        before=self.state();after=copy.deepcopy(before)
        for name,d in after['counter_diagnostics'].items():
            d['value']='0';after['structure']['metadata'][name]['table']['AUTO_INCREMENT']='0'
        result=self.compare(before,after);self.assertTrue(result['ok'],result)
        self.assertEqual(result['diagnostics']['affected_tables'],12)

    def test_removed_or_new_structural_counter_column_rejected(self):
        before=self.state()
        for automatic in (True,False):
            after=copy.deepcopy(before)
            for table in after['structure']['metadata'].values():
                found=next((c for c in table['columns'] if (c['EXTRA']=='auto_increment')==automatic),None)
                if found is not None:
                    found['EXTRA']='' if automatic else 'auto_increment';break
            self.assertFalse(self.compare(before,after)['ok'])

    def test_missing_counter_evidence_and_wrong_counter_column_rejected(self):
        before=self.state()
        for mutation in ('missing','column','count','pk_set','row_hash'):
            after=copy.deepcopy(before);name=next(iter(after['counter_diagnostics']))
            if mutation=='missing':del after['counter_diagnostics'][name]
            else:after['counter_diagnostics'][name][mutation]={'column':'wrong','count':999,'pk_set':['999'],'row_hash':'0'*64}[mutation]
            self.assertFalse(self.compare(before,after)['ok'],mutation)

    def test_changed_rows_pks_values_and_hash_rejected(self):
        before=self.state();name=next(n for n,r in before['rows'].items() if r)
        for mutation in ('count','pk','value','hash'):
            after=copy.deepcopy(before)
            if mutation=='count':after['rows'][name].pop()
            elif mutation=='pk':after['rows'][name][0]['id']='999'
            elif mutation=='value':after['rows'][name][0]['value']='changed'
            else:after['row_hash']='0'*64
            self.assertFalse(self.compare(before,after)['ok'],mutation)

    def test_changed_ledger_units_and_grants_rejected(self):
        before=self.state()
        for mutation in ('ledger','units','grants'):
            after=copy.deepcopy(before)
            if mutation=='ledger':after['ledger'][0]['checksum']='changed'
            elif mutation=='units':after['units'][0]['definition']='changed'
            else:after['environment']['grants']=['different']
            self.assertFalse(self.compare(before,after)['ok'],mutation)

    def test_phase3c_rule_no_reset_or_max_release_condition(self):
        contract=(ROOT/'docs/database/PHASE3C_MARKET_FLOW.md').read_text(encoding='utf8')
        self.assertIn('nicht identische\nAUTO_INCREMENT-Zähler',contract.replace('\r\n','\n'))
        source=(ROOT/'scripts/phase3m/state_integrity.php').read_text(encoding='utf8')
        self.assertNotRegex(source,r'(?i)ALTER\s+TABLE[^;]*AUTO_INCREMENT')
        self.assertNotRegex(source,r'(?i)check\([^;]*(?:max_pk|MAX\s*\()')

    def ddl_state(self):
        state=self.state();name=next(iter(state['counter_diagnostics']))
        ddl="CREATE TABLE `synthetic` (`id` bigint NOT NULL AUTO_INCREMENT, `x` int DEFAULT 1, PRIMARY KEY (`id`), KEY `ix` (`x`), CONSTRAINT `fk` FOREIGN KEY (`x`) REFERENCES `parent` (`id`), CONSTRAINT `ck` CHECK (`x` > 0)) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin COMMENT='AUTO_INCREMENT=10 (quoted)' ROW_FORMAT=DYNAMIC"
        state['structure']['metadata'][name]['show_create']=ddl
        return state,name,ddl

    def assert_same_hash(self,before,after):
        result=self.compare(before,after);self.assertTrue(result['ok'],result)
        hashes=self.php(r'echo json_encode([\Mosa2\Phase3O\stateHash($v[0]),\Mosa2\Phase3O\stateHash($v[1])]);',[before,after])
        self.assertEqual(*hashes)

    def test_top_level_table_counter_option_normalized(self):
        before,name,ddl=self.ddl_state();after=copy.deepcopy(before)
        after['structure']['metadata'][name]['show_create']=ddl.replace('ENGINE=InnoDB AUTO_INCREMENT=10','ENGINE=InnoDB AUTO_INCREMENT=20')
        self.assert_same_hash(before,after)

    def test_nested_show_create_counter_option_normalized(self):
        before,name,ddl=self.ddl_state()
        before['structure']['metadata'][name]['comparisons']={'check':{'show_create_table':ddl}}
        after=copy.deepcopy(before)
        after['structure']['metadata'][name]['comparisons']['check']['show_create_table']=ddl.replace('ENGINE=InnoDB AUTO_INCREMENT=10','ENGINE=InnoDB AUTO_INCREMENT=20')
        self.assert_same_hash(before,after)

    def test_seven_diagnostic_copies_normalized_raw_state_preserved(self):
        before,name,ddl=self.ddl_state()
        before['structure']['metadata'][name]['comparisons']={str(i):{'show_create_table':ddl} for i in range(7)}
        after=copy.deepcopy(before)
        for i,item in enumerate(after['structure']['metadata'][name]['comparisons'].values()):
            item['show_create_table']=ddl.replace('ENGINE=InnoDB AUTO_INCREMENT=10',f'ENGINE=InnoDB AUTO_INCREMENT={20+i}')
        original=copy.deepcopy(after);self.assert_same_hash(before,after);self.assertEqual(after,original)

    def test_real_ddl_changes_including_column_auto_increment_rejected(self):
        before,name,ddl=self.ddl_state()
        for old,new in [('NOT NULL AUTO_INCREMENT','NOT NULL'),('bigint','int'),('DEFAULT 1','DEFAULT 2'),
                        ('PRIMARY KEY (`id`)','PRIMARY KEY (`x`)'),('KEY `ix`','UNIQUE KEY `ix`'),
                        ('REFERENCES `parent`','REFERENCES `other`'),('`x` > 0','`x` >= 0'),
                        ('ENGINE=InnoDB','ENGINE=MyISAM'),('CHARSET=utf8mb4','CHARSET=latin1'),
                        ('COLLATE=utf8mb4_bin','COLLATE=utf8mb4_general_ci'),('ROW_FORMAT=DYNAMIC','ROW_FORMAT=COMPACT'),
                        ("COMMENT='AUTO_INCREMENT=10 (quoted)'","COMMENT='AUTO_INCREMENT=20 (quoted)'")]:
            with self.subTest(change=old):
                after=copy.deepcopy(before);after['structure']['metadata'][name]['show_create']=ddl.replace(old,new)
                self.assertFalse(self.compare(before,after)['ok'])
                # The same structural change must remain visible in nested copies.
                before_nested=copy.deepcopy(before);before_nested['structure']['metadata'][name]['comparisons']={'x':{'show_create_table':ddl}}
                after_nested=copy.deepcopy(before_nested);after_nested['structure']['metadata'][name]['comparisons']['x']['show_create_table']=ddl.replace(old,new)
                self.assertFalse(self.compare(before_nested,after_nested)['ok'])


class TransactionExecutorTests(unittest.TestCase):
    def test_validated_plan_prepared_execution_and_rollback_with_fake_pdo(self):
        # The PHP double has no connection constructor. Exercise actual executor
        # and transaction code, including 19 plan corruptions before prepare.
        process=subprocess.run(['php',str(ROOT/'scripts/phase3o/self_test.php')],capture_output=True,text=True)
        self.assertEqual(process.returncode,0,process.stdout+process.stderr)
        self.assertEqual(json.loads(process.stdout),dict(four_insert_plans_exact=True,prepared_only=True,
            success_rollback=True,invalid_plans_rejected=19,error_and_sql_failure_rollback=True,
            state_hash_units_pks_and_counter_diagnostics=True,origin_https_query_csrf=True,
            rollback_control_flow_and_post_readback_gates=True,capability_fingerprint_and_evidence_fail_closed=True))

    def test_capability_actual_gateway_chain_and_source_binding_before_database(self):
        writer=(ROOT/'scripts/phase3o/live_writer.php').read_text(encoding='utf8')
        transport=writer[writer.index('function writerPlans'):writer.index('function insertValues')]
        for invalid in ('PHP_SAPI','PHP_BINARY','is_executable','is_file','/opt/'):
            self.assertNotIn(invalid,transport)
        run=writer[writer.index('function run('):]
        self.assertLess(run.index('requireCapability('),run.index('connection('))
        self.assertLess(run.rindex('requireCapability('),run.index('transactionProof('))
        cap=(ROOT/'scripts/phase3o/capability.php').read_text(encoding='utf8')
        self.assertIn('writerPlans($root,$request',cap)
        self.assertIn("same($plans,$expected,'runtime_golden')",cap)
        self.assertIn('capabilityFingerprint($config)',cap)
        self.assertIn("'probe_already_attempted'",cap)
        for invalid in ('connection(', 'new PDO', 'PHP_BINARY', 'PHP_SAPI'):
            self.assertNotIn(invalid,cap)

    def test_executor_has_no_out_of_scope_write_or_credentials_transport(self):
        writer=(ROOT/'scripts/phase3o/live_writer.php').read_text(encoding='utf8')
        for forbidden in ('UPDATE ', 'UPSERT', 'INSERT IGNORE', 'ALTER TABLE', 'CREATE TABLE', 'TRUNCATE ',
                          'DELETE FROM', '->commit(', 'SET AUTO_INCREMENT', 'INTO m2_schema_migrations',
                          'INTO m2_market_current', 'INTO m2_market_bars'):
            self.assertNotIn(forbidden,writer)
        self.assertIn('GET_LOCK(?,0)',writer)
        self.assertIn('LOCK_EX|LOCK_NB',writer)
        self.assertIn('finally{',writer)
        self.assertIn('$p->rollBack()',writer)
        self.assertIn('foreach([1,2] as $i)',writer)
        self.assertNotIn('password',writer[writer.index('function writerPlans'):writer.index('function insertValues')])
        gateway=(ROOT/'scripts/phase3o/password_gateway.php').read_text(encoding='utf8')
        self.assertIn("'writer_runs'=>0",gateway)
        self.assertLess(gateway.index("if(($_POST['probe']"),gateway.index('$result=run('))
        for name in ('live_writer.php','state_integrity.php','password_gateway.php','self_test.php'):
            lint=subprocess.run(['php','-l',str(ROOT/'scripts/phase3o'/name)],capture_output=True,text=True)
            self.assertEqual(lint.returncode,0,lint.stdout+lint.stderr)


class PortableProcessAdapterTests(unittest.TestCase):
    def setUp(self):
        self.adapter=live.writer.observation

    def reply(self, stdout=None, stderr=b'', code=0):
        if stdout is None:
            stdout=json.dumps(dict(ok=True,result='Grüße'),ensure_ascii=False).encode('utf-8')
        return subprocess.CompletedProcess(['php'],code,stdout,stderr)

    def test_legacy_compatible_api_bytes_input_and_utf8_output(self):
        # This callable rejects all unsupported high-level subprocess options.
        def binary_run(command, *, input, stdout, stderr, timeout):
            self.assertEqual(command,['php',str(self.adapter.HERE/'value_adapter.php')])
            self.assertIs(type(input),bytes)
            self.assertEqual(input,self.adapter.units.compact(dict(operation='identity',value='Grüße')).encode('utf-8'))
            self.assertEqual(stdout,subprocess.PIPE);self.assertEqual(stderr,subprocess.PIPE)
            self.assertEqual(timeout,10)
            return self.reply()
        with patch.object(self.adapter.subprocess,'run',side_effect=binary_run) as run:
            self.assertEqual(self.adapter.shared('identity',value='Grüße'),'Grüße')
            run.assert_called_once()

    def test_nonzero_exit_fails_even_with_success_payload(self):
        with patch.object(self.adapter.subprocess,'run',return_value=self.reply(code=7)):
            with self.assertRaisesRegex(ValueError,'value adapter process failed'):
                self.adapter.shared('identity',value='1')

    def test_utf8_diagnostics_fail_closed(self):
        with patch.object(self.adapter.subprocess,'run',return_value=self.reply(stderr='Störung'.encode('utf-8'))):
            with self.assertRaisesRegex(ValueError,'value adapter diagnostics'):
                self.adapter.shared('identity',value='1')

    def test_invalid_utf8_stdout_and_stderr_are_rejected(self):
        for response in (self.reply(stdout=b'\xff'),self.reply(stderr=b'\xff')):
            with self.subTest(response=response),patch.object(self.adapter.subprocess,'run',return_value=response):
                with self.assertRaises(UnicodeDecodeError):self.adapter.shared('identity',value='1')

    def test_timeout_propagates_without_retry(self):
        with patch.object(self.adapter.subprocess,'run',side_effect=subprocess.TimeoutExpired(['php'],10)) as run:
            with self.assertRaises(subprocess.TimeoutExpired):self.adapter.shared('identity',value='1')
            run.assert_called_once()

    def test_invalid_json_and_adapter_rejection_fail_closed(self):
        for data in (b'bad json',b'{"ok":false,"reason":"invalid identity"}'):
            with self.subTest(data=data),patch.object(self.adapter.subprocess,'run',return_value=self.reply(stdout=data)):
                with self.assertRaises(ValueError):self.adapter.shared('identity',value='1')


if __name__=='__main__':unittest.main()
