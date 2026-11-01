import copy
from contextlib import contextmanager
import hashlib
import io
import json
import stat
from types import SimpleNamespace
import unittest
from scripts import fundamentals_archive_import_once as importer
from scripts.fundamentals import zeiss, archived_zeiss as archive
from test_fundamentals_generic import fixture, OBSERVED
from test_fundamentals_archive_diagnosis import ReadOnlyFiles

def wrapped(raw):return b'<table><tr><td>layout-before'+raw+b'layout-after</td></tr></table>'

class WritableMarkerFiles(ReadOnlyFiles):
    O_WRONLY=1;O_CREAT=64;O_EXCL=128
    def open(self,path,flags,mode=None,dir_fd=None):
        if not flags & self.O_CREAT:return super().open(path,flags,dir_fd=dir_fd)
        assert flags==self.O_WRONLY|self.O_CREAT|self.O_EXCL|self.O_NOFOLLOW and mode==0o600
        full=self.full(path,dir_fd)
        assert full.endswith('/locks/fundamentals-zeiss-qualified-import-20261101-01.consumed')
        if full in self.contents:raise FileExistsError()
        self.contents[full]=b'';self.writes.append(full)
        self.nodes[full]=SimpleNamespace(st_mode=stat.S_IFREG|0o600,st_uid=10317,st_gid=1003,st_nlink=1,st_size=0)
        self.next_fd+=1;self.fds[self.next_fd]=full;return self.next_fd
    @contextmanager
    def fdopen(self,fd,mode,closefd=False):
        path=self.fds[fd];stream=io.BytesIO(self.contents[path]);yield stream
        if mode=='wb':self.contents[path]=stream.getvalue();self.nodes[path].st_size=len(self.contents[path])
    def fsync(self,fd):pass

class ArchiveImportTests(unittest.TestCase):
    def test_nested_results_and_unrelated_layout_tables_keep_exact_facts(self):
        expected=zeiss.parse(fixture(),OBSERVED)
        for raw in (wrapped(fixture()),wrapped(wrapped(fixture())),
            b'<table><tr><td>foreign<table><tr><td>not results</td></tr></table>end</td></tr></table>'+fixture()):
            result=zeiss.parse(raw,OBSERVED)
            strip=lambda p:[{k:v for k,v in r.items() if k!='field_path'} for r in p['observations']]
            self.assertEqual(strip(result),strip(expected));self.assertEqual(result['units'],expected['units'])
            self.assertEqual({(r['period_start'],r['period_end']) for r in result['observations']},
                {('2024-10-01','2025-09-30'),('2023-10-01','2024-09-30')})
    def test_parent_child_cell_text_and_rows_are_never_merged(self):
        p=zeiss.Tables();p.feed('<table><tr><td>before<table><tr><td>inner</td></tr></table>after</td><td>sibling</td></tr></table>')
        self.assertEqual(p.tables,[[['[NESTED_TABLE_CONTENT]','sibling']],[['inner']]])
        bad=fixture().replace(b'1.234,5',b'1.<table><tr><td>999</td></tr></table>234,5',1)
        with self.assertRaisesRegex(ValueError,'RESULT_VALUE_OR_UNIT'):zeiss.parse(bad,OBSERVED)
    def test_nested_duplicate_missing_year_and_unit_fail_closed(self):
        for raw in (wrapped(fixture()+fixture()),wrapped(fixture().replace(b'1.234,5',b'',1)),
                    wrapped(fixture().replace(b'2024/25',b'2023/24')),
                    wrapped(fixture().replace('1,23 €'.encode(),'1,23 %'.encode()))):
            with self.assertRaises(ValueError):zeiss.parse(raw,OBSERVED)
    def scope(self,raw):
        scope={'__name__':'fixture'};exec(compile(importer.source(),'<remote-import>','exec'),scope)
        metadata=dict(execution=archive.EXECUTION,commit=archive.COMMIT,url=zeiss.URL,
            sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),request_started_at=OBSERVED,observed_at=OBSERVED,http_status=200,content_type='text/html')
        files=WritableMarkerFiles(scope,raw,metadata);scope['os']=files
        data=metadata|dict(action='plan',apply_commit='a'*40,authorization=importer.AUTHORIZATION+'a'*40)
        return scope,files,data
    def test_large_archive_plan_marker_and_original_readback(self):
        raw=wrapped(fixture())+b'<!--'+b'PRIVATE_SENTINEL'*(40000)+b'-->'
        scope,files,data=self.scope(raw);original=copy.deepcopy(files.contents)
        result=scope['import_operation'](data)
        self.assertTrue(result['ok'],result);self.assertLess(len(json.dumps(result).encode()),49152)
        self.assertNotIn('PRIVATE_SENTINEL',json.dumps(result));self.assertNotIn('<table',json.dumps(result))
        plan=result['plan']
        # Core validates the synthetic plan offline, with the production provenance binding substituted only in this test.
        plan['metadata']['sha256']=archive.SHA256;plan['archive']['sha256']=archive.SHA256
        importer.validate_plan(plan)
        reservation=data|dict(action='reserve',plan_sha256=result['plan_sha256'])
        reserved=scope['import_operation'](reservation);self.assertTrue(reserved['ok'],reserved)
        self.assertEqual(len(files.writes),1)
        self.assertEqual(scope['import_operation'](reservation)['error'],'APPLY_ALREADY_CONSUMED')
        self.assertTrue(scope['import_operation'](data|dict(action='verify'))['ok'])
        for path,value in original.items():self.assertEqual(files.contents[path],value)
    def test_failed_adapter_or_plan_binding_cannot_create_marker(self):
        scope,files,data=self.scope(wrapped(fixture().replace(b'1.234,5',b'',1)))
        result=scope['import_operation'](data|dict(action='reserve',plan_sha256='0'*64))
        self.assertFalse(result['ok']);self.assertEqual(result['archive'],'PASS');self.assertEqual(result['phase'],'ADAPTER')
        self.assertEqual(files.writes,[])
        scope,files,data=self.scope(wrapped(fixture()))
        result=scope['import_operation'](data|dict(action='reserve',plan_sha256='0'*64))
        self.assertEqual(result['error'],'PLAN_CHANGED');self.assertEqual(files.writes,[])

if __name__=='__main__':unittest.main()
