import ast
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import fundamentals_hkex_once as once


class HkexOnceTests(unittest.TestCase):
    def env(self):
        sha='a'*40
        return dict(GITHUB_REPOSITORY='masterxfix/MOSA-2',GITHUB_REF='refs/heads/main',GITHUB_EVENT_NAME='workflow_dispatch',
                    GITHUB_RUN_ATTEMPT='1',GITHUB_RUN_NUMBER='2',GITHUB_SHA=sha,EXPECTED_COMMIT=sha,
                    AUTHORIZATION=once.AUTH+sha,GITHUB_WORKFLOW_REF='masterxfix/MOSA-2/'+once.WORKFLOW+'@refs/heads/main')

    def test_exact_workflow_and_execution_bindings(self):
        once.guard(self.env())
        self.assertEqual(once.execution_overrides(json.dumps(once.EXECUTIONS)),once.EXECUTIONS)
        workflow=(Path(__file__).resolve().parents[1]/'.github/workflows/fundamentals-hkex-once.yml').read_text(encoding='utf-8')
        for marker in ('workflow_dispatch:','github.run_attempt == 1','github.run_number == 2','MOSA2-HKEX-FUNDAMENTALS-SECOND-20261102:$GITHUB_SHA',
                       'fundamentals-hkex-byd-20261102-01','fundamentals-hkex-ubtech-20261102-01','scripts/fundamentals_hkex_once.py'):
            self.assertIn(marker,workflow)
        self.assertIn('reusable_manual=True',Path(__file__).resolve().parents[1].joinpath('scripts/fundamentals_hkex_once.py').read_text(encoding='utf-8'))
        self.assertNotIn('schedule:',workflow);self.assertNotIn('push:',workflow)

    def test_binding_rejects_changed_commit_attempt_workflow_or_execution(self):
        base=self.env()
        for key,value in [('GITHUB_SHA','b'*40),('EXPECTED_COMMIT','b'*40),('GITHUB_RUN_ATTEMPT','2'),
                          ('GITHUB_RUN_NUMBER','1'),('GITHUB_RUN_NUMBER','3'),
                          ('GITHUB_WORKFLOW_REF','masterxfix/MOSA-2/.github/workflows/other.yml@refs/heads/main'),
                          ('AUTHORIZATION','MOSA2-HKEX-FUNDAMENTALS-SECOND-20261102:'+'b'*40)]:
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


if __name__=='__main__':unittest.main()
