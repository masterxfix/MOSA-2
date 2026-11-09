"""Controlled MOSA-2 testsite history jobs, using existing acquisition and persistence."""
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shlex
import sys
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import fundamentals_pilot_once as shared
from scripts.fundamentals import esef, history
from scripts.fundamentals_esef_once import download
from scripts.market_collector.http_transport import HttpGet, ReadOnlyHttpTransport

WORKFLOW = 'masterxfix/MOSA-2/.github/workflows/fundamentals-history.yml@refs/heads/main'
MAX_REPORTS = 8


def guard(env):
    required = {'GITHUB_REPOSITORY': 'masterxfix/MOSA-2', 'GITHUB_REF': 'refs/heads/main',
                'GITHUB_WORKFLOW_REF': WORKFLOW, 'GITHUB_RUN_ATTEMPT': '1'}
    if any(env.get(key) != value for key, value in required.items()):
        raise ValueError('WORKFLOW')
    sha = env.get('GITHUB_SHA', '')
    if not re.fullmatch('[a-f0-9]{40}', sha):
        raise ValueError('SHA')
    operation = env.get('HISTORY_OPERATION')
    event = env.get('GITHUB_EVENT_NAME')
    job_id = env.get('HISTORY_REQUEST_ID', '')
    if event == 'schedule' and env.get('HISTORY_ENABLED') == 'true':
        return 'process', None
    if (event != 'workflow_dispatch' or operation not in ('setup', 'process') or
        env.get('EXPECTED_COMMIT') != sha or
        (operation == 'process' and not re.fullmatch('[a-f0-9]{64}', job_id)) or
        (operation == 'setup' and job_id) or
        env.get('AUTHORIZATION') != f'MOSA2-HISTORY-{operation}:{sha}:{job_id}'):
        raise ValueError('AUTHORIZATION')
    return operation, job_id


def queue(transport, action, **data):
    library = shared.directories.REMOTE_SOURCE.split('\nif __name__=="__main__":')[0]
    source = library + '\n' + (history.ROOT / 'history_queue_remote.py').read_text(encoding='utf-8')
    cmd = shlex.join([shared.directories.PYTHON, '-I', '-B', '-c', source])
    code, out, err, _ = shared.remote.remote_call(
        transport, cmd, json.dumps(dict(data, action=action)).encode(), timeout=30)
    if code or err:
        raise ValueError('QUEUE')
    reply = json.loads(out)
    if reply.get('ok') is not True:
        raise ValueError('QUEUE')
    return reply['result']


def request_scope(job):
    isin = job['isin']
    start, end, kind = (job[k] for k in ('start', 'end', 'kind'))
    if (not re.fullmatch('[A-Z]{2}[A-Z0-9]{9}[0-9]', isin) or
        type(start) is not int or type(end) is not int or not 1900 <= start <= end <= date.today().year or
        end - start > 9 or kind not in ('fy', 'fq', 'both') or
        not re.fullmatch('[a-f0-9]{64}', job['id'])):
        raise ValueError('REQUEST')
    return {'start': start, 'end': end, 'kind': kind}


