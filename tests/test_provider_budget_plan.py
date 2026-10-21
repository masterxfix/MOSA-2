"""Synthetic load/errors only. No network, DB, scheduler or live transport."""
import ast
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from scripts import provider_budget_plan as budget
import test_observation_v2_writer_phase3 as reference

ROOT = Path(__file__).resolve().parents[1]
PROVIDER = "boerse_frankfurt_api_v1"
NOW = datetime(2026, 10, 21, 10, tzinfo=timezone.utc)


def fixture():
    config = json.loads((ROOT/"config/collector-provider-budget.json").read_text())
    config["execution_enabled"] = True
    p = config["providers"][PROVIDER]
    p["rights_confirmed"] = True  # synthetic simulation, never repository permission
    p["limits"].update(mosa2_per_60s=5, mosa2_per_day=5520,
                       combined_per_60s=20, combined_per_day=20000,
                       combined_parallel=12, evidence_max_age_seconds=30)
    p["monitoring"].update(min_samples=4, error_ratio_stop=0.5,
                           consecutive_error_stop=2, latency_ms_stop=2000, stale_seconds=300)
    state = dict(provider=PROVIDER, checked_at=NOW.isoformat(), budget_date="2026-10-21",
                 used_60s=0, used_day=0, in_flight=0, stop_latched=False, unresolved=False, mosa_impact=False)
    baseline = dict(provider=PROVIDER, checked_at=NOW.isoformat(), budget_date="2026-10-21",
                    used_60s=10, used_day=10000, in_flight=0, healthy=True)
    monitor = dict(errors=[], consecutive_errors=0, stop_latched=False)
    event = dict(http_status=200, timeout=False, network_error=False, blocked_signal=False,
                 valid_payload=True, mosa_impact=False, latency_ms=200, data_age_seconds=60,
                 dedupe_decision="INSERT")
    return config, state, baseline, monitor, event


class LoadTests(unittest.TestCase):
    def test_ordinary_weekday_weekend_holiday_and_week(self):
        self.assertEqual(budget.day_load(date(2026,10,21),holiday=False)["requests"],5520)
        self.assertEqual(budget.day_load(date(2026,10,24),holiday=False)["requests"],480)
        self.assertEqual(budget.day_load(date(2026,10,21),holiday=True)["requests"],480)
        total=sum(budget.day_load(date(2026,10,12)+timedelta(days=i),holiday=False)["requests"] for i in range(7))
        self.assertEqual(total,28560)
        dst_week=sum(budget.day_load(date(2026,10,19)+timedelta(days=i),holiday=False)["requests"] for i in range(7))
        self.assertEqual(dst_week,28580)
        holiday_week=sum(budget.day_load(date(2026,10,12)+timedelta(days=i),holiday=(i==2))["requests"] for i in range(7))
        self.assertEqual(holiday_week,23520)

    def test_dst_real_hours_and_missing_calendar(self):
        self.assertEqual(budget.day_load(date(2026,3,29),holiday=False)["requests"],460)
        self.assertEqual(budget.day_load(date(2026,10,25),holiday=False)["requests"],500)
        self.assertIsNone(budget.cadence_seconds(NOW,holiday=None))
        self.assertIsNone(budget.cadence_seconds(NOW.replace(tzinfo=None),holiday=False))
        with self.assertRaises(ValueError):
            budget.day_load(date(2026,10,21),holiday=None)

    def test_boundaries_and_per_provider(self):
        for hour, expected in ((3,900),(4,60),(21,60),(22,900)):
            self.assertEqual(budget.cadence_seconds(NOW.replace(hour=hour),holiday=False),expected)
        result=budget.day_load(date(2026,10,21),holiday=False)
        self.assertEqual(result["per_provider"],{PROVIDER:5520})
        self.assertEqual(budget.day_load(date(2026,10,21),holiday=False,assets=1)["requests"],1104)


