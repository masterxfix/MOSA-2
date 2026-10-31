"""One bounded qualification in the existing ephemeral GHA MySQL8 service.
No Dogado connector, external hostname, provider, credential or deployment code.
"""
from copy import deepcopy
from datetime import date, datetime, timedelta
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import time
import unittest

from test_collector_persistence_mysql import ENABLED, connect
import test_fundamentals_schema as contract

ROOT=contract.ROOT
NOW='2026-10-31 00:00:10.000000'
PERIODS=('snapshot','fy','fq','ttm','forward')
ASSETS=100
METRICS=50
REVISIONS=4
REPEATS=40
WARMUPS=3
DIMENSIONS=('monetary','ratio','monetary_per_share','shares','count')
UNITS=('EUR','ONE','EUR_PER_SHARE','SHARE','COUNT')
DDL_NAMES=list(contract.OLD)+['0006_fundamentals_and_payload_provenance.sql']

def sha(value):
    return hashlib.sha256(value.encode() if isinstance(value,str) else value).digest()

def periods(kind,revision):
    out=dict(period_type=kind,fiscal_year=None,fiscal_quarter=None,period_start=None,
             period_end=None,estimate_horizon=None,as_of_at=f'2026-10-30 21:00:0{revision}.000000',
             reported_at=None)
    if kind=='fy':
        year=2022+revision
        out.update(fiscal_year=year,period_start=date(year,1,1),period_end=date(year,12,31))
    elif kind=='fq':
        out.update(fiscal_year=2025,fiscal_quarter=revision+1,
                   period_start=date(2025,1+revision*3,1),
                   period_end=(date(2025,4+revision*3,1)-timedelta(days=1)) if revision<3 else date(2025,12,31))
    elif kind=='ttm':
        out.update(period_start=date(2022+revision,11,1),period_end=date(2023+revision,10,30))
    elif kind=='forward':
        out.update(fiscal_year=2027,period_start=date(2027,1,1),period_end=date(2027,12,31),
                   estimate_horizon='next_fy')
    out['period_key']=contract.period_identity(out)
    return out

def observation(asset,metric,kind,revision,identity):
    source=(metric+revision)%3+1
    return dict(id=identity,asset_id=asset,source_id=source,route_id=(asset-1)*3+source,
      metric_key=f'synthetic_metric_{metric:02d}',value_type='decimal',
      dimension_key=DIMENSIONS[metric%5],unit_key=UNITS[metric%5],unit_version=1,
      value_decimal=Decimal(asset*10000+metric*100+revision)/Decimal(10000),
      value_text=None,value_date=None,**periods(kind,revision),
      observed_at=f'2026-10-31 00:00:0{revision}.000000',
      fetch_id=((asset-1)*3+source-1)*REVISIONS+revision+1,field_path='$.synthetic.value',
      dedupe_key=sha(f'synthetic-fact:{asset}:{metric}:{kind}:{revision}'),created_at=NOW)

def projection(row):
    return {k:row.get(k) for k in contract.COLUMNS[contract.CURRENT]} | dict(observation_id=row['id'],updated_at=NOW)

