"""Synthetic identity and immutable-route plans; no credentials, network, or database."""
import copy
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
IDENTITY = dict(canonical_name='Synthetic Alpha', display_name='Synthetic Alpha', asset_class='equity',
    identifier_type='isin', identifier_value='US0378331005', normalized_value='US0378331005', scope_key='', is_primary=1)
UNITS = dict(unit_contract_version='mosa2-market-unit-v1', quote_unit_key='EUR', quote_unit_version='1',
    quantity_basis_unit_key=None, quantity_basis_unit_version=None, quantity_basis_amount=None,
    volume_unit_key=None, volume_unit_version=None)


def call(**data):
    return json.loads(subprocess.check_output(['php', str(ROOT/'tests/market_onboarding_fixture.php')], input=json.dumps(data).encode()))


def state(identifier=False):
    s = dict(m2_entities=[dict(id='7', entity_type='asset', canonical_name=IDENTITY['canonical_name'], status='active')],
        m2_assets=[dict(entity_id='7', asset_class='equity', display_name=IDENTITY['display_name'], base_currency=None, status='active')], m2_asset_identifiers=[])
    if identifier:
        s['m2_asset_identifiers'] = [dict(id='8', asset_id='7', identifier_type='isin', normalized_value=IDENTITY['normalized_value'],
            identifier_value=IDENTITY['identifier_value'], scope_key='', is_primary='1', source_id=None, valid_from=None, valid_to=None)]
    return s


def route_input():
    return dict(asset_id='7', source_id='9', route_type='quote', priority=0, enabled=0,
        evidence=dict(sample_id='SYNTH-A', source_reference='synthetic:observation', family='synthetic',
            row=dict(isin=IDENTITY['normalized_value'], provider_key='synthetic_provider', venue_key='synthetic_venue',
                currency='EUR', quote_variant=None, series='snapshot', observation_kind='market_quote'),
            proof=dict(external_identity=dict(instrument='synthetic-instrument'), route_reference='synthetic:stored-reference')))