def qualify(report, identity, meta, item):
    if report.adapter is None:
        raw, response = download(report.profile, item)
        meta.update(response)
        return esef.parse(raw, meta, identity, report.profile), raw

    adapter = report.adapter
    mime = getattr(adapter, 'CONTENT_TYPE', 'text/html')
    transport = ReadOnlyHttpTransport(HttpGet(None, adapter.URL, (('Accept', mime), ('Accept-Encoding', 'identity'))),
                                      timeout=30, max_bytes=8 * 1024 * 1024)
    item['provider_requests'] = 1
    response = transport.fetch(None)
    raw = response.payload_bytes
    if response.http_status != 200 or response.content_type.split(';', 1)[0].strip().lower() != mime or not raw:
        raise ValueError('SOURCE_RESPONSE')
    meta.update(url=adapter.URL, request_started_at=transport.request_started_at, observed_at=response.collected_at,
                http_status=response.http_status, content_type=response.content_type, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    plan = shared._parse_adapter(adapter, raw, response, meta, identity)
    if report.profile.get('retention') == 'derived_evidence':
        builder = getattr(adapter, 'evidence', None) or shared.evidence
        compact, stored = builder(plan, meta, identity)
        plan.update(evidence_json=compact.decode('utf-8'), stored_evidence=stored)
    return plan, raw


def process(env, transport, port, job):
    scope = request_scope(job)
    identity = {'isin': job['isin'], 'name': job['name']}
    selected = {'identity': identity, 'preserve_assets': []}
    before, _ = shared.database(env, port, 'inspect', selected=selected, history_scope=scope)
    reports, uncovered = history.candidates(scope, history.catalog(job['isin']), history.inventory(before['inventory']))
    result = {'status': 'complete', 'inserted': 0, 'uncovered_periods': len(uncovered), 'reports': []}
    for report, missing in reports:
        if not missing:
            continue
        if len(result['reports']) >= MAX_REPORTS:
            result['uncovered_periods'] += 1
            continue
        item = {'period': report.period, 'provider_requests': 0}
        result['reports'].append(item)
        execution = 'fundamentals-history-' + hashlib.sha256(f"{job['isin']}:{report.key}".encode()).hexdigest()[:32]
        selected['execution'] = execution
        meta = {'execution': execution, 'commit': env['GITHUB_SHA']}
        stage = 'RESERVE'
        try:
            reserved = shared.archive(transport, 'reserve', env, selected=selected)
            stage = 'QUALIFY'
            plan, raw = qualify(report, identity, meta, item)
            item.update(source_url=meta['url'], source_sha256=meta['sha256'], execution=execution)
            # Recheck after network access. The generic writer also binds the
            # complete baseline and rejects drift immediately before commit.
            stage = 'RECHECK'
            before, _ = shared.database(env, port, 'inspect', selected=selected, history_scope=scope)
            stored = history.inventory(before['inventory'])
            plan = history.select_facts(plan, report, stored, scope)
            item['remaining_metrics'] = sorted(missing - ({r['metric_key'] for r in plan['observations']} if plan else set()))
            if item['remaining_metrics']:
                result['uncovered_periods'] += 1
            if plan is None:
                continue
            stage = 'ARCHIVE'
            evidence = plan.get('stored_evidence')
            payload = plan['evidence_json'].encode('utf-8') if evidence else raw
            meta_storage = evidence or meta
            shared.archive(transport, 'archive', env, reserved['identity'], meta_storage, payload, selected=selected)
            plan['archive'] = shared.archive(transport, 'verify', env, reserved['identity'], meta_storage, selected=selected)
            plan['metadata'] = meta
            stage = 'APPLY'
            receipt, _ = shared.database(env, port, 'apply', selected=selected, history_scope=scope,
                baseline=before['baseline'], protected=before['protected'], asset_id=before['asset_id'], plan=plan)
            stage = 'FINAL_ARCHIVE'
            shared.archive(transport, 'verify', env, reserved['identity'], meta_storage, selected=selected)
            if receipt['readback'] != 'PASS' or receipt['current'] != 0 or receipt['current_updates'] != 0:
                raise ValueError('RECEIPT')
            result['inserted'] += receipt['observations']
            item['readback'] = receipt
        except Exception as error:
            item['stage'] = stage
            if isinstance(error, RuntimeError) and str(error) in {'INPUT','IDENTITY','SCHEMA6','PLAN','TRANSACTION','COMMIT','INDEPENDENT_READBACK'}:
                item['database_stage'] = str(error)
            if stage in ('APPLY', 'FINAL_ARCHIVE'):
                result['status'] = 'unknown'
            elif str(error) == 'HISTORY_CONFLICT':
                result['status'] = 'conflict'
            else:
                result['status'] = 'failed'
            return result
    if result['uncovered_periods']:
        result['status'] = 'partial' if result['inserted'] else 'unavailable'
    return result


def execute(env):
    operation, job_id = guard(env)
    shared.no_other_runs(env)
    import paramiko
    logging.getLogger('paramiko').disabled = True
    with shared.access.ssh_client(shared.access.configuration(env), {}, paramiko) as transport:
        if operation == 'setup':
            return queue(transport, 'setup')
        job = queue(transport, 'claim', id=job_id, run=env['GITHUB_RUN_ID'])['job']
        if job is None:
            return {'status': 'empty'}
        try:
            with shared.access.tunnel(transport, {}) as port:
                result = process(env, transport, port, job)
        except Exception as error:
            result = {'status': 'conflict' if str(error) == 'HISTORY_CONFLICT' else 'failed', 'inserted': 0}
        queue(transport, 'finish', id=job['id'], run=env['GITHUB_RUN_ID'],
              result={k: result[k] for k in ('status', 'inserted')})
        return dict(result, request_id=job['id'], isin=job['isin'], scope=request_scope(job))


if __name__ == '__main__':
    try:
        result = execute(os.environ)
    except Exception:
        result = {'status': 'failed', 'stage': 'GUARDS_OR_QUEUE'}
    print(shared.access.public_text(result, os.environ))
    sys.exit(1 if result.get('status') in ('conflict', 'unknown', 'failed') else 0)
