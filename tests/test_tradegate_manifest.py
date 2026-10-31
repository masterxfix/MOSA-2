"""Tradegate qualification uses the existing identity and route materializer."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import unittest

from tests import test_market_onboarding as onboarding

ROOT = Path(__file__).resolve().parents[1]
NOW = '2026-10-31 08:00:00.000000'


def call(**data):
    result = subprocess.run(['php', str(ROOT / 'tests/tradegate_manifest_fixture.php')],
        input=json.dumps(data), text=True, capture_output=True, check=True)
    if result.stderr:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class TradegateManifestTests(unittest.TestCase):
    def test_source_plan_and_existing_identity_route_materialize_then_replay(self):
        source = call(action='source', sources=[], now=NOW)
        self.assertTrue(source['ok'], source)
        self.assertEqual(source['result']['decision'], 'INSERT')
        values = source['result']['values']
        self.assertNotIn('id', values)
        self.assertEqual(values['source_key'], 'provider:tradegate_bsx_mid')
        self.assertEqual(values['display_name'], 'Tradegate · XGAT · Mid')
        self.assertEqual(values['base_url'], 'https://www.tradegatebsx.com/')
        self.assertEqual((values['created_at'], values['updated_at']), (NOW, NOW))
        # Explicit synthetic DB identity. Production sourcePlan never allocates one.
        stored_source = dict(id='18446744073709551614', **values)
        legacy_source = dict(stored_source, id='9', source_key='provider:tradegate_bsx',
                             display_name='Legacy Tradegate source', base_url=None)
        self.assertEqual(call(action='source', sources=[legacy_source], now=NOW)['result'],
                         dict(decision='INSERT', values=values))
        existing = call(action='source', sources=[stored_source], now=NOW)
        self.assertEqual(existing['result'], dict(decision='EXISTING_MATCH', row=stored_source))
        state = onboarding.state(True)
        state.update(m2_sources=[legacy_source, stored_source], m2_asset_source_routes=[],
            m2_units=[dict(unit_key='EUR', unit_version='1',
                          unit_contract_version=onboarding.UNITS['unit_contract_version'],
                          monetary_currency_code='EUR')])
        selection = dict(isin=onboarding.IDENTITY['normalized_value'], name=onboarding.IDENTITY['display_name'])
        before = deepcopy(state)
        planned = call(action='manifest', state=state, selection=selection)
        self.assertTrue(planned['ok'], planned)
        self.assertEqual(state, before)
        result = planned['result']
        self.assertEqual(result['manifest']['policy'], 'ONBOARD_NEW_ROUTE')
        self.assertEqual(result['plan']['asset']['decision'], 'EXISTING_MATCH')
        self.assertEqual(result['plan']['source']['source_id'], stored_source['id'])
        self.assertEqual(result['candidate']['proposed_source_key'], 'provider:tradegate_bsx_mid')
        key = json.loads(result['candidate']['proposed_route_key'].removeprefix('route:'))
        self.assertEqual((key['provider'], key['venue'], key['quote_variant'], key['series']),
                         ('tradegate_bsx_mid', 'tradegate', 'mid', 'snapshot'))
        self.assertNotIn('route_id', result['plan']['route'])

        # Reuse IdentityMemoryStore and the actual applyMarketRoutePlan implementation.
        materialized = onboarding.call(action='materialize', state=state,
                                       plan=result['plan']['route'], asset_id='7')
        self.assertTrue(materialized['ok'], materialized)
        stored = materialized['result']
        self.assertEqual([w['table'] for w in stored['writes']], ['m2_asset_source_routes'])
        self.assertEqual(stored['row']['source_id'], stored_source['id'])
        self.assertEqual(stored['after']['m2_sources'], [legacy_source, stored_source])
        replay = call(action='manifest', state=stored['after'], selection=selection)
        self.assertTrue(replay['ok'], replay)
        self.assertEqual(replay['result']['manifest']['policy'], 'USE_EXISTING_ROUTE')
        self.assertEqual(replay['result']['plan']['route']['route_id'], stored['row']['id'])
        again = onboarding.call(action='materialize', state=stored['after'],
            plan=replay['result']['plan']['route'], asset_id='7')
        self.assertEqual(again['result']['writes'], [])

        for field, value in [('source_type', 'other'), ('base_url', 'https://other.invalid/'),
                             ('display_name', 'Last trade'), ('enabled', '0')]:
            bad = dict(stored_source, **{field: value})
            with self.subTest(source_field=field):
                self.assertFalse(call(action='source', sources=[bad], now=NOW)['ok'])
        self.assertFalse(call(action='source', sources=[stored_source, stored_source], now=NOW)['ok'])
        missing = deepcopy(state)
        missing['m2_sources'] = []
        self.assertFalse(call(action='manifest', state=missing, selection=selection)['ok'])
        missing = deepcopy(state)
        missing['m2_asset_identifiers'] = []
        self.assertFalse(call(action='manifest', state=missing, selection=selection)['ok'])
        self.assertFalse(call(action='manifest', state=state,
                              selection=dict(selection, name='Unqualified name'))['ok'])


if __name__ == '__main__':
    unittest.main()