class MarketOnboardingTests(unittest.TestCase):
    def asset(self, s, q=None, apply=False):
        return call(action='asset', state=s, identity=q or IDENTITY, apply=apply)['result']

    def route(self, routes=(), qualified=None, units=None):
        return call(action='route', routes=list(routes), qualified=qualified or route_input(), units=units or UNITS)['result']

    def test_new_identity_inserts_only_three_rows_and_replays(self):
        r = self.asset({}, apply=True)
        self.assertEqual(r['plan']['decision'], 'CREATE_ASSET_AND_IDENTIFIER')
        self.assertEqual([w['table'] for w in r['writes']], ['m2_entities','m2_assets','m2_asset_identifiers'])
        self.assertEqual(r['replay']['decision'], 'EXISTING_MATCH')

    def test_bind_identifier_only(self):
        r = self.asset(state(), apply=True)
        self.assertEqual(r['plan']['decision'], 'BIND_IDENTIFIER')
        self.assertEqual([w['table'] for w in r['writes']], ['m2_asset_identifiers'])

    def test_existing_match_writes_nothing(self):
        r = self.asset(state(True), apply=True)
        self.assertEqual(r['plan']['decision'], 'EXISTING_MATCH')
        self.assertEqual(r['writes'], [])

    def test_multiple_asset_candidates_conflict(self):
        s = state();s['m2_entities'].append(dict(s['m2_entities'][0], id='12'))
        self.assertEqual(self.asset(s)['plan']['decision'], 'CONFLICT')

    def test_global_identifier_contradictions_conflict(self):
        for field, value in [('asset_id','12'), ('identifier_value','US5949181045'), ('is_primary','0')]:
            s = state(True);s['m2_asset_identifiers'][0][field] = value
            self.assertEqual(self.asset(s)['plan']['decision'], 'CONFLICT')

    def test_same_contract_for_two_synthetic_equities(self):
        for name, isin in [('Synthetic Alpha','US0378331005'), ('Synthetic Beta','US5949181045')]:
            q = dict(IDENTITY, canonical_name=name, display_name=name, identifier_value=isin, normalized_value=isin)
            self.assertEqual(self.asset({}, q, apply=True)['replay']['decision'], 'EXISTING_MATCH')

    def test_new_route_revision_one_without_allocated_asset_id(self):
        q = route_input();q['asset_id'] = None;r = self.route(qualified=q)
        self.assertEqual(r['decision'], 'CREATE_REVISION');self.assertEqual(r['row']['route_revision'], '1')
        self.assertIsNone(r['row']['asset_id'])

    def test_legacy_group_next_revision_and_no_mutation(self):
        r = self.route()['row'];legacy = dict(r, id='11', route_revision='4', **{k:None for k in UNITS})
        before = copy.deepcopy(legacy);plan = self.route([legacy])
        self.assertEqual(plan['row']['route_revision'], '5');self.assertEqual(legacy, before)

    def test_both_unique_groups_reject_conflicting_binding(self):
        r = dict(self.route()['row'], id='11')
        for bad in [dict(r, asset_id='20'), dict(r, external_key='other'), r]:
            rows = [bad, dict(bad, id='12')] if bad == r else [bad]
            self.assertEqual(self.route(rows)['decision'], 'CONFLICT')

    def test_unit_binding_immutable_and_existing_match(self):
        r = dict(self.route()['row'], id='11')
        self.assertEqual(self.route([r])['decision'], 'EXISTING_MATCH')
        units = dict(UNITS, quote_unit_key='GBP');p = self.route([r], units=units)
        self.assertEqual(p['row']['route_revision'], '2');self.assertEqual(r['quote_unit_key'], 'EUR')

    def test_missing_reference_or_partial_units_rejected(self):
        q = route_input();q['evidence']['proof'].pop('route_reference')
        self.assertFalse(call(action='route', routes=[], qualified=q, units=UNITS)['ok'])
        u = dict(UNITS, volume_unit_key='shares')
        self.assertFalse(call(action='route', routes=[], qualified=route_input(), units=u)['ok'])

    def test_shared_code_has_no_asset_literals_or_mutating_sql(self):
        files = [ROOT/'scripts/market_collector'/n for n in ['onboarding.php','live_persistence.php','live_bridge.py']]
        text = '\n'.join(p.read_text() for p in files)
        self.assertNotIn('P'+'NE', text)
        self.assertNotIn('DE'+'000A0JBPG2', text)
        for pattern in ['UPDATE ', 'UPSERT ', 'REPLACE INTO', 'INSERT IGNORE']:
            self.assertNotIn(pattern, text)

    def existing_live(self):
        route = dict(self.route()['row'], id='11', created_at='2026-01-01 00:00:00.000000',
                     updated_at='2026-01-01 00:00:00.000000')
        s = state(True)
        s.update(m2_sources=[dict(id='9', source_key='provider:synthetic_provider', source_type='market_data', enabled='1')],
                 m2_units=[dict(unit_key='EUR', unit_version='1', unit_contract_version=UNITS['unit_contract_version'], monetary_currency_code='EUR')],
                 m2_asset_source_routes=[route], m2_market_observations=[dict(id='21', price='42')])
        m = dict(policy='USE_EXISTING_ROUTE', identity=IDENTITY, instrument=IDENTITY['normalized_value'],
                 route_evidence=route_input()['evidence'], unit_binding=UNITS,
                 adapter_module='synthetic.adapter', adapter_class='SyntheticAdapter')
        return s, m

    def test_historical_isin_request_binding_remains_exact(self):
        s, m = self.existing_live()
        self.assertTrue(call(action='complete_plan', state=s, manifest=m)['ok'])
        m['instrument'] = 'UNBOUND-SYMBOL'
        self.assertFalse(call(action='complete_plan', state=s, manifest=m)['ok'])

    def test_explicit_symbol_requires_unique_source_scoped_registry_binding(self):
        s, m = self.existing_live()
        m = copy.deepcopy(m)
        m.update(request_identity_field='symbol', instrument='SYNTH.A')
        m['route_evidence']['proof']['external_identity'] = dict(symbol=m['instrument'])
        q = route_input();q['evidence'] = m['route_evidence']
        s['m2_asset_source_routes'] = [dict(self.route(qualified=q)['row'], id='11',
            created_at='2026-01-01 00:00:00.000000', updated_at='2026-01-01 00:00:00.000000')]
        symbol = dict(id='10', asset_id='7', identifier_type='ticker',
            identifier_value=m['instrument'], normalized_value=m['instrument'],
            scope_key=s['m2_sources'][0]['source_key'], source_id=s['m2_sources'][0]['id'],
            is_primary='0', valid_from=None, valid_to=None)
        self.assertFalse(call(action='complete_plan', state=s, manifest=m)['ok'])
        s['m2_asset_identifiers'].append(symbol)
        self.assertTrue(call(action='complete_plan', state=s, manifest=m)['ok'])
        for field, value in [('asset_id','other'), ('source_id','other'), ('scope_key',''),
                             ('valid_to','2026-01-01 00:00:00.000000')]:
            bad = copy.deepcopy(s);bad['m2_asset_identifiers'][-1][field] = value
            self.assertFalse(call(action='complete_plan', state=bad, manifest=m)['ok'])
        bad = copy.deepcopy(s);bad['m2_asset_identifiers'].append(dict(symbol,id='11'))
        self.assertFalse(call(action='complete_plan', state=bad, manifest=m)['ok'])
        bad = copy.deepcopy(m);bad['route_evidence']['proof']['external_identity']['symbol']='OTHER'
        self.assertFalse(call(action='complete_plan', state=s, manifest=bad)['ok'])

    def test_reuse_materializes_exact_row_without_writes(self):
        s, _ = self.existing_live();plan = self.route(s['m2_asset_source_routes'])
        r = call(action='materialize', state=s, plan=plan, asset_id='7')['result']
        self.assertEqual(r['writes'], []);self.assertEqual(r['row'], s['m2_asset_source_routes'][0])
        self.assertEqual(r['after'], r['before'])

    def test_reuse_materializer_rejects_binding_drift(self):
        s, _ = self.existing_live();plan = self.route(s['m2_asset_source_routes'])
        for field, value in [('id','12'), ('asset_id','12'), ('route_revision','2'), ('priority','1'),
                             ('enabled','1'), ('quote_unit_key','GBP')]:
            changed = copy.deepcopy(s);changed['m2_asset_source_routes'][0][field] = value
            self.assertFalse(call(action='materialize', state=changed, plan=plan, asset_id='7')['ok'])

    def test_reuse_requires_existing_asset_before_acquisition(self):
        s, m = self.existing_live();s['m2_asset_identifiers'] = []
        r = call(action='complete_plan', state=s, manifest=m)
        self.assertFalse(r['ok']);self.assertIn('existing_asset_required', r['error'])

    def test_reuse_requires_existing_route_before_acquisition(self):
        s, m = self.existing_live();s['m2_asset_source_routes'] = []
        r = call(action='complete_plan', state=s, manifest=m)
        self.assertFalse(r['ok']);self.assertIn('policy_route_required', r['error'])

    def test_reuse_rejects_revision_creation_for_unit_drift(self):
        s, m = self.existing_live();s['m2_asset_source_routes'][0]['quote_unit_version'] = '2'
        r = call(action='complete_plan', state=s, manifest=m)
        self.assertFalse(r['ok']);self.assertIn('policy_route_required', r['error'])

    def test_reuse_delta_allows_only_observation_and_preserves_complete_route(self):
        s, m = self.existing_live();plan = call(action='complete_plan', state=s, manifest=m)['result']
        self.assertEqual(plan['asset']['decision'], 'EXISTING_MATCH')
        self.assertEqual(plan['route']['decision'], 'EXISTING_MATCH')
        self.assertEqual(plan['deltas'], dict(m2_entities=0,m2_assets=0,m2_asset_identifiers=0,
                                            m2_asset_source_routes=0,m2_market_observations=1))
        after = copy.deepcopy(s);new = dict(id='22', price='42');after['m2_market_observations'].append(new)
        args = dict(action='delta', before=s, after=after, plan=plan, inserted=dict(m2_market_observations=[new]))
        self.assertTrue(call(**args)['ok'])
        for field in s['m2_asset_source_routes'][0]:
            bad = copy.deepcopy(after);bad['m2_asset_source_routes'][0][field] = 'changed'
            self.assertFalse(call(**dict(args, after=bad))['ok'])
        bad = copy.deepcopy(after);bad['m2_market_observations'][0]['price'] = '43'
        self.assertFalse(call(**dict(args, after=bad))['ok'])

    def test_onboarding_policy_still_creates_one_route(self):
        s, m = self.existing_live();s['m2_asset_source_routes'] = [];m.pop('policy')
        plan = call(action='complete_plan', state=s, manifest=m)['result']
        self.assertEqual(plan['policy'], 'ONBOARD_NEW_ROUTE');self.assertEqual(plan['route']['decision'], 'CREATE_REVISION')
        result = call(action='materialize', state=s, plan=plan['route'], asset_id='7')['result']
        self.assertEqual(len(result['writes']), 1);self.assertEqual(result['row']['route_revision'], '1')

    def test_reuse_remains_in_common_orchestrator_without_asset_literals(self):
        self.test_shared_code_has_no_asset_literals_or_mutating_sql()
        text = (ROOT/'scripts/market_collector/live_persistence.php').read_text()
        self.assertEqual(text.count('function run('), 1)
        s, m = self.existing_live();m['policy'] = 'UNKNOWN'
        self.assertFalse(call(action='complete_plan', state=s, manifest=m)['ok'])
