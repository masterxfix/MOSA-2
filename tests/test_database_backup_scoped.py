"""Focused recovery/gating tests, no DB, SSH, provider, password prompt or live export."""
import base64,copy,json,os,tempfile,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from scripts import database_backup as b
from scripts import database_backup_scoped as s
from scripts import database_backup_once as once

class ScopedTests(unittest.TestCase):
    def setUp(self):
        self.keytext=os.urandom(32).hex();self.password,self.key=s.recovery(self.keytext)
        now=int(time.time())
        self.claim=dict(purpose='MOSA2_SCHEMA4_BACKUP',database=b.SOURCE,commit='a'*40,
            all_test_writers_stopped=True,ddl_prohibited=True,issued_at=now,expires_at=now+900,run_id='synthetic-scoped-proof')
        self.document=self.signed(self.claim)
    def signed(self,claim):
        return dict(claim=claim,signature=base64.b64encode(self.key.sign(b.canonical(claim))).decode())
    def test_recovery_is_required_independent_and_never_falls_back_to_password(self):
        for key in ('',None,'password','f'*64):
            with self.assertRaises(b.Rejected):s.recovery(key)
        with tempfile.TemporaryDirectory() as tmp:
            env=dict(GITHUB_ACTIONS='true',GITHUB_RUN_ATTEMPT='1',GITHUB_SHA='a'*40,RUNNER_TEMP=tmp,
                MOSA_TEST_SFTP_PASSWORD='PRIVATE_PASSWORD',MOSA_TEST_DB_PASSWORD='PRIVATE_PASSWORD')
            factory=Mock(side_effect=AssertionError('not allowed'))
            with self.assertRaisesRegex(b.Rejected,'RECOVERY_KEY_REQUIRED'):
                once.run(env,dict(authorization='MOSA2-DB-BACKUP-ONCE:'+'a'*40),factory)
            factory.assert_not_called()
    def test_unsigned_expired_wrong_schema_and_uncontrolled_writers_block_before_source(self):
        self.assertEqual(s.lease(self.document,self.key.public_key(),'a'*40),self.claim)
        for change in (dict(expires_at=self.claim['issued_at']-1),dict(database='other'),
                       dict(all_test_writers_stopped=False),dict(ddl_prohibited=False),dict(commit='b'*40)):
            claim=dict(self.claim,**change)
            with self.assertRaises(b.Rejected):s.lease(self.signed(claim),self.key.public_key(),'a'*40)
        with self.assertRaises(b.Rejected):s.lease({'claim':self.claim,'signature':'bad'},self.key.public_key(),'a'*40)
    def test_resource_retention_missing_key_and_replay_guards_precede_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);root.chmod(0o700)
            for kwargs in (dict(storage_confirmed=False,retention_days=7),
                           dict(storage_confirmed=True,retention_days=8),
                           dict(storage_confirmed=True,retention_days=7,free_bytes=0)):
                with self.assertRaises(b.Rejected):
                    s.pre_export(root,self.keytext,self.document,'a'*40,**kwargs)
            s.pre_export(root,self.keytext,self.document,'a'*40,storage_confirmed=True,retention_days=7)
            (root/'export.claim').write_bytes(b'claim')
            source=Mock()
            with self.assertRaises(b.Rejected):
                s.export(source,root,self.keytext,self.document,'a'*40,storage_confirmed=True,retention_days=7)
            source.permissions.assert_not_called();source.dump.assert_not_called()
    def test_credentials_stay_out_of_argv_and_environment_and_flags_are_bounded(self):
        wire=s.client_input(3309,'PRIVATE_"\\PASSWORD')
        self.assertIn(b'user=h29077_mosa2_test',wire);self.assertIn(b'password=',wire)
        for secret in ('','x\npassword','x\x00password'):
            with self.assertRaises(b.Rejected):s.client_input(3309,secret)
        self.assertIn('--skip-routines',s.FLAGS);self.assertIn('--events',s.FLAGS);self.assertIn('--triggers',s.FLAGS)
        self.assertFalse(any('flush' in v or 'all-databases' in v or v=='--routines' for v in s.FLAGS))
    def test_server_identity_mapping_never_discards_data_or_schema_facts(self):
        sql='SELECT DATABASE() AS db,VERSION() AS version,@@port AS port,@@foreign_key_checks AS fk_checks'
        expected=dict(rows={'synthetic':[{'x':{'decimal':'1.0000000000'}}]},evidence=dict(
            properties=dict(version='8.0.26-16',port='3307',db=b.SOURCE,fk_checks='1'),
            inventory=[dict(sql=sql,args=[],rows=[dict(version='8.0.26-16',port='3307',db=b.SOURCE,fk_checks='1')])]))
        actual=copy.deepcopy(expected);actual['evidence']['properties'].update(version='8.0.46',port='3306')
        actual['evidence']['inventory'][0]['rows'][0].update(version='8.0.46',port='3306')
        self.assertEqual(b.external_comparison(actual,expected,'8.0.46'),expected)
        actual['rows']['synthetic'][0]['x']['decimal']='2.0000000000'
        self.assertNotEqual(b.external_comparison(actual,expected,'8.0.46'),expected)
        with self.assertRaises(b.Rejected):s.restore(object(),'/missing',self.keytext,'b'*36,'h29077_mosa2_test')
    def test_schema_object_visibility_and_writer_preconditions_fail_closed(self):
        report=dict(status='BACKUP_PERMISSIONS_INSPECTED',database_identity='PASS',read_only_confirmed=True,
            complete_object_visibility='JA',rights={r:True for r in ('SELECT','SHOW VIEW','TRIGGER','EVENT')},
            objects={'ROUTINE':{'visible_count':0}},schema6_prepare=dict(status='SCHEMA6_PREPARE_INVENTORY_PASS',
                schema_version=4,table_count=17,exact_structure='PASS',ledger_checksums='PASS',all_innodb=True,
                enabled_jobs='0',running_jobs='0',other_schema_sessions_visible=0,named_locks_in_use={}))
        s.prerequisites(report)
        for section,key,val in [('schema6_prepare','all_innodb',False),('schema6_prepare','enabled_jobs','1'),
                                 ('rights','EVENT',False),('schema6_prepare','table_count',26)]:
            bad=copy.deepcopy(report);bad[section][key]=val
            with self.assertRaises(b.Rejected):s.prerequisites(bad)
        bad=copy.deepcopy(report);bad['objects']['ROUTINE']['visible_count']=1
        with self.assertRaises(b.Rejected):s.prerequisites(bad)
if __name__=='__main__':unittest.main()
