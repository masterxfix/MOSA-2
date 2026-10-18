<?php
declare(strict_types=1);
const MOSA2_HISTORY_PROFILE='history1000000_v1';
const MOSA2_HISTORY_MILLION=true;
require __DIR__.'/million.php';
use function Mosa2\Phase1B\ensure;
use function Mosa2\History10000\{profileSpec,validateCount,boundedBatches,historyRow,stamp,rows,expectedDigest,batchStatistics,statistics,validateState,querySet,expectedQueries};
$checks=0;
function check(bool $ok):void {global $checks;ensure($ok,'million_offline_assertion');++$checks;}
function rejects(callable $f):void {try{$f();}catch(\Mosa2\Phase1B\Failure){check(true);return;}throw new RuntimeException('guard_not_rejected');}
$spec=profileSpec();check($spec['per_entity']===10000 && $spec['expected']['history']===1000000);
check(profileSpec('history100000_v1')['limits']['history']===100000);
check(profileSpec('history10000_v1')['limits']['history']===10000);
rejects(fn()=>profileSpec('history10000000_v1'));
rejects(fn()=>validateCount('history',1000001));
rejects(fn()=>validateCount('history',100001,'history100000_v1'));
rejects(fn()=>rows('history'));
rejects(fn()=>stamp(10001));
rejects(fn()=>statistics(range(1,31)));
rejects(fn()=>batchStatistics(range(1,2001)));
check(batchStatistics(range(1,2000))===['samples'=>2000,'median_ms'=>1000.5,'p95_ms'=>1900.0]);
$seen=0;$batches=0;$counts=array_fill(1,100,0);$hash=hash_init('sha256');
foreach(boundedBatches('history') as $batch) {
    ++$batches;check(count($batch)===500);
    foreach($batch as $row) {
        ++$seen;ensure($row[0]===$seen,'id_sequence');
        ++$counts[$row[1]];hash_update($hash,implode('|',$row)."\n");
    }
}
$digest=hash_final($hash);
check($seen===1000000 && $batches===2000 && array_values(array_unique($counts))===[10000]);
check($digest===expectedDigest());
check($digest==='3a80ac0ad6741320a1477cf250c3268a5a1f41d12298b27f033c1cd4030057b9');
check(historyRow(100,10000)===[1000000,100,10000,'2020-01-04 11:19:00.000000',110000]);
check(stamp(9999)===stamp(10000));
check(rows('current')[6][1]===70000);
$state=['profile'=>$spec['id'],'per_entity'=>$spec['per_entity'],'limits'=>$spec['limits'],'expected'=>$spec['expected'],'owner'=>str_repeat('a',32),'tables'=>[],'baseline'=>[],'used'=>['cli'=>false,'fpm-fcgi'=>false]];
foreach(array_keys($spec['limits']) as $n=>$k)$state['tables'][$k]='mosa2_tmp_'.str_pad(dechex($n),16,'0',STR_PAD_LEFT);
validateState($state);check(true);
foreach(['profile','per_entity','limits','expected','owner','tables','baseline','used'] as $k){$bad=$state;unset($bad[$k]);rejects(fn()=>validateState($bad));}
$bad=$state;$bad['tables']['history']=$bad['tables']['entity'];rejects(fn()=>validateState($bad));
$bad=$state;$bad['tables']['history']='production';rejects(fn()=>validateState($bad));
$q=querySet($state);$expected=expectedQueries();
check(count($q)===7 && count($expected)===7);
check($q['history_wide_window'][1]===[7,stamp(1),stamp(9901)]);
check(count($expected['history_wide_window'])===50 && $expected['history_latest'][0][0]===70000);
foreach($q as [$sql,$params])check(str_contains($sql,'LIMIT '));
check(\Mosa2\Million\assess(['current_single'=>['first_ms'=>20,'subsequent'=>['median_ms'=>1,'p95_ms'=>1],'explain'=>[]]])===['current_single_latency']);
$source=file_get_contents(__DIR__.'/../phase1c/profile.php');
check(str_contains($source,"ensure(!file_exists(".'$path'.")"));
check(str_contains($source,"proveOwnership(".'$pdo,$state,$kind'.")"));
check(str_contains($source,"'baseline_not_restored'"));
echo json_encode(['ok'=>true,'checks'=>$checks,'history_rows'=>$seen,'history_batches'=>$batches,'digest'=>$digest,'database_connections'=>0]),PHP_EOL;
