import copy
import base64
from contextlib import contextmanager
import hashlib
import io
import json
from pathlib import Path
import subprocess
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from scripts.fundamentals import pne
from scripts import fundamentals_pilot_once as pilot
from scripts.market_collector.http_transport import ReadOnlyHttpTransport,HttpGet
from test_collector_private_directories import FakeOS

# Invented fixture amounts only. Never substitute these for a provider response.
HTML='''<html><script>PRIVATE NOT CONTENT</script><p>Cuxhaven, 26. März 2026 – Die PNE AG hat das Geschäftsjahr 2025 operativ erfolgreich abgeschlossen.
Die Gesamtleistung stieg auf <strong>123,4</strong> Mio. Euro (Vorjahr: 111,2 Mio. Euro).</p>
<p>Das um Sondereffekte bereinigte EBITDA („normalised EBITDA“) erreichte 33,7 Mio. und bewegt sich innerhalb der ursprünglichen Guidance-Spanne von 10 bis 90 Mio. Euro.
Mit 22,5 Mio. Euro (Vorjahr: 21,4 Mio. Euro) liegt das EBITDA in der Spanne der Guidance.
Im Geschäftsjahr 2025 erzielte das Unternehmen ein Betriebsergebnis (EBIT) von -4,3 Mio. Euro (Vorjahr: 2,1 Mio. Euro).
Den Bericht für das Geschäftsjahr 2025 hat PNE heute veröffentlicht.</p>
<p>Für 2026 wird EBITDA von 999 bis 9999 Mio. Euro erwartet. Eine Dividende wird vorgeschlagen.</p></html>'''
OBSERVED='2026-11-01 00:00:00.123456'

