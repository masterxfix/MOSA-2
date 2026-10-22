"""Injected synthetic facts only; grants in fixtures never modify configuration."""
import ast
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import unittest
from scripts import collector_cycle as flow, collector_operation_plan as op, provider_budget_plan as budget
import test_collector_operation_plan as legacy
import test_provider_budget_plan as prior

ROOT = Path(__file__).resolve().parents[1]
NOW = prior.NOW
ASSETS = ["DE000A0JBPG2", "DE0005313704", "AU000000DRO2", "CNE100000296", "CNE1000066X8"]


def fixture(now=NOW, holiday=False):
    operation, state, qualification = legacy.fixture(now)
    operation.update(format=op.FORMAT_V2, execution_enabled=False, schedule_policy=op.SCHEDULE,
                     selection=ASSETS.copy(), provider_budget=dict(per_run=5, per_day=5520))
    for key in ("windows", "weekdays", "interval_seconds"):
        del operation[key]
    day = now.astimezone(op.ZONE).date()
    known = [(day+timedelta(days=i)).isoformat() for i in range(2)]
    operation["calendar"].update(open_dates=known if not holiday else known[1:], closed_dates=[known[0]] if holiday else [])
    state["last_completed_at"] = None
    qualification["selection"] = ASSETS.copy()
    config, usage, baseline, monitor, event = prior.fixture()
    config["execution_enabled"] = False
    config["proposal"]["calendar_approved"] = True  # Synthetic calendar only.
    provider = config["providers"][flow.PROVIDER]
    provider["documented_provider_limit"] = dict(evidence_ref="SYNTHETIC_TEST_ONLY", per_60s=20, per_day=20000, parallel=12)
    for item in (usage, baseline):
        item.update(checked_at=now.isoformat(), budget_date=day.isoformat())
    usage["simulated_attempt_ids"] = []
    monitor["checked_at"] = now.isoformat()
    event.update(checked_at=now.isoformat(), provenance_conflict=False)
    evidence = dict(operation_state=state, qualification=qualification, budget_state=usage,
                    mosa_baseline=baseline, monitoring_previous=monitor, monitoring_event=event, receipts=[])
    return dict(now=now.isoformat(), operation_config=operation, budget_config=config, evidence=evidence)


def decide(data):
    return flow.cycle(data["operation_config"], data["budget_config"], data["evidence"], op.instant(data["now"]))


