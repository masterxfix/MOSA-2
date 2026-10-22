"""Pure bounded/authentication failures; no database or transport is opened."""
import base64,copy,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from scripts import database_backup as b

class BackupProtocolTests(unittest.TestCase):
    def test_hosting_mode_and_arbitrary_targets_are_not_available(self):
        with patch.dict(os.environ,{},clear=True),self.assertRaisesRegex(b.Rejected,'ISOLATED_BACKUP_MODE_REQUIRED'):
            b.IsolatedBackup(lambda:None,lambda:None,'a'*40)
        self.assertNotIn('h29077_mosa2_test',b.TARGETS)
        self.assertFalse(hasattr(b,'main'))
    def test_canonical_exact_types(self):
        from datetime import datetime
        from decimal import Decimal
        x=[b.value(bytes(range(32))),b.value(Decimal('123456789012345678.1234567890')),b.value(datetime(2026,1,1,1,2,3,123456))]
        self.assertEqual(x[1],{'decimal':'123456789012345678.1234567890'})
        self.assertEqual(x[2],{'datetime6':'2026-01-01 01:02:03.123456'})
        self.assertEqual(base64.b64decode(x[0]['binary']),bytes(range(32)))
        with self.assertRaises(b.Rejected):b.value(1.5)
        metadata={'Table':'synthetic','Create Table':'CREATE TABLE synthetic'}
        self.assertEqual(list(b.decode(b.state_bytes(metadata))),list(metadata))
    def test_process_failures_are_bounded_and_do_not_disclose_diagnostics(self):
        for code,seconds,limit in [('import sys;sys.stderr.write("PRIVATE SQL PASSWORD");sys.exit(1)',1,1000),
            ('import time;time.sleep(1)',.03,1000),('print("x"*10000)',1,32)]:
            with self.assertRaises(b.Rejected) as e:b.command([sys.executable,'-c',code],seconds=seconds,limit=limit)
            self.assertNotIn('PRIVATE',str(e.exception));self.assertNotIn('PASSWORD',str(e.exception))
        for code,expected in [(1064,'PROCESS_SQL_FAILED'),(2013,'PROCESS_CONNECTION_LOST')]:
            program=f'import sys;sys.stderr.write("ERROR {code} (HY000): PRIVATE SQL");sys.exit(1)'
            with self.assertRaisesRegex(b.Rejected,expected):b.command([sys.executable,'-c',program])
    def test_file_limits_modes_links_and_missing_material_fail_before_decryption(self):
        key=Ed25519PrivateKey.generate()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);root.chmod(0o700)
            for name in ['backup.sealed.json','manifest.json']:(root/name).write_bytes(b'{}');(root/name).chmod(0o600)
            with self.assertRaises(b.Rejected):b.unseal(root,'SYNTHETIC',key.public_key(),commit='a'*40,server_uuid='b'*36)
            with patch.object(b,'FILE_LIMIT',1),self.assertRaisesRegex(b.Rejected,'BACKUP_SIZE_LIMIT'):
                b.unseal(root,'SYNTHETIC',key.public_key(),commit='a'*40,server_uuid='b'*36)

if __name__=='__main__':unittest.main()
