"""Web reader deployment closure and bounded native Current contract."""
import hashlib,json,subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class CurrentWebTests(unittest.TestCase):
    def fixture(self,case='valid'):
        p=subprocess.run(['php',str(ROOT/'tests/fixtures/current_web.php'),str(ROOT),case],capture_output=True,text=True,check=True)
        self.assertEqual(p.stderr,'');return json.loads(p.stdout)
    def test_five_resolved_scope_ignores_legacy_numeric_private_scope(self):
        r=self.fixture();self.assertEqual(r['status'],'ok');self.assertEqual([x['name'] for x in r['items']],['PNE AG','Carl Zeiss Meditec','DroneShield','BYD','Ubtech Robotics'])
        self.assertEqual(len(r['parameters']),15);self.assertTrue(all(x['status']=='stale' for x in r['items']))
        self.assertEqual(r['events'],['SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ','SET SESSION TRANSACTION READ ONLY','BEGIN','ROLLBACK'])
    def test_invalid_binding_source_units_or_provenance_fail_closed(self):
        for case in ('route','unit','source','provenance','current_price','current_source'):
            with self.subTest(case=case):
                r=self.fixture(case);self.assertEqual(r['status'],'error');self.assertEqual(r['events'][-1],'ROLLBACK')
    def test_current_missing_has_no_observation_fallback(self):
        r=self.fixture('missing');self.assertEqual(r['items'][0]['status'],'missing');self.assertNotIn('price',r['items'][0]);self.assertEqual(len(r['parameters']),14)
    def test_native_decimal_market_age_and_acquisition_time(self):
        r=self.fixture('decimal');self.assertEqual(r['items'][0]['price'],'123456789012345678.1234567890')
        self.assertEqual(r['items'][0]['market_at'],'2026-01-01 00:00:00.000000Z');self.assertEqual(r['items'][0]['observed_at'],'2026-01-01 00:00:03.000000Z')
        self.assertEqual(self.fixture('fresh')['items'][0]['status'],'stored')
    def test_web_dependencies_are_closed_and_have_no_cli_or_writer(self):
        files=['api/market.php','api/read_model.php','api/current_read.php','api/observations_read.php','api/qualified_scope.php',*[str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'api/market_core').iterdir()]]
        for name in (name for name in files if name.endswith('.php')):
            text=(ROOT/name).read_text()
            with self.subTest(name=name):
                for forbidden in ('proc_open','stream_get_contents(STDIN)','scripts/','docs/','new MarketFlow','function refresh(','MOSA_TEST_DB_PASSWORD','INSERT INTO','UPDATE m2_','DELETE FROM'):
                    self.assertNotIn(forbidden,text)
        catalog=(ROOT/'api/market_core/units.json').read_bytes()
        self.assertEqual(hashlib.sha256(catalog).hexdigest(),'0d9f196e4ccbd5e687292fa3d7a1a087b343ec81fb609b8b64b6454713246bbf')
        self.assertEqual(catalog,(ROOT/'docs/database/seeds/0001_market_units_v1.json').read_bytes().replace(b'\r\n',b'\n'))
    def test_frozen_v1_parser_primitives_match_web_core(self):
        original=(ROOT/'scripts/phase3c/market_flow.php').read_text()
        primitives=original[original.index('// Offline reference'):original.index('function normalizeObservation(')]
        self.assertTrue((ROOT/'api/market_core/primitives.php').read_text().endswith(primitives))
    def test_selected_web_package_requires_every_safe_dependency(self):
        import sys
        sys.path.insert(0,str(ROOT/'scripts'));import deploy_test_sftp as deploy
        from unittest.mock import patch
        files=[(name,b'synthetic') for name in deploy.CURRENT_WEB_PACKAGE]
        with patch.object(deploy.shared,'web_files',return_value=files):
            with self.assertRaises(ValueError):deploy.selected_files('["api/read_model.php"]')
            self.assertEqual(len(deploy.selected_files(json.dumps(list(deploy.CURRENT_WEB_PACKAGE)))),8)
    def test_encrypted_backup_roundtrip_uses_existing_secret_and_no_plaintext_artifact(self):
        import os,sys,tempfile,base64
        from unittest.mock import patch
        sys.path.insert(0,str(ROOT/'scripts'));import deploy_test_sftp as deploy
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'RUNNER_TEMP':folder}):
            before={'index.html':'synthetic-hash'};files={'index.html':'c3ludGhldGljLW9sZC13ZWI='}
            deploy.persist_backup(before,files,'synthetic-existing-secret')
            sealed=(Path(folder)/'mosa2-web-backup.sealed.json').read_text();self.assertNotIn(files['index.html'],sealed)
            e=json.loads(sealed);context=e['context'].encode()
            key=HKDF(algorithm=hashes.SHA256(),length=32,salt=base64.b64decode(e['salt']),info=context).derive(b'synthetic-existing-secret')
            payload=AESGCM(key).decrypt(base64.b64decode(e['nonce']),base64.b64decode(e['ciphertext']),context)
            self.assertEqual(json.loads(payload),dict(before=before,files=files))

    def test_backup_only_explicit_files_before_overwrite(self):
        import sys
        sys.path.insert(0,str(ROOT/'scripts'));import deploy_test_sftp as deploy
        import test_deploy_testsite as fixture
        fake=fixture.ScopedSFTP();import stat
        fake.nodes[deploy.shared.TEST_ROOT+'/index.html']=stat.S_IFREG|0o644;fake.contents[deploy.shared.TEST_ROOT+'/index.html']=b'old MOSA'
        before,contents=deploy.backup_files(fake,[('index.html',b'new MOSA'),('new.html',b'new')])
        self.assertEqual(before['index.html'],hashlib.sha256(b'old MOSA').hexdigest());self.assertIsNone(before['new.html'])
        self.assertEqual(fake.writes,[]);self.assertEqual(fake.contents[deploy.shared.TEST_ROOT+'/index.html'],b'old MOSA')
        self.assertIn('index.html',contents)
if __name__=='__main__':unittest.main()
