"""Operating plans only: all clocks, qualifications and receipts are synthetic."""
import ast
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest
from scripts import collector_operation_plan as plan

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 21, 10, tzinfo=timezone.utc)
A, B = "DE000A0JBPG2", "DE0005313704"


def fixture(now=NOW):
    stamp = now.isoformat()
    local = now.astimezone(plan.ZONE).date().isoformat()
    c = json.loads((ROOT / "config/collector-operation.json").read_text())
    c.update(execution_enabled=True, selection=[A, B], venue="XFRA",
             weekdays=[0, 1, 2, 3, 4], windows=[{"start": "09:00", "end": "17:00"}],
             interval_seconds=300, max_duration_seconds=240,
             evidence_max_age_seconds=30, freshness_seconds=900,
             provider_budget={"per_run": 2, "per_day": 20},
             calendar={"approved": True, "source": "synthetic-test-only", "version": "test-1",
                       "valid_from": "2026-01-01", "valid_until": "2026-12-31",
                       "open_dates": [local], "closed_dates": []})
    state = dict(checked_at=stamp, active=False, unresolved=False, seen_run_ids=[],
                 last_status="IDLE", last_started_at=None, provider_budget_date=local, provider_requests_used=0)
    q = dict(checked_at=stamp, contract="mosa2-operation-qualification-v1",
             selection=[A, B], venue="XFRA", policy="USE_EXISTING_ROUTE", asset_class="equity", all_qualified=True)
    return c, state, q


def receipt(run="test-one", status="COMPLETE", stage=None):
    return dict(run_id=run, started_at="2026-10-21T09:55:00Z", completed_at="2026-10-21T09:56:00Z",
                receipt={"batch": dict(overall_status=status, requested_count=1, started_count=1,
                    completed_count=1 if status == "COMPLETE" else 0, provider_requests=1,
                    insert_count=1, duplicate_unchanged_count=0, local_batch_ms=4310,
                    item_results=[dict(asset_identity=A, status="COMPLETE" if status == "COMPLETE" else "FAILED",
                        writer="INSERT", observation_id=4909, failure_stage=stage,
                        metrics=dict(collector_ms=4310, provider_ms=162, database_check_ms=372))])})


