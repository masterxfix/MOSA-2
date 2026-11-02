import ast
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import fundamentals_hkex_once as once
from scripts import fundamentals_analysis_once as analysis_once


class HkexOnceTests(unittest.TestCase):
    def env(self):
        sha='a'*40
        return dict(GITHUB_REPOSITORY='masterxfix/MOSA-2',GITHUB_REF='refs/heads/main',GITHUB_EVENT_NAME='workflow_dispatch',
                    GITHUB_RUN_ATTEMPT='1',GITHUB_RUN_NUMBER='4',GITHUB_SHA=sha,EXPECTED_COMMIT=sha,
                    AUTHORIZATION=once.AUTH+sha,GITHUB_WORKFLOW_REF='masterxfix/MOSA-2/'+once.WORKFLOW+'@refs/heads/main')

    def test_exact_workflow_and_execution_bindings(self):
        once.guard(self.env())
        self.assertEqual(once.execution_overrides(json.dumps(once.EXECUTIONS)),once.EXECUTIONS)
        workflow=(Path(__file__).resolve().parents[1]/'.github/workflows/fundamentals-hkex-once.yml').read_text(encoding='utf-8')
        for marker in ('workflow_dispatch:','github.run_attempt == 1','github.run_number == 4','MOSA2-HKEX-FUNDAMENTALS-FOURTH-20261102:$GITHUB_SHA',
                       'fundamentals-hkex-byd-20261102-01','fundamentals-hkex-ubtech-20261102-01','scripts/fundamentals_hkex_once.py'):
            self.assertIn(marker,workflow)
        self.assertIn('reusable_manual=True',Path(__file__).resolve().parents[1].joinpath('scripts/fundamentals_hkex_once.py').read_text(encoding='utf-8'))
        self.assertNotIn('test_fundamentals_esef.py',workflow)
        self.assertNotIn('schedule:',workflow);self.assertNotIn('push:',workflow)

    def test_binding_rejects_changed_commit_attempt_workflow_or_execution(self):
        base=self.env()
        for key,value in [('GITHUB_SHA','b'*40),('EXPECTED_COMMIT','b'*40),('GITHUB_RUN_ATTEMPT','2'),
                          ('GITHUB_RUN_NUMBER','1'),('GITHUB_RUN_NUMBER','2'),('GITHUB_RUN_NUMBER','3'),('GITHUB_RUN_NUMBER','5'),('GITHUB_RUN_NUMBER','6'),
                          ('GITHUB_WORKFLOW_REF','masterxfix/MOSA-2/.github/workflows/other.yml@refs/heads/main'),
                          ('AUTHORIZATION','MOSA2-HKEX-FUNDAMENTALS-FOURTH-20261102:'+'b'*40)]:
            with self.subTest(key=key):
                with self.assertRaises(ValueError): once.guard(base|{key:value})
        bad=dict(once.EXECUTIONS);bad['CNE100000296']='fundamentals-hkex-byd-20261102-02'
        with self.assertRaises(ValueError): once.execution_overrides(json.dumps(bad))

    def test_manifest_binds_both_profiles_and_target_counts(self):
        self.assertEqual({p['profile']['isin'] for p in once.PROFILES},{'CNE100000296','CNE100006CQ4'})
        self.assertEqual(set(once.EXECUTIONS),{p['profile']['isin'] for p in once.PROFILES})
        for entry in once.PROFILES:
            expected=once.EXPECTED['profiles'][entry['profile']['profile_key']]
            self.assertEqual(expected['isin'],entry['profile']['isin'])
            self.assertEqual(set(expected['values']),{'revenue','operating_profit','profit_before_tax','profit_after_tax','operating_cashflow'})
            self.assertEqual({y for values in expected['values'].values() for y in values},{'2024','2025'})

    def test_canonical_db_names_bind_to_their_unique_isins(self):
        assets=[
            dict(name='BYD',identifiers=[dict(normalized_value='CNE100000296')],facts=[],current={}),
            dict(name='Ubtech Robotics',identifiers=[dict(normalized_value='CNE100006CQ4')],facts=[],current={}),
            dict(name='BYD Company Limited',identifiers=[dict(normalized_value='CNE100000296')],facts=[],current={}),
            dict(name='UBTECH ROBOTICS CORP LTD',identifiers=[dict(normalized_value='CNE100006CQ4')],facts=[],current={}),
        ]
        self.assertEqual(once.select_asset(dict(assets=assets[:2]), once.PROFILES[0]['profile']), assets[0])
        self.assertEqual(once.select_asset(dict(assets=assets[:2]), once.PROFILES[1]['profile']), assets[1])
        self.assertEqual(once.select_asset(dict(assets=assets[2:]), once.PROFILES[0]['profile']), assets[2])
        self.assertEqual(once.select_asset(dict(assets=assets[2:]), once.PROFILES[1]['profile']), assets[3])
        for bad in (
            dict(name='BYD',identifiers=[dict(normalized_value='CNE100006CQ4')],facts=[],current={}),
            dict(name='Ubtech Robotics',identifiers=[dict(normalized_value='CNE100000296')],facts=[],current={}),
            dict(name='Other Company',identifiers=[dict(normalized_value='CNE100000296')],facts=[],current={}),
        ):
            with self.assertRaises(ValueError): once.select_asset(dict(assets=[bad]), once.PROFILES[0]['profile'])

    def test_preservation_scope_binds_all_seven_assets_and_fingerprints(self):
        self.assertEqual(sum(row['observations'] for row in once.PRESERVE),79)
        self.assertEqual(sum(row['current'] for row in once.PRESERVE),40)
        self.assertEqual({row['isin'] for row in once.PRESERVE},
                         {'DE000A0JBPG2','DE0005313704','AU000000DRO2','US67066G1040',
                          'US76655K1034','NO0010081235','DK0060252690'})
        assets=[]
        for entry in once.PRESERVE:
            assets.append(dict(name=entry['name'],identifiers=[dict(normalized_value=entry['isin'])],
                               facts=[dict(id=str(i)) for i in range(entry['observations'])],
                               current={str(i):[dict(observation_id=str(i))] for i in range(entry['current'])}))
        preserved=once.assets_with_fundamentals(dict(assets=assets))
        self.assertEqual({row['isin'] for row in preserved},{row['isin'] for row in once.PRESERVE})
        self.assertTrue(all(len(row['fingerprint'])==64 for row in preserved))
        changed=list(assets);changed[0]=dict(changed[0],facts=changed[0]['facts'][:-1])
        with self.assertRaises(ValueError): once.assets_with_fundamentals(dict(assets=changed))

    def test_archive_allowlist_is_exclusive_for_hkex_executions(self):
        source=(Path(__file__).resolve().parents[1]/'scripts/fundamentals/archive_remote.py').read_text(encoding='utf-8')
        tree=ast.parse(source)
        values={}
        for node in tree.body:
            if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
                if node.targets[0].id in {'EVIDENCE_EXECUTIONS','CURATED_EXECUTIONS'}:
                    values[node.targets[0].id]=ast.literal_eval(node.value)
        evidence=values['EVIDENCE_EXECUTIONS'];curated=values['CURATED_EXECUTIONS']
        hkex={'fundamentals-hkex-byd-20261102-01','fundamentals-hkex-ubtech-20261102-01'}
        self.assertTrue(hkex <= evidence)
        self.assertTrue(hkex.isdisjoint(curated))
        for value in ('fundamentals-hkex-byd-20261102-02','fundamentals-hkex-ubtech-20261102-02',
                      'fundamentals-hkex-ubtech-20261102-01-swapped','unknown-hkex-execution'):
            self.assertNotIn(value,evidence)

    def test_execution_for_uses_only_authorized_static_mapping(self):
        profile=once.PROFILES[0]['profile']
        with patch.dict(os.environ,{},clear=True):
            self.assertEqual(once.execution_for(profile),once.EXECUTIONS[profile['isin']])
        for bad in (
            {},
            {'CNE100000296':'fundamentals-hkex-ubtech-20261102-01','CNE100006CQ4':'fundamentals-hkex-byd-20261102-01'},
            {'CNE100000296':'unknown-execution','CNE100006CQ4':'fundamentals-hkex-ubtech-20261102-01'},
        ):
            with patch.dict(os.environ,{'HKEX_EXECUTION_OVERRIDES':json.dumps(bad)},clear=True):
                with self.assertRaises(ValueError): once.execution_for(profile)

    def test_apply_result_binds_report_and_exact_decimal_facts(self):
        facts=[dict(metric_key='revenue',value_decimal='1.0000000',unit_key='CNY_THOUSAND',fiscal_year='2025',
                    period_start='2025-01-01',period_end='2025-12-31',field_path='evidence:facts/0')]
        report=dict(isin='CNE100000296',ok=False,provider_requests=1)
        result=dict(ok=True,readback='PASS',observations=10,current=5,verified_facts=facts)
        once.bind_db_result(report,result,12.5)
        self.assertTrue(report['ok'])
        self.assertEqual(report['readback'],'PASS')
        self.assertIs(report['verified_facts'],facts)
        equivalent=[dict(facts[0],value_decimal='1')]
        different=[dict(facts[0],value_decimal='2')]
        self.assertEqual(once.normalize_fact_rows(facts),once.normalize_fact_rows(equivalent))
        self.assertNotEqual(once.normalize_fact_rows(facts),once.normalize_fact_rows(different))
        with self.assertRaisesRegex(ValueError,'HKEX_DB_READBACK'):
            once.bind_db_result(dict(ok=False),dict(ok=True,readback='FAIL'),1)

    def test_hkex_readonly_validation_requires_exact_targets_and_preservation(self):
        def raw_fact(metric,year,value,index):
            return dict(metric_key=metric,fiscal_year=year,value_decimal=value,unit_key='CNY_THOUSAND',
                        monetary_currency_code='CNY',fetch_id=100+index,field_path=f'evidence:facts/{index}',evidence_sha256='a'*64)
        assets=[]
        snapshots=[]
        for preserved in once.PRESERVE:
            assets.append(dict(name=preserved['name'],identifiers=[dict(normalized_value=preserved['isin'])],
                               facts=[dict(id=str(i)) for i in range(preserved['observations'])],
                               current={str(i):[dict(observation_id=str(i))] for i in range(preserved['current'])}))
            snapshots.append(dict(identity=dict(isin=[preserved['isin']]),facts=[],current_observation_ids=[]))
        for expected in analysis_once.HKEX_EXPECTED['profiles'].values():
            rows=[];index=0
            for metric,periods in expected['values'].items():
                for year,value in periods.items():
                    rows.append(raw_fact(metric,year,value,index));index+=1
            assets.append(dict(name=expected['isin'],identifiers=[dict(normalized_value=expected['isin'])],facts=rows,
                               current={str(i):[dict(observation_id=str(i))] for i in range(5)}))
            snapshots.append(dict(identity=dict(isin=[expected['isin']]),facts=[dict(unit='CNY_THOUSAND',currency='CNY',origin='issuer_annual_report') for _ in rows],current_observation_ids=[str(i) for i in range(5)]))
        data=dict(assets=assets,validated_totals=analysis_once.HKEX_TOTALS,db_unchanged=True)
        summary=analysis_once.validate_hkex_snapshot(data,snapshots)
        self.assertEqual(summary['target_companies'],2)
        self.assertEqual(summary['preserved_observations'],79)
        changed=json.loads(json.dumps(data))
        changed['assets'][-1]['facts'][0]['value_decimal']='999'
        with self.assertRaisesRegex(ValueError,'HKEX_VALUES'):
            analysis_once.validate_hkex_snapshot(changed,snapshots)


if __name__=='__main__':unittest.main()
