<?php
declare(strict_types=1);

require __DIR__ . '/profile.php';

use Mosa2\Phase1B\Failure;
use function Mosa2\Phase1B\ensure;
use function Mosa2\History10000\{rows,historyRow,stamp,newer,statistics,chunks,validateCount,validateState,checkpoint,expectedDigest,expectedQueries};
use const Mosa2\History10000\{LIMITS,EXPECTED,SAMPLES,BATCH};

$checks = 0;
function check(bool $condition): void { global $checks; ensure($condition, 'offline_profile_assertion'); ++$checks; }
function rejects(callable $run): void {
    try { $run(); } catch (Failure) { check(true); return; }
    throw new RuntimeException('profile_guard_not_rejected');
}
foreach (EXPECTED as $kind => $expected) {
    $data = rows($kind);
    check(count($data) === $expected);
    validateCount($kind,count($data));
    check(count($data) <= LIMITS[$kind]);
    foreach (chunks($data) as $chunk) check(count($chunk) <= BATCH);
    rejects(fn() => validateCount($kind,LIMITS[$kind]+1));
    rejects(fn() => validateCount($kind,-1));
}
check(SAMPLES === 11 && SAMPLES <= 30);
check(count(array_unique(array_column(rows('entity'),1))) === 100);
check(count(array_unique(array_column(rows('identity'),3))) === 100);
check(count(array_unique(array_column(rows('history'),0))) === 10000);
check(count(array_unique(array_column(rows('history'),1))) === 100);
check(array_values(array_unique(array_count_values(array_column(rows('history'),1)))) === [100]);
check(expectedDigest() === expectedDigest());
check(expectedDigest() === '8abd1bd16ab12701a2d4abeccb4147116bbff0c65d3df6e247f03c960929a670');
check(historyRow(1,1) === [1,1,1,'2020-01-01 00:00:00.000000',1001]);
check(historyRow(100,100) === [10000,100,100,'2020-01-01 00:49:00.000000',100100]);
check(stamp(99) === stamp(100));
check(newer(historyRow(7,100),historyRow(7,99)));
check(!newer(historyRow(7,99),historyRow(7,100)));
check(!newer(historyRow(7,98),historyRow(7,100)));
check(!newer(historyRow(7,100),historyRow(7,100)));
check(count(expectedQueries()['history_window']) === 10);
check(count(expectedQueries()['chart']) === 25);
check(expectedQueries()['history_latest'][0][0] === 700);
rejects(fn() => historyRow(0,1)); rejects(fn() => historyRow(101,1));
rejects(fn() => stamp(0)); rejects(fn() => stamp(101));
rejects(fn() => rows('other')); rejects(fn() => chunks(array_fill(0,10001,[])));
rejects(fn() => statistics([])); rejects(fn() => statistics(array_fill(0,31,1)));
check(statistics([4,1,3,2]) === ['samples'=>4,'median_ms'=>2.5,'p95_ms'=>4.0]);
rejects(fn() => checkpoint(microtime(true)-1));
$state=['profile'=>'history10000_v1','owner'=>str_repeat('a',32),'tables'=>[],'baseline'=>[],'used'=>['cli'=>false,'fpm-fcgi'=>false]];
foreach (array_keys(LIMITS) as $n=>$kind) $state['tables'][$kind]='mosa2_tmp_'.str_pad(dechex($n),16,'0',STR_PAD_LEFT);
validateState($state); check(true);
foreach (['profile','owner','tables','baseline'] as $key) {
    $bad=$state; unset($bad[$key]); rejects(fn()=>validateState($bad));
}
$bad=$state; $bad['tables']['history']='existing_table'; rejects(fn()=>validateState($bad));
$bad=$state; $bad['tables']['history']=$bad['tables']['entity']; rejects(fn()=>validateState($bad));
$bad=$state; $bad['used']['cli']=31; rejects(fn()=>validateState($bad));
// The original baseline guard and its 100-row budget remain independently unchanged.
echo json_encode(['ok'=>true,'profile_checks'=>$checks,'history_rows'=>count(rows('history')),'database_connections'=>0],JSON_THROW_ON_ERROR),PHP_EOL;