class AdmissionTests(unittest.TestCase):
    def call(self,c,s,b,n=5):
        return budget.admission(c,PROVIDER,s,b,planned_requests=n,now=NOW)

    def test_defaults_disabled_and_no_claimed_provider_limit(self):
        c=json.loads((ROOT/"config/collector-provider-budget.json").read_text())
        _,s,b,_,_=fixture()
        self.assertEqual(self.call(c,s,b)["decision"],"SKIP")
        self.assertFalse(c["providers"][PROVIDER]["rights_confirmed"])
        self.assertIsNone(c["providers"][PROVIDER]["documented_provider_limit"])
        c["execution_enabled"]=True
        self.assertEqual(self.call(c,s,b)["reason"],"RIGHTS_UNCONFIRMED")
        c["providers"][PROVIDER]["rights_confirmed"]=True
        self.assertEqual(self.call(c,s,b)["reason"],"BUDGET_UNAPPROVED")

    def test_combined_usage_and_no_execution_authority(self):
        c,s,b,_,_=fixture()
        before=deepcopy((c,s,b))
        r=self.call(c,s,b)
        self.assertEqual(r["decision"],"RUN_ELIGIBLE")
        self.assertFalse(r["execution_authorized"])
        self.assertEqual((c,s,b),before)
        self.assertEqual(self.call(c,s,b|{"used_60s":16})["reason"],"COMBINED_BUDGET")
        self.assertEqual(self.call(c,s,b|{"used_day":19000})["decision"],"RUN_ELIGIBLE")
        self.assertEqual(self.call(c,s|{"used_day":5516},b)["reason"],"MOSA2_BUDGET")

    def test_concurrency_mosa_priority_without_changing_mosa(self):
        c,s,b,_,_=fixture()
        before=deepcopy(b)
        self.assertEqual(self.call(c,s,b|{"in_flight":12})["reason"],"MOSA_PRIORITY")
        self.assertEqual(self.call(c,s|{"in_flight":1},b)["reason"],"MOSA2_BUSY")
        self.assertEqual(b,before)

    def test_missing_stale_future_baseline_and_wrong_budget_date(self):
        c,s,b,_,_=fixture()
        for change in ({"checked_at":(NOW-timedelta(seconds=31)).isoformat()},
                       {"checked_at":(NOW+timedelta(seconds=1)).isoformat()},
                       {"used_day":None},{"budget_date":"2026-10-20"},{"healthy":False}):
            self.assertEqual(self.call(c,s,b|change)["decision"],"BLOCKED")
        self.assertEqual(self.call(c,s,{})["decision"],"BLOCKED")

    def test_stop_unresolved_impact_scope_and_retries(self):
        c,s,b,_,_=fixture()
        for change in ({"stop_latched":True},{"unresolved":True},{"mosa_impact":True}):
            self.assertEqual(self.call(c,s|change,b)["decision"],"BLOCKED")
        for n in (0,6,True):
            self.assertEqual(self.call(c,s,b,n)["decision"],"BLOCKED")
        c["providers"][PROVIDER]["automatic_retries"]=1
        self.assertEqual(self.call(c,s,b)["decision"],"BLOCKED")


