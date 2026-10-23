"""Only synthetic scheduler states; shared quote/web regressions are reused unchanged."""
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

from scripts import collector_scheduler_decision as scheduler
from scripts import collector_operation_plan as op
from test_collector_cycle import fixture, NOW
from test_collector_operation_plan import receipt

ROOT = Path(__file__).resolve().parents[1]


def data(now=NOW, holiday=False):
    d = fixture(now, holiday)
    d["operation_config"]["execution_enabled"] = True
    d["budget_config"]["execution_enabled"] = True
    d.update(records=[], provider="boerse_frankfurt_api_v1",
             qualification=deepcopy(d["evidence"]["qualification"]))
    return d


def prior(now=NOW, status="completed", slot=None):
    start = now-timedelta(minutes=15)
    slot = slot or start.replace(second=0, microsecond=0)
    end = start+timedelta(seconds=10)
    envelope = receipt("cycle-"+slot.strftime("%Y%m%dt%H%M%Sz"))
    envelope.update(started_at=start.isoformat(), completed_at=end.isoformat())
    return dict(status=status, attempt_no=1, started_at=start.isoformat(), finished_at=end.isoformat(),
                summary=dict(contract="mosa2-scheduler-v1", slot=slot.isoformat(),
                             reserved_requests=5, envelope=envelope))


class SchedulerDecisionTests(unittest.TestCase):
    def test_begin_with_cron_jitter_and_no_catchup(self):
        d = data(NOW+timedelta(seconds=7))
        result = scheduler.decide(d)
        self.assertEqual(result["decision"], "RUN_ELIGIBLE", result)
        self.assertEqual(op.instant(result["scheduled_at"]), NOW)
        self.assertEqual(result["interval_seconds"], 60)
        d = data(op.instant("2026-10-21T01:01:07Z"))
        self.assertEqual(scheduler.decide(d)["decision"], "SKIP")

    def test_restart_uses_persistent_predecessor_and_budget(self):
        d = data(); d["records"] = [prior()]
        self.assertEqual(scheduler.decide(d)["decision"], "RUN_ELIGIBLE")
        # Neither stale supplied counters nor a fake IDLE predecessor can erase DB usage.
        d["records"][0]["summary"]["reserved_requests"] = 10
        d["budget_config"]["providers"][d["provider"]]["limits"]["mosa2_per_day"] = 10
        self.assertEqual(scheduler.decide(d)["decision"], "BLOCKED")

    def test_duplicate_slot_and_unresolved_predecessor_never_resume(self):
        for status in ("running", "failed", "cancelled"):
            d = data(); d["records"] = [prior(status=status)]
            self.assertEqual(scheduler.decide(d)["reason"], "PREDECESSOR_UNRESOLVED")
        d = data(NOW+timedelta(seconds=30))
        row = prior(); row.update(started_at=NOW.isoformat(), finished_at=(NOW+timedelta(seconds=10)).isoformat())
        row["summary"].update(slot=NOW.isoformat())
        row["summary"]["envelope"].update(run_id="cycle-"+NOW.strftime("%Y%m%dt%H%M%Sz"),
                                         started_at=row["started_at"], completed_at=row["finished_at"])
        d["records"] = [row]
        self.assertNotEqual(scheduler.decide(d)["decision"], "RUN_ELIGIBLE")

    def test_permissions_calendar_baseline_and_unknown_receipt_fail_closed(self):
        for key in ("operation_config", "budget_config"):
            d = data(); d[key]["execution_enabled"] = False
            self.assertEqual(scheduler.decide(d)["reason"], "DISABLED")
        for change in ("calendar", "rights", "baseline", "unknown-receipt", "future-evidence", "external-busy"):
            d = data()
            if change == "calendar": d["operation_config"]["calendar"]["approved"] = False
            if change == "rights": d["budget_config"]["providers"][d["provider"]]["rights_confirmed"] = False
            if change == "baseline": d["evidence"]["mosa_baseline"] = None
            if change == "external-busy": d["evidence"]["budget_state"]["in_flight"] = 1
            if change == "unknown-receipt":
                d["records"] = [prior()]
                d["records"][0]["summary"]["envelope"]["receipt"]["batch"]["overall_status"] = "OUTCOME_UNKNOWN"
            if change == "future-evidence":
                d["evidence"]["monitoring_event"]["checked_at"] = (NOW+timedelta(seconds=1)).isoformat()
            with self.subTest(change=change):
                self.assertIn(scheduler.decide(d)["decision"], ("BLOCKED", "SKIP"))

    def test_berlin_night_weekend_holiday_and_dst_have_unique_utc_cycles(self):
        stamps = ["2026-03-29T01:15:07+01:00", "2026-03-29T03:15:07+02:00",
                  "2026-10-25T02:15:07+02:00", "2026-10-25T02:15:07+01:00"]
        ids = []
        for stamp in stamps:
            result = scheduler.decide(data(op.instant(stamp)))
            self.assertEqual(result["decision"], "RUN_ELIGIBLE", result)
            self.assertEqual(result["interval_seconds"], 900)
            ids.append(result["cycle_id"])
        self.assertEqual(len(ids), len(set(ids)))
        result = scheduler.decide(data(NOW, holiday=True))
        self.assertEqual(result["interval_seconds"], 900)

    def test_corrupt_history_and_cli_errors_are_safe(self):
        for change in ("attempt", "finished", "slot", "duplicate"):
            d = data(); d["records"] = [prior()]
            if change == "attempt": d["records"][0]["attempt_no"] = 2
            if change == "finished": d["records"][0]["finished_at"] = None
            if change == "slot": d["records"][0]["summary"]["slot"] = "bad"
            if change == "duplicate": d["records"] *= 2
            self.assertEqual(scheduler.decide(d)["decision"], "BLOCKED")
        p = subprocess.run([sys.executable, "-B", str(ROOT/"scripts/collector_scheduler_decision.py")],
                           input="SECRET invalid", text=True, capture_output=True, check=True)
        self.assertEqual(p.stderr, "")
        self.assertEqual(json.loads(p.stdout)["decision"], "BLOCKED")
        self.assertNotIn("SECRET", p.stdout)


