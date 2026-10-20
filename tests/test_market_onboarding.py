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
