"""Prepared 0006 contract only: existing parser/model; no MySQL, network or writer."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch
import market_units_schema_fixture as schema
from test_core_schema_phase2 import ROOT, MIGRATIONS, split_sql

OLD = {
 '0001_core_asset_identity.sql': '9c3ac21f02fc242e9561d94aaa4a4c4fe6a430d11aa5f0681f0c9eace81446dd',
 '0002_market_current_history.sql': '205bea42cfc93a64f76eb61c10377e47dceae38815c4351817a17aced00a75ee',
 '0003_market_units.sql': '199933884802bd139b706e50e57e04687e9cbe5f8bd1366e98e302af7d47b8ee',
 '0004_current_observation_provenance.sql': '46238979889d2fe1bdaac4c5ba4c1ddda7f5810cd87cdf1a8b806db71f63df70',
 '0005_collector_reservations.sql': '2521552c548370806bc311798f12be39f16b102733aeb74ac9c01337e7e46333',
}
PATH = MIGRATIONS/'0006_fundamentals_and_payload_provenance.sql'
SQL = PATH.read_text(encoding='utf-8')
BASE = ''.join((MIGRATIONS/n).read_text(encoding='utf-8') for n in list(OLD)[:4])
# Reuse the restricted parser, adding only DATE and 0004's TINYINT UNSIGNED tokens locally.
# No change to the frozen market parser or its interpretation.
with patch.object(schema, 'TYPE', '(?:'+schema.TYPE+'|DATE|TINYINT UNSIGNED)'):
    BEFORE = schema.parse_schema(BASE)
    AFTER = schema.parse_schema(BASE+SQL)
FETCH='m2_provider_fetches'; METRIC='m2_fundamental_metrics'; UNIT='m2_fundamental_units'
OBS='m2_fundamental_observations'; CURRENT='m2_fundamental_current'
NEW={FETCH,METRIC,UNIT,OBS,CURRENT}
VALUE_FIELDS='value_type dimension_key unit_key unit_version value_decimal value_text value_date'.split()
PERIOD_FIELDS='period_type fiscal_year fiscal_quarter period_start period_end estimate_horizon period_key as_of_at reported_at'.split()
COLUMNS={
 FETCH: 'id fetch_key source_id asset_id route_id route_revision route_sha256 job_run_id file_id payload_sha256 payload_bytes content_type observed_at http_status parser_key parser_version parse_status created_at'.split(),
 METRIC: 'metric_key display_name category value_type value_semantics dimension_key definition_sha256 status created_at updated_at'.split(),
 UNIT: 'unit_key unit_version display_name dimension_key monetary_currency_code scale_numerator scale_denominator definition_sha256 status created_at'.split(),
 OBS: 'id asset_id source_id route_id metric_key'.split()+VALUE_FIELDS+PERIOD_FIELDS+'observed_at fetch_id field_path dedupe_key created_at'.split(),
 CURRENT: 'asset_id metric_key'.split()+PERIOD_FIELDS+'observation_id source_id'.split()+VALUE_FIELDS+'observed_at updated_at'.split(),
}
NULLABLE={
 FETCH:set('asset_id route_id route_revision route_sha256 job_run_id http_status parser_key parser_version'.split()),
 METRIC:set(), UNIT:{'monetary_currency_code'},
 OBS:set('route_id value_decimal value_text value_date fiscal_year fiscal_quarter period_start period_end estimate_horizon as_of_at reported_at'.split()),
 CURRENT:set('value_decimal value_text value_date fiscal_year fiscal_quarter period_start period_end estimate_horizon as_of_at reported_at'.split()),
}
TYPES=dict(
 id='BIGINT UNSIGNED',fetch_key='BINARY(32)',source_id='BIGINT UNSIGNED',asset_id='BIGINT UNSIGNED',
 route_id='BIGINT UNSIGNED',route_revision='INT UNSIGNED',route_sha256='BINARY(32)',job_run_id='BIGINT UNSIGNED',
 file_id='BIGINT UNSIGNED',payload_sha256='BINARY(32)',payload_bytes='BIGINT UNSIGNED',content_type='VARCHAR(255)',
 observed_at='DATETIME(6)',http_status='SMALLINT UNSIGNED',parser_key='VARCHAR(64)',parser_version='VARCHAR(64)',
 parse_status='VARCHAR(16)',created_at='DATETIME(6)',metric_key='VARCHAR(64)',category='VARCHAR(64)',
 value_type='VARCHAR(16)',value_semantics='VARCHAR(255)',dimension_key='VARCHAR(64)',
 definition_sha256='BINARY(32)',status='VARCHAR(16)',updated_at='DATETIME(6)',unit_key='VARCHAR(64)',
 unit_version='INT UNSIGNED',monetary_currency_code='CHAR(3)',scale_numerator='DECIMAL(38,0)',
 scale_denominator='DECIMAL(38,0)',value_decimal='DECIMAL(38,12)',value_text='VARCHAR(1024)',
 value_date='DATE',period_type='VARCHAR(16)',fiscal_year='SMALLINT UNSIGNED',fiscal_quarter='SMALLINT UNSIGNED',
 period_start='DATE',period_end='DATE',estimate_horizon='VARCHAR(64)',period_key='BINARY(32)',
 as_of_at='DATETIME(6)',reported_at='DATETIME(6)',fetch_id='BIGINT UNSIGNED',field_path='VARCHAR(512)',
 dedupe_key='BINARY(32)',observation_id='BIGINT UNSIGNED')
PK={FETCH:('id',), METRIC:('metric_key',), UNIT:('unit_key','unit_version'),
 OBS:('id',), CURRENT:('asset_id','metric_key','period_type')}
INDEXES={
 FETCH:{
 'uq_fetch_key':(('fetch_key',),True),'uq_fetch_source':(('id','source_id'),True),
 'ix_fetch_source_time':(('source_id','observed_at','id'),False),
 'ix_fetch_asset_time':(('asset_id','observed_at','id'),False),'ix_fetch_route':(('route_id',),False),
 'ix_fetch_job':(('job_run_id',),False),'ix_fetch_file':(('file_id',),False),
 'ix_fetch_payload':(('payload_sha256','payload_bytes','id'),False)},
 METRIC:{'uq_metric_contract':(('metric_key','value_type','dimension_key'),True)},
 UNIT:{'uq_fund_unit_dimension':(('unit_key','unit_version','dimension_key'),True)},
 OBS:{
 'uq_fund_obs_dedupe':(('dedupe_key',),True),
 'uq_fund_obs_identity':(('id','asset_id','metric_key','period_type','source_id'),True),
 'ix_fund_obs_timeline':(('asset_id','metric_key','period_type','as_of_at','id'),False),
 'ix_fund_obs_period':(('asset_id','metric_key','period_type','fiscal_year','fiscal_quarter','period_end','id'),False),
 'ix_fund_obs_source':(('source_id','observed_at','id'),False),
 'ix_fund_obs_fetch':(('fetch_id','source_id','id'),False),'ix_fund_obs_route':(('route_id',),False),
 'ix_fund_obs_metric':(('metric_key','value_type','dimension_key'),False),
 'ix_fund_obs_unit':(('unit_key','unit_version','dimension_key'),False)},
 CURRENT:{
 'ix_fund_current_origin':(('observation_id','asset_id','metric_key','period_type','source_id'),False),
 'ix_fund_current_metric':(('metric_key','value_type','dimension_key'),False),
 'ix_fund_current_unit':(('unit_key','unit_version','dimension_key'),False)}
}
FKS={
 FETCH:{
 'fk_fetch_source':(('source_id',),'m2_sources',('id',),'RESTRICT'),
 'fk_fetch_asset':(('asset_id',),'m2_assets',('entity_id',),'RESTRICT'),
 'fk_fetch_route':(('route_id',),'m2_asset_source_routes',('id',),'RESTRICT'),
 'fk_fetch_job':(('job_run_id',),'m2_job_runs',('id',),'RESTRICT'),
 'fk_fetch_file':(('file_id',),'m2_files',('id',),'RESTRICT')},
 METRIC:{},UNIT:{},
 OBS:{
 'fk_fund_obs_asset':(('asset_id',),'m2_assets',('entity_id',),'RESTRICT'),
 'fk_fund_obs_source':(('source_id',),'m2_sources',('id',),'RESTRICT'),
 'fk_fund_obs_route':(('route_id',),'m2_asset_source_routes',('id',),'RESTRICT'),
 'fk_fund_obs_metric':(('metric_key','value_type','dimension_key'),METRIC,('metric_key','value_type','dimension_key'),'RESTRICT'),
 'fk_fund_obs_unit':(('unit_key','unit_version','dimension_key'),UNIT,('unit_key','unit_version','dimension_key'),'RESTRICT'),
 'fk_fund_obs_fetch':(('fetch_id','source_id'),FETCH,('id','source_id'),'RESTRICT')},
 CURRENT:{
 'fk_fund_current_origin':(('observation_id','asset_id','metric_key','period_type','source_id'),OBS,('id','asset_id','metric_key','period_type','source_id'),'RESTRICT'),
 'fk_fund_current_metric':(('metric_key','value_type','dimension_key'),METRIC,('metric_key','value_type','dimension_key'),'RESTRICT'),
 'fk_fund_current_unit':(('unit_key','unit_version','dimension_key'),UNIT,('unit_key','unit_version','dimension_key'),'RESTRICT')}
}
CHECK_NAMES={
 FETCH:{'ck_fetch_route','ck_fetch_parser','ck_fetch_metadata'},
 METRIC:{'ck_metric_definition'},UNIT:{'ck_fund_unit_definition','ck_fund_unit_currency'},
 OBS:{'ck_fund_obs_value','ck_fund_obs_period','ck_fund_obs_bounds','ck_fund_obs_evidence'},
 CURRENT:{'ck_fund_current_value','ck_fund_current_period','ck_fund_current_bounds','ck_fund_current_time'}
}
def checks(table,row):
    return all(schema.CheckExpression(e).evaluate(row) is True for e in AFTER[table]['checks'].values())

def fks(table,row,catalog):
    for columns,parent,target,_ in AFTER[table]['fks'].values():
        values=tuple(row.get(c) for c in columns)
        if any(v is None for v in values):continue
        if not any(tuple(p.get(c) for c in target)==values for p in catalog.get(parent,[])):return False
    return True

def fact(**change):
    r=dict.fromkeys(COLUMNS[OBS]);r.update(id=10,asset_id=1,source_id=2,metric_key='synthetic_metric',
      value_type='decimal',dimension_key='monetary',unit_key='EUR',unit_version=1,
      value_decimal=Decimal('-12.250000000000'),period_type='snapshot',period_key=b'p'*32,
      observed_at='2026-10-31 10:00:00.000000',fetch_id=3,field_path='$.result.value',
      dedupe_key=b'd'*32,created_at='2026-10-31 10:00:01.000000')
    r.update(change);return r

def period_identity(row):
    keys='period_type fiscal_year fiscal_quarter period_start period_end estimate_horizon'.split()
    return hashlib.sha256(json.dumps(['mosa2-fundamental-period-v1']+
        [row.get(k) for k in keys],default=str,separators=(',',':')).encode()).digest()

def dedupe_model(row):
    # Executable design example, not a production writer or receipt.
    keys='asset_id source_id route_id route_revision route_sha256 metric_key definition_sha256 value_type dimension_key unit_key unit_version unit_definition_sha256 as_of_at reported_at value_text value_date'.split()
    value=row.get('value_decimal')
    decimal=None if value is None else format(Decimal(value).normalize(),'f')
    return hashlib.sha256(json.dumps(['mosa2-fundamental-fact-v1',period_identity(row).hex(),decimal]+
      [row.get(k) for k in keys],default=str,separators=(',',':')).encode()).digest()

class FundamentalsSchemaTests(unittest.TestCase):
    def test_old_migrations_byte_identical_and_existing_schema_unchanged(self):
        for name,digest in OLD.items():
            self.assertEqual(hashlib.sha256((MIGRATIONS/name).read_bytes()).hexdigest(),digest,name)
        self.assertEqual({k:AFTER[k] for k in BEFORE},BEFORE)
        self.assertEqual(set(AFTER)-set(BEFORE),NEW)

    def test_only_five_create_statements_no_provider_or_asset_rules(self):
        body=re.sub(r'^\s*--[^\n]*$','',SQL,flags=re.M)
        statements=split_sql(body,';');self.assertEqual(statements.pop(),'')
        self.assertEqual(len(statements),5)
        self.assertTrue(all(s.startswith('CREATE TABLE m2_') for s in statements))
        self.assertNotRegex(body.replace('ON DELETE RESTRICT',''),r'(?i)\b(ALTER|INSERT|UPDATE|DELETE|SELECT|USE|SET|TRIGGER|PROCEDURE|JSON|BLOB|FLOAT|DOUBLE)\b')
        self.assertNotRegex(body,r'(?i)yahoo|tradegate|frankfurt|justetf|droneshield|\bbyd\b|ubtech|\bpne\b|zeiss|\bisin\b')

    def test_exact_columns_types_nulls_collations_and_auto_increment(self):
        for name in NEW:
            t=AFTER[name];self.assertEqual(list(t['columns']),COLUMNS[name],name)
            for key,col in t['columns'].items():
                expected_type=('VARCHAR(128)' if name==UNIT else 'VARCHAR(255)') if key=='display_name' else TYPES[key]
                self.assertEqual(col[0],expected_type,(name,key))
                self.assertEqual(col[1],key in NULLABLE[name],(name,key))
                self.assertEqual(col[3],key=='id' and name in (FETCH,OBS))
                self.assertIsNone(col[4])
                if key not in ('display_name','value_text') and expected_type.startswith(('VARCHAR','CHAR')):
                    self.assertEqual(col[2],'utf8mb4_0900_bin',(name,key))

    def test_exact_primary_unique_foreign_keys_checks_and_indexes(self):
        for name in NEW:
            t=AFTER[name];self.assertEqual(t['pk'],PK[name]);self.assertEqual(t['indexes'],INDEXES[name])
            self.assertEqual(t['fks'],FKS[name]);self.assertEqual(set(t['checks']),CHECK_NAMES[name])
            for expression in t['checks'].values():
                self.assertTrue(schema.CheckExpression(expression).fields<=t['columns'].keys())

    def test_all_fk_prefixes_and_key_sizes(self):
        schema.validate_references(AFTER)
        for name in NEW:
            t=AFTER[name]
            for key in [t['pk']]+[v[0] for v in t['indexes'].values()]:
                total=0
                for field in key:
                    typ=t['columns'][field][0]
                    m=re.match(r'(?:VAR)?CHAR\((\d+)\)',typ)
                    total+=int(m[1])*4 if m else 32 if typ=='BINARY(32)' else 8
                self.assertLessEqual(total,3072,(name,key,total))

    def test_fy_fq_ttm_snapshot_forward_and_nullable_bounds(self):
        for r in [fact(),fact(period_type='fy',fiscal_year=2025,period_start=date(2025,1,1),period_end=date(2025,12,31)),
                  fact(period_type='fq',fiscal_year=2025,fiscal_quarter=4,period_start=date(2025,10,1),period_end=date(2025,12,31)),
                  fact(period_type='ttm'),fact(period_type='forward',estimate_horizon='next_fy'),
                  fact(period_type='forward',estimate_horizon='next_fq',fiscal_year=2027,fiscal_quarter=1)]:
            self.assertTrue(checks(OBS,r),r)
            c={k:r.get(k) for k in COLUMNS[CURRENT]};c.update(observation_id=10,updated_at=r['created_at'])
            self.assertTrue(checks(CURRENT,c),c)
        invalid=[dict(period_type='unknown'),dict(fiscal_year=2025),dict(period_type='fy'),
          dict(period_type='fq',fiscal_year=2025,fiscal_quarter=0),dict(period_type='ttm',fiscal_quarter=4),
          dict(period_type='forward'),dict(period_type='forward',estimate_horizon=''),
          dict(period_type='forward',estimate_horizon='next_fq',fiscal_quarter=1),
          dict(period_type='ttm',period_end=date(2025,12,31)),
          dict(period_type='ttm',period_start=date(2026,1,1),period_end=date(2025,1,1)),
          dict(period_type='forward',estimate_horizon='next_fy',fiscal_year=10000)]
        for change in invalid:self.assertFalse(checks(OBS,fact(**change)),change)

    def test_exact_one_value_zero_negative_and_date_text(self):
        self.assertTrue(checks(OBS,fact(value_decimal=Decimal(0))))
        self.assertTrue(checks(OBS,fact()))
        self.assertTrue(checks(OBS,fact(value_type='text',dimension_key='text',unit_key='TEXT',value_decimal=None,value_text='synthetic')))
        self.assertTrue(checks(OBS,fact(value_type='date',dimension_key='date',unit_key='DATE',value_decimal=None,value_date=date(2025,3,1))))
        for change in [dict(value_decimal=None),dict(value_text='also'),dict(value_type='unknown'),
                       dict(value_type='date',value_decimal=None),dict(value_type='text',value_decimal=None)]:
            self.assertFalse(checks(OBS,fact(**change)),change)

    def test_fetch_route_parser_and_metadata_fail_closed(self):
        r=dict.fromkeys(COLUMNS[FETCH]);r.update(content_type='application/json',observed_at='a',created_at='b',parse_status='unparsed')
        self.assertTrue(checks(FETCH,r))
        for change in [dict(route_id=1),dict(parse_status='parsed'),dict(parser_key='p'),dict(http_status=600),
                       dict(content_type=''),dict(created_at='0')]:
            self.assertFalse(checks(FETCH,r|change),change)
        bound=r|dict(asset_id=1,route_id=9,route_revision=1,route_sha256=b'h'*32,
                     parse_status='partial',parser_key='generic-parser',parser_version='1')
        self.assertTrue(checks(FETCH,bound))
        self.assertFalse(checks(FETCH,bound|dict(route_revision=0)))

    def test_metric_and_separate_frozen_unit_dimensions(self):
        m=dict(metric_key='synthetic',display_name='Synthetic',category='future_category',value_type='decimal',
          value_semantics='exact synthetic contract',dimension_key='ratio',status='active',created_at='a',updated_at='b')
        self.assertTrue(checks(METRIC,m))
        self.assertFalse(checks(METRIC,m|dict(value_type='json')))
        self.assertFalse(checks(METRIC,m|dict(category='')))
        self.assertFalse(checks(METRIC,m|dict(value_type='date')))
        self.assertTrue(checks(METRIC,m|dict(value_type='date',dimension_key='date')))
        u=dict(unit_key='PERCENT',unit_version=1,display_name='Percent',dimension_key='ratio',
               monetary_currency_code=None,scale_numerator=1,scale_denominator=100,status='frozen')
        self.assertTrue(checks(UNIT,u));self.assertFalse(checks(UNIT,u|dict(scale_denominator=0)))
        self.assertFalse(checks(UNIT,u|dict(monetary_currency_code='EUR')))
        self.assertFalse(checks(UNIT,u|dict(dimension_key='monetary')))
        self.assertFalse(checks(UNIT,u|dict(dimension_key='date')))
        self.assertTrue(checks(UNIT,u|dict(dimension_key='date',scale_denominator=1)))
        self.assertTrue(checks(UNIT,u|dict(dimension_key='monetary_per_share',monetary_currency_code='EUR')))
        self.assertEqual(AFTER['m2_units'],BEFORE['m2_units'])

    def test_current_reference_binds_exact_history_identity(self):
        f=fact();c={k:f.get(k) for k in COLUMNS[CURRENT]};c['observation_id']=10
        catalog={OBS:[f],METRIC:[f],UNIT:[f]}
        self.assertTrue(fks(CURRENT,c,catalog))
        for key in ('observation_id','asset_id','metric_key','period_type','source_id','unit_version','dimension_key','value_type'):
            changed=dict(c);changed[key]='different'
            self.assertFalse(fks(CURRENT,changed,catalog),key)

    def test_fetch_file_source_and_metric_unit_fk_provenance(self):
        f=fact()
        catalog={'m2_assets':[dict(entity_id=1)],'m2_sources':[dict(id=2)],
                 METRIC:[f],UNIT:[f],FETCH:[dict(id=3,source_id=2)]}
        self.assertTrue(fks(OBS,f,catalog))
        for change in (dict(fetch_id=4),dict(source_id=9),dict(unit_version=2),dict(dimension_key='count')):
            self.assertFalse(fks(OBS,f|change,catalog),change)
        fetch=dict(source_id=2,file_id=99)
        self.assertTrue(fks(FETCH,fetch,{'m2_sources':[dict(id=2)],'m2_files':[dict(id=99)]}))
        self.assertFalse(fks(FETCH,fetch,{'m2_sources':[dict(id=2)],'m2_files':[]}))

    def test_dedupe_separates_periods_units_sources_and_preserves_identical_fetches(self):
        f=fact()
        equivalent=f|dict(observed_at='later',created_at='later',fetch_id=44,value_decimal='-12.25')
        self.assertEqual(dedupe_model(f),dedupe_model(equivalent))
        variants=[dict(period_type='ttm'),dict(period_type='fy',fiscal_year=2025),
          dict(period_type='fq',fiscal_year=2025,fiscal_quarter=4),dict(source_id=77),
          dict(unit_version=2),dict(as_of_at='other'),dict(value_decimal='-13'),
          dict(route_revision=2),dict(route_sha256='other'),dict(definition_sha256='other')]
        for change in variants:self.assertNotEqual(dedupe_model(f),dedupe_model(f|change),change)
        a=f|dict(period_type='forward',estimate_horizon='next_fy')
        self.assertNotEqual(period_identity(a),period_identity(a|dict(estimate_horizon='next_fq')))

    def test_unknown_fields_remain_in_file_not_hot_projection(self):
        body=b'{"known":"12.50","unknown":{"future":[1,"x",null]}}'
        digest=hashlib.sha256(body).digest()
        archive={digest:body};parsed=json.loads(body)
        hot={'value_decimal':Decimal(parsed['known'])}
        self.assertEqual(json.loads(archive[digest])['unknown']['future'],[1,'x',None])
        self.assertEqual(archive[digest],body);self.assertNotIn('unknown',hot)
        for table in (OBS,CURRENT):
            self.assertNotIn('payload',AFTER[table]['columns'])
            self.assertFalse(any(c[0] in ('JSON','BLOB') for c in AFTER[table]['columns'].values()))
        self.assertIn('field_path',AFTER[OBS]['columns'])

    def test_documented_bounded_access_paths_and_performance_limits(self):
        doc=(ROOT/'docs/database/FUNDAMENTALS_ARCHITECTURE.md').read_text(encoding='utf-8')
        for term in ('ix_fund_obs_timeline','ix_fund_obs_period','uq_fetch_source',
                     'LIMIT 129','LIMIT 101','<20 ms','<100 ms','<200 ms','<1,0 s','<1,5 s','2,0 s'):
            self.assertIn(term,doc)
        self.assertEqual(AFTER[CURRENT]['pk'],('asset_id','metric_key','period_type'))
        self.assertEqual(AFTER[OBS]['indexes']['ix_fund_obs_timeline'][0][:3],('asset_id','metric_key','period_type'))
        self.assertEqual(AFTER[OBS]['indexes']['ix_fund_obs_period'][0][:3],('asset_id','metric_key','period_type'))
        self.assertIn('kein gemessenes EXPLAIN',doc)

    def test_constraint_mutations_are_detectable(self):
        # Real parsed CHECK mutation, no second production validation framework.
        original=AFTER[OBS]['checks']['ck_fund_obs_value']
        changed=original.replace('value_text IS NULL','value_text IS NOT NULL',1)
        r=fact(value_text='contradictory')
        self.assertFalse(schema.CheckExpression(original).evaluate(r))
        self.assertTrue(schema.CheckExpression(changed).evaluate(r))
        changed_fk=deepcopy(AFTER);changed_fk[CURRENT]['indexes'].pop('ix_fund_current_origin')
        with self.assertRaises(ValueError):schema.validate_references(changed_fk)
        with patch.object(schema,'TYPE','(?:'+schema.TYPE+'|DATE|TINYINT UNSIGNED)'):
            with self.assertRaises(ValueError):schema.parse_schema(BASE+SQL+'DROP TABLE m2_assets;')

if __name__=='__main__':unittest.main()
