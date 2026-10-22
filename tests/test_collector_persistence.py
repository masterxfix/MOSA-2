"""Offline failure boundaries; real SQL/locking is tested separately on MySQL."""
import ast
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, MagicMock
from uuid import uuid4

from scripts import collector_persistence as store
from test_collector_cycle import fixture, decide, NOW

ROOT = Path(__file__).resolve().parents[1]


class OfflinePersistenceTests(unittest.TestCase):
    def transaction(self, *, commit_error=False, rollback_error=False, action_error=False):
        c = MagicMock()
        adapter = store.Store(Mock(return_value=c))
        adapter._guard = Mock(return_value="intent")
        adapter._connection = Mock(return_value=c)
        adapter._lock = Mock(return_value=dict(operation_token="intent", stop_latched=0))
        adapter._now = Mock(return_value=NOW)
        adapter._release = Mock()
        if commit_error:
            c.commit.side_effect = RuntimeError("secret password SQL private/path")
        if rollback_error:
            c.rollback.side_effect = RuntimeError("private rollback")
        action = Mock(side_effect=RuntimeError("secret password SQL private/path")) if action_error else Mock(return_value=store.answer("RESERVATION_COMMITTED"))
        result = adapter._transaction(action)
        return adapter, c, action, result

    def test_acknowledged_commit_precedes_guard_release(self):
        adapter, c, action, result = self.transaction()
        self.assertEqual(result["code"], "RESERVATION_COMMITTED")
        c.commit.assert_called_once(); adapter._release.assert_called_once_with("intent")
        action.assert_called_once(); c.close.assert_called_once()
        self.assertFalse(result["execution_authorized"])

    def test_unknown_commit_keeps_intent_and_no_retry(self):
        adapter, c, action, result = self.transaction(commit_error=True)
        self.assertEqual(result["code"], "OUTCOME_UNKNOWN")
        self.assertEqual(result["error_code"], "COMMIT_UNKNOWN")
        adapter._release.assert_not_called(); action.assert_called_once()
        c.commit.assert_called_once(); c.rollback.assert_not_called()
        self.assertTrue(adapter.poisoned)

    def test_proven_rollback_keeps_barrier_and_no_quota_release(self):
        adapter, c, action, result = self.transaction(action_error=True)
        self.assertEqual(result["error_code"], "TRANSACTION_ROLLED_BACK")
        c.rollback.assert_called_once(); c.commit.assert_not_called()
        adapter._release.assert_not_called()

    def test_rollback_exception_is_unknown(self):
        adapter, c, action, result = self.transaction(action_error=True, rollback_error=True)
        self.assertEqual(result["code"], "OUTCOME_UNKNOWN")
        adapter._release.assert_not_called()

    def test_crash_after_commit_before_guard_release(self):
        c = MagicMock(); adapter = store.Store(lambda: c)
        adapter._guard = Mock(return_value="intent"); adapter._connection = Mock(return_value=c)
        adapter._lock = Mock(return_value=dict(operation_token="intent", stop_latched=0))
        adapter._now = Mock(return_value=NOW)
        adapter._release = Mock(side_effect=RuntimeError("lost connection"))
        result = adapter._transaction(lambda *args: store.answer("FINAL_COMMITTED"))
        self.assertEqual(result["code"], "OUTCOME_UNKNOWN")
        c.commit.assert_called_once()

    def test_unknown_guard_commit_does_not_attempt_main_transaction(self):
        adapter = store.Store(Mock())
        adapter._guard = Mock(side_effect=store.Blocked("COMMIT_UNKNOWN"))
        action = Mock()
        self.assertEqual(adapter._transaction(action)["code"], "OUTCOME_UNKNOWN")
        action.assert_not_called(); adapter.factory.assert_not_called()

    def test_cleanup_error_does_not_replace_fixed_diagnostic(self):
        c = Mock(); c.close.side_effect = RuntimeError("private/path secret")
        persistence_error = store.close(c)
        self.assertIsNone(persistence_error)

    def test_no_diagnostics_leak_exception(self):
        for kwargs in (dict(commit_error=True), dict(action_error=True), dict(action_error=True, rollback_error=True)):
            result = self.transaction(**kwargs)[-1]
            encoded = json.dumps(result)
            for forbidden in ("secret", "password", "SQL", "private/path", "rollback"):
                self.assertNotIn(forbidden, encoded)

    def test_berlin_days_have_correct_dst_lengths(self):
        for stamp, hours in (("2026-03-29T12:00:00Z", 23), ("2026-10-25T12:00:00Z", 25), ("2026-10-22T12:00:00Z", 24)):
            day, start, end = store.day_bounds(datetime.fromisoformat(stamp))
            self.assertEqual((end-start).total_seconds(), hours*3600)
            self.assertEqual(start.tzinfo, timezone.utc)

    def test_rolling_minute_crosses_day_and_dst(self):
        for stamp in ("2026-10-21T22:00:00Z", "2026-03-29T01:00:00Z", "2026-10-25T01:00:00Z"):
            now = datetime.fromisoformat(stamp)
            self.assertEqual((store.sql_time(now)-store.sql_time(now-timedelta(seconds=60))).total_seconds(), 60)

    def test_policy_changes_invalidate_hash_no_mutation(self):
        data = fixture(); before = deepcopy(data)
        digest = store.policy_hash(data)
        self.assertEqual(data, before)
        data["budget_config"]["execution_enabled"] = True
        self.assertNotEqual(digest, store.policy_hash(data))
        self.assertEqual(decide(before)["decision"], "RUN_ELIGIBLE")

    def test_no_connection_starter_transport_or_grant_api(self):
        tree = ast.parse((ROOT/"scripts/collector_persistence.py").read_text())
        imports = [n.names[0].name for n in ast.walk(tree) if isinstance(n, ast.Import)]
        self.assertEqual(set(imports), {"hashlib", "json"})
        for name in ("reset", "resume", "enable", "retry", "connect", "execute_provider"):
            self.assertFalse(hasattr(store.Store, name))
        for path in ("collector-operation.json", "collector-provider-budget.json"):
            config = json.loads((ROOT/"config"/path).read_text())
            self.assertIs(config["execution_enabled"], False)
            for provider in config.get("providers", {}).values():
                self.assertIs(provider["rights_confirmed"], False)

    def test_invalid_missing_state_readback_is_unknown(self):
        c = MagicMock(); c.cursor.return_value.__enter__.return_value.fetchone.return_value = None
        adapter = store.Store(lambda: c); adapter._connection = Mock(return_value=c)
        result = adapter.inspect()
        self.assertEqual(result["code"], "OUTCOME_UNKNOWN")
        self.assertTrue(result["stop_latched"])

    def test_owner_must_be_canonical_uuid(self):
        self.assertEqual(store.owner_token(str(uuid4())).__class__, str)
        for bad in ("", "private/path", "secret", None):
            with self.assertRaises((ValueError, store.Blocked)):
                store.owner_token(bad)

    def test_migration_constraints_and_locked_bootstrap(self):
        schema = (ROOT/"docs/database/migrations/0005_collector_reservations.sql").read_text()
        self.assertEqual(schema.count("ENGINE=InnoDB"), 4)
        for contract in ("PRIMARY KEY (cycle_id, asset_id)", "uq_collector_request_order", "fk_collector_request_asset", "DEFAULT 1", "'UNWIRED',0", "5,'LOCKED'", "DATETIME(6)"):
            self.assertIn(contract, schema)


if __name__ == "__main__":
    unittest.main()
