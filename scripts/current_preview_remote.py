"""One fileless, SELECT-only snapshot through the existing pinned SSH access."""
import json
import logging
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'scripts'))
import collector_actions as access
import collector_db_locality as remote
import deploy_test_sftp as profile
from scripts.market_current import preview


def execute(env, paramiko):
    if env.get('GITHUB_RUN_ATTEMPT') != '1':
        return dict(real_data_checked=False, failure='FIRST_ATTEMPT_ONLY', business_writes=0, provider_requests=0)
    phase = 'EXISTING_SSH_ACCESS_UNAVAILABLE'
    try:
        config = profile.configuration(env)  # Only the existing SSH secrets, no writer DB secret.
        logging.getLogger('paramiko').disabled = True
        p = subprocess.run(['php', str(ROOT/'scripts/market_current/read_bundle.php')],
                           capture_output=True, text=True, check=True, timeout=10)
        if p.stderr:raise ValueError('bundle')
        wire = json.dumps(dict(source=p.stdout)).encode()
        if len(wire)>40000:raise ValueError('bundle size')
        with access.ssh_client(config, {}, paramiko) as transport:
            phase = 'EXISTING_PHP_EXEC_ACCESS_UNAVAILABLE'
            binary, _ = remote.capability(transport)
            # Exactly one inspection. No SFTP, installation, tunnel, writer password or retry.
            code, raw, errors, _ = remote.remote_call(transport, remote.command(binary, remote.BOOTSTRAP), wire, timeout=75)
        phase = 'READ_SNAPSHOT_UNAVAILABLE'
        if code or errors:raise ValueError('read process')
        reply = json.loads(raw)
        if reply.get('ok') is not True:
            allowed = {'READ_CONFIG_UNAVAILABLE','READ_CONFIG_UNSAFE','READ_CONFIG_REJECTED',
                       'READ_CONNECTION_UNAVAILABLE','READ_PRIVILEGES_REJECTED','READ_SNAPSHOT_REJECTED'}
            return dict(real_data_checked=False, failure=reply['failure'] if reply.get('failure') in allowed else phase,
                        business_writes=0, provider_requests=0)
        phase = 'SNAPSHOT_QUALIFICATION_FAILED'
        report = preview.snapshot_preview(reply['snapshot'])
        # Full private preview stays in memory; only operational decisions leave this process.
        return dict(real_data_checked=True, **preview.public_summary(report))
    except Exception:
        return dict(real_data_checked=False, failure=phase, business_writes=0, provider_requests=0)


if __name__ == '__main__':
    import paramiko
    result = execute(os.environ, paramiko)
    print(json.dumps(result, ensure_ascii=False))
    # An unavailable reader is an explicit allowed outcome, not a false preview PASS.
