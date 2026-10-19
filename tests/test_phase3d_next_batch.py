"""Synthetic offline next-batch evidence, selection and canonical dedupe checks."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'scripts/phase3d/next_batch.php'


class NextBatchTests(unittest.TestCase):
    def candidate(self, n=1):
        isin = 'US0378331005'  # Public test identifier; names and context synthetic.
        key = 'isin_' + isin.lower()
        return dict(candidate_id=f'C{n}', source_reference=f'synthetic:{n}', isin=isin,
                    source_asset_key=key, portfolio_rows=[dict(user_id=1, isin=isin,
                    asset_key=key, mosa_object_key='object_'+'a'*24,
                    display_name='Synthetic Instrument', wkn='ABC123', status='active')],
                    registrations=[dict(user_id=1, isin=isin, asset_key=key,
                    provider_key='boerse_frankfurt_api', source_key=f'boerse_frankfurt_api:{key}:test',
                    status='found', discovered_at='2026-01-01T00:00:00Z',
                    technical=dict(mic='XFRA', currency='EUR'))],
                    etf_evidence=[], consistency_names=['Synthetic Instrument'],
                    consistency_types=[], original_transformable=True, target_type='observation',
                    native_market_quote=True, unit_class='currency_per_instrument',
                    time_semantics_confirmed=True, proposed_source_key='provider:synthetic',
                    proposed_route_key=f'synthetic:route:{n}', observation=dict(currency='EUR',
                    market_at='2026-01-01 12:00:00.000000', observed_at='2026-01-01 12:00:01.000000',
                    price='10.25', bid=None, ask=None, volume=None))

    def run_plan(self, cs=None, facts=None, **kwargs):
        x=dict(candidates=cs if cs is not None else [self.candidate()],
               target_snapshot=dict(complete=True, facts=facts or {}), **kwargs)
        p=subprocess.run(['php', '-r', r'require $argv[1];echo \Mosa2\Phase3D\json(\Mosa2\Phase3D\NextBatch\plan(json_decode($argv[2],true)));', str(MODULE), json.dumps(x)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def result(self, c):
        return self.run_plan([c])['results'][0]

    def etf(self, c):
        return dict(reference_contract_valid=True, active_relationship_valid=True,
                    record=dict(contract_version='mosa_etf_reference_v1', asset_type='etf',
                    isin=c['isin'], object_key=c['isin'], user_id=1, object_name='Synthetic Instrument'))

    def test_exact_name_stock_contract_and_pending_ids(self):
        r=self.result(self.candidate())
        self.assertTrue(r['eligible'])
        self.assertEqual(r['asset']['canonical_name'], 'Synthetic Instrument')
        self.assertEqual(r['asset']['asset_class'], 'equity')
        self.assertEqual(r['evidence']['stock_records'], 1)
        self.assertIsNone(r['asset']['asset_id']); self.assertIsNone(r['route']['route_id'])
        self.assertIsNone(r['dedupe_hex'])
        self.assertEqual(r['expected_action'], 'planned_insert_after_catalog_resolution')

    def test_missing_and_conflicting_names_block(self):
        c=self.candidate(); c['portfolio_rows'][0]['display_name']=''
        self.assertEqual(self.result(c)['status'], 'BLOCKED_NAME')
        c=self.candidate(); c['consistency_names']=['Different Instrument']
        self.assertIn('name_conflict', self.result(c)['reasons'])
        c=self.candidate(); c['portfolio_rows'].append(dict(c['portfolio_rows'][0], display_name='Other'))
        self.assertEqual(self.result(c)['status'], 'BLOCKED_CONFLICT')

    def test_etf_requires_valid_reference_and_active_relationship(self):
        c=self.candidate(); c['registrations']=[]; c['etf_evidence']=[self.etf(c)]
        self.assertEqual(self.result(c)['asset']['asset_class'], 'etf')
        c['etf_evidence'][0]['active_relationship_valid']=False
        self.assertEqual(self.result(c)['status'], 'BLOCKED_CLASS')
        c['etf_evidence'][0]['active_relationship_valid']=True
        c['etf_evidence'][0]['reference_contract_valid']=False
        self.assertFalse(self.result(c)['eligible'])

    def test_stock_etf_conflict_blocks(self):
        c=self.candidate(); c['etf_evidence']=[self.etf(c)]
        self.assertIn('asset_class_conflict',self.result(c)['reasons'])
        self.assertEqual(self.result(c)['status'],'BLOCKED_CONFLICT')

    def test_no_symbol_currency_provider_or_name_type_default(self):
        c=self.candidate(); c['registrations']=[]; c['symbol']='STOCK'; c['currency']='EUR'
        self.assertEqual(self.result(c)['status'],'BLOCKED_CLASS')
        c=self.candidate(); c['registrations'][0]['status']='missing'
        self.assertFalse(self.result(c)['eligible'])
        c=self.candidate(); c['registrations'][0]['discovered_at']=''
        self.assertFalse(self.result(c)['eligible'])
        c=self.candidate(); c['consistency_types']=['ETF']
        self.assertIn('asset_class_conflict',self.result(c)['reasons'])

    def test_identity_context_must_match(self):
        c=self.candidate(); c['registrations'][0]['user_id']=2
        self.assertFalse(self.result(c)['eligible'])
        c=self.candidate(); c['registrations'][0]['isin']='US5949181045'
        self.assertIn('source_identity_conflict',self.result(c)['reasons'])

    def test_cap_determinism_and_existing_source_preference(self):
        cs=[self.candidate(n) for n in range(1,6)]
        cs[-1]['proposed_source_key']='provider:existing'
        facts=dict(m2_sources=[dict(id=7,source_key='provider:existing',source_type='market_data',enabled=1)])
        a=self.run_plan(cs,facts); b=self.run_plan(list(reversed(cs)),facts)
        self.assertEqual(a,b); self.assertEqual(len(a['selected']),3)
        self.assertEqual(a['selected'][0]['candidate_id'],'C5')
        self.assertEqual([r['sample_id'] for r in a['selected']],['P2-A1','P2-A2','P2-A3'])
        h=a.pop('manifest_sha256')
        self.assertEqual(h,hashlib.sha256(json.dumps(a,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest())

    def test_imported_invalid_units_and_current_bars_excluded(self):
        cs=[self.candidate(n) for n in range(1,7)]
        cs[1]['target_type']='bar'; cs[2]['target_type']='current'; cs[3]['original_transformable']=False
        cs[4]['observation']['currency']='GBX'; cs[5]['time_semantics_confirmed']=False
        r=self.run_plan(cs,already_imported_refs=['synthetic:1'])
        self.assertEqual(r['summary']['package_size'],0)

    def test_shared_dedupe_only_with_actual_ids_and_duplicate_readback(self):
        c=self.candidate(); external='market-v1:'+hashlib.sha256(c['proposed_route_key'].encode()).hexdigest()
        facts=dict(m2_asset_identifiers=[dict(identifier_type='isin',scope_key='',normalized_value=c['isin'],asset_id=7)],
                   m2_assets=[dict(entity_id=7,display_name='Synthetic Instrument',asset_class='equity')],
                   m2_sources=[dict(id=8,source_key=c['proposed_source_key'],source_type='market_data',enabled=1)],
                   m2_asset_source_routes=[dict(id=9,asset_id=7,source_id=8,route_type='quote',external_key=external,enabled=1,priority=0)])
        r=self.run_plan([c],facts)['results'][0]
        row=dict(asset_id='7',source_id='8',route_id='9',**r['observation'])
        p=subprocess.run(['php','-r',r'require $argv[1];echo bin2hex(\Mosa2\Phase3C\dedupeKey(json_decode($argv[2],true)));',str(ROOT/'scripts/phase3c/market_flow.php'),json.dumps(row)],capture_output=True,text=True,check=True)
        self.assertEqual(r['dedupe_hex'],p.stdout)
        facts['m2_market_observations']=[dict(row,dedupe_hex=p.stdout)]
        out=self.run_plan([c],facts)
        self.assertEqual(out['results'][0]['expected_action'],'expected_duplicate')
        self.assertEqual(out['summary']['package_size'],0)

    def test_module_has_no_db_or_provider_adapter(self):
        source=MODULE.read_text()
        for forbidden in ['new PDO','mysqli_','curl_exec','file_put_contents','INSERT INTO','UPDATE m2_']:
            self.assertNotIn(forbidden,source)


if __name__=='__main__':
    unittest.main()
