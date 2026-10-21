"""Bounded, read-only Python provisioning assessment safety tests."""
from contextlib import contextmanager
import ast
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import collector_python_options as probe


def php_case(found=False):
    prefix=probe.php_source().split("if(!defined('MOSA_PROVISION_LIBRARY_ONLY'))")[0]
    program=prefix+r'''
$executed=[];$checked=[];
$exists=static function($path)use(&$checked){$checked[]=$path;return $path==='/usr/bin/python3'||($GLOBALS['found']&&$path==='/usr/bin/python3.12');};
$child=static function($cmd,$stdin)use(&$executed){
    $executed[]=['command'=>$cmd,'input'=>$stdin];
    if($cmd[0]==='/usr/bin/python3')return ['result'=>['machine'=>'x86_64','libc'=>'glibc 2.17']];
    if($cmd[4]==='version-marker')return ['result'=>['version_info'=>[3,12,15],'version'=>'3.12.15']];
    return ['result'=>['ok'=>true]];
};
$result=provisionProbe(['platform_source'=>'platform-marker','version_source'=>'version-marker','module_source'=>'module-marker'],$exists,$child);
echo json_encode(['result'=>$result,'executed'=>$executed,'checked'=>$checked]);
'''
    program=program.replace("$executed=[];", "$GLOBALS['found']="+('true' if found else 'false')+";$executed=[];",1)
    p=subprocess.run(['php','-d','display_errors=0','-d','log_errors=0','-r',program],
                     text=True,capture_output=True,check=True)
    if p.stderr:
        raise AssertionError('fixture stderr')
    return json.loads(p.stdout)


class PythonOptionsTests(unittest.TestCase):
    def test_exact_finite_candidates_and_no_directory_search(self):
        self.assertEqual(len(probe.CANDIDATES),18)
        self.assertEqual(len(set(probe.CANDIDATES)),18)
        for path in probe.CANDIDATES:
            self.assertTrue(path.startswith(('/usr/bin/python3.','/usr/local/bin/python3.','/opt/alt/python3')))
            self.assertFalse(any(c in path for c in '*?[]'))
        result=php_case()
        self.assertTrue(result['result']['assessment_complete'])
        self.assertFalse(result['result']['compatible_python_found'])
        self.assertEqual([x['path'] for x in result['result']['candidates']],list(probe.CANDIDATES))
        self.assertEqual(len(result['executed']),1)
        self.assertEqual(result['executed'][0]['command'][0],'/usr/bin/python3')

    def test_found_candidate_gets_version_modules_and_pinned_php_contract(self):
        result=php_case(found=True)
        self.assertTrue(result['result']['compatible_python_found'])
        self.assertEqual(result['result']['selected_python'],'/usr/bin/python3.12')
        self.assertEqual(len(result['result']['candidates']),1)
        self.assertEqual(len(result['executed']),3)
        data=json.loads(result['executed'][-1]['input'])
        self.assertEqual(set(data),{'php_binary','php_flags'})
        self.assertEqual(result['executed'][-1]['command'][1:4],['-I','-B','-c'])

    def test_php_source_lints_and_payload_has_no_secret_fields(self):
        p=subprocess.run(['php','-l'],input='<?php\n'+probe.php_source(),text=True,capture_output=True)
        self.assertEqual(p.returncode,0)
        data=json.loads(probe.payload())
        self.assertEqual(set(data),{'source','platform_source','module_source','version_source'})
        self.assertNotIn('password',data)
        self.assertNotIn('MOSA_TEST_DB_PASSWORD',json.dumps(data))

    def test_platform_probe_reports_only_abi_and_explicit_library_checks(self):
        p=subprocess.run([sys.executable,'-I','-B','-c',probe.PLATFORM_PROBE],
                         text=True,capture_output=True,check=True,timeout=5)
        self.assertEqual(p.stderr,'')
        r=json.loads(p.stdout)
        self.assertIn(r['pointer_bits'],(32,64))
        self.assertEqual(r['provider_requests'],0);self.assertEqual(r['database_connections'],0)
        self.assertEqual(len(r['libraries']),7)
        tree=ast.parse(probe.PLATFORM_PROBE)
        calls=[n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
        self.assertFalse({'walk','listdir','scandir','glob','rglob','connect','urlopen','write_text','mkdir'}.intersection(calls))

    def test_negative_assessment_and_no_credentials_in_transport(self):
        @contextmanager
        def ssh(*args):
            yield Mock()
        env={name:'synthetic-private' for name in probe.shared.SECRETS}
        with patch.object(probe.shared,'configuration',return_value={}), \
             patch.object(probe.shared,'ssh_client',ssh), \
             patch.object(probe.remote,'capability',return_value=('php',[])), \
             patch.object(probe.remote,'remote_call',return_value=(0,b'{"assessment_complete":true,"compatible_python_found":false}',False,1)) as remote:
            result=probe.execute(env,paramiko=Mock())
        self.assertTrue(result['ok']);self.assertFalse(result['compatible_python_found'])
        self.assertNotIn('synthetic-private',remote.call_args.args[2].decode())
        self.assertEqual(remote.call_args.kwargs['timeout'],90)

    def test_workflow_is_manual_and_no_install_or_transfer_operation(self):
        text=(ROOT/'.github/workflows/collector-python-options.yml').read_text()
        self.assertIn('workflow_dispatch:',text);self.assertNotIn('  push:',text)
        self.assertNotIn('  schedule:',text);self.assertNotIn('upload-artifact',text)
        source=probe.php_source()
        for bad in ('open_sftp(', 'file_put_contents(', 'mkdir(', 'scandir(', 'glob(', 'new PDO(', 'pip install', 'yum ', 'apt ', 'cloudlinux-selector get'):
            self.assertNotIn(bad,source)
        self.assertIn('PROBE_BUDGET_EXHAUSTED',source)

if __name__=='__main__':
    unittest.main()
