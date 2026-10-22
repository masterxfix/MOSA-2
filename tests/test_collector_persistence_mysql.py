"""Destructive fixtures ONLY in the ephemeral, loopback GitHub MySQL service.

Never imports a project connection helper, Dogado configuration or credentials.
Skipped everywhere else. Each connection has finite socket/lock timeouts.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from threading import Barrier
import unittest
from uuid import uuid4

from scripts import collector_persistence as persistence
from test_collector_cycle import fixture, NOW, ASSETS

ROOT = Path(__file__).resolve().parents[1]
ENABLED = os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("MOSA2_ISOLATED_MYSQL") == "1"


def connect():
    if not ENABLED:
        raise RuntimeError("ISOLATED_CI_SERVICE_REQUIRED")
    import pymysql
    c = pymysql.connect(host="127.0.0.1", port=3307, user="root", password="",
                        database="mosa2_collector_isolated", autocommit=False,
                        cursorclass=pymysql.cursors.DictCursor, connect_timeout=3,
                        read_timeout=5, write_timeout=5, charset="utf8mb4")
    with c.cursor() as q:
        q.execute("SELECT VERSION() AS version, DATABASE() AS db")
        identity = q.fetchone()
        if not identity["version"].startswith("8.0.") or identity["db"] != "mosa2_collector_isolated":
            c.close()
            raise RuntimeError("ISOLATED_MYSQL8_IDENTITY_REQUIRED")
    c.rollback()
    return c


class LostCommit:
    """Inject loss of main commit acknowledgement, either side of actual COMMIT."""
    def __init__(self, c, commit_applied):
        self.c = c; self.commit_applied = commit_applied; self.commits = 0

    def __getattr__(self, key):
        return getattr(self.c, key)

    def commit(self):
        self.commits += 1
        # _connection initialization is first, reservation main commit second.
        if self.commits == 2:
            if self.commit_applied:
                self.c.commit()
            raise OSError("SYNTHETIC_LOST_ACK secret SQL must never escape")
        return self.c.commit()


@unittest.skipUnless(ENABLED, "temporary GitHub MySQL8 service only")
class MySQLPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with connect() as c:
            with c.cursor() as q:
                for path in sorted((ROOT/"docs/database/migrations").glob("000[1-5]_*.sql")):
                    # Migrations contain ordinary statements, no stored programs.
                    sql = "\n".join(line for line in path.read_text().splitlines() if not line.lstrip().startswith("--"))
                    for statement in sql.split(";"):
                        if statement.strip():
                            q.execute(statement)
                for index, isin in enumerate(ASSETS, 1):
                    q.execute("INSERT INTO m2_entities (id,entity_type,canonical_name,status,created_at,updated_at) VALUES (%s,'asset','SYNTHETIC','active',UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))", (index,))
                    q.execute("INSERT INTO m2_assets (entity_id,asset_class,display_name,status,created_at,updated_at) VALUES (%s,'equity','SYNTHETIC','active',UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))", (index,))
                    q.execute("INSERT INTO m2_asset_identifiers (asset_id,identifier_type,identifier_value,normalized_value,is_primary,created_at) VALUES (%s,'isin',%s,%s,1,UTC_TIMESTAMP(6))", (index, isin, isin))
            c.commit()

    def sql(self, statement, args=()):
        with connect() as c:
            with c.cursor() as q:
                q.execute(statement, args)
                rows = q.fetchall() if q.description else []
            c.commit()
            return rows

    def setUp(self):
        self.sql("UPDATE m2_collector_state SET active_cycle=NULL,last_confirmed_cycle=NULL,pending_asset=NULL,operation_token=NULL")
        self.sql("DELETE FROM m2_collector_requests")
        self.sql("DELETE FROM m2_collector_cycles")
        self.sql("DELETE FROM m2_collector_days")
        self.sql("UPDATE m2_collector_state SET status='IDLE',stop_latched=0,unresolved=0,last_observed_utc=NULL,error_code='NONE'")
        self.sql("UPDATE m2_jobs SET enabled=0 WHERE job_key='collector_reservations_v1'")
        self.sql("UPDATE m2_module_state SET schema_version=5,status='LOCKED' WHERE module_key='collector_reservations'")
        self.now = NOW
        self.data = fixture(self.now)
        self.owner = str(uuid4())
        self.adapter = persistence.Store(connect, test_clock=lambda: self.now)

    def start(self):
        result = self.adapter.begin(self.data, self.owner)
        self.assertEqual(result["code"], "CYCLE_COMMITTED", result)
        self.cid = result["cycle_id"]
        return result

    def reserve(self, index=0, adapter=None):
        return (adapter or self.adapter).reserve(self.cid, self.owner, ASSETS[index], self.data)

    def final(self, index=0, outcome="SUCCESS", attempted=True):
        return self.adapter.record(self.cid, self.owner, ASSETS[index], outcome, attempt_confirmed=attempted)

    def five(self):
        for i in range(5):
            result = self.reserve(i)
            self.assertEqual(result["code"], "RESERVATION_COMMITTED", result)
            self.assertFalse(result["execution_authorized"])
            self.assertEqual(result["actual_provider_requests"], 0)
            self.assertEqual(result["used_day"], i+1)
            result = self.final(i)
            self.assertEqual(result["code"], "FINAL_COMMITTED", result)
        self.assertEqual(result["status"], "COMPLETE")

    def test_initial_migration_is_locked_and_missing_state_blocks(self):
        self.sql("UPDATE m2_collector_state SET stop_latched=1,error_code='INITIAL_LOCK'")
        self.assertEqual(self.adapter.begin(self.data, self.owner)["error_code"], "STOP_LATCHED")
        self.sql("DELETE FROM m2_collector_state")
        self.assertEqual(self.adapter.begin(self.data, self.owner)["error_code"], "STATE_INVALID")
        self.sql("INSERT INTO m2_collector_state (provider,job_id) SELECT %s,id FROM m2_jobs WHERE job_key='collector_reservations_v1'", (persistence.PROVIDER,))

    def test_five_sequential_synthetic_requests_and_sixth_denied(self):
        self.start(); self.five()
        self.assertEqual(self.reserve()["code"], "BLOCKED")
        rows = self.sql("SELECT COUNT(*) AS n,SUM(attempt_confirmed) AS attempts FROM m2_collector_requests")
        self.assertEqual(int(rows[0]["n"]), 5); self.assertEqual(int(rows[0]["attempts"]), 5)
        self.assertEqual(self.adapter.inspect()["status"], "COMPLETE")

    def test_restart_keeps_reserved_quota_and_blocks_replay(self):
        self.start(); self.assertEqual(self.reserve()["code"], "RESERVATION_COMMITTED")
        restarted = persistence.Store(connect, test_clock=lambda: self.now)
        self.assertEqual(restarted.inspect()["status"], "OUTCOME_UNKNOWN")
        self.assertEqual(self.reserve(adapter=restarted)["error_code"], "OPEN_OR_UNKNOWN_REQUEST")
        self.assertEqual(restarted.begin(self.data, str(uuid4()))["code"], "BLOCKED")
        self.assertEqual(self.sql("SELECT reserved_count FROM m2_collector_days")[0]["reserved_count"], 1)

    def test_duplicate_cycle_after_complete_and_restart(self):
        self.start(); self.five()
        self.assertEqual(self.adapter.begin(self.data, str(uuid4()))["code"], "BLOCKED")
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM m2_collector_cycles")[0]["n"], 1)

    def test_independent_connections_parallel_same_request(self):
        self.start()
        barrier = Barrier(2)
        def attempt():
            independent = persistence.Store(connect, test_clock=lambda: self.now)
            barrier.wait(timeout=5)
            return independent.reserve(self.cid, self.owner, ASSETS[0], self.data)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: attempt(), range(2)))
        self.assertEqual(sum(r["code"] == "RESERVATION_COMMITTED" for r in results), 1, results)
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM m2_collector_requests")[0]["n"], 1)
        self.assertEqual(self.sql("SELECT reserved_count FROM m2_collector_days")[0]["reserved_count"], 1)

    def test_parallel_same_cycle_start(self):
        barrier = Barrier(2)
        def start():
            other = persistence.Store(connect, test_clock=lambda: self.now)
            barrier.wait(timeout=5)
            return other.begin(self.data, str(uuid4()))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: start(), range(2)))
        self.assertEqual(sum(r["code"] == "CYCLE_COMMITTED" for r in results), 1, results)

    def test_duplicate_asset_and_owner_mismatch(self):
        self.start(); self.reserve(); self.final()
        self.assertEqual(self.reserve()["error_code"], "DUPLICATE_OR_OUT_OF_ORDER")
        result = self.adapter.reserve(self.cid, str(uuid4()), ASSETS[1], self.data)
        self.assertEqual(result["error_code"], "OWNER_OR_CYCLE_MISMATCH")

    def test_minute_exhaustion_cannot_be_reset_with_injected_usage(self):
        self.start(); self.five()
        self.now += timedelta(seconds=60)
        # Exact 60-second boundary is outside the rolling window.
        self.data = fixture(self.now); self.owner = str(uuid4()); self.start()
        self.reserve(); self.final()
        self.now += timedelta(seconds=1)
        # Last 59s: four older entries + current one => full minute.
        stamp = persistence.sql_time(self.now-timedelta(seconds=59))
        self.sql("UPDATE m2_collector_requests SET reserved_utc=%s,finished_utc=%s WHERE cycle_id<>%s", (stamp, stamp, self.cid))
        self.data["evidence"]["budget_state"]["used_60s"] = 0
        result = self.reserve(1)
        self.assertEqual(result["error_code"], "BUDGET_OR_BASELINE_BLOCKED", result)

    def test_day_exhaustion(self):
        self.data["budget_config"]["providers"][persistence.PROVIDER]["limits"]["mosa2_per_day"] = 5
        self.start(); self.five()
        self.now += timedelta(seconds=60); self.data["now"] = self.now.isoformat()
        for item in (self.data["evidence"]["qualification"], self.data["evidence"]["mosa_baseline"], self.data["evidence"]["monitoring_previous"], self.data["evidence"]["monitoring_event"]):
            item["checked_at"] = self.now.isoformat()
        self.assertEqual(self.adapter.begin(self.data, str(uuid4()))["code"], "BLOCKED")
        self.assertEqual(self.sql("SELECT reserved_count FROM m2_collector_days")[0]["reserved_count"], 5)

    def test_berlin_day_change_preserves_previous_day_and_rolling_minute(self):
        self.now = datetime.fromisoformat("2026-10-21T21:59:00+00:00")
        self.data = fixture(self.now); self.start(); self.five()
        self.now += timedelta(minutes=1); self.data = fixture(self.now); self.owner = str(uuid4()); self.start()
        self.assertEqual(self.reserve()["used_day"], 1)
        days = self.sql("SELECT berlin_day,reserved_count FROM m2_collector_days ORDER BY berlin_day")
        self.assertEqual([r["reserved_count"] for r in days], [5, 1])

    def test_dst_spring_and_autumn_utc_reservations(self):
        for before, after in (("2026-03-29T00:45:00Z", "2026-03-29T01:00:00Z"), ("2026-10-25T00:45:00Z", "2026-10-25T01:00:00Z")):
            self.setUp()
            self.now = datetime.fromisoformat(before); self.data = fixture(self.now); self.start(); self.five()
            old_cid = self.cid
            self.now = datetime.fromisoformat(after); self.data = fixture(self.now); self.owner = str(uuid4()); self.start()
            self.assertNotEqual(self.cid, old_cid)
            self.assertEqual(self.reserve()["used_day"], 6)

    def test_incomplete_baseline_and_unknown_limits_no_reservation(self):
        for key in ("baseline", "limits"):
            data = deepcopy(self.data)
            if key == "baseline":
                del data["evidence"]["mosa_baseline"]["used_day"]
            else:
                data["budget_config"]["providers"][persistence.PROVIDER]["documented_provider_limit"] = None
            self.assertEqual(self.adapter.begin(data, self.owner)["code"], "BLOCKED")
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM m2_collector_requests")[0]["n"], 0)

    def test_baseline_must_be_fresh_for_each_reservation(self):
        self.start(); self.now += timedelta(seconds=31)
        # Refresh qualification/monitoring, deliberately leave baseline stale.
        for key in ("qualification", "monitoring_previous", "monitoring_event"):
            self.data["evidence"][key]["checked_at"] = self.now.isoformat()
        self.assertEqual(self.reserve()["error_code"], "BUDGET_OR_BASELINE_BLOCKED")

    def test_sticky_stop_after_failed_attempt_and_no_restart(self):
        self.start(); self.reserve()
        self.assertEqual(self.final(outcome="FAILED")["status"], "FAILED")
        restarted = persistence.Store(connect, test_clock=lambda: self.now)
        self.assertTrue(restarted.inspect()["stop_latched"])
        self.assertEqual(self.reserve(adapter=restarted)["error_code"], "STOP_LATCHED")
        self.assertEqual(self.sql("SELECT reserved_count FROM m2_collector_days")[0]["reserved_count"], 1)

    def test_partial_failure_and_missing_final_timeout_stay_unknown(self):
        for outcome in ("FAILED", "TIMEOUT", "MISSING_FINAL"):
            self.setUp(); self.start(); self.reserve(); self.final(); self.reserve(1)
            result = self.final(1, outcome)
            self.assertEqual(result["status"], "PARTIAL_FAILED" if outcome == "FAILED" else "OUTCOME_UNKNOWN")
            self.assertTrue(self.adapter.inspect()["stop_latched"])
            self.assertEqual(self.reserve(2)["code"], "BLOCKED")

    def test_unknown_predecessor_and_crash_before_first_reservation(self):
        self.start()
        restarted = persistence.Store(connect, test_clock=lambda: self.now)
        self.assertEqual(restarted.begin(self.data, str(uuid4()))["error_code"], "ACTIVE_OR_UNKNOWN_PREDECESSOR")
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM m2_collector_requests")[0]["n"], 0)

    def test_real_transaction_rollback_after_reservation_insert(self):
        self.start()
        class Crash(persistence.Store):
            def _usage(inner, q, now):
                result = super()._usage(q, now)
                # Error after first DB write inside the reservation transaction.
                q.execute("INSERT INTO m2_collector_days VALUES (%s,%s,1)", (persistence.PROVIDER, now.date()))
                raise RuntimeError("SYNTHETIC_CRASH")
        crashed = Crash(connect, test_clock=lambda: self.now)
        result = self.reserve(adapter=crashed)
        self.assertEqual(result["error_code"], "TRANSACTION_ROLLED_BACK")
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM m2_collector_days")[0]["n"], 0)
        self.assertEqual(self.adapter.inspect()["status"], "OUTCOME_UNKNOWN")
        self.assertEqual(self.reserve()["error_code"], "UNRESOLVED_OPERATION")

    def test_unknown_commit_before_and_after_server_commit_keeps_guard(self):
        for applied in (False, True):
            self.setUp(); self.start()
            calls = 0
            def factory():
                nonlocal calls
                calls += 1
                return LostCommit(connect(), applied) if calls == 2 else connect()
            unknown = persistence.Store(factory, test_clock=lambda: self.now)
            result = self.reserve(adapter=unknown)
            self.assertEqual(result["code"], "OUTCOME_UNKNOWN", result)
            self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM m2_collector_requests")[0]["n"], int(applied))
            self.assertEqual(self.adapter.inspect()["status"], "OUTCOME_UNKNOWN")
            self.assertEqual(self.reserve()["error_code"], "UNRESOLVED_OPERATION")
            self.assertEqual(calls, 2)  # No implicit reconnect/retry/recovery write.

    def test_unknown_final_commit_cannot_hide_behind_complete_cycle(self):
        self.start()
        for index in range(4):
            self.reserve(index); self.final(index)
        self.reserve(4)
        calls = 0
        def factory():
            nonlocal calls
            calls += 1
            return LostCommit(connect(), True) if calls == 2 else connect()
        unknown = persistence.Store(factory, test_clock=lambda: self.now)
        result = unknown.record(self.cid, self.owner, ASSETS[4], "SUCCESS", attempt_confirmed=True)
        self.assertEqual(result["code"], "OUTCOME_UNKNOWN")
        self.assertEqual(self.sql("SELECT status FROM m2_collector_cycles")[0]["status"], "COMPLETE")
        self.assertEqual(self.adapter.inspect()["status"], "OUTCOME_UNKNOWN")
        self.now += timedelta(minutes=1); self.data = fixture(self.now)
        self.assertEqual(self.adapter.begin(self.data, str(uuid4()))["error_code"], "UNRESOLVED_OPERATION")

    def test_database_unique_key_rejects_direct_duplicate(self):
        import pymysql
        self.start(); self.reserve()
        with self.assertRaises(pymysql.IntegrityError):
            self.sql("INSERT INTO m2_collector_requests SELECT * FROM m2_collector_requests")
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM m2_collector_requests")[0]["n"], 1)

    def test_no_unauthorized_grant_or_policy_change(self):
        self.start()
        self.data["budget_config"]["execution_enabled"] = True
        self.assertEqual(self.reserve()["error_code"], "POLICY_CHANGED")
        self.sql("UPDATE m2_jobs SET enabled=1 WHERE job_key='collector_reservations_v1'")
        self.assertEqual(self.reserve()["error_code"], "STATE_INVALID")

    def test_corrupt_counter_and_clock_regression_block(self):
        self.start(); self.reserve(); self.final()
        self.sql("UPDATE m2_collector_days SET reserved_count=0")
        self.assertEqual(self.reserve(1)["error_code"], "STATE_INVALID")
        self.now -= timedelta(seconds=1)
        self.assertEqual(self.reserve(1)["error_code"], "CLOCK_REGRESSION")


if __name__ == "__main__":
    unittest.main()