def read_paths():
    fields='metric_key,period_type,value_decimal,unit_key,observed_at,as_of_at,observation_id'
    return {
      'A':dict(label='Current asset',sql=f'SELECT {fields} FROM m2_fundamental_current WHERE asset_id=%s ORDER BY metric_key,period_type LIMIT 129',
               args=(42,),keys={'PRIMARY'},tables={'m2_fundamental_current'}),
      'B':dict(label='Current slot',sql=f'SELECT {fields} FROM m2_fundamental_current WHERE asset_id=%s AND metric_key=%s AND period_type=%s',
               args=(42,'synthetic_metric_00','snapshot'),keys={'PRIMARY'},tables={'m2_fundamental_current'}),
      'C':dict(label='History timeline',sql='SELECT id,value_decimal,as_of_at FROM m2_fundamental_observations WHERE asset_id=%s AND metric_key=%s AND period_type=%s AND as_of_at<%s ORDER BY as_of_at DESC,id DESC LIMIT 100',
               args=(42,'synthetic_metric_00','snapshot','2027-01-01'),keys={'ix_fund_obs_timeline'},tables={'m2_fundamental_observations'}),
      'D':dict(label='FY series',sql='SELECT id,value_decimal,fiscal_year,period_end FROM m2_fundamental_observations WHERE asset_id=%s AND metric_key=%s AND period_type=%s AND fiscal_year BETWEEN %s AND %s ORDER BY fiscal_year DESC,fiscal_quarter DESC,period_end DESC,id DESC LIMIT 100',
               args=(42,'synthetic_metric_00','fy',1900,2027),keys={'ix_fund_obs_period'},tables={'m2_fundamental_observations'}),
      'E':dict(label='FQ series',sql='SELECT id,value_decimal,fiscal_year,fiscal_quarter,period_end FROM m2_fundamental_observations WHERE asset_id=%s AND metric_key=%s AND period_type=%s AND fiscal_year BETWEEN %s AND %s ORDER BY fiscal_year DESC,fiscal_quarter DESC,period_end DESC,id DESC LIMIT 100',
               args=(42,'synthetic_metric_00','fq',1900,2027),keys={'ix_fund_obs_period'},tables={'m2_fundamental_observations'}),
      'F':dict(label='Source provenance',sql='SELECT o.id,o.source_id,s.source_key FROM m2_fundamental_observations o JOIN m2_sources s ON s.id=o.source_id WHERE o.id=%s',
               args=(41004,),keys={'PRIMARY'},tables={'o','s'}),
      'G':dict(label='Payload metadata',sql='SELECT o.id,f.id AS fetch_id,f.payload_sha256,f.payload_bytes,b.id AS file_id,b.sha256,b.byte_size FROM m2_fundamental_observations o JOIN m2_provider_fetches f ON f.id=o.fetch_id AND f.source_id=o.source_id JOIN m2_files b ON b.id=f.file_id WHERE o.id=%s',
               args=(41004,),keys={'PRIMARY','uq_fetch_source'},tables={'o','f','b'}),
    }

def plan_tables(value):
    rows=[]
    if isinstance(value,dict):
        if 'table_name' in value and 'access_type' in value:rows.append(value)
        for v in value.values():rows.extend(plan_tables(v))
    elif isinstance(value,list):
        for v in value:rows.extend(plan_tables(v))
    return rows

def compare_checks(pairs):
    code="require $argv[1];$pairs=json_decode(stream_get_contents(STDIN),true,128,JSON_THROW_ON_ERROR);$out=[];foreach($pairs as $r){$out[]=\\Mosa2\\Phase2\\compareCheck($r['table'],$r['name'],$r['expected'],$r['actual'],$r['show'],true);}echo json_encode($out,JSON_THROW_ON_ERROR);"
    result=subprocess.run(['php','-r',code,(ROOT/'scripts/phase2/check_expression.php').as_posix()],
                          input=json.dumps(pairs),capture_output=True,text=True,check=True,timeout=20)
    if result.stderr:raise AssertionError(result.stderr)
    return json.loads(result.stdout)