class CycleTests(unittest.TestCase):
    def test_eligible_is_deterministic_simulation_without_mutation_or_execution(self):
        data = fixture(); before = deepcopy(data)
        result = decide(data)
        self.assertEqual(result["decision"], "RUN_ELIGIBLE")
        self.assertEqual(result["interval_seconds"], 60)
        self.assertEqual(result["expected_provider_requests"], 5)
        self.assertEqual(result["assets"], ASSETS)
        self.assertEqual(len(set(result["assets"])), 5)
        for key in ("execution_authorized", "atomic_reservation", "automatic_resume"):
            self.assertIs(result[key], False)
        self.assertEqual(result["actual_provider_requests"], 0)
        self.assertEqual(result["max_parallel"], 1)
        self.assertEqual(result["requests_per_asset"], 1)
        self.assertEqual(result["automatic_retries"], 0)
        self.assertEqual(decide(data), result)
        self.assertEqual(data, before)

    def test_registry_scope_is_bounded_without_a_fixed_five_asset_requirement(self):
        for count in (1, 2, 5):
            data = fixture()
            selected = ASSETS[:count]
            data['operation_config']['selection'] = selected
            data['evidence']['qualification'].update(selection=selected, asset_class='etf')
            data['budget_config']['proposal']['assets'] = count
            provider = data['budget_config']['providers'].pop(flow.PROVIDER)
            data['budget_config']['providers']['synthetic_adapter_v1'] = provider
            for field in ('budget_state', 'mosa_baseline'):
                data['evidence'][field]['provider'] = 'synthetic_adapter_v1'
            result = flow.cycle(data['operation_config'], data['budget_config'], data['evidence'],
                                op.instant(data['now']), provider_key='synthetic_adapter_v1')
            self.assertEqual(result['decision'], 'RUN_ELIGIBLE', result)
            self.assertEqual(result['expected_provider_requests'], count)
            self.assertEqual(result['actual_provider_requests'], 0)

    def test_berlin_0600_midnight_night_weekend_holiday(self):
        for stamp, holiday, seconds in [
            ("2026-10-21T05:45:00+02:00", False, 900),
            ("2026-10-21T06:00:00+02:00", False, 60),
            ("2026-10-21T23:59:00+02:00", False, 60),
            ("2026-10-22T00:00:00+02:00", False, 900),
            ("2026-10-24T12:00:00+02:00", False, 900),
            ("2026-10-25T12:00:00+01:00", False, 900),
            ("2026-10-21T12:00:00+02:00", True, 900),
        ]:
            with self.subTest(stamp=stamp):
                result = decide(fixture(op.instant(stamp), holiday))
                self.assertEqual(result["decision"], "RUN_ELIGIBLE")
                self.assertEqual(result["interval_seconds"], seconds)

    def test_legacy_contract_retained_and_v2_explicit(self):
        c, s, q = legacy.fixture()
        c["calendar"].update(open_dates=[], closed_dates=["2026-10-21"])
        self.assertEqual(op.decide(c, s, q, NOW, "legacy"), "SKIP")
        self.assertEqual(decide(fixture(holiday=True))["decision"], "RUN_ELIGIBLE")
        data = fixture(); data["operation_config"]["format"] = op.FORMAT
        self.assertEqual(decide(data)["reason"], "EXPLICIT_V2_POLICY_REQUIRED")

    def test_unknown_calendar_and_coverage_block_no_implicit_weekend(self):
        data = fixture(); data["budget_config"]["proposal"]["calendar_approved"] = False
        self.assertEqual(decide(data)["reason"], "CALENDAR_PROPOSAL_UNCONFIRMED")
        for changes in ({"approved": False}, {"open_dates": []}, {"valid_until": "2026-10-20", "open_dates": []}):
            data = fixture(); data["operation_config"]["calendar"].update(changes)
            self.assertEqual(decide(data)["decision"], "BLOCKED")
        data = fixture(); data["operation_config"]["calendar"] = None
        self.assertEqual(decide(data)["interval_seconds"], None)
        data = fixture(op.instant("2026-10-24T12:00:00+02:00"))
        data["operation_config"]["calendar"]["open_dates"] = []
        self.assertEqual(decide(data)["decision"], "BLOCKED")

    def test_dst_unique_utc_slots_and_next_tick_across_fold_and_gap(self):
        for day, count in [("2026-03-29", 92), ("2026-10-25", 100)]:
            start = datetime.fromisoformat(day).replace(tzinfo=op.ZONE).astimezone(timezone.utc)
            end = (datetime.fromisoformat(day)+timedelta(days=1)).replace(tzinfo=op.ZONE).astimezone(timezone.utc)
            ticks = [start+timedelta(minutes=i) for i in range(int((end-start).total_seconds()/60))]
            ticks = [t for t in ticks if op.is_slot(t, holiday=False)]
            ids = [decide(fixture(t))["cycle_id"] for t in ticks]
            self.assertEqual(len(ids), count)
            self.assertEqual(len(set(ids)), count)
            for t in ticks:
                result = decide(fixture(t))
                self.assertEqual(op.instant(result["next_theoretical_at"]), t+timedelta(seconds=900))
        self.assertEqual(flow.cycle({}, {}, {}, NOW.replace(tzinfo=None))["decision"], "BLOCKED")

    def test_off_grid_missed_ticks_never_catch_up(self):
        for now in (NOW+timedelta(seconds=1), NOW+timedelta(microseconds=1), NOW.replace(hour=1, minute=1)):
            result = decide(fixture(now))
            self.assertEqual(result["decision"], "SKIP")
            self.assertIsNone(result["scheduled_at"])
            self.assertGreater(op.instant(result["next_theoretical_at"]), now)

    def test_overlapping_long_running_and_unresolved_predecessor(self):
        data = fixture()
        state = data["evidence"]["operation_state"]
        state.update(active=True, last_status="COMPLETE", last_started_at=(NOW-timedelta(seconds=90)).isoformat(),
                     last_completed_at=None)
        self.assertEqual(decide(data)["decision"], "BLOCKED")
        # Completion between ticks never causes an immediate catch-up.
        later = NOW+timedelta(seconds=30)
        data = fixture(later)
        data["evidence"]["operation_state"].update(last_status="COMPLETE", last_started_at=(NOW-timedelta(seconds=60)).isoformat(),
                                                   last_completed_at=(NOW+timedelta(seconds=10)).isoformat())
        receipt = legacy.receipt()
        receipt.update(started_at=(NOW-timedelta(seconds=60)).isoformat(), completed_at=(NOW+timedelta(seconds=10)).isoformat())
        data["evidence"]["receipts"] = [receipt]
        self.assertEqual(decide(data)["decision"], "SKIP")
        for change in ({"active": None}, {"unresolved": True}, {"last_status": "OUTCOME_UNKNOWN"},
                       {"last_status": "FAILED"}, {"last_status": "PARTIAL_FAILED"}):
            data = fixture(); data["evidence"]["operation_state"].update(change)
            result = decide(data)
            self.assertEqual(result["decision"], "BLOCKED")
            self.assertTrue(result["stop_latched"])
            later = fixture(NOW+timedelta(minutes=1))
            later["evidence"]["monitoring_previous"] = result["monitoring_state"] | dict(checked_at=later["now"])
            self.assertTrue(decide(later)["stop_latched"])

    def test_completed_overrun_skips_missed_slot_and_allows_only_future_grid(self):
        data = fixture()
        start, end = NOW-timedelta(seconds=120), NOW-timedelta(seconds=30)
        data["evidence"]["operation_state"].update(last_status="COMPLETE", last_started_at=start.isoformat(), last_completed_at=end.isoformat())
        receipt = legacy.receipt(); receipt.update(started_at=start.isoformat(), completed_at=end.isoformat())
        data["evidence"]["receipts"] = [receipt]
        self.assertEqual(decide(data)["decision"], "RUN_ELIGIBLE")
        data["evidence"]["receipts"] = []
        self.assertEqual(decide(data)["decision"], "BLOCKED")

    def test_midnight_transition_and_unknown_next_day(self):
        now = op.instant("2026-10-22T00:00:00+02:00")
        data = fixture(now)
        start, end = now-timedelta(seconds=60), now-timedelta(seconds=30)
        data["evidence"]["operation_state"].update(last_status="COMPLETE", last_started_at=start.isoformat(), last_completed_at=end.isoformat())
        receipt = legacy.receipt(); receipt.update(started_at=start.isoformat(), completed_at=end.isoformat())
        data["evidence"]["receipts"] = [receipt]
        self.assertEqual(decide(data)["decision"], "RUN_ELIGIBLE")
        data = fixture(op.instant("2026-10-21T23:59:00+02:00"))
        data["operation_config"]["calendar"]["open_dates"] = ["2026-10-21"]
        self.assertIsNone(decide(data)["next_theoretical_at"])

    def test_duplicates_and_unknown_qualification_block(self):
        for change in ({"all_qualified": False}, {"policy": "CREATE_ROUTE"}, {"selection": list(reversed(ASSETS))}):
            data = fixture(); data["evidence"]["qualification"].update(change)
            self.assertEqual(decide(data)["decision"], "BLOCKED")
        data = fixture(); data["operation_config"]["selection"][1] = ASSETS[0]
        self.assertEqual(decide(data)["decision"], "BLOCKED")
        data = fixture(); data["evidence"]["operation_state"]["seen_run_ids"] = [decide(data)["cycle_id"]]
        self.assertEqual(decide(data)["decision"], "BLOCKED")

    def test_rights_baseline_combined_limits_and_provider_documentation_required(self):
        for field in ("rights", "baseline", "limits", "documented", "stale", "mosa_priority", "own_budget"):
            data = fixture(); e = data["evidence"]; provider = data["budget_config"]["providers"][flow.PROVIDER]
            if field == "rights": provider["rights_confirmed"] = False
            if field == "baseline": e["mosa_baseline"] = None
            if field == "limits": provider["limits"]["combined_per_60s"] = None
            if field == "documented": provider["documented_provider_limit"] = None
            if field == "stale": e["mosa_baseline"]["checked_at"] = (NOW-timedelta(seconds=31)).isoformat()
            if field == "mosa_priority": e["mosa_baseline"]["in_flight"] = 12
            if field == "own_budget": e["budget_state"]["used_60s"] = 5
            with self.subTest(field=field):
                self.assertIn(decide(data)["decision"], ("BLOCKED", "SKIP"))

    def test_http_429_retry_after_and_403_are_sticky_without_resume(self):
        for status in (429, 401, 403):
            data = fixture(); data["evidence"]["monitoring_event"].update(http_status=status, retry_after="120")
            stopped = decide(data)
            self.assertEqual(stopped["decision"], "BLOCKED")
            self.assertTrue(stopped["stop_latched"])
            if status == 429: self.assertEqual(stopped["retry_not_before"], (NOW+timedelta(seconds=120)).isoformat())
            after = fixture(NOW+timedelta(minutes=15))
            after["evidence"]["monitoring_previous"] = stopped["monitoring_state"] | dict(checked_at=after["now"])
            self.assertTrue(decide(after)["stop_latched"])
            self.assertEqual(decide(after)["decision"], "BLOCKED")

    def test_timeout_error_trend_latency_invalid_payload_conflicts_mosa_impact(self):
        for change in ({"timeout": True}, {"latency_ms": 2001}, {"valid_payload": False},
                       {"dedupe_decision": "CONFLICT"}, {"provenance_conflict": True}, {"mosa_impact": True}):
            data = fixture(); data["evidence"]["monitoring_event"].update(change)
            self.assertTrue(decide(data)["stop_latched"])
            self.assertEqual(decide(data)["decision"], "BLOCKED")
        data = fixture(); data["evidence"]["monitoring_previous"].update(errors=[True, False, True])
        self.assertEqual(decide(data)["monitor_reason"], "ERROR_TREND")

    def test_unknown_receipt_cannot_be_hidden_by_success(self):
        data = fixture(); data["evidence"]["receipts"] = [{}, legacy.receipt()]
        self.assertEqual(decide(data)["decision"], "BLOCKED")
        self.assertTrue(decide(data)["stop_latched"])

    def test_failed_attempts_count_no_retry_and_no_following_asset(self):
        data = fixture(); attempts = [dict(asset=ASSETS[0], outcome="SUCCESS"), dict(asset=ASSETS[1], outcome="TIMEOUT")]
        data["evidence"]["simulated_attempts"] = attempts
        result = decide(data)
        self.assertEqual(result["simulated_used_60s"], 2)
        self.assertEqual(result["simulated_used_day"], 2)
        self.assertTrue(result["stop_latched"])
        self.assertEqual(result["actual_provider_requests"], 0)
        self.assertEqual(result["admission_decision"], "RUN_ELIGIBLE")
        self.assertEqual(result["decision"], "BLOCKED")
        for invalid in (attempts+[dict(asset=ASSETS[2], outcome="SUCCESS")],
                        [attempts[0], attempts[0]], [dict(asset=ASSETS[1], outcome="SUCCESS")]):
            data["evidence"]["simulated_attempts"] = invalid
            self.assertEqual(decide(data)["decision"], "BLOCKED")
        usage = budget.simulate_attempts(data["evidence"]["budget_state"], ASSETS, attempts, cycle_id="test")
        usage["simulated_attempt_ids"]  # Explicit private model ledger, not an atomic reservation.
        self.assertEqual(budget.simulate_attempts(usage, ASSETS, attempts, cycle_id="test")["decision"], "BLOCKED")

    def test_partial_attempts_are_not_success_and_mosa_health_latches(self):
        for count in (0, 1, 5):
            data = fixture()
            data["evidence"]["simulated_attempts"] = [dict(asset=asset, outcome="SUCCESS") for asset in ASSETS[:count]]
            result = decide(data)
            self.assertEqual(result["simulated_cycle_status"], "COMPLETE" if count == 5 else "INCOMPLETE")
            self.assertEqual(result["stop_latched"], count != 5)
        for field, changes in (("budget_state", {"mosa_impact": True}), ("mosa_baseline", {"healthy": False})):
            data = fixture(); data["evidence"][field].update(changes)
            result = decide(data)
            self.assertEqual(result["decision"], "BLOCKED")
            self.assertTrue(result["stop_latched"])

    def test_missing_mandatory_information_and_no_secrets(self):
        for name in fixture()["evidence"]:
            data = fixture(); del data["evidence"][name]
            self.assertEqual(decide(data)["decision"], "BLOCKED")
        data = fixture(); data["evidence"]["monitoring_event"].update(body="SECRET /private/path SELECT price", headers={"password": "SECRET"})
        self.assertNotIn("SECRET", json.dumps(decide(data)))
        for name in ("operation_config", "budget_config"):
            data = fixture(); data[name]["execution_enabled"] = True
            self.assertEqual(decide(data)["reason"], "EXECUTION_MUST_REMAIN_DISABLED")

    def test_cli_dry_run_and_invalid_json_are_safe(self):
        for raw, expected in ((json.dumps(fixture()), "RUN_ELIGIBLE"), ("SECRET invalid json", "BLOCKED")):
            p = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/collector_cycle_dry_run.py')],
                               input=raw, text=True, capture_output=True, timeout=10, check=True)
            self.assertEqual(p.stderr, "")
            report = json.loads(p.stdout)
            self.assertEqual(report["decision"], expected)
            self.assertFalse(report["execution_authorized"])
            self.assertEqual(report["actual_provider_requests"], 0)
            self.assertNotIn("SECRET", p.stdout)

    def test_no_transport_and_repository_grants_remain_disabled(self):
        for name in ("collector_cycle.py", "collector_cycle_dry_run.py"):
            tree = ast.parse((ROOT/'scripts'/name).read_text())
            modules = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            modules |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
            self.assertTrue(modules <= {"datetime", "scripts", "scripts.collector_cycle", "scripts.collector_operation_plan", "json", "sys", "pathlib"})
        for name in ("collector-operation.json", "collector-provider-budget.json"):
            config = json.loads((ROOT/'config'/name).read_text())
            self.assertFalse(config["execution_enabled"])
            for provider in config.get("providers", {}).values():
                self.assertFalse(provider["rights_confirmed"])


if __name__ == "__main__":
    unittest.main()
