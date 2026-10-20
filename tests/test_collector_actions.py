"""Offline transport/secrecy/configuration and generic acceptance integration checks."""
from dataclasses import asdict
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import collector_actions as runner
import test_market_onboarding as onboarding
import test_market_collector_v1 as fixtures
from scripts.market_collector import live_bridge
import test_market_runtime as runtime_fixture


def environment():
    return {**{runner.profile.PREFIX+k: v for k, v in runner.profile.EXPECTED.items()},
            'MOSA_TEST_SFTP_PASSWORD': 'synthetic-ssh-value',
            'MOSA_TEST_SFTP_HOST_KEY_SHA256': 'SHA256:'+'A'*43,
            'MOSA_TEST_DB_PASSWORD': 'synthetic-db-value', 'PATH': os.environ['PATH']}


class TransportTests(unittest.TestCase):
    def test_each_missing_secret_stops_before_ssh_and_names_only_missing_key(self):
        for name in runner.SECRETS:
            env = environment(); del env[name]
            with patch.object(runner, 'ssh_client') as ssh:
                result = runner.execute(env)
            ssh.assert_not_called()
            self.assertEqual(result['failure'], 'MISSING_SECRET: '+name)
            self.assertIsNone(result['acceptance'])
            self.assertFalse(result['ok'])

    def test_fixed_profile_rejects_every_changed_variable(self):
        for suffix in runner.profile.EXPECTED:
            env = environment(); env[runner.profile.PREFIX+suffix] = 'other'
            with self.assertRaises(runner.ConfigurationError): runner.configuration(env)

    def test_invalid_fingerprint_format_rejected(self):
        env = environment(); env[runner.SECRETS[1]] = 'invalid'
        with self.assertRaises(runner.ConfigurationError): runner.configuration(env)

    def test_host_key_verification_reuses_shared_function_before_auth(self):
        client = MagicMock(); client.get_transport.return_value = 'transport'
        api = SimpleNamespace(SSHClient=lambda: client, MissingHostKeyPolicy=object)
        status = {}
        def connect(*args, **kwargs):
            self.assertFalse(kwargs['allow_agent']); self.assertFalse(kwargs['look_for_keys'])
            policy = client.set_missing_host_key_policy.call_args.args[0]
            policy.missing_host_key(client, 'synthetic-host', SimpleNamespace(asbytes=lambda: b'key'))
        client.connect.side_effect = connect
        with patch.object(runner.shared, 'verify_fingerprint') as verify:
            with runner.ssh_client(runner.configuration(environment()), status, api) as transport:
                self.assertEqual(transport, 'transport')
            verify.assert_called_once_with(b'key', environment()[runner.SECRETS[1]])
        self.assertEqual(status, dict(host_key='PASS', ssh='PASS'))
        client.close.assert_called_once()
        client.exec_command.assert_not_called(); client.open_sftp.assert_not_called()

    def test_mismatched_key_aborts_and_closes_before_runner(self):
        client = MagicMock(); api = SimpleNamespace(SSHClient=lambda: client, MissingHostKeyPolicy=object)
        def connect(*args, **kwargs):
            client.set_missing_host_key_policy.call_args.args[0].missing_host_key(client, '', SimpleNamespace(asbytes=lambda: b'bad'))
        client.connect.side_effect = connect
        with patch.object(runner.shared, 'verify_fingerprint', side_effect=ValueError('key mismatch')):
            with self.assertRaises(ValueError):
                with runner.ssh_client(runner.configuration(environment()), {}, api): self.fail('accepted unknown key')
        client.close.assert_called_once(); client.get_transport.assert_not_called()

    def test_forwarding_denial_stops_before_collector(self):
        transport = MagicMock(); transport.open_channel.side_effect = OSError('synthetic secret')
        with self.assertRaises(OSError):
            with runner.tunnel(transport, {}): self.fail('tunnel accepted')
        self.assertEqual(transport.open_channel.call_args.args[:2], ('direct-tcpip', ('127.0.0.1', 3307)))

    def test_tunnel_binds_only_ephemeral_loopback_and_closes(self):
        transport = MagicMock(); status = {}
        with runner.tunnel(transport, status) as port:
            self.assertGreater(port, 0)
        self.assertEqual(status['db_tunnel'], 'PASS')
        transport.open_channel.return_value.close.assert_called_once()

    def test_php_password_stdin_only_and_child_env_stripped(self):
        env = environment(); env['GITHUB_TOKEN'] = 'synthetic-github'
        mock = MagicMock(return_value=SimpleNamespace(returncode=0, stderr='', stdout='{"ok":false}'))
        runner.invoke_acceptance(45678, '/synthetic/private', env, run=mock)
        args, kw = mock.call_args
        self.assertEqual(args[0], ['php', str(ROOT/'scripts/market_collector/actions_acceptance.php')])
        wire = json.loads(kw['input']); self.assertEqual(wire['password'], env['MOSA_TEST_DB_PASSWORD'])
        self.assertEqual(wire['config']['db_port'], 45678)
        for name in (*runner.SECRETS, 'GITHUB_TOKEN'): self.assertNotIn(name, kw['env'])
        self.assertNotIn(env['MOSA_TEST_DB_PASSWORD'], repr(args))

    def test_subprocess_secret_stderr_never_published(self):
        mock = MagicMock(return_value=SimpleNamespace(returncode=1, stderr=environment()[runner.SECRETS[2]], stdout=''))
        with self.assertRaisesRegex(RuntimeError, '^COLLECTOR_PROCESS_FAILED$'):
            runner.invoke_acceptance(45678, '/synthetic/private', environment(), run=mock)

    def test_secret_contaminated_public_result_is_discarded(self):
        for value in ['line1\nline2"\\value', environment()[runner.SECRETS[2]]]:
            env = environment(); env[runner.SECRETS[2]] = value
            result = runner.public_text(dict(ok=True, data=value), env)
            self.assertNotIn(value, result); self.assertFalse(json.loads(result)['ok'])
            self.assertEqual(json.loads(result)['failure'], 'SECRET_OUTPUT_BLOCKED')

    def test_exception_text_is_not_logged(self):
        with patch.object(runner, 'ssh_client', side_effect=RuntimeError(environment()[runner.SECRETS[0]])):
            result = runner.execute(environment(), object())
        self.assertNotIn(environment()[runner.SECRETS[0]], json.dumps(result))
        self.assertEqual(result['failure_type'], 'RuntimeError')

    def test_workflow_manual_only_no_artifact_no_deploy(self):
        source = (ROOT/'.github/workflows/collector-live-test.yml').read_text()
        for forbidden in ['  push:', '  schedule:', 'upload-artifact', 'deploy_sftp.py deploy', 'workflow_run:']:
            self.assertNotIn(forbidden, source)
        self.assertIn('github.run_attempt == 1', source)
        self.assertIn('ref: ${{ github.sha }}', source)
        self.assertIn('test "$EXPECTED_COMMIT" = "$GITHUB_SHA"', source)
        for name in runner.SECRETS: self.assertIn('secrets.'+name, source)

    def test_runtime_endpoint_validation_before_pdo(self):
        # Valid defaults preserved; malicious DSN fragments, nonloopback and invalid ports fail before PDO.
        for host, port in [('localhost', 3307), ('127.0.0.1;dbname=other', 3307), ('127.0.0.1', 0), ('127.0.0.1', 65536)]:
            code = "require 'scripts/phase2/postcheck.php'; try { Mosa2\\Phase2\\connection('synthetic',"+json.dumps(host)+","+str(port)+"); } catch(Throwable $e) { echo $e->getMessage(); }"
            result = subprocess.check_output(['php', '-r', code], cwd=ROOT, text=True)
            self.assertEqual(result, 'runtime_endpoint')

    def test_shared_descriptor_matches_historical_protocol(self):
        result = subprocess.run(['php', str(ROOT/'scripts/market_collector/frankfurt_request.php')],
            input=json.dumps(dict(isin='US0378331005', instant='2026-01-01 12:00:00 UTC')), text=True, capture_output=True, check=True)
        self.assertEqual(result.stderr, '')
        descriptor = json.loads(result.stdout)
        self.assertEqual(descriptor['url'], 'https://api.live.deutsche-boerse.com/v1/data/price_information/single?isin=US0378331005&mic=XFRA')
        self.assertEqual(descriptor['series'], 'snapshot')
        self.assertEqual(descriptor['role'], 'price_information')
        self.assertEqual(len(descriptor['headers']), 5)