@unittest.skipUnless(ENABLED,'existing temporary loopback GitHub MySQL8 service only')
class FundamentalsMySQLTests(unittest.TestCase):
    def sql(self,sql,args=()):
        with self.connection.cursor() as q:
            q.execute(sql,args)
            return q.fetchall() if q.description else []

    def insert(self,table,row):
        cols=list(row)
        self.sql('INSERT INTO '+table+' ('+','.join(cols)+') VALUES ('+','.join(['%s']*len(cols))+')',tuple(row.values()))

    def many(self,table,rows):
        if not rows:return
        columns=list(rows[0]);sql='INSERT INTO '+table+' ('+','.join(columns)+') VALUES ('+','.join(['%s']*len(columns))+')'
        with self.connection.cursor() as q:q.executemany(sql,[tuple(r[c] for c in columns) for r in rows])

    def reject(self,label,table,row,code):
        import pymysql
        self.sql('SAVEPOINT invalid_probe')
        try:
            try:self.insert(table,row)
            except pymysql.MySQLError as error:
                self.assertEqual(error.args[0],code,(label,str(error)))
                self.report['constraints'].append(dict(probe=label,error=code,result='PASS'))
            else:self.fail('Unexpectedly accepted: '+label)
        finally:self.sql('ROLLBACK TO SAVEPOINT invalid_probe')

    def apply(self):
        self.before_hashes={n:hashlib.sha256((contract.MIGRATIONS/n).read_bytes()).hexdigest() for n in DDL_NAMES}
        self.assertEqual({n:self.before_hashes[n] for n in contract.OLD},contract.OLD)
        self.assertEqual(self.sql('SHOW TABLES'),[],'Service database must be initially empty')
        self.report['mysql_version']=self.sql('SELECT VERSION() AS version')[0]['version']
        self.report['applied']=[]
        for name in DDL_NAMES:
            before=self.show_all() if name.startswith('0006') else None
            text='\n'.join(l for l in (contract.MIGRATIONS/name).read_text().splitlines() if not l.lstrip().startswith('--'))
            for statement in contract.split_sql(text,';'):
                if statement.strip():self.sql(statement)
            self.report['applied'].append(dict(name=name,sha256=self.before_hashes[name]))
            if before is not None:
                after=self.show_all()
                self.assertEqual(set(after)-set(before),contract.NEW)
                for table,create in before.items():self.assertEqual(after[table],create,table)
        self.assertEqual(len(self.show_all()),26)
        self.assertEqual(self.sql('SELECT COUNT(*) AS n FROM m2_schema_migrations')[0]['n'],0)
        self.assertEqual(self.sql('SELECT enabled FROM m2_jobs')[0]['enabled'],0)
        for r in self.sql('SELECT stop_latched,unresolved FROM m2_collector_state'):
            self.assertEqual((r['stop_latched'],r['unresolved']),(1,0))
        self.report['ledger']='EMPTY_SYNTHETIC_NO_HISTORY_CLAIMED'
        self.report['migration5_state']='APPLIED_LOCKED'

    def show_all(self):
        names=[next(iter(r.values())) for r in self.sql('SHOW TABLES')]
        return {n:self.sql('SHOW CREATE TABLE '+n)[0]['Create Table'] for n in names}

    def postcheck(self):
        pairs=[];self.report['tables']={}
        for table in sorted(contract.NEW):
            expected=contract.AFTER[table]
            columns=self.sql('SELECT COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,COLUMN_DEFAULT,EXTRA,COLLATION_NAME FROM information_schema.columns WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION',(table,))
            self.assertEqual([r['COLUMN_NAME'] for r in columns],list(expected['columns']))
            for c in columns:
                name=c['COLUMN_NAME'];typ,nullable,collate,auto,default=expected['columns'][name]
                self.assertEqual(c['COLUMN_TYPE'].lower(),typ.lower(),(table,name,c))
                self.assertEqual(c['IS_NULLABLE']=='YES',nullable)
                self.assertIsNone(c['COLUMN_DEFAULT']);self.assertIsNone(default)
                self.assertEqual(c['EXTRA'],'auto_increment' if auto else '')
                self.assertEqual(c['COLLATION_NAME'],(collate or 'utf8mb4_0900_ai_ci') if typ.startswith(('VARCHAR','CHAR')) else None)
            attrs=self.sql('SELECT ENGINE,TABLE_COLLATION FROM information_schema.tables WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s',(table,))[0]
            self.assertEqual(attrs,dict(ENGINE='InnoDB',TABLE_COLLATION='utf8mb4_0900_ai_ci'))
            ix=self.sql('SELECT INDEX_NAME,NON_UNIQUE,COLUMN_NAME,SUB_PART,INDEX_TYPE,IS_VISIBLE FROM information_schema.statistics WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s ORDER BY INDEX_NAME,SEQ_IN_INDEX',(table,))
            indexes={}
            for r in ix:
                self.assertIsNone(r['SUB_PART']);self.assertEqual(r['INDEX_TYPE'],'BTREE');self.assertEqual(r['IS_VISIBLE'],'YES')
                columns0,unique=indexes.setdefault(r['INDEX_NAME'],([],r['NON_UNIQUE']==0));columns0.append(r['COLUMN_NAME'])
            indexes={k:(tuple(cols),unique) for k,(cols,unique) in indexes.items()}
            self.assertEqual(indexes,expected['indexes']|{'PRIMARY':(expected['pk'],True)},table)
            rows=self.sql('SELECT k.CONSTRAINT_NAME,k.COLUMN_NAME,k.REFERENCED_TABLE_NAME,k.REFERENCED_COLUMN_NAME,r.DELETE_RULE,r.UPDATE_RULE FROM information_schema.key_column_usage k JOIN information_schema.referential_constraints r ON r.CONSTRAINT_SCHEMA=k.CONSTRAINT_SCHEMA AND r.CONSTRAINT_NAME=k.CONSTRAINT_NAME AND r.TABLE_NAME=k.TABLE_NAME WHERE k.TABLE_SCHEMA=DATABASE() AND k.TABLE_NAME=%s ORDER BY k.CONSTRAINT_NAME,k.ORDINAL_POSITION',(table,))
            foreign={}
            for r in rows:
                self.assertEqual(r['DELETE_RULE'],'RESTRICT');self.assertIn(r['UPDATE_RULE'],('RESTRICT','NO ACTION'))
                e=foreign.setdefault(r['CONSTRAINT_NAME'],[[],r['REFERENCED_TABLE_NAME'],[],'RESTRICT'])
                e[0].append(r['COLUMN_NAME']);e[2].append(r['REFERENCED_COLUMN_NAME'])
            self.assertEqual({k:(tuple(v[0]),v[1],tuple(v[2]),v[3]) for k,v in foreign.items()},expected['fks'],table)
            checks=self.sql("SELECT c.CONSTRAINT_NAME,c.CHECK_CLAUSE,t.ENFORCED FROM information_schema.check_constraints c JOIN information_schema.table_constraints t ON t.CONSTRAINT_SCHEMA=c.CONSTRAINT_SCHEMA AND t.CONSTRAINT_NAME=c.CONSTRAINT_NAME WHERE t.TABLE_SCHEMA=DATABASE() AND t.TABLE_NAME=%s AND t.CONSTRAINT_TYPE='CHECK'",(table,))
            self.assertEqual({r['CONSTRAINT_NAME'] for r in checks},set(expected['checks']))
            create=self.sql('SHOW CREATE TABLE '+table)[0]['Create Table']
            self.assertTrue(create.startswith('CREATE TABLE `'+table+'`'))
            self.assertIn('ENGINE=InnoDB',create);self.assertIn('COLLATE=utf8mb4_0900_ai_ci',create)
            for r in checks:
                self.assertEqual(r['ENFORCED'],'YES')
                self.assertIn(r['CONSTRAINT_NAME'],create)
                pairs.append(dict(table=table,name=r['CONSTRAINT_NAME'],expected=expected['checks'][r['CONSTRAINT_NAME']],actual=r['CHECK_CLAUSE'],show=create))
            self.report['tables'][table]=dict(columns=len(columns),indexes=len(indexes),foreign_keys=len(foreign),checks=len(checks),show_create_sha256=sha(create).hex())
        compared=compare_checks(pairs)
        self.assertEqual(len(compared),len(pairs))
        self.assertTrue(all(r['equal'] for r in compared),compared)
        self.report['postcheck']='PASS'

    def seed_core(self):
        now='2026-01-01 00:00:00.000000';self.body=b'{"synthetic":true,"unmapped":{"future":"retained"}}'
        self.many('m2_sources',[dict(id=s,source_key=f'synthetic_source_{s}',source_type='synthetic',display_name=f'Synthetic {s}',enabled=0,created_at=now,updated_at=now) for s in range(1,4)])
        self.many('m2_entities',[dict(id=a,entity_type='asset',canonical_name=f'Synthetic {a}',status='active',created_at=now,updated_at=now) for a in range(1,ASSETS+1)])
        self.many('m2_assets',[dict(entity_id=a,asset_class='equity',display_name=f'Synthetic {a}',status='active',created_at=now,updated_at=now) for a in range(1,ASSETS+1)])
        self.many('m2_asset_source_routes',[dict(id=(a-1)*3+s,asset_id=a,source_id=s,route_type='fundamental',external_key=f'synthetic_{a}_{s}',priority=0,enabled=0,created_at=now,updated_at=now) for a in range(1,ASSETS+1) for s in range(1,4)])
        self.insert('m2_files',dict(id=1,storage_backend='synthetic_memory',storage_key='synthetic-not-an-installed-file',mime_type='application/json',byte_size=len(self.body),sha256=sha(self.body),created_at=now))
        self.many(contract.METRIC,[dict(metric_key=f'synthetic_metric_{m:02d}',display_name=f'Synthetic metric {m}',category='synthetic',value_type='decimal',value_semantics=f'Synthetic deterministic metric {m}',dimension_key=DIMENSIONS[m%5],definition_sha256=sha(f'metric:{m}'),status='active',created_at=now,updated_at=now) for m in range(METRICS)])
        for typ in ('text','date'):
            self.insert(contract.METRIC,dict(metric_key='synthetic_'+typ,display_name='Synthetic '+typ,category='synthetic',value_type=typ,value_semantics='Synthetic '+typ,dimension_key=typ,definition_sha256=sha(typ),status='active',created_at=now,updated_at=now))
        for unit,dim,currency,num,den in [('EUR','monetary','EUR',1,1),('ONE','ratio',None,1,1),('EUR_PER_SHARE','monetary_per_share','EUR',1,1),('SHARE','shares',None,1,1),('COUNT','count',None,1,1),('PERCENT','ratio',None,1,100),('DIMENSIONLESS','dimensionless',None,1,1),('TEXT','text',None,1,1),('DATE','date',None,1,1)]:
            self.insert(contract.UNIT,dict(unit_key=unit,unit_version=1,display_name='Synthetic '+unit,dimension_key=dim,monetary_currency_code=currency,scale_numerator=num,scale_denominator=den,definition_sha256=sha(unit),status='frozen',created_at=now))
        self.connection.commit()

    def fetch(self,asset,source,revision,identity=None):
        return dict(id=identity or ((asset-1)*3+source-1)*REVISIONS+revision+1,
          fetch_key=sha(f'synthetic-fetch:{asset}:{source}:{revision}'),source_id=source,asset_id=asset,
          route_id=(asset-1)*3+source,route_revision=1,route_sha256=sha(f'synthetic-route:{asset}:{source}:1'),
          job_run_id=None,file_id=1,payload_sha256=sha(self.body),payload_bytes=len(self.body),
          content_type='application/json',observed_at=f'2026-10-31 00:00:0{revision}.000000',
          http_status=200,parser_key='synthetic',parser_version='1',parse_status='parsed',created_at=NOW)

    def constraints(self):
        self.sql('SAVEPOINT probes');self.counter=900010
        def fresh(row,kind):
            self.counter+=1
            return row|dict(id=self.counter,**{('fetch_key' if kind=='fetch' else 'dedupe_key'):sha(str(self.counter))})
        try:
            fetch=self.fetch(1,1,0,900001);self.insert(contract.FETCH,fetch)
            for label,change,code in [('fetch source FK',dict(source_id=999999),1452),('fetch file FK',dict(file_id=999999),1452),
                 ('fetch key unique',dict(fetch_key=fetch['fetch_key']),1062),('fetch parser state',dict(parse_status='unknown'),3819),
                 ('fetch parser identity',dict(parser_version=None),3819),('fetch route revision',dict(route_revision=0),3819)]:
                self.reject(label,contract.FETCH,fresh(fetch,'fetch')|change,code)
            same=fresh(fetch,'fetch')|dict(observed_at='2026-10-31 00:00:05.000000')
            self.insert(contract.FETCH,same)
            seen=self.sql('SELECT payload_sha256,payload_bytes,file_id,observed_at FROM m2_provider_fetches ORDER BY id')
            self.assertEqual(len(seen),2);self.assertEqual({r['payload_sha256'] for r in seen},{sha(self.body)})
            self.assertEqual({r['payload_bytes'] for r in seen},{len(self.body)});self.assertEqual(len({r['observed_at'] for r in seen}),2)
            self.assertEqual(len(self.sql('SELECT id FROM m2_files WHERE sha256=%s',(sha(self.body),))),1)
            metric=self.sql("SELECT * FROM m2_fundamental_metrics WHERE metric_key='synthetic_metric_00'")[0]
            self.reject('metric key unique',contract.METRIC,metric,1062)
            self.reject('metric missing definition hash',contract.METRIC,metric|dict(metric_key='missing_hash',definition_sha256=None),1048)
            self.reject('metric category',contract.METRIC,metric|dict(metric_key='empty_category',category=''),3819)
            self.reject('metric semantics',contract.METRIC,metric|dict(metric_key='empty_semantics',value_semantics=''),3819)
            unit=self.sql("SELECT * FROM m2_fundamental_units WHERE unit_key='EUR'")[0]
            self.reject('unit version unique',contract.UNIT,unit,1062)
            self.reject('unit monetary currency required',contract.UNIT,unit|dict(unit_version=2,monetary_currency_code=None),3819)
            self.reject('unit ratio currency forbidden',contract.UNIT,unit|dict(unit_key='BAD_RATIO',dimension_key='ratio'),3819)
            self.reject('unit positive version',contract.UNIT,unit|dict(unit_version=0),3819)
            self.insert(contract.UNIT,unit|dict(unit_version=2))
            facts=[]
            for i,kind in enumerate(PERIODS):
                row=observation(1,0,kind,0,900001+i)|dict(source_id=1,route_id=1,fetch_id=900001,value_decimal=Decimal('-1.250000000000'))
                self.insert(contract.OBS,row);facts.append(row);self.insert(contract.CURRENT,projection(row))
            self.assertEqual(self.sql('SELECT COUNT(*) AS n FROM m2_fundamental_current')[0]['n'],5)
            self.assertEqual({r['period_type'] for r in self.sql('SELECT period_type FROM m2_fundamental_current')},set(PERIODS))
            base=facts[0]
            for label,change,code in [('observation dedupe unique',dict(dedupe_key=base['dedupe_key']),1062),
              ('observation source FK',dict(source_id=999999),1452),('observation asset FK',dict(asset_id=999999),1452),
              ('observation route FK',dict(route_id=999999),1452),('observation fetch FK',dict(fetch_id=999999),1452),
              ('fetch source binding',dict(source_id=2),1452),('metric FK',dict(metric_key='missing_metric'),1452),
              ('unit FK',dict(unit_version=99),1452),('one value only',dict(value_text='extra'),3819),
              ('value missing',dict(value_decimal=None),3819),('snapshot period mismatch',dict(fiscal_year=2025),3819)]:
                self.reject(label,contract.OBS,fresh(base,'obs')|change,code)
            fq=facts[2]
            for label,change in [('quarter number',dict(fiscal_quarter=5)),('quarter missing',dict(fiscal_quarter=None)),
              ('period backwards',dict(period_start=fq['period_end'])),('half period',dict(period_end=None))]:
                self.reject(label,contract.OBS,fresh(fq,'obs')|change,3819)
            self.reject('forward horizon required',contract.OBS,fresh(facts[4],'obs')|dict(estimate_horizon=None),3819)
            self.insert(contract.OBS,fresh(base,'obs')|dict(value_decimal=Decimal(0)))
            for typ,change in [('text',dict(value_text='synthetic text')),('date',dict(value_date=date(2025,1,1)))]:
                self.insert(contract.OBS,fresh(base,'obs')|dict(metric_key='synthetic_'+typ,value_type=typ,
                    dimension_key=typ,unit_key=typ.upper(),value_decimal=None,**change))
            current=projection(base)
            self.reject('current slot unique',contract.CURRENT,current,1062)
            for label,change in [('current observation FK',dict(observation_id=999999)),
              ('current source binding',dict(source_id=2)),('current period binding',dict(period_type='ttm')),
              ('current asset binding',dict(asset_id=2)),('current metric binding',dict(metric_key='synthetic_metric_05'))]:
                if label=='current period binding':
                    self.sql("DELETE FROM m2_fundamental_current WHERE asset_id=1 AND metric_key='synthetic_metric_00' AND period_type='ttm'")
                self.sql('SAVEPOINT invalid_current')
                try:
                    import pymysql
                    assignment=','.join(k+'=%s' for k in change)
                    try:
                        self.sql("UPDATE m2_fundamental_current SET "+assignment+" WHERE asset_id=1 AND metric_key='synthetic_metric_00' AND period_type='snapshot'",tuple(change.values()))
                    except pymysql.MySQLError as error:
                        self.assertEqual(error.args[0],1452,(label,str(error)))
                        self.report['constraints'].append(dict(probe=label,error=1452,result='PASS'))
                    else:self.fail('Unexpectedly accepted: '+label)
                finally:self.sql('ROLLBACK TO SAVEPOINT invalid_current')
            self.report['valid_probes']=['five period kinds coexist','negative financial value','zero financial value',
                'typed text','typed date','unit version 2','two fetch times share exact file hash and byte size']
        finally:self.sql('ROLLBACK TO SAVEPOINT probes');self.connection.rollback()

    def populate(self):
        for a in range(1,ASSETS+1):
            self.many(contract.FETCH,[self.fetch(a,s,r) for s in range(1,4) for r in range(REVISIONS)])
        self.connection.commit()
        facts=[];current=[];identity=0
        for a in range(1,ASSETS+1):
            for m in range(METRICS):
                for kind in PERIODS:
                    for revision in range(REVISIONS):
                        identity+=1;r=observation(a,m,kind,revision,identity);facts.append(r)
                        if revision==REVISIONS-1:current.append(projection(r))
                        if len(facts)==1000:self.many(contract.OBS,facts);facts=[]
            self.connection.commit()
        self.many(contract.OBS,facts)
        # Dense histories for the measured asset exercise the full LIMIT 100,
        # rather than timing four rows against a large but irrelevant table.
        dense=[]
        for kind in ('snapshot','fy','fq'):
            for n in range(96):
                identity+=1
                row=observation(42,0,kind,0,identity)|dict(source_id=1,route_id=124,fetch_id=493,
                    dedupe_key=sha(f'dense:{kind}:{n}'))
                if kind=='snapshot':
                    row['as_of_at']=(datetime(2020,1,1)+timedelta(days=n)).strftime('%Y-%m-%d %H:%M:%S.%f')
                elif kind=='fy':
                    year=1925+n;row.update(fiscal_year=year,period_start=date(year,1,1),period_end=date(year,12,31),
                                          as_of_at=f'{year}-12-31 00:00:00.000000')
                else:
                    year=2000+n//4;quarter=n%4+1;month=(quarter-1)*3+1
                    end=date(year,month+3,1)-timedelta(days=1) if quarter<4 else date(year,12,31)
                    row.update(fiscal_year=year,fiscal_quarter=quarter,period_start=date(year,month,1),
                               period_end=end,as_of_at=str(end)+' 00:00:00.000000')
                row['period_key']=contract.period_identity(row);dense.append(row)
        self.many(contract.OBS,dense)
        for i in range(0,len(current),1000):self.many(contract.CURRENT,current[i:i+1000])
        self.connection.commit()
        self.report['counts']={}
        for table in ('m2_assets','m2_sources',contract.METRIC,contract.UNIT,contract.FETCH,contract.OBS,contract.CURRENT,'m2_files'):
            self.report['counts'][table]=int(self.sql('SELECT COUNT(*) AS n FROM '+table)[0]['n'])
        self.assertEqual(self.report['counts'][contract.OBS],100288)
        self.assertEqual(self.report['counts'][contract.CURRENT],25000)
        self.sql('ANALYZE TABLE m2_fundamental_current,m2_fundamental_observations,m2_provider_fetches')
        self.connection.commit()

    def read(self,code,sql,args):
        result=self.sql(sql,args)
        if code!='A':return result
        # Architecture's bounded 128-row pages plus one sentinel.
        out=result[:128]
        if len(result)>128:
            cursor=out[-1]
            next_sql=sql.replace('WHERE asset_id=%s','WHERE asset_id=%s AND (metric_key,period_type)>(%s,%s)')
            second=self.sql(next_sql,(args[0],cursor['metric_key'],cursor['period_type']))
            self.assertLessEqual(len(second),128,'Fixture must fit exactly two bounded pages')
            out+=second
        return out

    def explain_and_measure(self):
        self.report['reads']={}
        for code,definition in read_paths().items():
            sql,args=definition['sql'],definition['args']
            plan=json.loads(next(iter(self.sql('EXPLAIN FORMAT=JSON '+sql,args)[0].values())))
            tables=plan_tables(plan)
            self.assertEqual({t['table_name'] for t in tables},definition['tables'],(code,plan))
            for t in tables:
                self.assertNotIn(t['access_type'],('ALL','index'),(code,t))
                self.assertIn(t.get('key'),definition['keys'],(code,t))
            analyze=next(iter(self.sql('EXPLAIN ANALYZE '+sql,args)[0].values()))
            self.assertIn('actual time=',analyze)
            for _ in range(WARMUPS):self.read(code,sql,args)
            durations=[];rows=None
            for _ in range(REPEATS):
                started=time.perf_counter_ns();result=self.read(code,sql,args)
                durations.append((time.perf_counter_ns()-started)/1000000);rows=len(result)
            p95=sorted(durations)[math.ceil(REPEATS*0.95)-1];median=statistics.median(durations)
            item=dict(label=definition['label'],median_ms=round(median,4),p95_ms=round(p95,4),
                warmups=WARMUPS,repeats=REPEATS,returned_rows=rows,
                explain=[{k:t[k] for k in ('table_name','access_type','key','used_key_parts','rows_examined_per_scan','rows_produced_per_join') if k in t} for t in tables],
                explain_analyze=analyze)
            if code=='A':
                first=self.sql(sql,args);cursor=first[127]
                next_sql=sql.replace('WHERE asset_id=%s','WHERE asset_id=%s AND (metric_key,period_type)>(%s,%s)')
                continuation=json.loads(next(iter(self.sql('EXPLAIN FORMAT=JSON '+next_sql,(42,cursor['metric_key'],cursor['period_type']))[0].values())))
                for table in plan_tables(continuation):
                    self.assertEqual(table.get('key'),'PRIMARY')
                    self.assertNotIn(table['access_type'],('ALL','index'))
                item['continuation_explain']=plan_tables(continuation)
                item['statements_per_read']=2
            self.report['reads'][code]=item
            self.assertLess(p95,100,(code,item))
            if code in ('A','B'):self.assertLess(p95,20,(code,item))
            if code=='A':self.assertEqual(rows,250)
            elif code in ('C','D','E'):self.assertEqual(rows,100)
            else:self.assertEqual(rows,1)

    def test_complete_isolated_mysql8_qualification(self):
        self.report=dict(status='STARTED',constraints=[],provider_requests=0,live_database_connections=0,
                         deployment=False,connection_scope='existing GHA 127.0.0.1:3307 service only')
        self.connection=connect()
        try:
            self.sql("SET SESSION time_zone='+00:00'")
            self.sql("SET SESSION sql_mode='STRICT_ALL_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION,ONLY_FULL_GROUP_BY'")
            self.sql('SET SESSION max_execution_time=10000')
            self.apply();self.postcheck();self.seed_core();self.constraints();self.populate();self.explain_and_measure()
            after={n:hashlib.sha256((contract.MIGRATIONS/n).read_bytes()).hexdigest() for n in DDL_NAMES}
            self.assertEqual(after,self.before_hashes);self.report['migration_hashes_unchanged']=True
            self.report['status']='PASS'
        except Exception as error:
            self.report.update(status='FAILED',failure_type=type(error).__name__,failure=str(error))
            raise
        finally:
            self.connection.rollback();self.connection.close()
            wire=json.dumps(self.report,sort_keys=True,indent=2,default=str)
            target=os.environ.get('MOSA2_FUNDAMENTALS_REPORT')
            if target:Path(target).write_text(wire,encoding='utf-8')
            summary=os.environ.get('GITHUB_STEP_SUMMARY')
            if summary:
                with open(summary,'a',encoding='utf-8') as f:f.write('Isolated synthetic MySQL8 qualification; no Dogado apply\n\n~~~json\n'+wire+'\n~~~\n')
            print('FUNDAMENTALS6_EVIDENCE\n'+wire,flush=True)

if __name__=='__main__':unittest.main()
