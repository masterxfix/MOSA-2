"""Synthetic packages only: no provider, model or database connections."""
import copy
from contextlib import nullcontext
import hashlib
import io
import json
from pathlib import Path
import socket
import subprocess
import unittest
from unittest.mock import patch, Mock
import zipfile
from scripts.fundamentals import esef
from scripts import fundamentals_esef_once as runner
from scripts.fundamentals.analysis import build
from scripts.fundamentals.assessment import prepare

STAMP='2026-11-01 17:00:00.000000'
NS='https://xbrl.ifrs.org/taxonomy/2024-03-27/ifrs-full'


def document(profile=runner.PROFILES[0]):
    contexts=''
    for year in (2024,2025):
        contexts+=f'<xbrli:context id="Y{year}"><xbrli:entity><xbrli:identifier scheme="http://standards.iso.org/iso/17442">{profile["lei"]}</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>{year}-01-01</xbrli:startDate><xbrli:endDate>{year}-12-31</xbrli:endDate></xbrli:period></xbrli:context>'
    facts=''
    for tag in esef.TAGS:
        for year in (2024,2025):
            sign='' if tag=='Revenue' else 'sign="-"'
            facts+=f'<ix:nonFraction name="ifrs:{tag}" contextRef="Y{year}" unitRef="money" decimals="-6" scale="6" {sign} format="ixt:num-dot-decimal">{100 if year==2024 else 120}</ix:nonFraction>'
    for tag,value in [('NameOfReportingEntityOrOtherMeansOfIdentification',profile['names'][0]),('DescriptionOfNatureOfFinancialStatements','Consolidated financial statements'),('DateOfEndOfReportingPeriod2013','2025-12-31')]:
        facts+=f'<ix:nonNumeric name="ifrs:{tag}" contextRef="Y2025">{value}</ix:nonNumeric>'
    return f'''<?xml version="1.0" encoding="utf-8"?>
    <html xmlns="http://www.w3.org/1999/xhtml" xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
    xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:ifrs="{NS}"
    xmlns:iso4217="http://www.xbrl.org/2003/iso4217" xmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/2020-02-12"
    xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:ext="https://synthetic.invalid/2025"
    xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink">
    <head><title>Synthetic annual consolidated report</title></head><body>
    <div style="display:none"><ix:header><ix:references><link:schemaRef xlink:type="simple" xlink:href="https://synthetic.invalid/taxonomy.xsd"/></ix:references><ix:resources>{contexts}<xbrli:unit id="money"><xbrli:measure>iso4217:{profile['expected_currency']}</xbrli:measure></xbrli:unit></ix:resources></ix:header></div>
    <div>{facts}</div></body></html>'''


def zipped(text, name='report/reports/annual.xhtml'):
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:z.writestr(name,text)
    return buf.getvalue()


def plan(text=None, profile=runner.PROFILES[0], execution=None):
    raw=zipped(document(profile) if text is None else text)
    meta=dict(url=profile['url'],http_status=200,content_type='application/zip',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
              request_started_at=STAMP,observed_at=STAMP,
              execution=profile['execution'] if execution is None else execution,commit='a'*40)
    p=esef.parse(raw,meta,dict(isin=profile['isin'],name=profile['names'][0]),profile)
    p['archive']=dict(storage_key='/private/synthetic/evidence.json',durable=True,sha256=p['stored_evidence']['sha256'],bytes=p['stored_evidence']['bytes'])
    return p


def snapshot(p):
    rows=[];current={}
    for i,r in enumerate(p['observations']):
        rows.append(dict(r,id=str(i+1),source_id='1',fetch_id='1',parser_key=p['parser_key'],parse_status='parsed',
            evidence_sha256=p['stored_evidence']['sha256'],monetary_currency_code=r['unit_key'],scale_numerator='1',scale_denominator='1'))
        current.setdefault(r['metric_key']+':fy',[dict(observation_id=str(i+1))])
    return build(dict(id='1',name='Synthetic',identifiers=[dict(normalized_value='NO0010081235')],facts=rows,current=current,market_sources=[]),[dict(id='1',source_type='issuer_annual_report')])


