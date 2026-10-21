"""Synthetic read-only observation-reader fixture; no live database/provider."""
from pathlib import Path
import json
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]


class ObservationReadTests(unittest.TestCase):
    def run_case(self,case):
        p=subprocess.run(["php",str(ROOT/"tests/fixtures/observation_read.php"),str(ROOT),case],
                         capture_output=True,text=True,check=True)
        self.assertEqual(p.stderr,"")
        return json.loads(p.stdout)

    def test_latest_market_observed_and_id_with_unchanged_current(self):
        r=self.run_case("normal")
        self.assertEqual(r["status"],"ok")
        self.assertEqual(len(r["items"]),5)
        self.assertEqual(r["items"][0]["observation_id"],"9002")
        self.assertEqual(r["items"][0]["status"],"stale")
        self.assertEqual(r["items"][0]["age_seconds"],3600)
        self.assertEqual(r["events"],["SET TRANSACTION READ ONLY","BEGIN","ROLLBACK"])
        self.assertEqual(len(r["parameters"]),10)
        self.assertEqual(r["parameters"][0],["DE000A0JBPG2"])
        self.assertTrue(all("m2_market_current" not in q and "m2_market_bars" not in q for q in r["sql"]))
        self.assertIn("WHERE asset_id=? AND source_id=? ORDER BY market_at DESC,id DESC LIMIT 101",r["sql"][1])
        self.assertIn("MAX_EXECUTION_TIME",r["sql"][1])

    def test_missing_and_legacy_missing_are_clear(self):
        for mode in ("missing","legacy"):
            r=self.run_case(mode)
            self.assertTrue(all(x["status"]=="missing" for x in r["items"]))
            self.assertTrue(all("price" not in x for x in r["items"]))

    def test_older_market_new_acquisition_does_not_win_or_freshen(self):
        r=self.run_case("normal")
        self.assertEqual(r["items"][0]["price"],"2.0000000000")
        self.assertEqual(r["items"][0]["status"],"stale")

    def test_bad_binding_hash_unit_time_route_conflicts_fail_closed(self):
        for mode in ("route","source","unit","hash","future","format","equal_conflict","scope","scope_unit","scope_key","boundary","source_disabled","source_type"):
            with self.subTest(mode=mode):
                r=self.run_case(mode)
                self.assertEqual(r["status"],"error")
                self.assertNotIn("PRIVATE_CANARY",json.dumps(r))
                self.assertEqual(r["events"][-1],"ROLLBACK")

    def test_selection_has_no_equity_class_special_case(self):
        self.assertEqual(self.run_case('generic_class')['status'], 'ok')

    def test_query_failure_rolls_back_and_no_diagnostics(self):
        r=self.run_case("query")
        self.assertEqual(r["status"],"error")
        self.assertNotIn("PRIVATE_CANARY",json.dumps(r))
        self.assertEqual(r["events"][-1],"ROLLBACK")

    def test_scope_matches_existing_qualification_and_route_contract(self):
        r=self.run_case("normal")
        qualified=json.loads((ROOT/"scripts/market_collector/live_test_scope.json").read_text())
        self.assertEqual({i["isin"] for i in r["items"]},{i["isin"] for i in qualified})
        self.assertTrue(r["route_contract_matches"])

    def test_bounded_rows_and_index_order(self):
        r=self.run_case("bounded")
        self.assertEqual(len(r["items"]),5)
        self.assertEqual(r["items"][0]["observation_id"],"9002")
        self.assertNotIn("WHERE observation_format_version",r["sql"][1])

    def test_endpoint_reuses_private_config_and_fixed_selector(self):
        api=(ROOT/"api/market.php").read_text()
        source=(ROOT/"api/observations_read.php").read_text()
        self.assertIn("dirname(__DIR__,2).'/mosa2-market-read-private/access.php'",api)
        self.assertIn("['current','observations']",api)
        self.assertNotIn("$_GET",source)
        for term in ("INSERT ","UPDATE ","DELETE ","REPLACE ","ALTER ","TRUNCATE ","market_collector","shell_exec","curl_"):
            self.assertNotIn(term,source+api)
        self.assertIn("Cache-Control: no-store, private",api)
        self.assertIn("http_response_code(503)",api)


if __name__=="__main__":unittest.main()
