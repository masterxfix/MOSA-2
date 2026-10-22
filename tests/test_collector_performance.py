"""Diagnostic-only safety and timing tests. No network, real DB or provider."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import collector_performance as diagnostic


def php(**data):
    result = subprocess.run(['php', str(ROOT/'tests/market_performance_fixture.php')],
                            input=json.dumps(data), text=True, capture_output=True, check=True)
    if result.stderr:
        raise AssertionError('unexpected fixture stderr')
    return json.loads(result.stdout)


class DiagnosticTests(unittest.TestCase):
    def test_write_and_lock_sql_rejected_before_delegate(self):
        for sql in ['INSERT INTO x VALUES(1)', 'UPDATE x SET a=1', 'DELETE FROM x', 'ALTER TABLE x ADD a INT',
                    'SELECT 1; DELETE FROM x', "SELECT GET_LOCK('x',0)", 'SELECT 1 INTO OUTFILE x',
                    'SELECT 1 FOR UPDATE', 'SELECT SLEEP(1)', 'SELECT BENCHMARK(1,1)']:
            for action in ('sql', 'prepare_sql'):
                result = php(action=action, sql=sql)
                self.assertTrue(result['rejected'], sql)
                self.assertEqual(result['calls'], [])
                self.assertEqual(result['writes'], 0)

    def test_commit_exec_and_transaction_changes_are_rejected(self):
        for method in ('exec', 'commit', 'beginTransaction', 'rollBack'):
            result = php(action='forbidden_api', method=method)
            self.assertTrue(result['rejected']); self.assertEqual(result['writes'], 0)

    def test_server_transaction_is_required(self):
        result = php(action='outside_transaction')
        self.assertTrue(result['rejected']); self.assertEqual(result['calls'], [])

    def test_real_runtime_read_shapes_remain_allowed(self):
        for sql in ['SHOW INDEX FROM m2_asset_source_routes', 'SELECT * FROM m2_assets WHERE entity_id=? LIMIT 2']:
            result = php(action='sql', sql=sql)
            self.assertEqual(result['result'], 'allowed')
            self.assertEqual(result['writes'], 0)

    def test_direct_query_and_native_prepare_execute_are_measured_separately(self):
        direct = php(action='phase', prepared=False)['result']['phase']
        native = php(action='phase', prepared=True)['result']['phase']
        self.assertEqual(direct['by_operation']['query']['calls'], 1)
        self.assertEqual(native['by_operation']['prepare']['calls'], 1)
        self.assertEqual(native['by_operation']['execute']['calls'], 1)
        self.assertGreater(direct['pdo_ms'], 1)
        self.assertGreater(native['pdo_ms'], 2)
        for report in (direct, native):
            self.assertEqual(report['returned_rows'], 1)
            self.assertGreaterEqual(report['php_wall_residual_ms'], 0)
            self.assertGreaterEqual(report['php_process_cpu_ms'], 0)
            self.assertGreaterEqual(report['wall_ms'], report['pdo_ms'])
            self.assertNotIn('not_logged', json.dumps(report))
            self.assertNotIn('SELECT', json.dumps(report))

    def test_missing_secret_stops_before_ssh(self):
        with patch.object(diagnostic.shared, 'ssh_client') as ssh:
            result = diagnostic.execute({})
        ssh.assert_not_called()
        self.assertFalse(result['ok'])
        self.assertEqual(result['provider_requests'], 0)
        self.assertEqual(result['business_writes'], 0)
        self.assertIn('MISSING_SECRET', result['failure'])

    def test_public_output_reuses_existing_secret_guard(self):
        for name in diagnostic.shared.SECRETS:
            env = {name:'synthetic-sensitive-value'}
            output = diagnostic.shared.public_text({'ok':True,'data':env[name]}, env)
            self.assertNotIn(env[name], output)
            self.assertFalse(json.loads(output)['ok'])

    def test_diagnostic_workflow_is_manual_and_contains_only_diagnostic_invocation(self):
        text = (ROOT/'.github/archived-workflows/collector-performance.yml').read_text()
        self.assertIn('workflow_dispatch:', text)
        self.assertNotIn('  push:', text); self.assertNotIn('  schedule:', text)
        self.assertIn('python3 scripts/collector_performance.py', text)
        self.assertNotIn('python3 scripts/collector_actions.py', text)
        self.assertNotIn('upload-artifact', text)
        self.assertIn('persist-credentials: false', text)

    def test_simple_select_budget_is_ten_and_no_active_runtime_or_provider_is_called(self):
        text = (ROOT/'scripts/market_collector/performance_diagnostic.php').read_text()
        self.assertIn('for($i=0;$i<10;$i++)', text)
        self.assertEqual(text.count("'SELECT 1 AS probe'"), 2)  # two exclusive branches, 10 executions total
        for forbidden in ["['action'=>'fetch'", 'runtimeRun(', 'MarketBatch\\execute(', 'applyMarketRoutePlan(', 'executePlan(']:
            self.assertNotIn(forbidden, text)


if __name__ == '__main__':
    unittest.main()