class PlanningTests(unittest.TestCase):
    def decision(self, c=None, s=None, q=None, now=NOW, run="next-run"):
        a, b, d = fixture(now)
        return plan.decide(c if c is not None else a, s if s is not None else b,
                           q if q is not None else d, now, run)

    def test_repository_defaults_disabled_no_implicit_permissions(self):
        c = json.loads((ROOT / "config/collector-operation.json").read_text())
        self.assertEqual(self.decision(c=c), "SKIP")
        for key in ("calendar", "venue", "interval_seconds", "max_duration_seconds"):
            self.assertIsNone(c[key])
        self.assertEqual(c["selection"], [])
        c["execution_enabled"] = True
        self.assertEqual(self.decision(c=c), "BLOCKED")

    def test_eligible_simulation_never_executes(self):
        self.assertEqual(self.decision(), "RUN_ELIGIBLE")

    def test_registered_etf_uses_the_same_qualified_plan(self):
        c, state, qualification = fixture()
        qualification["asset_class"] = "etf"
        self.assertEqual(self.decision(c, state, qualification), "RUN_ELIGIBLE")
        qualification["all_qualified"] = False
        self.assertEqual(self.decision(c, state, qualification), "BLOCKED")

    def test_valid_and_invalid_window_boundaries(self):
        for hour, minute, expected in [(6, 59, "SKIP"), (7, 0, "RUN_ELIGIBLE"), (14, 59, "RUN_ELIGIBLE"), (15, 0, "SKIP")]:
            now = NOW.replace(hour=hour, minute=minute)
            self.assertEqual(self.decision(now=now), expected)
        for windows in ([], [{"start": "17:00", "end": "09:00"}], [{"start": "09:00", "end": "25:00"}],
                        [{"start": "09:00", "end": "12:00"}, {"start": "11:00", "end": "17:00"}]):
            c, _, _ = fixture()
            c["windows"] = windows
            self.assertEqual(self.decision(c=c), "BLOCKED")

    def test_weekend_and_explicit_holiday_closed(self):
        self.assertEqual(self.decision(now=NOW.replace(day=24)), "SKIP")
        c, s, q = fixture()
        c["calendar"].update(open_dates=[], closed_dates=["2026-10-21"])
        self.assertEqual(self.decision(c, s, q), "SKIP")

    def test_missing_calendar_coverage_never_grants_trade(self):
        for change in ({"approved": False}, {"open_dates": []}, {"valid_until": "2026-10-20", "open_dates": []},
                       {"closed_dates": ["2026-10-21"]}):
            c, s, q = fixture()
            c["calendar"].update(change)
            self.assertEqual(self.decision(c, s, q), "BLOCKED")
        c, s, q = fixture()
        c["calendar"] = None
        self.assertEqual(self.decision(c, s, q), "BLOCKED")

    def test_berlin_summer_winter_and_dst_sundays(self):
        # 07:30 UTC is 09:30 in summer, but 08:30 in winter.
        for month, day, expected in [(7, 1, "RUN_ELIGIBLE"), (1, 21, "SKIP")]:
            self.assertEqual(self.decision(now=NOW.replace(month=month, day=day, hour=7, minute=30)), expected)
        for month, day in [(3, 29), (10, 25)]:
            for hour in (0, 1, 2):
                self.assertEqual(self.decision(now=NOW.replace(month=month, day=day, hour=hour)), "SKIP")
        self.assertEqual(self.decision(now=NOW.replace(tzinfo=None)), "BLOCKED")

    def test_due_uses_absolute_elapsed_time(self):
        c, s, q = fixture()
        s.update(last_status="COMPLETE", last_started_at=(NOW - timedelta(seconds=299)).isoformat())
        self.assertEqual(self.decision(c, s, q), "SKIP")
        s["last_started_at"] = (NOW - timedelta(seconds=300)).isoformat()
        self.assertEqual(self.decision(c, s, q), "RUN_ELIGIBLE")
        s["last_started_at"] = (NOW + timedelta(seconds=1)).isoformat()
        self.assertEqual(self.decision(c, s, q), "BLOCKED")

    def test_duplicate_active_lock_unknown_and_failure_stop(self):
        c, s, q = fixture()
        for change in ({"seen_run_ids": ["next-run"]}, {"active": True}, {"active": None},
                       {"unresolved": True}, {"unresolved": None},
                       {"last_status": "OUTCOME_UNKNOWN"}, {"last_status": "PARTIAL_FAILED"}, {"last_status": "FAILED"}):
            altered = s | change
            self.assertEqual(self.decision(c, altered, q), "BLOCKED")

    def test_stale_and_incomplete_evidence(self):
        c, s, q = fixture()
        for evidence in (s, q):
            for stamp in ((NOW-timedelta(seconds=31)).isoformat(), (NOW+timedelta(seconds=1)).isoformat(), "invalid"):
                altered = deepcopy(evidence)
                altered["checked_at"] = stamp
                args = (c, altered, q) if evidence is s else (c, s, altered)
                self.assertEqual(self.decision(*args), "BLOCKED")
        s.pop("unresolved")
        self.assertEqual(self.decision(c, s, q), "BLOCKED")

    def test_unqualified_equity_route_venue_and_order(self):
        c, s, q = fixture()
        for change in ({"asset_class": "unqualified"}, {"all_qualified": False}, {"all_qualified": 1},
                       {"venue": "XXXX"}, {"policy": "CREATE_ROUTE"}, {"selection": [B, A]}):
            self.assertEqual(self.decision(c, s, q | change), "BLOCKED")

    def test_invalid_selections_and_size_limit(self):
        for values in ([], [A, A], ["invalid"], [A]*11):
            c, _, _ = fixture()
            c["selection"] = values
            self.assertEqual(self.decision(c=c), "BLOCKED")
        c, _, _ = fixture()
        c["max_batch_size"] = 11
        self.assertEqual(self.decision(c=c), "BLOCKED")

    def test_one_two_five_ten_assets_use_same_decision(self):
        for count in (1, 2, 5, 10):
            c, s, q = fixture()
            values = ["DE" + str(i).zfill(10) for i in range(count)]
            c["selection"] = values
            q["selection"] = values
            c["provider_budget"] = {"per_run": 10, "per_day": 20}
            self.assertEqual(self.decision(c,s,q), "RUN_ELIGIBLE")
        # Existing qualification validates checksum/identity; this planner does not query DB.

    def test_budget_unknown_exhausted_and_zero(self):
        c, s, q = fixture()
        for change in ({"provider_requests_used": 19}, {"provider_requests_used": None}, {"provider_budget_date": "2026-10-20"}):
            self.assertEqual(self.decision(c, s | change, q), "BLOCKED")
        for budget in ({"per_run": 1, "per_day": 20}, {"per_run": 2, "per_day": 0}):
            altered = deepcopy(c)
            altered["provider_budget"] = budget
            self.assertEqual(self.decision(altered, s, q), "BLOCKED")

    def test_malformed_input_safe_closed_and_no_mutation(self):
        c, s, q = fixture()
        before = deepcopy((c, s, q))
        for value in (None, [], {}, "secret-canary"):
            self.assertEqual(self.decision(c=value) if value is not None else plan.decide(value,s,q,NOW,"run"), "BLOCKED")
        self.decision(c, s, q)
        self.assertEqual((c, s, q), before)
        self.assertEqual(self.decision(c, s, q, run="../secret"), "BLOCKED")