class SchedulerControllerTests(unittest.TestCase):
    def scenario(self, name):
        php = shutil.which("php")
        self.assertIsNotNone(php, "PHP is required for scheduler acceptance")
        p = subprocess.run([php, str(ROOT/"tests/collector_scheduler_fixture.php"), name],
                           capture_output=True, text=True, timeout=15, check=True)
        self.assertEqual(p.stderr, "")
        self.assertNotIn("SECRET", p.stdout)
        return json.loads(p.stdout)

    def test_one_reservation_before_pipeline_and_restart_does_not_repeat(self):
        r = self.scenario("success")
        self.assertEqual(r["first"]["status"], "COMPLETE")
        self.assertEqual(r["second"]["status"], "SKIP")
        self.assertEqual(r["calls"], 1)
        self.assertEqual(r["reservations"], ["running"])

    def test_parallel_start_does_not_qualify_or_fetch(self):
        r = self.scenario("parallel")
        self.assertEqual(r["first"]["status"], "COMPLETE")
        self.assertEqual(r["calls"], 1)
        r = self.scenario("busy")
        self.assertEqual(r["first"]["reason"], "BUSY")
        self.assertEqual(r["calls"], 0)

    def test_no_permission_missing_calendar_unknown_or_failed_predecessor(self):
        for name in ("disabled", "missing-calendar", "unknown", "failed", "qualification-failure", "missed-slot"):
            with self.subTest(name=name):
                r = self.scenario(name)
                self.assertEqual(r["calls"], 0)
                self.assertIn(r["first"]["status"], ("SKIP", "BLOCKED"))

    def test_crash_commit_ambiguity_and_readback_failure_latch_without_retry(self):
        for name, calls in (("crash", 1), ("claim-unknown", 0), ("finish-unknown", 1), ("readback-failure", 1)):
            with self.subTest(name=name):
                r = self.scenario(name)
                self.assertEqual(r["first"]["status"], "OUTCOME_UNKNOWN")
                self.assertEqual(r["second"]["status"], "BLOCKED")
                self.assertEqual(r["calls"], calls)

    def test_disabled_cli_requires_no_private_config_database_or_provider(self):
        php = shutil.which("php")
        self.assertIsNotNone(php)
        p = subprocess.run([php, str(ROOT/"scripts/collector_scheduler.php"), "/nonexistent/private/config.json"],
                           capture_output=True, text=True, timeout=10, check=True)
        self.assertEqual(json.loads(p.stdout), {"status": "SKIP", "reason": "DISABLED"})
        self.assertEqual(p.stderr, "")


if __name__ == "__main__":
    unittest.main()
