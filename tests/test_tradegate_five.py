"""Five published equities: existing Tradegate DroneShield plus four source transitions."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import unittest
from scripts import collector_schema4_once as driver
from scripts.market_current import planner as current
import test_market_onboarding as onboarding
import test_tradegate_manifest as manifests
import test_tradegate_collector as quotes
from test_market_live_batch import isin, call as batch_call
from test_current_route_transition import CurrentRouteTransitionTests
from test_observation_v2_writer_phase3 import row, route

ROOT = Path(__file__).resolve().parents[1]
NAMES = ["BYD", "DroneShield", "Ubtech Robotics", "PNE AG", "Carl Zeiss Meditec"]


def choose(published):
    p = subprocess.run(["php", str(ROOT/"tests/tradegate_five_fixture.php")],
                       input=json.dumps(dict(published=published)), capture_output=True, text=True, check=True)
    if p.stderr:
        raise AssertionError(p.stderr)
    return json.loads(p.stdout)


class TradegateFiveTests(unittest.TestCase):
    def published(self):
        return [dict(route=dict(display_name=name, isin=isin(i+1), asset_class="equity",
                     source_key="provider:tradegate_bsx_mid" if i == 1 else "provider:boerse_frankfurt_api",
                     quote_unit_key="EUR", quote_unit_version="1")) for i, name in enumerate(NAMES)]

    def test_mixed_registry_to_actual_tradegate_writer_current_and_web(self):
        published = self.published()
        self.assertEqual([x["route"]["display_name"] for x in choose(list(reversed(published)))["items"]], NAMES)
        state = onboarding.state(True)
        template = deepcopy(state)
        for table in ("m2_entities", "m2_assets", "m2_asset_identifiers"):
            state[table] = []
        for i, name in enumerate(NAMES):
            identity = str(101+i)
            entity = deepcopy(template["m2_entities"][0]); entity.update(id=identity, canonical_name=name)
            asset = deepcopy(template["m2_assets"][0]); asset.update(entity_id=identity, display_name=name)
            identifier = deepcopy(template["m2_asset_identifiers"][0])
            identifier.update(id=str(201+i), asset_id=identity, identifier_value=isin(i+1), normalized_value=isin(i+1))
            state["m2_entities"].append(entity); state["m2_assets"].append(asset); state["m2_asset_identifiers"].append(identifier)
        source = manifests.call(action="source", sources=[], now=manifests.NOW)["result"]["values"]
        state.update(m2_sources=[dict(id="301", **source)], m2_asset_source_routes=[],
                     m2_units=[dict(unit_key="EUR", unit_version="1",
                        unit_contract_version=onboarding.UNITS["unit_contract_version"], monetary_currency_code="EUR")])
        # Materialize the previously registered DroneShield route first.
        selection = dict(isin=isin(2), name=NAMES[1])
        pre = manifests.call(action="manifest", state=state, selection=selection)["result"]
        state = onboarding.call(action="materialize", state=state, plan=pre["plan"]["route"], asset_id="102")["result"]["after"]
        original_route = deepcopy(state["m2_asset_source_routes"][0])
        route_counts = []; prepared = []; decisions = []
        for i, name in enumerate(NAMES):
            selection = dict(isin=isin(i+1), name=name)
            planned = manifests.call(action="manifest", state=state, selection=selection)
            self.assertTrue(planned["ok"], planned)
            plan = planned["result"]["plan"]["route"]
            route_counts.append(int(plan["decision"] == "CREATE_REVISION"))
            stored = onboarding.call(action="materialize", state=state, plan=plan, asset_id=str(101+i))
            self.assertTrue(stored["ok"], stored)
            state = stored["result"]["after"]; physical = stored["result"]["row"]
            m = manifests.call(action="manifest", state=state, selection=selection)["result"]["manifest"]
            self.assertEqual(m["policy"], "USE_EXISTING_ROUTE")
            prepared.append(m)
            fixture = quotes.TradegateCollectorTests(); fixture.setUp()
            binding = dict(fixture.route.route, id=physical["id"], source_id="301", asset_id=str(101+i))
            request = replace(fixture.request, instrument=selection["isin"],
                              source_id="301", route_id=physical["id"])
            response = replace(fixture.response, payload_bytes=quotes.BODY.replace(b"DE0007030009", selection["isin"].encode()))
            contract = replace(fixture.route, instrument=selection["isin"], route=binding)
            quote = fixture.run_pipeline(response, request, contract)
            self.assertEqual(quote["decision"], "INSERT", quote)
            fact = quote["writer_plan"]["normalized"] | dict(id=str(900+i), observation_format_version="2",
                dedupe_key=quote["dedupe_key"].hex().upper(), created_at=fixture.created)
            raw = row(asset_id=str(101+i), source_id="301" if i==1 else "401",
                      route_id=physical["id"] if i==1 else str(500+i))
            old_route = route(raw)["route"] | dict(route_type="quote", priority="0", enabled="0")
            old_fact = CurrentRouteTransitionTests().fact(raw, str(800+i))
            old = current.plan(dict(route=old_route, facts=[old_fact], now=fixture.created,
                approval=dict(route_sha256=current.route_hash(old_route), approved_at=fixture.created,
                              allow_disabled_projection=True)))["values"]
            new_route = dict(physical)
            inputs = dict(route=new_route, current=old, current_fact=old_fact, facts=[fact], now=fixture.created,
                approval=dict(route_sha256=current.route_hash(new_route), approved_at=fixture.created,
                    allow_disabled_projection=True, allow_route_transition=True,
                    previous_route_sha256=current.route_hash(old_route)))
            if i!=1:
                inputs["current_route"] = old_route
            projection = current.plan(inputs)
            self.assertEqual(projection["decision"], "UPDATE", projection)
            self.assertEqual(projection["values"]["observation_id"], fact["id"])
            decisions.append(projection["decision"])
            web_row = projection["values"] | dict(display_name=name, source_name="Tradegate · XGAT · Mid",
                                                   venue="—", valid_binding="1")
            code = "require $argv[1].'/api/read_model.php';$d=json_decode(stream_get_contents(STDIN),true);echo json_encode(\\Mosa2\\MarketRead\\present($d['row'],$d['now'],60));"
            web = subprocess.run(["php","-r",code,str(ROOT)],
                input=json.dumps(dict(row=web_row, now=fixture.created)), capture_output=True,text=True,check=True)
            self.assertEqual(web.stderr,"")
            self.assertEqual(json.loads(web.stdout)["price"],fact["price"])
            inputs.update(current=projection["values"],current_fact=fact); inputs.pop("current_route",None)
            self.assertEqual(current.plan(inputs)["decision"],"UNCHANGED")
        self.assertEqual(route_counts,[1,0,1,1,1])
        self.assertIn(original_route,state["m2_asset_source_routes"])
        self.assertEqual(len(state["m2_sources"]),1)
        batch = batch_call(prepared, outcomes=[dict(writer="DUPLICATE_UNCHANGED")]*5)["batch"]
        self.assertEqual(batch["overall_status"],"COMPLETE")
        self.assertEqual(batch["provider_requests"],5)
        self.assertEqual([i["asset_identity"] for i in batch["item_results"]],[isin(i+1) for i in range(5)])

    def test_missing_duplicate_or_wrong_unit_published_scope_blocks(self):
        for kind in ("missing","duplicate","unit"):
            data=self.published()
            if kind=="missing": data.pop()
            if kind=="duplicate": data.append(deepcopy(data[1]))
            if kind=="unit": data[0]["route"]["quote_unit_key"]="USD"
            self.assertFalse(choose(data)["ok"])

    def test_five_authorization_is_not_the_historical_single_grant(self):
        commit="a"*40
        env=dict(MOSA_SCHEMA4_EXPECTED_COMMIT=commit,MOSA_SCHEMA4_SCOPE="five",
                 MOSA_SCHEMA4_AUTHORIZATION=driver.FIVE_TOKEN+commit,GITHUB_ACTIONS="true",
                 GITHUB_RUN_ATTEMPT="1",GITHUB_EVENT_NAME="workflow_dispatch",GITHUB_REF="refs/heads/main",
                 GITHUB_REPOSITORY="masterxfix/MOSA-2",GITHUB_SHA=commit,GITHUB_RUN_ID="123")
        self.assertEqual(driver.authorize(env)[0],commit)
        env["MOSA_SCHEMA4_AUTHORIZATION"]=driver.TOKEN+commit
        with self.assertRaises(PermissionError): driver.authorize(env)


if __name__ == "__main__":
    unittest.main()