class MonitoringTests(unittest.TestCase):
    def test_existing_batch_receipt_shape_and_last_success(self):
        good = receipt()
        failed = receipt("test-two", "PARTIAL_FAILED", "provider")
        failed["started_at"] = "2026-10-21T09:57:00Z"
        failed["completed_at"] = "2026-10-21T09:58:00Z"
        result = plan.monitoring([failed, good], NOW, 900)
        self.assertEqual(result["last_successful_run"]["run_id"], "test-one")
        self.assertEqual(result["last_started_run"]["run_id"], "test-two")
        self.assertEqual(result["status"], "PARTIAL_FAILED")
        self.assertEqual(result["last_error_code"], "PROVIDER_ERROR")
        self.assertEqual(result["last_started_run"]["provider_errors"], 1)
        self.assertFalse(result["execution_authorized"])

    def test_data_freshness_unknown_stale_fresh(self):
        for stamp, expected in [(None, "UNKNOWN"), ("2026-10-21T08:00:00Z", "STALE"),
                                ("2026-10-21T09:59:00Z", "FRESH"), ("2026-10-21T11:00:00Z", "UNKNOWN")]:
            e = receipt()
            if stamp:
                e["receipt"]["batch"]["item_results"][0]["market_at"] = stamp
            result = plan.project_receipt(e, NOW, 900)
            self.assertEqual(result["assets"][0]["data_freshness"], expected)

    def test_unknown_not_hidden_by_later_complete_or_item_status(self):
        unknown = receipt("unknown-run", "OUTCOME_UNKNOWN")
        good = receipt()
        good["started_at"] = "2026-10-21T09:57:00Z"
        good["completed_at"] = "2026-10-21T09:58:00Z"
        self.assertEqual(plan.monitoring([unknown, good], NOW, 900)["status"], "OUTCOME_UNKNOWN")
        good["receipt"]["batch"]["item_results"][0]["status"] = "OUTCOME_UNKNOWN"
        self.assertEqual(plan.project_receipt(good, NOW, 900)["status"], "OUTCOME_UNKNOWN")

    def test_failures_and_duplicates(self):
        e = receipt(status="FAILED_BEFORE_FIRST_COMMIT")
        self.assertEqual(plan.project_receipt(e, NOW, 900)["status"], "FAILED")
        e = receipt()
        e["receipt"]["batch"]["item_results"][0]["writer"] = "DUPLICATE_UNCHANGED"
        self.assertEqual(plan.project_receipt(e,NOW,900)["assets"][0]["writer"], "DUPLICATE_UNCHANGED")

    def test_secret_raw_errors_paths_and_sql_not_projected(self):
        e = receipt(status="FAILED", stage="provider")
        canary = "PRIVATE_PASSWORD_CANARY_123!"
        e["password"] = canary
        e["receipt"]["batch"].update(failure_code=canary, raw_sql=canary, private_evidence=canary, run="/var/private/"+canary)
        e["receipt"]["batch"]["item_results"][0]["metrics"]["raw"] = canary
        output = json.dumps(plan.monitoring([e], NOW, 900))
        self.assertNotIn(canary, output)
        self.assertNotIn("/var/", output)
        self.assertNotIn("raw_sql", output)

    def test_malformed_and_missing_receipts_not_success(self):
        for bad in (None, {}, {"run_id": "../private"}, receipt(status="raw secret")):
            result = plan.project_receipt(bad, NOW, 900)
            self.assertEqual(result, {"status": "OUTCOME_UNKNOWN", "last_error_code": "INVALID_RECEIPT"})
        self.assertEqual(plan.monitoring([],NOW,900)["status"], "NOT_STARTED")
        self.assertEqual(plan.monitoring([{}],NOW,900)["status"], "OUTCOME_UNKNOWN")
        e = receipt()
        e["receipt"]["batch"]["local_batch_ms"] = float("nan")
        self.assertIsNone(plan.project_receipt(e,NOW,900)["batch_ms"])

    def test_pure_module_no_execution_network_or_mutating_imports(self):
        tree = ast.parse((ROOT/"scripts/collector_operation_plan.py").read_text())
        modules = {n.names[0].name for n in ast.walk(tree) if isinstance(n,ast.Import)}
        modules |= {n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
        self.assertTrue(modules <= {"datetime", "math", "re", "zoneinfo"})
        forbidden = {"open", "exec", "eval", "__import__", "compile"}
        self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in forbidden for n in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main()
