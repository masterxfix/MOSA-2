"""Focused standard-library checks of the isolated 0006 test harness, no database."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import inspect
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
import test_fundamentals_mysql as fixture
import test_collector_persistence_mysql as isolated
import test_fundamentals_schema as contract

class FundamentalsHarnessTests(unittest.TestCase):
    def test_existing_loopback_connector_is_reused_and_closed_without_opt_in(self):
        self.assertIs(fixture.connect,isolated.connect)
        with patch.object(isolated,'ENABLED',False):
            with self.assertRaisesRegex(RuntimeError,'ISOLATED_CI_SERVICE_REQUIRED'):fixture.connect()
        source=inspect.getsource(isolated.connect)
        for text in ('127.0.0.1','3307','mosa2_collector_isolated','ISOLATED_MYSQL8_IDENTITY_REQUIRED'):
            self.assertIn(text,source)
        self.assertNotIn('MOSA_TEST_',inspect.getsource(fixture))
        self.assertNotIn('h29077_mosa2_test',inspect.getsource(fixture))

    def test_sample_rows_cover_five_periods_dimensions_sources_and_exact_values(self):
        ids=set();dedupe=set()
        for asset in (1,42,100):
            for metric in range(5):
                for kind in fixture.PERIODS:
                    for revision in range(fixture.REVISIONS):
                        identity=len(ids)+1;r=fixture.observation(asset,metric,kind,revision,identity)
                        self.assertTrue(contract.checks(contract.OBS,r),(asset,metric,kind,revision))
                        self.assertTrue(contract.checks(contract.CURRENT,fixture.projection(r)))
                        self.assertIsInstance(r['value_decimal'],Decimal)
                        self.assertEqual(r['route_id'],(asset-1)*3+r['source_id'])
                        self.assertEqual(r['fetch_id'],((asset-1)*3+r['source_id']-1)*4+revision+1)
                        self.assertEqual(len(r['dedupe_key']),32)
                        self.assertNotIn(identity,ids);self.assertNotIn(r['dedupe_key'],dedupe)
                        ids.add(identity);dedupe.add(r['dedupe_key'])

    def test_current_read_returns_all_slots_through_bounded_pages(self):
        runner=fixture.FundamentalsMySQLTests()
        rows=[dict(metric_key=f'm{i:03d}',period_type='snapshot') for i in range(250)]
        runner.sql=Mock(side_effect=[rows[:129],rows[128:]])
        d=fixture.read_paths()['A'];result=runner.read('A',d['sql'],d['args'])
        self.assertEqual(result,rows);self.assertEqual(runner.sql.call_count,2)
        call=runner.sql.call_args_list[1]
        self.assertIn('(metric_key,period_type)>(%s,%s)',call.args[0])
        self.assertEqual(call.args[1],(42,'m127','snapshot'))
        self.assertIn('LIMIT 129',call.args[0])

    def test_reject_probe_requires_the_actual_expected_mysql_error(self):
        class Error(Exception):pass
        module=SimpleNamespace(MySQLError=Error)
        for actual in (1452,1062,1064,None):
            runner=fixture.FundamentalsMySQLTests();runner.report={'constraints':[]}
            runner.sql=Mock();runner.insert=Mock(side_effect=Error(actual,'synthetic') if actual else None)
            with patch.dict(sys.modules,{'pymysql':module}):
                if actual==1452:
                    runner.reject('FK',contract.OBS,{},1452)
                    self.assertEqual(runner.report['constraints'][0]['error'],1452)
                else:
                    with self.assertRaises(AssertionError):runner.reject('FK',contract.OBS,{},1452)
            self.assertEqual(runner.sql.call_args_list[-1].args[0],'ROLLBACK TO SAVEPOINT invalid_probe')

    def test_shared_mysql_check_parser_handles_qualified_mysql_rendering(self):
        pair=dict(table='synthetic',name='ck_synthetic',expected="(a = 'decimal' OR b IS NULL) IS TRUE",
                  actual=r"(((`a` = _utf8mb4\'decimal\') or (`b` is null)) is true)",
                  show="CREATE TABLE synthetic (\n CONSTRAINT `ck_synthetic` CHECK ((((`a` = _utf8mb4'decimal') or (`b` is null)) is true))\n)")
        result=fixture.compare_checks([pair]);self.assertTrue(result[0]['equal'],result)
        pair['actual']=pair['actual'].replace('decimal','text')
        self.assertFalse(fixture.compare_checks([pair])[0]['equal'])

    def test_all_seven_read_paths_are_bound_and_hot_path_is_current_only(self):
        paths=fixture.read_paths();self.assertEqual(set(paths),set('ABCDEFG'))
        for code,d in paths.items():
            self.assertNotIn('FORCE INDEX',d['sql'].upper())
            self.assertIn(' WHERE ',d['sql'])
            self.assertTrue(d['args'])
            if code in 'ABCDE':self.assertIn('asset_id=%s',d['sql'])
            if code in 'CDE':
                self.assertIn('metric_key=%s',d['sql']);self.assertIn('period_type=%s',d['sql'])
                self.assertIn('LIMIT 100',d['sql'])
        for code in 'AB':
            self.assertEqual(paths[code]['tables'],{'m2_fundamental_current'})
            self.assertNotRegex(paths[code]['sql'],r'observations|provider_fetches|m2_files')
        self.assertEqual(fixture.ASSETS*fixture.METRICS*len(fixture.PERIODS)*fixture.REVISIONS,100000)
        self.assertEqual((fixture.WARMUPS,fixture.REPEATS),(3,40))

    def test_explain_tree_collects_all_nested_tables(self):
        plan={'query_block':{'nested_loop':[{'table':{'table_name':'o','access_type':'const','key':'PRIMARY'}},
              {'table':{'table_name':'f','access_type':'eq_ref','key':'uq_fetch_source'}}]}}
        self.assertEqual([t['table_name'] for t in fixture.plan_tables(plan)],['o','f'])

    def test_workflow_uses_existing_service_without_production_secrets_or_other_suites(self):
        workflow=(contract.ROOT/'.github/workflows/collector-release-offline.yml').read_text(encoding='utf-8')
        self.assertIn('tradegate-five, fundamentals6, persistence',workflow)
        offline=workflow.split('  offline:',1)[1].split('  persistence:',1)[0]
        self.assertIn("inputs.verification_scope != 'fundamentals6'",offline.split('runs-on:',1)[0])
        persistence=workflow.split('  persistence:',1)[1].split('  backup-permissions:',1)[0]
        for required in ('image: mysql:8.0','127.0.0.1:3307:3306','MYSQL_DATABASE: mosa2_collector_isolated',
                         'test_fundamentals_mysql','retention-days: 7'):
            self.assertIn(required,persistence)
        self.assertNotIn('secrets.',persistence)
        self.assertEqual(persistence.count("if: inputs.verification_scope != 'fundamentals6'"),3)
        self.assertIn("if: inputs.verification_scope == 'fundamentals6'",persistence)
        live=workflow.split('  migration5-readonly:',1)[1]
        self.assertIn("inputs.verification_scope == 'migration5' && inputs.read_preflight",live)

    def test_migrations_are_exact_and_no_ledger_history_is_fabricated(self):
        self.assertEqual(fixture.DDL_NAMES,list(contract.OLD)+['0006_fundamentals_and_payload_provenance.sql'])
        source=inspect.getsource(fixture.FundamentalsMySQLTests.apply)
        self.assertNotIn('INSERT INTO m2_schema_migrations',source)
        self.assertIn("self.assertEqual(len(self.show_all()),26)",source)
        for name,digest in contract.OLD.items():
            self.assertEqual(hashlib.sha256((contract.MIGRATIONS/name).read_bytes()).hexdigest(),digest)


    def test_empty_table_guard_accepts_both_cursor_containers_and_blocks_any_table(self):
        class BeforeDDL(Exception):pass
        for tables in ([],(),[{'Tables_in_service':'unexpected'}],({'Tables_in_service':'unexpected'},)):
            runner=fixture.FundamentalsMySQLTests();runner.report={};calls=[]
            def query(sql,args=()):
                calls.append(sql)
                if sql=='SELECT VERSION() AS version':return [dict(version='8.0.synthetic')]
                if sql=='SHOW TABLES':return tables
                raise BeforeDDL('No actual database or DDL in this offline probe')
            runner.sql=query
            if tables:
                with self.assertRaisesRegex(AssertionError,'Service database must be initially empty'):runner.apply()
                self.assertFalse(any(sql.startswith('CREATE TABLE') for sql in calls))
            else:
                with self.assertRaises(BeforeDDL):runner.apply()
                self.assertTrue(calls[-1].startswith('CREATE TABLE'))
            self.assertEqual(runner.report['mysql_version'],'8.0.synthetic')

if __name__=='__main__':unittest.main()
