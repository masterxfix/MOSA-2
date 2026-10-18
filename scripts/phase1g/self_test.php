<?php
declare(strict_types=1);
const MOSA2_HISTORY_PROFILE='history100000_v1';
require __DIR__.'/backup.php';
use function Mosa2\BackupRestore\{validatePair,canonical,comparison,writeRecord,readRecord};
use function Mosa2\Phase1B\ensure;
$n=0;
function check(bool $ok): void {global $n;ensure($ok,'offline_check_failed');++$n;}
function reject(callable $f): void {try{$f();}catch(Throwable){check(true);return;}check(false);}
$s=['database'=>'test_mosa2_test','user'=>'test_mosa2_test'];
$r=['database'=>'test_mosa2_restore_test','user'=>'test_mosa2_restore_test'];
validatePair($s,$r);check(true);
foreach(['test_mosa2_test','other_mosa2_restore_test','production','test_mosa2_restore_test;DROP DATABASE x','test_mosa2_restore_test'.chr(96),'test_mosa2_restore_test ',"\ntest_mosa2_restore_test"] as $db)
 reject(fn()=>validatePair($s,['database'=>$db,'user'=>$db]));
reject(fn()=>validatePair($s,['database'=>$r['database'],'user'=>'test_mosa2_test']));
reject(fn()=>validatePair(['database'=>'production','user'=>'production'],$r));
check(canonical(['a|b','c'])!==canonical(['a','b|c']));
check(canonical([null])!==canonical(['']));
check(canonical([1])!==canonical(['1']));
check(json_decode(canonical(['Grüße',"\n",'"','\\']),true)===['Grüße',"\n",'"','\\']);
$f=fopen('php://memory','w+');
writeRecord($f,['rows'=>[[1,'a'],[2,'b']]]);rewind($f);
check(readRecord($f)===['rows'=>[[1,'a'],[2,'b']]]);check(readRecord($f)===null);fclose($f);
foreach(['{}','not-json'."\n",'null'."\n",str_repeat('x',262145)."\n"] as $bad) {
 $f=fopen('php://memory','w+');fwrite($f,$bad);rewind($f);reject(fn()=>readRecord($f));fclose($f);
}
$f=fopen('php://memory','w+');reject(fn()=>writeRecord($f,['x'=>str_repeat('x',262144)]));fclose($f);
$a=['counts'=>['entity'=>100],'integrity'=>['current_latest'=>true],'tables'=>[]];
foreach(Mosa2\BackupRestore\KINDS as $kind)$a['tables'][$kind]=['ddl'=>'CREATE TABLE test','sha256'=>str_repeat('a',64)];
check(!in_array(false,comparison($a,$a),true));
$b=$a;$b['counts']['entity']=99;reject(fn()=>comparison($a,$b));
$b=$a;$b['tables']['history']['sha256']=str_repeat('b',64);reject(fn()=>comparison($a,$b));
$b=$a;$b['tables']['history']['ddl']='ALTERED';reject(fn()=>comparison($a,$b));
$b=$a;$b['integrity']['current_latest']=false;reject(fn()=>comparison($a,$b));
$b=$a;unset($b['tables']['identity']);reject(fn()=>comparison($a,$b));
check(Mosa2\BackupRestore\normalizedDdl('code varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs')===Mosa2\BackupRestore\normalizedDdl('code varchar(32) COLLATE utf8mb4_0900_as_cs'));
check(Mosa2\BackupRestore\normalizedDdl('code varchar(32) CHARACTER SET latin1 COLLATE latin1_bin')!=='code varchar(32) COLLATE utf8mb4_0900_as_cs');
$b=$a;$a['tables']['entity']['ddl']='code varchar(32) COLLATE utf8mb4_0900_as_cs';$b['tables']['entity']['ddl']='code varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs';check(comparison($a,$b)['structure']);
echo json_encode(['ok'=>true,'backup_checks'=>$n,'database_connections'=>0]),PHP_EOL;