class QualificationTests(unittest.TestCase):
    def test_existing_adapter_normalizer_and_unit_contract_qualify_without_database(self):
        f = fixtures.FrankfurtCollectorTests(); f.setUp()
        acquired = dict(provider_key=f.adapter.provider_key, instrument=f.request.instrument,
            request_key=f.request.request_key, requested_at=f.request.requested_at,
            adapter_module='scripts.market_collector.boerse_frankfurt', adapter_class='FrankfurtSnapshotV1',
            response=live_bridge.transport(asdict(f.response)))
        binding = dict(id='1', asset_id='7', source_id='9', route_revision='1', **onboarding.UNITS)
        proof = live_bridge.run(dict(action='qualify', acquired=acquired, route=binding))
        self.assertTrue(proof['ok']); self.assertEqual(proof['scope'], 'NON_PERSISTENT_TEST_ROUTE')
        self.assertEqual(proof['currency'], 'EUR'); self.assertEqual(proof['quote_unit_version'], '1')
        damaged = json.loads(json.dumps(acquired)); damaged['instrument'] = 'US5949181045'
        with self.assertRaises(ValueError): live_bridge.run(dict(action='qualify', acquired=damaged, route=binding))


class AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime_fixture.RuntimeTests.setUpClass()

    def call(self, **extra):
        inputs = runtime_fixture.RuntimeTests().batch_inputs(5)
        state, entries, acquired = inputs['state'], inputs['batch'], inputs['acquired_batch']
        state['m2_sources'][0]['source_key'] = 'provider:boerse_frankfurt_api'
        scope = [dict(name=e['manifest']['identity']['display_name'], isin=e['manifest']['instrument'], qualify=i<3) for i,e in enumerate(entries)]
        routes = []
        for i, entry in enumerate(entries):
            m = entry['manifest']; value = m['instrument']
            evidence = dict(sample_id='SYNTH', source_reference='synthetic:frankfurt', family='frankfurt_snapshot',
                row=dict(isin=value, provider_key='boerse_frankfurt_api', venue_key='boerse_frankfurt', currency='EUR', quote_variant=None, series='snapshot', observation_kind='market_quote'),
                proof=dict(external_identity=dict(isin=value, venue='boerse_frankfurt'), route_reference='synthetic:phase3d'))
            q = dict(asset_id=str(100+i), source_id=state['m2_sources'][0]['id'], route_type='quote', priority=0, enabled=0, evidence=evidence)
            row = onboarding.call(action='route', routes=[], qualified=q, units=onboarding.UNITS)['result']['row']|dict(id=str(10+i))
            if i==1:
                row.update({k:None for k in onboarding.UNITS}); row['enabled']='1'
            if i in (1,3,4): routes.append(row)
        state['m2_asset_source_routes'] = routes
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary).resolve(); private=base/'private'; public=base/'web'; private.mkdir(); public.mkdir()
            data=dict(action='acceptance', state=state, scope=scope, private_root=str(private).replace('\\','/'),
                config=runtime_fixture.RuntimeTests.config|dict(state_contract=dict(schema_version=4, allow_current=True), public_root=str(public).replace('\\','/')),
                acquired_by_isin={s['isin']:a for s,a in zip(scope, acquired)})|extra
            result=subprocess.run(['php',str(ROOT/'tests/market_runtime_fixture.php')],input=json.dumps(data),text=True,capture_output=True,check=True)
            self.assertEqual(result.stderr,'')
            try: return json.loads(result.stdout),state
            except ValueError: self.fail(result.stdout[:1200])

    def test_full_five_asset_acceptance_three_qualifications_and_one_final_batch(self):
        result,before=self.call(); report=result['reports'][0]
        self.assertTrue(report['ok'],report)
        self.assertEqual(report['preparation_provider_requests'],3)
        self.assertEqual(result['providers'],8)
        self.assertEqual(report['batch']['overall_status'],'COMPLETE')
        for field in ['started_count','completed_count','committed_count']: self.assertEqual(report['batch'][field],5)
        for item in report['batch']['item_results']:
            self.assertEqual(item['readback'],'PASS'); self.assertEqual(item['replay'],'DUPLICATE_UNCHANGED')
        self.assertEqual(report['catalog_route_deltas']['m2_asset_source_routes'],3)
        self.assertEqual(report['observation_delta'],5)
        self.assertEqual(report['current_unchanged'],'PASS'); self.assertEqual(report['bars_unchanged'],'PASS')
        self.assertEqual(report['unexpected_writes'],'PASS')
        for table in ['m2_entities','m2_assets','m2_asset_identifiers','m2_sources']:
            self.assertEqual(result['state'][table],before[table])
        for route in before['m2_asset_source_routes']: self.assertIn(route,result['state']['m2_asset_source_routes'])

    def test_qualification_failure_stops_without_onboarding_or_final_requests(self):
        result,before=self.call(fail_provider=2); report=result['reports'][0]
        self.assertFalse(report['ok']); self.assertEqual(report['stage'],'qualification')
        self.assertIsNone(report['batch']); self.assertEqual(result['providers'],2)
        self.assertEqual(report['preparation_provider_requests'],2)
        self.assertEqual(report['unexpected_writes'],'PASS')
        self.assertEqual(result['state']['m2_asset_source_routes'],before['m2_asset_source_routes'])
        self.assertEqual(result['state']['m2_market_observations'],[])

    def test_final_failure_retains_two_commits_and_does_not_retry(self):
        result,before=self.call(fail_provider=6); report=result['reports'][0]
        self.assertFalse(report['ok']); self.assertEqual(result['providers'],6)
        self.assertEqual(report['batch']['overall_status'],'PARTIAL_FAILED')
        self.assertEqual(report['batch']['committed_count'],2)
        self.assertEqual(report['batch']['not_started_count'],2)
        self.assertEqual(len(result['state']['m2_market_observations']),2)
        self.assertEqual(report['unexpected_writes'],'PASS')

    def test_authentication_and_ledger_failure_prevent_all_provider_access(self):
        for fault in [dict(fault='authentication'),dict(bad_ledger=True)]:
            result,_=self.call(**fault); report=result['reports'][0]
            self.assertFalse(report['ok']); self.assertEqual(result['providers'],0)
            self.assertEqual(report['preparation_provider_requests'],0)
            self.assertIsNone(report['batch'])


if __name__ == '__main__': unittest.main()
