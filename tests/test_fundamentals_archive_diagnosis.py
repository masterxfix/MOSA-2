"""Offline: real transport limit, remote code, read-only fake archive and redaction."""
import base64
from contextlib import contextmanager
import copy
import hashlib
import io
import json
import stat
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from test_collector_private_directories import FakeOS
from test_fundamentals_generic import fixture, OBSERVED
from scripts.fundamentals import archived_zeiss as archive
from scripts.fundamentals_archive_diagnose import diagnose

class Channel:
    def __init__(self, output): self.output=output; self.closed=False
    def settimeout(self, value): pass
    def exec_command(self, cmd): pass
    def sendall(self, payload): pass
    def shutdown_write(self): pass
    def recv_ready(self): return bool(self.output)
    def recv(self, n): result=self.output[:n]; self.output=self.output[n:]; return result
    def recv_stderr_ready(self): return False
    def exit_status_ready(self): return not self.output
    def recv_exit_status(self): return 0
    def close(self): self.closed=True

class ReadOnlyFiles(FakeOS):
    def __init__(self, lib, raw, metadata):
        super().__init__(lib)
        self.contents={}
        for i,path in enumerate((*lib['TARGETS'],lib['ROOT']+'/runs/'+archive.EXECUTION)):
            self.nodes[path]=SimpleNamespace(st_mode=stat.S_IFDIR|0o700,st_uid=10317,st_gid=1003,st_dev=64768,st_ino=9000+i)
        folder=lib['ROOT']+'/runs/'+archive.EXECUTION
        self.body=folder+'/response.body'
        for path,data in [(self.body,raw),(folder+'/response.json',json.dumps(metadata).encode()),
            (lib['ROOT']+'/locks/'+archive.EXECUTION+'.consumed',json.dumps(dict(execution=archive.EXECUTION,commit=archive.COMMIT),sort_keys=True).encode())]:
            self.contents[path]=data
            self.nodes[path]=SimpleNamespace(st_mode=stat.S_IFREG|0o600,st_uid=10317,st_gid=1003,st_nlink=1,st_size=len(data))
    def open(self,path,flags,dir_fd=None):
        if flags & self.O_DIRECTORY:return super().open(path,flags,dir_fd=dir_fd)
        assert flags==self.O_RDONLY|self.O_NOFOLLOW
        full=self.full(path,dir_fd)
        if full not in self.contents:raise FileNotFoundError('private path must not leak')
        if stat.S_ISLNK(self.nodes[full].st_mode):raise OSError('private path must not leak')
        self.next_fd+=1;self.fds[self.next_fd]=full;return self.next_fd
    @contextmanager
    def fdopen(self,fd,mode,closefd=False):
        assert mode=='rb'
        yield io.BytesIO(self.contents[self.fds[fd]])

class ArchiveDiagnosisTests(unittest.TestCase):
    def scope(self):
        scope={'__name__':'fixture'}
        exec(compile(archive.source(),'<actual-remote-source>','exec'),scope)
        return scope
    def data(self, raw):
        return dict(execution=archive.EXECUTION,commit=archive.COMMIT,url=archive.zeiss.URL,
                    sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),
                    request_started_at=OBSERVED,observed_at=OBSERVED,http_status=200,content_type='text/html; charset=utf-8')
    def test_old_48k_raw_exceeds_unchanged_transport_limit(self):
        raw=b'x'*(48*1024)
        wire=json.dumps(dict(payload=base64.b64encode(raw).decode())).encode()
        self.assertEqual(archive.remote.MAX_OUTPUT,65536)
        self.assertGreater(len(wire),archive.remote.MAX_OUTPUT)
        channel=Channel(wire)
        with self.assertRaisesRegex(archive.remote.ProbeError,'^SSH_OUTPUT_LIMIT$'):
            archive.remote.remote_call(SimpleNamespace(open_session=lambda **kw:channel),'synthetic')
        self.assertTrue(channel.closed)
    def test_large_archive_diagnosed_in_place_with_small_private_free_result(self):
        raw=fixture()+b'<!--PRIVATE_SENTINEL '+b'x'*(512*1024)+b'-->'
        metadata=self.data(raw);scope=self.scope();files=ReadOnlyFiles(scope,raw,metadata);scope['os']=files
        original=copy.deepcopy(files.contents)
        result=scope['run_diagnosis'](metadata)
        self.assertTrue(result['ok'],result)
        self.assertEqual(result['archive_sha256'],'PASS')
        self.assertTrue(result['legacy_transport_would_exceed_limit'])
        self.assertEqual(result['diagnosis']['first_error'],'NONE')
        self.assertEqual(result['diagnosis']['matching_tables'],1)
        output=json.dumps(result).encode()
        self.assertLess(len(output),16384)
        for private in (b'PRIVATE_SENTINEL',b'1.234,5',b'1234.5',b'987,6',b'/private/',b'<table',b'payload'):
            self.assertNotIn(private,output)
        channel=Channel(output)
        self.assertEqual(archive.remote.remote_call(SimpleNamespace(open_session=lambda **kw:channel),'synthetic')[1],output)
        self.assertEqual(files.contents,original);self.assertEqual(files.writes,[]);self.assertEqual(files.fds,{})
    def test_hash_mode_owner_link_and_size_guards_and_safe_phase_errors(self):
        raw=fixture();metadata=self.data(raw)
        for mutation in ('hash','mode','owner','link','size','json'):
            scope=self.scope();files=ReadOnlyFiles(scope,raw,metadata);scope['os']=files
            if mutation=='hash':files.contents[files.body]=raw[:-1]+b'!'
            if mutation=='mode':files.nodes[files.body].st_mode=stat.S_IFREG|0o644
            if mutation=='owner':files.nodes[files.body].st_uid=0
            if mutation=='link':files.nodes[files.body].st_mode=stat.S_IFLNK|0o600
            if mutation=='size':files.nodes[files.body].st_size=8*1024*1024+1
            if mutation=='json':files.contents[files.body.replace('response.body','response.json')]=b'INVALID'
            result=scope['run_diagnosis'](metadata)
            self.assertFalse(result['ok'],mutation)
            self.assertIn(result['phase'],('ARCHIVE_BYTES','ARCHIVE_METADATA'))
            self.assertNotIn('private path',json.dumps(result));self.assertEqual(files.writes,[])
    def test_first_adapter_failure_and_structural_only_output(self):
        raw=fixture().replace(b'<td>',b'<td></td><td>',1)
        result=diagnose(raw,self.data(raw))
        self.assertEqual(result['first_error'],'AMBIGUOUS_RESULTS_TABLE')
        self.assertEqual(result['matching_tables'],0)
        self.assertTrue(any(r['label_cell']==1 for t in result['tables'] for r in t['rows']))
        self.assertIn('revenue',result['recognized_metric_keys'])
    def test_transport_codes_are_not_swallowed(self):
        with patch.object(archive.remote,'remote_call',side_effect=archive.remote.ProbeError('SSH_OUTPUT_LIMIT')):
            with self.assertRaisesRegex(archive.remote.ProbeError,'^SSH_OUTPUT_LIMIT$'):archive.load(object())

if __name__=='__main__':unittest.main()