class EsefTests(unittest.TestCase):
    def test_two_issuers_real_arelle_no_network_scaling_and_analysis(self):
        with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')):
            for profile in runner.PROFILES:
                p=plan(profile=profile);s=snapshot(p);prepare(s)
                self.assertEqual(len(p['observations']),10)
                self.assertEqual({r['unit_key'] for r in p['observations']},{profile['expected_currency']})
                self.assertEqual(p['observations'][0]['value_decimal'],'120000000')
                self.assertEqual(p['observations'][1]['value_decimal'],'-120000000')
                self.assertEqual(sum(c['kind']=='absolute_change' for c in s['calculations']),5)
                self.assertNotIn('ebit',{r['metric_key'] for r in p['observations']})
    def test_identity_and_consolidated_scope(self):
        text=document()
        for old,new,code in [('549300G6XN5IXMRKEG37','5299007OWYZ61IE46843','LEI'),
                             ('NEL ASA','Unrelated Company','ENTITY_NAME'),
                             ('Consolidated financial statements','Separate financial statements','CONSOLIDATED_SCOPE')]:
            with self.assertRaisesRegex(ValueError,code):plan(text.replace(old,new))

    def test_pandora_canonical_lei_and_combined_nature_scope(self):
        profile=runner.PROFILES[1]
        self.assertEqual(profile['lei'],'5299007OWYZ6I1E46843')
        text=document(profile).replace('Consolidated financial statements',
                                      'Consolidated and separate financial statements')
        self.assertEqual(len(plan(text,profile)['observations']),10)
        wrong=text.replace('5299007OWYZ6I1E46843','5299007OWYZ61IE46843')
        with self.assertRaisesRegex(ValueError,'LEI'):
            plan(wrong,profile)
        with self.assertRaisesRegex(ValueError,'CONSOLIDATED_SCOPE'):
            plan(text.replace('Consolidated and separate financial statements',
                              'Separate financial statements'),profile)
    def test_explanatory_scope_and_context_end_fallback(self):
        text=document().replace(
            '<ix:nonNumeric name="ifrs:DescriptionOfNatureOfFinancialStatements" contextRef="Y2025">Consolidated financial statements</ix:nonNumeric>',
            '<ix:nonNumeric name="ifrs:DisclosureOfBasisOfPreparationOfFinancialStatementsExplanatory" contextRef="Y2025">The consolidated financial statements of the group</ix:nonNumeric>')
        text=text.replace('<ix:nonNumeric name="ifrs:DateOfEndOfReportingPeriod2013" contextRef="Y2025">2025-12-31</ix:nonNumeric>','')
        p=plan(text); evidence=json.loads(p['evidence_json'])
        self.assertEqual(len(p['observations']),10)
        self.assertEqual(evidence['consolidation_evidence'][0]['tag'],
                         'DisclosureOfBasisOfPreparationOfFinancialStatementsExplanatory')
        self.assertEqual(evidence['report_end_evidence'][0]['tag'],'xbrli:endDate')
        self.assertEqual(evidence['report_end_evidence'][0]['value'],'2025-12-31')
    def test_parent_and_segment_contexts_never_consolidated(self):
        for axis,member in [('ConsolidatedAndSeparateFinancialStatementsAxis','SeparateMember'),('ProductsAndServicesAxis','Revenue')]:
            text=document().replace('</xbrli:entity>',f'<xbrli:segment><xbrldi:explicitMember dimension="ifrs:{axis}">ifrs:{member}</xbrldi:explicitMember></xbrli:segment></xbrli:entity>')
            with self.assertRaisesRegex(ValueError,'LEI'):plan(text)
        text=document().replace('</xbrli:entity>','<xbrli:segment><xbrldi:explicitMember dimension="ifrs:ConsolidatedAndSeparateFinancialStatementsAxis">ifrs:ConsolidatedMember</xbrldi:explicitMember></xbrli:segment></xbrli:entity>')
        self.assertEqual(len(plan(text)['observations']),10)
    def test_instants_quarters_extensions_and_taxonomy_versions(self):
        p=plan(document().replace('name="ifrs:Revenue"','name="ext:Revenue"'))
        self.assertNotIn('revenue',{r['metric_key'] for r in p['observations']})
        self.assertTrue(json.loads(p['evidence_json'])['structural_issues'])
        self.assertEqual(len(plan(document().replace('2024-03-27/ifrs-full','2025-03-27/ifrs-full'))['observations']),10)
        text=document().replace('<xbrli:startDate>2024-01-01</xbrli:startDate><xbrli:endDate>2024-12-31</xbrli:endDate>','<xbrli:instant>2024-12-31</xbrli:instant>')
        with self.assertRaisesRegex(ValueError,'ANNUAL_PERIOD'):plan(text)
        with self.assertRaisesRegex(ValueError,'ANNUAL_PERIOD'):plan(document().replace('2024-01-01','2024-10-01'))
    def test_noncalendar_years(self):
        profile=dict(runner.PROFILES[0],report_end='2025-09-30')
        text=document().replace('2024-01-01','2023-10-01').replace('2025-01-01','2024-10-01').replace('12-31','09-30')
        p=plan(text,profile);prepare(snapshot(p));self.assertEqual(p['reported_periods']['2024']['start'],'2023-10-01')
    def test_duplicate_conflicts_are_metric_gaps_not_zero_or_overwrites(self):
        extra='<ix:nonFraction name="ifrs:Revenue" contextRef="Y2025" unitRef="money" decimals="-6" scale="6">120</ix:nonFraction>'
        self.assertEqual(len(plan(document().replace('</div></body>',extra+'</div></body>'))['observations']),10)
        p=plan(document().replace('</div></body>',extra.replace('>120<','>121<')+'</div></body>'))
        self.assertEqual(len(p['observations']),9);self.assertEqual(p['unqualified_metrics'][0]['reason'],'CONFLICTING_DUPLICATE_FACTS')
    def test_currency_mismatch_and_invalid_transform(self):
        with self.assertRaisesRegex(ValueError,'NO_QUALIFIED_FACTS'):plan(document().replace('iso4217:NOK','iso4217:DKK'))
        p=plan(document().replace('>120</ix:nonFraction>','>nonsense</ix:nonFraction>',1))
        self.assertEqual(len(p['observations']),9)
        self.assertFalse(any(r['metric_key']=='revenue' and r['fiscal_year']=='2025' for r in p['observations']))
        self.assertTrue(any(i.get('arelle_code')=='ix11.10.1.1:transformValueError'
                            for i in json.loads(p['evidence_json'])['structural_issues']))
        # A missing required contextRef is a schema error, not an isolated value error.
        with self.assertRaisesRegex(ValueError,'ARELLE_STRUCTURE'):
            plan(document().replace('contextRef="Y2025"','',1))
    def test_zip_guards_and_cleanup(self):
        for name in ('../escape.xhtml','/escape.xhtml','C:/escape.xhtml'):
            with self.assertRaisesRegex(ValueError,'ZIP_PATH'):
                with esef.package(zipped(document(),name)):pass
        # ZipInfo normalizes Windows separators on creation; corrupt both headers explicitly.
        with self.assertRaisesRegex(ValueError,'ZIP_PATH'):
            with esef.package(zipped(document(),'report/escape.xhtml').replace(b'report/escape.xhtml',b'report\\escape.xhtml')):pass
        with self.assertRaisesRegex(ValueError,'ZIP_'):
            with esef.package(b'PK\x03\x04broken'):pass
        with self.assertRaisesRegex(ValueError,'ZIP_BOUND'):
            with esef.package(zipped('0'*1000000)):pass
        with self.assertRaisesRegex(ValueError,'XML_DTD'):
            with esef.package(zipped('<!DOCTYPE x [<!ENTITY a SYSTEM "https://invalid/">]>'+document())):pass
        catalog = '<?xml version="1.0"?><!DOCTYPE catalog PUBLIC "-//OASIS//DTD Entity Resolution XML Catalog V1.0//EN" "http://www.oasis-open.org/committees/entity/release/1.0/catalog.dtd"><catalog xmlns="urn:oasis:names:tc:entity:xmlns:xml:catalog"/>'
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('META-INF/catalog.xml',catalog)
            z.writestr('report/reports/annual.xhtml',document())
        with esef.package(buf.getvalue()) as (root,reports):
            self.assertEqual(len(reports),1)
            self.assertNotIn(b'<!DOCTYPE', (root/'META-INF/catalog.xml').read_bytes())
        dangerous = catalog.replace('<catalog ', '<!ENTITY bad SYSTEM "https://invalid/"><catalog ')
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('META-INF/catalog.xml',dangerous)
            z.writestr('report/reports/annual.xhtml',document())
        with self.assertRaisesRegex(ValueError,'XML_DTD'):
            with esef.package(buf.getvalue()): pass
        with esef.package(zipped(document())) as (root,reports):
            self.assertTrue(root.exists());self.assertEqual(len(reports),1)
        self.assertFalse(root.exists())
    def test_evidence_shared_writer_current_replay_and_tamper(self):
        a,b=[plan(profile=p) for p in runner.PROFILES]
        self.assertNotEqual(a['metadata']['sha256'],a['stored_evidence']['sha256'])
        result=subprocess.run(['php','tests/fundamentals_esef.php'],input=json.dumps([a,b]),text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr);self.assertEqual(result.stderr,'')
        self.assertTrue(json.loads(result.stdout)['ok'])
    def test_live3_plans_keep_reviewed_profiles_and_bind_execution(self):
        live3={'NO0010081235':'fundamentals-esef-nel-20261102-03',
               'DK0060252690':'fundamentals-esef-pandora-20261102-03'}
        plans=[plan(profile=profile,execution=live3[profile['isin']]) for profile in runner.PROFILES]
        result=subprocess.run(['php','tests/fundamentals_esef.php'],input=json.dumps(plans),text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertTrue(json.loads(result.stdout)['ok'])
    def test_one_shot_guards_and_safe_errors(self):
        env=dict(GITHUB_REPOSITORY='masterxfix/MOSA-2',GITHUB_REF='refs/heads/main',GITHUB_EVENT_NAME='workflow_dispatch',
            GITHUB_RUN_ATTEMPT='1',GITHUB_RUN_NUMBER='1',GITHUB_SHA='a'*40,EXPECTED_COMMIT='a'*40,
            AUTHORIZATION=runner.AUTH+'a'*40,GITHUB_WORKFLOW_REF='masterxfix/MOSA-2/'+runner.WORKFLOW+'@refs/heads/main')
        runner.guard(env)
        for k,v in [('GITHUB_RUN_ATTEMPT','2'),('GITHUB_RUN_NUMBER','2'),('EXPECTED_COMMIT','b'*40)]:
            with self.assertRaises(ValueError):runner.guard(dict(env,**{k:v}))
        self.assertEqual(runner.safe_code(ValueError('private secret raw body')),'SAFE_PHASE_FAILURE')

    def test_live2_bindings_and_archive_reservations_are_separate(self):
        overrides={'NO0010081235':'fundamentals-esef-nel-20261101-02',
                   'DK0060252690':'fundamentals-esef-pandora-20261101-02'}
        self.assertEqual(runner.execution_overrides(json.dumps(overrides)),overrides)
        with self.assertRaisesRegex(ValueError,'ESEF_EXECUTION_BINDING'):
            runner.execution_overrides(json.dumps({'NO0010081235':overrides['NO0010081235']}))
        source=(runner.shared.ROOT/'scripts/fundamentals/archive_remote.py').read_text(encoding='utf-8')
        self.assertIn("'fundamentals-esef-nel-20261101-02'",source)
        self.assertIn("'fundamentals-esef-pandora-20261101-02'",source)
        workflow=(runner.shared.ROOT/'.github/workflows/fundamentals-esef-live2-once.yml').read_text(encoding='utf-8')
        for token in ('workflow_dispatch','github.run_number == 1','github.run_attempt == 1',
                      'MOSA2-ESEF-LIVE2-20261101:$GITHUB_SHA',
                      'ESEF_WORKFLOW: .github/workflows/fundamentals-esef-live2-once.yml',
                      'fundamentals-esef-nel-20261101-02','fundamentals-esef-pandora-20261101-02'):
            self.assertIn(token,workflow)
        old=(runner.shared.ROOT/'.github/workflows/fundamentals-esef-once.yml').read_text(encoding='utf-8')
        self.assertNotIn('LIVE2',old)
        old_auth,old_workflow=runner.AUTH,runner.WORKFLOW
        try:
            runner.AUTH='MOSA2-ESEF-LIVE2-20261101:'
            runner.WORKFLOW='.github/workflows/fundamentals-esef-live2-once.yml'
            env=dict(GITHUB_REPOSITORY='masterxfix/MOSA-2',GITHUB_REF='refs/heads/main',GITHUB_EVENT_NAME='workflow_dispatch',
                GITHUB_RUN_ATTEMPT='1',GITHUB_RUN_NUMBER='1',GITHUB_SHA='a'*40,EXPECTED_COMMIT='a'*40,
                AUTHORIZATION=runner.AUTH+'a'*40,GITHUB_WORKFLOW_REF='masterxfix/MOSA-2/'+runner.WORKFLOW+'@refs/heads/main')
            runner.guard(env)
            with self.assertRaises(ValueError): runner.guard(env|{'GITHUB_RUN_ATTEMPT':'2'})
            with self.assertRaises(ValueError): runner.guard(env|{'AUTHORIZATION':'MOSA2-ESEF-20261101:'+'a'*40})
        finally:
            runner.AUTH,runner.WORKFLOW=old_auth,old_workflow
    def test_live3_bindings_are_exclusive_and_live1_live2_remain_unchanged(self):
        live2={'NO0010081235':'fundamentals-esef-nel-20261101-02',
               'DK0060252690':'fundamentals-esef-pandora-20261101-02'}
        live3={'NO0010081235':'fundamentals-esef-nel-20261102-03',
               'DK0060252690':'fundamentals-esef-pandora-20261102-03'}
        swapped={'NO0010081235':live3['DK0060252690'],
                 'DK0060252690':live3['NO0010081235']}
        old_auth,old_workflow=runner.AUTH,runner.WORKFLOW
        try:
            runner.WORKFLOW=runner.LIVE3_WORKFLOW
            self.assertEqual(runner.execution_overrides(json.dumps(live3)),live3)
            with self.assertRaisesRegex(ValueError,'ESEF_EXECUTION_BINDING'):
                runner.execution_overrides(json.dumps(swapped))
            with self.assertRaisesRegex(ValueError,'ESEF_EXECUTION_BINDING'):
                runner.execution_overrides(json.dumps(live2))
            runner.WORKFLOW=runner.LIVE2_WORKFLOW
            self.assertEqual(runner.execution_overrides(json.dumps(live2)),live2)
            with self.assertRaisesRegex(ValueError,'ESEF_EXECUTION_BINDING'):
                runner.execution_overrides(json.dumps(live3))
            runner.WORKFLOW='.github/workflows/fundamentals-esef-once.yml'
            with self.assertRaisesRegex(ValueError,'ESEF_EXECUTION_BINDING'):
                runner.execution_overrides(json.dumps(live3))
            source=(runner.shared.ROOT/'scripts/fundamentals/archive_remote.py').read_text(encoding='utf-8')
            for token in live3.values(): self.assertIn("'"+token+"'",source)
            workflow=(runner.shared.ROOT/'.github/workflows/fundamentals-esef-live3-once.yml').read_text(encoding='utf-8')
            for token in ('workflow_dispatch','github.run_number == 1','github.run_attempt == 1',
                          'MOSA2-ESEF-LIVE3-20261102:$GITHUB_SHA',
                          'ESEF_WORKFLOW: .github/workflows/fundamentals-esef-live3-once.yml',
                          'fundamentals-esef-nel-20261102-03','fundamentals-esef-pandora-20261102-03'):
                self.assertIn(token,workflow)
            old=(runner.shared.ROOT/'.github/workflows/fundamentals-esef-live2-once.yml').read_text(encoding='utf-8')
            self.assertNotIn('20261102-03',old)
        finally:
            runner.AUTH,runner.WORKFLOW=old_auth,old_workflow


if __name__=='__main__':unittest.main()
