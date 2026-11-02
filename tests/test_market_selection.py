"""General DB-driven market selection; synthetic only, no network or database."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
NOW = '2026-11-02 12:00:00.000000'
UNITS = dict(unit_contract_version='mosa2-market-unit-v1', quote_unit_key='EUR', quote_unit_version='1', unit_status='frozen', unit_currency='EUR')


def php_executable():
    candidates = [shutil.which('php')]
    if os.name == 'nt':
        candidates.append(r'C:\php\php.exe')
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    location = 'PATH' if os.name != 'nt' else 'PATH or C:\\php\\php.exe'
    raise FileNotFoundError(f'PHP executable not found in {location}')


def call(data):
    return json.loads(subprocess.check_output([php_executable(), str(ROOT / 'tests/market_selection_fixture.php')], input=json.dumps(data).encode()))


def route(asset_id, source_id='9', route_id=None, revision='1', **changes):
    row = dict(id=route_id or str(100 + int(asset_id)), asset_id=str(asset_id), source_id=str(source_id), source_key='provider:synthetic_quote', source_name='Synthetic quote', source_type='market_data', source_enabled='1', route_revision=str(revision), route_type='quote', priority='0', enabled='1', external_key='market-v1:' + 'a' * 64, **UNITS)
    row.update(changes)
    return row


def observation(asset_id, source_id, route_id, observation_id='501', market_at='2026-11-02 11:59:00.000000', price='42.50'):
    return dict(id=str(observation_id), asset_id=str(asset_id), source_id=str(source_id), route_id=str(route_id), observation_format_version='2', market_at=market_at, observed_at=market_at, price=price, currency='EUR')


def base():
    assets = [dict(asset_id=str(i), display_name=name, asset_class='equity', status='active') for i, name in [(1, 'Alpha'), (2, 'Beta'), (3, 'Gamma')]]
    assets.append(dict(asset_id='4', display_name='Synthetic ETF', asset_class='etf', status='active'))
    identifiers = [dict(asset_id=str(i), identifier_type='isin', normalized_value=isin, scope_key='', is_primary='1', valid_to=None) for i, isin in [(1, 'US0378331005'), (2, 'US5949181045'), (3, 'GB0002634946'), (4, 'IE00B4L5Y983')]]
    routes = [route(1, route_id='101'), route(2, route_id='102')]
    currents = [dict(asset_id='1', source_id='9', route_id='101', observation_id='501', observation_format_version='2', route_revision='1', market_at='2026-11-02 11:59:00.000000', observed_at='2026-11-02 11:59:00.000000', price='42.50')]
    return dict(assets=assets, identifiers=identifiers, routes=routes, currents=currents,
                observations=[observation('1', '9', '101')], now=NOW)


class MarketSelectionTests(unittest.TestCase):
    def test_active_equities_use_routes_without_fixed_five_or_nine_scope(self):
        result = call(base())['result']
        self.assertEqual(result['counts']['active_equities'], 3)
        self.assertEqual(result['counts']['active_etfs_excluded'], 1)
        self.assertEqual(result['counts']['qualified_for_collector'], 2)
        self.assertEqual([x['collector_status'] for x in result['assets']], ['READY', 'READY', 'ROUTE_UNAVAILABLE'])
        self.assertEqual(result['counts']['current_valid'], 1)
        self.assertEqual(result['counts']['current_missing'], 2)

    def test_disabled_qualified_route_is_manual_preparable_but_not_automatic(self):
        data = base();data['routes'][0]['enabled'] = '0'
        before = copy.deepcopy(data)
        result = call(data)['result'];item = next(x for x in result['assets'] if x['name'] == 'Alpha')
        self.assertEqual(item['route_status'], 'NO_QUALIFIED_ROUTE')
        self.assertEqual(item['collector_status'], 'ROUTE_UNAVAILABLE')
        self.assertEqual(item['manual_status'], 'MANUAL_ROUTE_PREPARABLE')
        self.assertEqual(len(item['manual_routes']), 1)
        self.assertEqual(item['manual_routes'][0]['enabled'], '0')
        self.assertEqual(result['counts']['manual_preparable'], 1)
        self.assertEqual(result['counts']['manual_route_options'], 1)
        self.assertEqual(data, before)

    def test_enabled_legacy_route_without_unit_is_not_manual_preparable(self):
        data = base();data['routes'][0].update(enabled='1', unit_contract_version=None, quote_unit_key=None, quote_unit_version=None, unit_status=None, unit_currency=None)
        result = call(data)['result'];item = next(x for x in result['assets'] if x['name'] == 'Alpha')
        self.assertEqual(item['route_reason'], 'UNIT_NOT_QUALIFIED')
        self.assertEqual(item['manual_status'], 'NO_MANUAL_ROUTE')
        self.assertEqual(item['manual_route_reason'], 'MANUAL_ROUTE_MUST_BE_DISABLED')
        self.assertEqual(item['manual_routes'], [])

    def test_multiple_manual_sources_are_options_without_automatic_selection(self):
        data = base();data['routes'][0]['enabled'] = '0'
        data['routes'].append(route(1, source_id='10', route_id='110', source_key='provider:other_quote', enabled='0'))
        result = call(data)['result'];item = next(x for x in result['assets'] if x['name'] == 'Alpha')
        self.assertEqual(item['route_status'], 'NO_QUALIFIED_ROUTE')
        self.assertEqual(item['collector_status'], 'ROUTE_UNAVAILABLE')
        self.assertEqual(item['manual_status'], 'MANUAL_ROUTE_PREPARABLE')
        self.assertEqual(item['manual_route_reason'], 'MULTIPLE_MANUAL_ROUTES')
        self.assertEqual({x['source_id'] for x in item['manual_routes']}, {'9', '10'})
        self.assertNotIn('Alpha', [x['name'] for x in result['collector_candidates']])

    def test_new_valid_equity_enters_without_selector_code_change(self):
        data = base()
        data['assets'].append(dict(asset_id='5', display_name='Delta', asset_class='equity', status='active'))
        data['identifiers'].append(dict(asset_id='5', identifier_type='isin', normalized_value='FR0000121014', scope_key='', is_primary='1', valid_to=None))
        data['routes'].append(route(5, route_id='105'))
        result = call(data)['result']
        self.assertEqual(result['counts']['active_equities'], 4)
        self.assertEqual(result['counts']['qualified_for_collector'], 3)
        self.assertIn('FR0000121014', [x['isin'] for x in result['collector_candidates']])

    def test_isin_duplicate_is_rejected(self):
        data = base();data['identifiers'][1]['normalized_value'] = data['identifiers'][0]['normalized_value']
        result = call(data)['result']
        by_name = {x['name']: x for x in result['assets']}
        self.assertEqual(by_name['Alpha']['identity_status'], 'DUPLICATE_ISIN')
        self.assertEqual(by_name['Beta']['identity_status'], 'DUPLICATE_ISIN')
        self.assertNotIn('Beta', [x['name'] for x in result['collector_candidates']])

    def test_latest_qualified_routes_from_two_sources_are_ambiguous(self):
        data = base();data['routes'].append(route(1, source_id='10', route_id='110', source_key='provider:other_quote'))
        result = call(data)['result'];item = next(x for x in result['assets'] if x['name'] == 'Alpha')
        self.assertEqual(item['route_status'], 'AMBIGUOUS_ROUTE')
        self.assertEqual(item['collector_status'], 'ROUTE_UNAVAILABLE')

    def test_disabled_latest_revision_does_not_fall_back_to_old_route(self):
        data = base();data['routes'].append(route(1, route_id='111', revision='2', enabled='0'))
        result = call(data)['result'];item = next(x for x in result['assets'] if x['name'] == 'Alpha')
        self.assertEqual(item['route_status'], 'NO_QUALIFIED_ROUTE')
        self.assertEqual(item['route_reason'], 'ROUTE_DISABLED')

    def test_unsupported_currency_is_not_converted_or_activated(self):
        data = base();data['routes'][1]['unit_currency'] = 'USD';data['routes'][1]['quote_unit_key'] = 'USD'
        result = call(data)['result'];item = next(x for x in result['assets'] if x['name'] == 'Beta')
        self.assertEqual(item['route_reason'], 'CURRENCY_NOT_QUALIFIED')
        self.assertNotIn('Beta', [x['name'] for x in result['collector_candidates']])

    def test_current_input_is_not_mutated_and_stale_is_explicit(self):
        data = base();data['currents'][0]['market_at'] = '2026-11-02 10:00:00.000000';data['currents'][0]['observed_at'] = '2026-11-02 10:00:00.000000'
        data['observations'][0]['market_at'] = '2026-11-02 10:00:00.000000';data['observations'][0]['observed_at'] = '2026-11-02 10:00:00.000000'
        before = copy.deepcopy(data)
        result = call(data)['result'];item = next(x for x in result['assets'] if x['name'] == 'Alpha')
        self.assertEqual(item['current_status'], 'CURRENT_STALE')
        self.assertEqual(data, before)

    def test_scope_overflow_aborts_instead_of_silently_truncating(self):
        data = base();data['assets'] = [dict(asset_id=str(i), display_name='Asset ' + str(i), asset_class='equity', status='active') for i in range(1, 12)]
        data['identifiers'] = [dict(asset_id=str(i), identifier_type='isin', normalized_value='US0378331005', scope_key='', is_primary='1', valid_to=None) for i in range(1, 12)]
        result = call(dict(data, max_assets=10))
        self.assertFalse(result['ok']);self.assertEqual(result['error'], 'selection_scope_overflow')

    def test_current_and_route_contracts_have_no_provider_or_write_capability(self):
        text = (ROOT / 'scripts/market_collector/selection.php').read_text()
        self.assertNotRegex(text, r'\b(INSERT|UPDATE|DELETE|REPLACE)\b')
        self.assertNotIn('http', text.lower())


if __name__ == '__main__':
    unittest.main()