def plan():
    raw=HTML.encode()
    value=pne.parse(raw,OBSERVED)
    value['metadata']=dict(url=pne.URL,observed_at=OBSERVED,http_status=200,content_type='text/html; charset=utf-8',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    value['archive']=dict(storage_key='/private/synthetic/response.body',sha256=value['metadata']['sha256'],bytes=len(raw),durable=True)
    return value

class PilotTests(unittest.TestCase):
    def php(self,body,data):
        p=subprocess.run(['php','-r',"require 'scripts/fundamentals/core.php';$p=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);"+body],
            input=json.dumps(data),text=True,capture_output=True,cwd=pilot.ROOT)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr);self.assertEqual(p.stderr,'');return json.loads(p.stdout)

    def test_adapter_values_units_years_and_exact_evidence(self):
        result=plan();rows=result['observations']
        self.assertEqual(len(rows),7)
        self.assertEqual({r['metric_key'] for r in rows},set(pne.METRICS))
        self.assertEqual([r['value_decimal'] for r in rows],['123.4','111.2','33.7','22.5','21.4','-4.3','2.1'])
        self.assertEqual(result['publication_date'],'2026-03-26')
        self.assertEqual({r['fiscal_year'] for r in rows},{'2024','2025'})
        self.assertTrue(all(r['reported_at'] is None and r['observed_at']==OBSERVED for r in rows))
        text=pne.normalized_text(HTML.encode())
        for r in rows:
            a,b=r['field_path'].split(';')[0].split(':')[1:]
            self.assertEqual(pne.number(text[int(a):int(b)]),r['value_decimal'])

    def test_adapter_rejects_missing_ambiguous_wrong_period_and_future_publication(self):
        for text in (HTML.replace('Gesamtleistung','Umsatzerlöse'), HTML+HTML,
                     HTML.replace('Geschäftsjahr 2025','Geschäftsjahr 2024'),HTML.replace('33,7 Mio.','unbekannt Mio.')):
            with self.assertRaises(ValueError):pne.parse(text.encode(),OBSERVED)
        with self.assertRaises(ValueError):pne.parse(HTML.encode(),'2026-01-01 00:00:00.000000')

    def test_generic_validation_conflicts_units_and_precision(self):
        base=plan();variants=[]
        for field,value in [('unit_key','PERCENT'),('value_decimal','1.1234567890123'),('value_decimal','NaN'),('period_end','2025-02-30'),('dimension_key','ratio')]:
            v=copy.deepcopy(base);v['observations'][0][field]=value;variants.append(v)
        v=copy.deepcopy(base);v['observations'].append(v['observations'][0]);variants.append(v)
        result=self.php('try{Mosa2\\Fundamentals\\validate($p);echo "true";}catch(Throwable){echo "false";}',base)
        self.assertTrue(result)
        for v in variants:self.assertFalse(self.php('try{Mosa2\\Fundamentals\\validate($p);echo "true";}catch(Throwable){echo "false";}',v))

    def test_transaction_failure_injection_and_unknown_commit(self):
        p=subprocess.run(['php','tests/fundamentals_offline.php'],input=json.dumps(plan()),text=True,capture_output=True,cwd=pilot.ROOT)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr);self.assertEqual(p.stderr,'')
        rows=json.loads(p.stdout)
        self.assertTrue(rows[0]['ok'],rows[0]);self.assertEqual(rows[0]['writes'],19)
        self.assertEqual(rows[0]['current_years'],['2025']*4)
        for r in rows[1:-1]:
            self.assertFalse(r['ok'],r);self.assertTrue(r['empty'],r);self.assertEqual(r['commits'],0);self.assertEqual(r['rollbacks'],1)
        self.assertEqual(rows[-1],dict(commits=1,rollbacks=0,retained=True))

    def test_projection_uses_period_not_ingestion_order(self):
        rows=[dict(asset_id='1',metric_key='metric',period_type='fy',period_end=y+'-12-31',unit_key='EUR_MILLION',unit_version='1',source_id='2',dedupe_key=y) for y in ('2025','2024')]
        self.assertEqual(self.php('echo json_encode(Mosa2\\Fundamentals\\choose($p));',rows)[0]['period_end'],'2025-12-31')
        rows[1]['period_end']='2025-12-31'
        self.assertFalse(self.php('try{Mosa2\\Fundamentals\\choose($p);echo "true";}catch(Throwable){echo "false";}',rows))

    def test_one_request_is_consumed_on_error(self):
        transport=ReadOnlyHttpTransport(HttpGet(None,pne.URL))
        with patch('urllib.request.build_opener') as factory:
            factory.return_value.open.side_effect=TimeoutError()
            with self.assertRaises(ValueError):transport.fetch(None)
            with self.assertRaises(ValueError):transport.fetch(None)
            self.assertEqual(factory.return_value.open.call_count,1)
        self.assertEqual(transport.attempt_count,1)

    def test_guard_rejects_second_run_attempt_or_changed_commit(self):
        env=dict(GITHUB_REPOSITORY='masterxfix/MOSA-2',GITHUB_REF='refs/heads/main',GITHUB_EVENT_NAME='workflow_dispatch',
            GITHUB_RUN_ATTEMPT='1',GITHUB_RUN_NUMBER='1',GITHUB_SHA='a'*40,EXPECTED_COMMIT='a'*40,AUTHORIZATION=pilot.AUTHORIZATION+'a'*40)
        pilot.guard(env)
        for key in env:
            with self.assertRaises(ValueError):pilot.guard(env|{key:'invalid'})

    def test_private_archive_exclusive_durable_readback_and_tamper_rejection(self):
        scope={'__name__':'fixture'}
        exec(compile(pilot.directories.REMOTE_SOURCE,'<existing-directory-checker>','exec'),scope)
        exec(compile((pilot.ROOT/'scripts/fundamentals/archive_remote.py').read_text(),'<archive>','exec'),scope)
        class Files(FakeOS):
            O_WRONLY=1;O_CREAT=64;O_EXCL=128
            def __init__(self,lib):
                super().__init__(lib);self.contents={};self.syncs=[]
                for i,path in enumerate(lib['TARGETS']):
                    self.nodes[path]=SimpleNamespace(st_mode=stat.S_IFDIR|0o700,st_uid=10317,st_gid=1003,st_dev=64768,st_ino=9000+i)
            def open(self,path,flags,mode=None,dir_fd=None):
                if flags & self.O_DIRECTORY:return super().open(path,flags,dir_fd=dir_fd)
                full=self.full(path,dir_fd)
                if flags & self.O_CREAT:
                    if full in self.nodes:raise FileExistsError()
                    assert flags & self.O_EXCL and flags & self.O_NOFOLLOW and mode==0o600
                    self.nodes[full]=SimpleNamespace(st_mode=stat.S_IFREG|mode,st_uid=10317,st_gid=1003,st_nlink=1,st_size=0)
                    self.contents[full]=b''
                elif full not in self.nodes:raise FileNotFoundError()
                if stat.S_ISLNK(self.nodes[full].st_mode):raise OSError('symlink')
                self.next_fd+=1;self.fds[self.next_fd]=full;return self.next_fd
            @contextmanager
            def fdopen(self,fd,mode,closefd=False):
                path=self.fds[fd];stream=io.BytesIO(self.contents[path])
                yield stream
                if mode=='wb':self.contents[path]=stream.getvalue();self.nodes[path].st_size=len(stream.getvalue())
                stream.close()
            def fsync(self,fd):self.syncs.append(self.fds[fd])
        api=Files(scope);scope['os']=api
        data=dict(execution=pilot.EXECUTION,commit='a'*40,action='reserve')
        reserved=scope['operation'](data)
        with self.assertRaises(FileExistsError):scope['operation'](data)
        raw=b'\x00synthetic original UTF-8 bytes\xff'
        metadata=dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
        request=data|dict(action='archive',identity=reserved['identity'],metadata=metadata,payload=base64.b64encode(raw).decode())
        receipt=scope['operation'](request)
        self.assertTrue(receipt['durable']);self.assertEqual(api.contents[receipt['storage_key']],raw)
        self.assertTrue(api.syncs);self.assertEqual(api.fds,{})
        self.assertEqual(scope['operation'](request|dict(action='verify'))['sha256'],metadata['sha256'])
        api.contents[receipt['storage_key']]=b'bad'
        with self.assertRaises(RuntimeError):scope['operation'](request|dict(action='verify'))
        api.nodes[scope['ROOT']].st_ino+=1
        with self.assertRaises(RuntimeError):scope['operation'](request|dict(action='verify'))

if __name__=='__main__':unittest.main()
