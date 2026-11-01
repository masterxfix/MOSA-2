"""Appended to qualified private directory/archive functions; one exclusive marker only."""
AI_ONCE='fundamentals-ai-droneshield-20261101-01'
EXECUTIONS.add(AI_ONCE)
def reserve_ai(data):
    need(data['execution']==AI_ONCE and data['isin']=='AU000000DRO2' and data['model']=='gpt-6.1-sol'
         and data['workflow']=='.github/workflows/fundamentals-assessment-once.yml'
         and re.fullmatch('[0-9a-f]{64}',data['input_digest']) is not None,'AI_BINDING')
    measured=checked(data)
    token=json.dumps({k:data[k] for k in ('execution','commit','isin','model','workflow','input_digest')},sort_keys=True).encode()
    need(len(token)<=1024,'AI_MARKER_BOUND')
    os.umask(0o077)
    fd=checked_fd(os,ROOT+'/locks',base_identity=tuple(measured[BASE]))
    try:
        create_file(fd,AI_ONCE+'.consumed',token)
        raw=read_file(fd,AI_ONCE+'.consumed')
        need(raw==token,'AI_MARKER_READBACK')
        return dict(sha256=hashlib.sha256(raw).hexdigest(),reserved=True)
    finally:os.close(fd)
if __name__=='__main__':
    try:print(json.dumps(dict(ok=True,result=reserve_ai(json.loads(sys.stdin.read())))))
    except Exception:print(json.dumps(dict(ok=False,error_code='AI_MARKER_STOP_NO_RETRY')));sys.exit(1)