class MonitoringTests(unittest.TestCase):
    def observe(self, changes=None, previous=None):
        c,_,_,m,e=fixture()
        return budget.observe(c["providers"][PROVIDER]["monitoring"],previous or m,e|(changes or {}),now=NOW)

    def test_429_seconds_and_http_date_never_retries(self):
        for header, expected in (("120","2026-10-21T10:02:00+00:00"),
                                 ("Wed, 21 Oct 2026 10:03:00 GMT","2026-10-21T10:03:00+00:00"),
                                 ("invalid",None),(None,None)):
            r=self.observe({"http_status":429,"retry_after":header})
            self.assertTrue(r["stop_latched"])
            self.assertEqual(r["retry_not_before"],expected)
            self.assertFalse(r["automatic_retry"])
            self.assertEqual(r["scope"],"MOSA2")
            later=self.observe(previous=r)
            self.assertTrue(later["stop_latched"])
            self.assertEqual(later["retry_not_before"],expected)
            self.assertEqual(later["reason"],"STOP_LATCHED")

    def test_403_block_signals_and_mosa_impact_stop_only_mosa2(self):
        for event in ({"http_status":403},{"http_status":401},{"blocked_signal":True},{"mosa_impact":True}):
            r=self.observe(event)
            self.assertTrue(r["stop_latched"])
            self.assertEqual(r["scope"],"MOSA2")
            self.assertNotIn("mosa_enabled",r)

    def test_timeouts_error_trend_and_latency(self):
        first=self.observe({"timeout":True})
        self.assertFalse(first["stop_latched"])
        self.assertTrue(self.observe({"timeout":True},first)["stop_latched"])
        mixed=dict(errors=[True,False,True],consecutive_errors=0,stop_latched=False)
        self.assertEqual(self.observe(previous=mixed)["reason"],"ERROR_TREND")
        self.assertEqual(self.observe({"latency_ms":2001})["reason"],"LATENCY")

    def test_age_and_dedupe_do_not_invent_new_market_data(self):
        for decision in ("INSERT","DUPLICATE_UNCHANGED"):
            r=self.observe({"dedupe_decision":decision,"data_age_seconds":900})
            self.assertEqual(r["freshness"],"STALE")
            self.assertFalse(r["stop_latched"])
            self.assertEqual(r["dedupe_decision"],decision)
        self.assertEqual(self.observe({"data_age_seconds":None})["freshness"],"UNKNOWN")
        self.assertTrue(self.observe({"dedupe_decision":"CONFLICT"})["stop_latched"])

    def test_allowlisted_output_and_invalid_inputs_stop(self):
        c,_,_,m,e=fixture()
        canary="PRIVATE_SECRET_CANARY"
        e.update(body=canary,url=canary,headers={"x":canary},error=canary)
        before=deepcopy((m,e))
        result=budget.observe(c["providers"][PROVIDER]["monitoring"],m,e,now=NOW)
        self.assertNotIn(canary,json.dumps(result))
        self.assertEqual((m,e),before)
        for change in ({"http_status":"raw secret"},{"blocked_signal":None},{"dedupe_decision":"secret"}):
            r=self.observe(change)
            self.assertTrue(r["stop_latched"])
            self.assertEqual(r["reason"],"INVALID_EVIDENCE")

    def test_no_network_process_database_or_file_calls(self):
        source=(ROOT/"scripts/provider_budget_plan.py").read_text()
        tree=ast.parse(source)
        modules={n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
        self.assertEqual(modules,{"datetime","email.utils","scripts.collector_operation_plan"})
        self.assertFalse(any(isinstance(n,ast.Import) for n in ast.walk(tree)))
        forbidden={"open","exec","eval","__import__","compile"}
        self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in forbidden for n in ast.walk(tree)))


class RealDedupeContractTests(unittest.TestCase):
    def test_exact_replay_duplicate_new_collection_time_insert(self):
        catalog=reference.adapter.normative_catalog()
        raw=reference.row()
        route=reference.route(raw)
        planner=reference.writer.WriterPlanner(catalog,[route])
        first=planner.plan(raw,format_version=2,intent="NEW_NATIVE_V2",created_at=reference.CREATED)
        self.assertEqual(first["decision"],"INSERT")
        old=dict(format_version=2,payload=first["normalized"],dedupe_key=first["dedupe_key"])
        planner=reference.writer.WriterPlanner(catalog,[route],[old])
        replay=planner.plan(raw,format_version=2,intent="NEW_NATIVE_V2",created_at=reference.CREATED)
        self.assertEqual(replay["decision"],"DUPLICATE_UNCHANGED")
        repeated=planner.plan(raw|{"observed_at":"2026-01-01 00:01:01"},format_version=2,
                              intent="NEW_NATIVE_V2",created_at=reference.CREATED)
        self.assertEqual(repeated["decision"],"INSERT")
        self.assertNotEqual(first["dedupe_key"],repeated["dedupe_key"])
        newer=planner.plan(raw|{"market_at":"2026-01-01 00:02:00","observed_at":"2026-01-01 00:02:01"},
                           format_version=2,intent="NEW_NATIVE_V2",created_at=reference.CREATED)
        self.assertEqual(newer["decision"],"INSERT")


if __name__=="__main__":
    unittest.main()
