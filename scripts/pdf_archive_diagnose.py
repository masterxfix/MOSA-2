"""Read-only PDF archive diagnostics. Fixed reviewed profiles; no DB or HTTP client."""
from io import BytesIO
import hashlib
import json
import logging
import os
from pathlib import Path
import shlex
import stat
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scripts import collector_actions as access, collector_private_directories as directories, collector_db_locality as remote
from scripts.fundamentals.archived_zeiss import READ_SOURCE
from scripts.fundamentals_archive_diagnose import guard
from scripts.fundamentals.pdf_document import MAX_BYTES, MAX_PAGES, MAX_CHARACTERS

AUTH='MOSA2-PDF-ARCHIVE-DIAGNOSE-20261101:'
PROFILE=dict(execution='fundamentals-droneshield-fy2025-20261101-01',commit='1b189de1bbbb25dd3241488d4f2d4795e910f3b2',
 sha256='79627f3d25ceb0a294231c632739177944eb11dee59c6a8bd51d4fd48d257171',
 url='https://announcements.asx.com.au/asxpdf/20260225/pdf/06wq71j5jq4dtc.pdf',bytes=2184282)
ROOT=Path(__file__).resolve().parents[1]

def inspect_pdf(raw,opener=None):
    result=dict(pdf_open=False,extraction_allowed=None,pages=None,page_limit_exceeded=None,characters=None,
                character_limit_exceeded=None,first_character_limit_page=None,first_error='NONE')
    if not raw.startswith(b'%PDF-') or not 0<len(raw)<=MAX_BYTES:
        result['first_error']='PDF_SIGNATURE_OR_BOUND';return result
    if opener is None:
        import pdfplumber
        opener=pdfplumber.open
    try:
        with opener(BytesIO(raw),unicode_norm='NFKC') as doc:
            result['pdf_open']=True
            allowed=bool(doc.doc.is_extractable);pages=len(doc.pages)
            result.update(extraction_allowed=allowed,pages=pages,page_limit_exceeded=not 1<=pages<=MAX_PAGES)
            if not allowed:result['first_error']='PDF_EXTRACTION_FORBIDDEN';return result
            if result['page_limit_exceeded']:result['first_error']='PDF_PAGE_LIMIT';return result
            total=0
            for index,page in enumerate(doc.pages,1):
                words=page.dedupe_chars(tolerance=1).extract_words(x_tolerance=2,y_tolerance=3,keep_blank_chars=False)
                total+=sum(len(w['text']) for w in words)
                if total>MAX_CHARACTERS:
                    result.update(characters=total,character_limit_exceeded=True,first_character_limit_page=index,first_error='PDF_CHARACTER_LIMIT');return result
            result.update(characters=total,character_limit_exceeded=False)
    except Exception:result['first_error']='PDF_LIBRARY_OR_STRUCTURE'
    return result

def verify_bytes(raw):
    if len(raw)!=PROFILE['bytes'] or hashlib.sha256(raw).hexdigest()!=PROFILE['sha256']:raise ValueError('ARCHIVE_HASH')

def archive_receipt(transport):
    library=directories.REMOTE_SOURCE.split('\nif __name__=="__main__":')[0]
    archive=(ROOT/'scripts/fundamentals/archive_remote.py').read_text(encoding='utf-8').split("\nif __name__ == '__main__':")[0]
    source=library+'\n'+archive+'\nfrom datetime import datetime\n'+READ_SOURCE+'''
phase='INPUT'
try:
    raw,meta=read_existing(REQUEST)
    need(len(raw)==REQUEST['bytes'],'ORIGINAL_SIZE')
    need(meta['http_status']==200 and meta['content_type'].split(';')[0].strip().lower()=='application/pdf','ORIGINAL_HTTP_METADATA')
    print(json.dumps({'ok':True,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}))
except Exception:
    print(json.dumps({'ok':False,'phase':phase,'error':'ARCHIVE_VALIDATION'}));sys.exit(1)
'''
    bootstrap="import json,sys;p=json.loads(sys.stdin.read());REQUEST=p['request'];exec(compile(p['source'],'<read-only-archive>','exec'))"
    code,out,err,_=remote.remote_call(transport,shlex.join([directories.PYTHON,'-I','-B','-c',bootstrap]),json.dumps(dict(source=source,request=PROFILE)).encode(),timeout=60)
    if code or err or len(out)>2048:raise ValueError('ARCHIVE_VALIDATION')
    reply=json.loads(out)
    if reply!=dict(ok=True,sha256=PROFILE['sha256'],bytes=PROFILE['bytes']):raise ValueError('ARCHIVE_VALIDATION')

def load_pdf(transport,paramiko):
    archive_receipt(transport)
    # Remote no-follow checks precede and follow this fixed-path read. Local hash binds the bytes.
    path='/var/www/vhosts/web213.server10.configcenter.info/private/mosa2-collector/runs/'+PROFILE['execution']+'/response.body'
    with paramiko.SFTPClient.from_transport(transport) as sftp:
        attrs=sftp.lstat(path)
        if not stat.S_ISREG(attrs.st_mode) or (attrs.st_uid,attrs.st_gid,stat.S_IMODE(attrs.st_mode),attrs.st_size)!=(10317,1003,0o600,PROFILE['bytes']):raise ValueError('ARCHIVE_FILE_PROTECTION')
        with sftp.open(path,'rb') as stream:raw=stream.read(MAX_BYTES+1)
    verify_bytes(raw)
    archive_receipt(transport)
    return raw

def execute(env):
    result=dict(ok=False,archive_sha256='FAIL',provider_requests=0,db_accesses=0,archive_changes=0)
    phase='GUARDS'
    try:
        guard(env,AUTH)
        phase='SSH_ARCHIVE'
        import paramiko
        logging.getLogger('paramiko').disabled=True
        config=access.profile.configuration(env)
        with access.ssh_client(config,{},paramiko) as transport:raw=load_pdf(transport,paramiko)
        result['archive_sha256']='PASS';phase='PDF_DIAGNOSIS'
        logging.getLogger('pdfminer').disabled=True
        result.update(diagnosis=inspect_pdf(raw),ok=True)
    except Exception:result.update(phase=phase,error='DIAGNOSIS_PHASE_FAILED')
    return result

if __name__=='__main__':
    result=execute(os.environ);public=access.public_text(result,os.environ)
    if len(public.encode())>4096:public=json.dumps(dict(ok=False,error='RESULT_BOUND'))
    print(public);sys.exit(0 if result['ok'] else 1)
