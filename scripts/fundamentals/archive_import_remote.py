"""Appended to the reviewed in-place archive reader; no raw stdout or provider IO."""
APPLY_MARKER='fundamentals-zeiss-archive-import-20261101-01.consumed'
APPLY_AUTHORIZATION='MOSA2-ZEISS-ARCHIVE-IMPORT-20261101:'

def prepared_plan(data):
    global phase, archive_verified
    raw,metadata=read_existing(data)
    archive_verified=True
    phase='ADAPTER'
    need(metadata['http_status']==200 and metadata['content_type'].lower().startswith('text/html'),'HTTP_RESPONSE')
    plan=zeiss.parse(raw,metadata['observed_at'])
    plan.update(metadata=metadata,archive=dict(sha256=metadata['sha256'],bytes=len(raw),durable=True,
        storage_key=ROOT+'/runs/'+data['execution']+'/response.body'))
    encoded=json.dumps(plan,sort_keys=True,ensure_ascii=True).encode()
    need(len(encoded)<=45000,'PLAN_BOUND')
    return plan,hashlib.sha256(encoded).hexdigest()

def import_operation(data):
    global phase, archive_verified
    phase='AUTHORIZATION'
    archive_verified=False
    report=dict(ok=False,archive='FAIL')
    try:
        need(re.fullmatch('[0-9a-f]{40}',data['apply_commit']) is not None,'APPLY_COMMIT')
        need(data['authorization']==APPLY_AUTHORIZATION+data['apply_commit'],'APPLY_AUTHORIZATION')
        need(data['action'] in ('plan','reserve','verify'),'APPLY_ACTION')
        if data['action']=='verify':
            read_existing(data)
            return dict(ok=True,archive='PASS',phase='ARCHIVE_READBACK')
        plan,plan_hash=prepared_plan(data)
        report['archive']='PASS'
        if data['action']=='plan':
            return dict(ok=True,archive='PASS',phase='PLAN_READY',plan=plan,plan_sha256=plan_hash)
        phase='APPLY_MARKER'
        need(plan_hash==data['plan_sha256'],'PLAN_CHANGED')
        measured=checked(data)
        fd=checked_fd(os,ROOT+'/locks',base_identity=tuple(measured[BASE]))
        try:
            token=json.dumps(dict(apply_commit=data['apply_commit'],archive_commit=data['commit'],
                archive_sha256=data['sha256'],plan_sha256=plan_hash),sort_keys=True).encode()
            os.umask(0o077)
            create_file(fd,APPLY_MARKER,token)
            need(read_file(fd,APPLY_MARKER)==token,'APPLY_MARKER_READBACK')
        finally:os.close(fd)
        return dict(ok=True,archive='PASS',phase='APPLY_RESERVED')
    except Exception as exc:
        allowed=SAFE_CODES|ERRORS|{'APPLY_COMMIT','APPLY_AUTHORIZATION','APPLY_ACTION','PLAN_BOUND','PLAN_CHANGED','APPLY_MARKER_READBACK'}
        code=str(exc) if str(exc) in allowed else ('APPLY_ALREADY_CONSUMED' if isinstance(exc,FileExistsError) else
            'FILE_NOT_FOUND' if isinstance(exc,FileNotFoundError) else 'ACCESS_DENIED' if isinstance(exc,PermissionError) else
            'REMOTE_VALIDATION_FAILED')
        return dict(ok=False,phase=phase,error=code,archive='PASS' if archive_verified else 'FAIL')

if __name__=='__main__':
    result=import_operation(REQUEST)
    encoded=json.dumps(result)
    if len(encoded.encode())>49152:
        result=dict(ok=False,phase='PLAN_TRANSFER',error='PLAN_BOUND',archive='PASS');encoded=json.dumps(result)
    print(encoded)
    sys.exit(0 if result['ok'] else 1)
