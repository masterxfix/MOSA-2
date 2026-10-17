<?php
declare(strict_types=1);

const MOSA2_HISTORY_PROFILE = 'history100000_v1';
require __DIR__ . '/../phase1c/profile.php';

use Mosa2\Phase1B\Failure;
use function Mosa2\Phase1B\ensure;
use function Mosa2\History10000\{profileSpec,generatedRows,boundedBatches,rows,stamp,historyRow,statistics,batchStatistics,expectedDigest,expectedQueries,validateState,validateCount,querySet};
use const Mosa2\History10000\{LIMITS,EXPECTED,SAMPLES,BATCH};

$checks=0;
function check(bool $ok):void { global $checks; ensure($ok,'offline_100000_assertion');++$checks; }
function rejects(callable $case):void {
    try {$case();} catch(Failure) {check(true);return;}
    throw new RuntimeException('100000_guard_not_rejected');
}
$big=profileSpec();$small=profileSpec('history10000_v1');
check($big['per_entity']===1000 && $big['limits']['history']===100000);
check($small['per_entity']===100 && $small['limits']['history']===10000);
check(LIMITS['history']===10000 && EXPECTED['history']===10000);
check(SAMPLES===11 && BATCH===500);
rejects(fn()=>profileSpec('history1000000_v1'));
rejects(fn()=>profileSpec('100000'));
rejects(fn()=>rows('history'));
rejects(fn()=>validateCount('history',100001));
rejects(fn()=>validateCount('history',10001,'history10000_v1'));
foreach(['entity','identity','current','migration'] as $kind) {
    check($big['limits'][$kind]===$small['limits'][$kind]);
    rejects(fn()=>validateCount($kind,$big['limits'][$kind]+1));
}
$seen=0;$batchCount=0;$perEntity=array_fill(1,100,0);
foreach(boundedBatches('history') as $batch) {
    ++$batchCount;check(count($batch)===500);
    foreach($batch as $row) {
        ++$seen;ensure($row[0]===$seen,'stream_id_mismatch');++$perEntity[$row[1]];
    }
}
check($seen===100000 && $batchCount===200);
check(array_values(array_unique($perEntity))===[1000]);
check(historyRow(100,1000)===[100000,100,1000,'2020-01-01 08:19:00.000000',101000]);
check(stamp(999)===stamp(1000));
rejects(fn()=>stamp(1001));
rejects(fn()=>stamp(101,'history10000_v1'));
rejects(fn()=>historyRow(101,1));
check(rows('current')[6][1]===7000);
check(rows('current','history10000_v1')[6][1]===700);
check(count(rows('entity'))===100 && count(rows('identity'))===100 && count(rows('migration'))===1);
check(expectedDigest()==='9d1be385cdc925c8a5968ffd1ea899fa9aa3b2e82369ef14d47e233dfbf98d68');
check(expectedDigest('history10000_v1')==='8abd1bd16ab12701a2d4abeccb4147116bbff0c65d3df6e247f03c960929a670');
rejects(fn()=>statistics(range(1,31)));
check(statistics(range(1,11))['samples']===11);
$batchStats=batchStatistics(range(1,200));
check($batchStats===['samples'=>200,'median_ms'=>100.5,'p95_ms'=>190.0]);
rejects(fn()=>batchStatistics(range(1,201)));
rejects(fn()=>batchStatistics(range(1,21),'history10000_v1'));
rejects(fn()=>batchStatistics([]));
$state=['profile'=>$big['id'],'per_entity'=>$big['per_entity'],'limits'=>$big['limits'],'expected'=>$big['expected'],'owner'=>str_repeat('a',32),'tables'=>[],'baseline'=>[],'used'=>['cli'=>false,'fpm-fcgi'=>false]];
foreach(array_keys(LIMITS) as $n=>$kind)$state['tables'][$kind]='mosa2_tmp_'.str_pad(dechex($n),16,'0',STR_PAD_LEFT);
validateState($state);check(true);
foreach(['profile','per_entity','limits','expected','owner','tables','baseline','used'] as $key) {
    $bad=$state;unset($bad[$key]);rejects(fn()=>validateState($bad));
}
$bad=$state;$bad['limits']['history']=10000;rejects(fn()=>validateState($bad));
$bad=$state;$bad['per_entity']=100;rejects(fn()=>validateState($bad));
$bad=$state;$bad['expected']['history']=100001;rejects(fn()=>validateState($bad));
$bad=$state;$bad['profile']=$small['id'];rejects(fn()=>validateState($bad));
$bad=$state;$bad['tables']['history']=$bad['tables']['entity'];rejects(fn()=>validateState($bad));
$bad=$state;$bad['tables']['history']='existing_table';rejects(fn()=>validateState($bad));
$bad=$state;$bad['used']['cli']=31;rejects(fn()=>validateState($bad));
$bad=$state;$bad['baseline']='not-an-array';rejects(fn()=>validateState($bad));
$queries=querySet($state);$expected=expectedQueries();
check(count($queries)===7 && count($expected)===7);
check(count($expected['history_wide_window'])===50);
check($expected['history_latest'][0][0]===7000);
check(count($expected['history_window'])===10 && count($expected['chart'])===25);
foreach($queries as [$sql,$params])check(str_contains($sql,'LIMIT '));
check(count($queries)*SAMPLES===77);
echo json_encode(['ok'=>true,'profile_checks'=>$checks,'history_rows'=>$seen,'history_batches'=>$batchCount,'database_connections'=>0],JSON_THROW_ON_ERROR),PHP_EOL;
