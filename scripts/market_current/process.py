"""Bounded one-shot process tree and fail-closed, allowlisted outcome protocol."""
import json
import os
import signal
import subprocess
import time

PHASES = {'PREFLIGHT', 'TRANSACTION_BEGIN', 'TRANSACTION_ACTIVE', 'COMMIT_ATTEMPT',
          'COMMIT_CONFIRMED', 'ROLLBACK', 'READBACK', 'READBACK_CONFIRMED', 'REPLAY',
          'REPLAY_CONFIRMED', 'COMPLETE'}
STATES = {'NOT_ATTEMPTED', 'UNKNOWN', 'CONFIRMED'}
CAUSES = {'NONE', 'PHASE_TIMEOUT', 'PLANNER_TIMEOUT', 'TRANSACTION_ERROR',
          'POST_COMMIT_ERROR', 'PREFLIGHT_OR_TRANSACTION_ERROR'}
SUCCESS = 'CURRENT_COMMITTED_READBACK_AND_REPLAY_PASS'
ABORT_CAUSES = {'PROCESS_TIMEOUT', 'MISSING_FINAL', 'INVALID_PROTOCOL', 'PROCESS_EXIT',
                'PROCESS_STDERR', 'PROCESS_IO_ERROR', 'TRANSPORT_ERROR', 'PROCESS_ERROR'}


def public_event(event):
    """Reject malformed records; never copy exception text or arbitrary child fields."""
    if (event.get('phase') not in PHASES or event.get('commit') not in STATES
            or event.get('rollback') not in STATES or event.get('cause') not in CAUSES):
        raise ValueError('protocol')
    keys = ('transaction_started', 'write_attempted', 'readback_confirmed', 'replay_unchanged')
    if any(type(event.get(k)) is not bool for k in keys):
        raise ValueError('protocol')
    times = event.get('phase_ms')
    if (not isinstance(times, dict) or set(times) - PHASES
            or any(type(v) is not int or not 0 <= v <= 300000 for v in times.values())
            or type(event.get('elapsed_ms')) is not int or not 0 <= event['elapsed_ms'] <= 300000):
        raise ValueError('protocol')
    return {k: event[k] for k in ('phase', 'commit', 'rollback', 'cause', 'elapsed_ms', 'phase_ms', *keys)}


def outcome(raw='', cause=None, returncode=0):
    if cause is not None and cause not in ABORT_CAUSES:
        cause = 'PROCESS_ERROR'
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8', errors='replace')
    last = {}; final = None
    try:
        if len(raw) > 1048576:
            raise ValueError('protocol')
        records = raw.splitlines()
        for line in records:
            event = json.loads(line)
            clean = public_event(event)
            if final is not None or event.get('kind') not in ('progress', 'final'):
                raise ValueError('protocol')
            last = clean
            if event['kind'] == 'final':
                final = event
        if final is None:
            cause = cause or 'MISSING_FINAL'
    except (ValueError, TypeError, AttributeError):
        cause = cause or 'INVALID_PROTOCOL'
    result = dict(status='OUTCOME_UNKNOWN', commit='UNKNOWN', rollback='UNKNOWN',
                  phase='PREFLIGHT', **{'readback_confirmed': False, 'replay_unchanged': False})
    result.update(last)
    if cause or returncode:
        result['cause'] = cause or 'PROCESS_EXIT'
        # A missing final record cannot prove non-commit or rollback, even if an older event did.
        if result['commit'] == 'CONFIRMED':
            result['status'] = 'ERROR_AFTER_COMMIT'
        else:
            result.update(status='OUTCOME_UNKNOWN', commit='UNKNOWN', rollback='UNKNOWN')
    elif final is not None:
        commit = result['commit']
        if commit == 'CONFIRMED':
            passed = (final.get('ok') is True and final.get('status') == SUCCESS
                      and result['phase'] == 'COMPLETE' and result['cause'] == 'NONE'
                      and result['readback_confirmed'] and result['replay_unchanged'])
            result['status'] = SUCCESS if passed else 'ERROR_AFTER_COMMIT'
        elif commit == 'UNKNOWN' or result['rollback'] == 'UNKNOWN':
            result['status'] = 'OUTCOME_UNKNOWN'
        elif result['rollback'] == 'CONFIRMED':
            result['status'] = 'ROLLBACK_CONFIRMED'
        elif result['transaction_started']:
            result['status'] = 'TRANSACTION_FAILED_BEFORE_COMMIT'
        else:
            result['status'] = 'PREFLIGHT_FAILED_NO_WRITE'
    result.update(retry_allowed=False, reconciliation='SEPARATE_READ_ONLY_EXISTING_RECONCILE')
    return result


def kill_tree(process):
    if os.name == 'posix':
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        try:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           capture_output=True, timeout=5, check=False)
        finally:
            if process.poll() is None:
                process.kill()


def run(command, request, env, cwd, seconds=240):
    start = time.monotonic()
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, env=env, cwd=cwd,
                               start_new_session=os.name == 'posix')
    cause = None
    try:
        out, err = process.communicate(json.dumps(request), timeout=seconds)
    except subprocess.TimeoutExpired as error:
        cause = 'PROCESS_TIMEOUT';out = error.stdout or ''
        kill_tree(process)
        try:
            out, _ = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.stdout.close();process.stderr.close()
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
        err = ''
    except Exception:
        cause = 'PROCESS_IO_ERROR';out = '';err = ''
        kill_tree(process)
        try:
            out, _ = process.communicate(timeout=5)
        except Exception:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
    finally:
        # Also reap descendants after an ordinary parent exit (no inherited pipe hang).
        if os.name == 'posix':
            kill_tree(process)
    result = outcome(out, cause or ('PROCESS_STDERR' if err else None), process.returncode)
    result['process_ms'] = round((time.monotonic() - start) * 1000)
    return result
