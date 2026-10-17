<?php
declare(strict_types=1);
const MOSA2_HISTORY_PROFILE='history100000_v1';
require __DIR__.'/optimization.php';
use Mosa2\Phase1B\Failure;
use function Mosa2\Phase1B\ensure;
use function Mosa2\History10000\{historyTimeIndex,querySet,expectedQueries,statistics};
use function Mosa2\HistoryOptimization\{stageSpec,reserve,analyzeLines};
use const Mosa2\HistoryOptimization\{STAGES,COMPARISONS};
$n=0;
function check(bool $ok):void {global $n;ensure($ok,'optimization_offline_assertion');++$n;}
function rejects(callable $f):void {try{$f();}catch(Failure){check(true);return;}throw new RuntimeException('guard_not_rejected');}
check(historyTimeIndex()==='KEY history_time(entity_id,observed_at ASC,id ASC)');
check(historyTimeIndex('DESC')==='KEY history_time(entity_id,observed_at DESC,id DESC)');
foreach(['asc','DESC,id','FORCE INDEX',''] as $s)rejects(fn()=>historyTimeIndex($s));
check(STAGES===['baseline','ordering_off','ascending']);
check(stageSpec('baseline')===['direction'=>'DESC','prefer_ordering_index'=>true]);
check(stageSpec('ordering_off')===['direction'=>'DESC','prefer_ordering_index'=>false]);
check(stageSpec('ascending')===['direction'=>'ASC','prefer_ordering_index'=>true]);
rejects(fn()=>stageSpec('fourth_variant'));
$state=['ready'=>true,'cleaned'=>false,'optimization'=>['version'=>1,'current'=>null,'used'=>[]],'tables'=>[]];
foreach(['entity','identity','history','current','migration'] as $k=>$kind)$state['tables'][$kind]='mosa2_tmp_'.str_pad((string)$k,16,'0',STR_PAD_LEFT);
$bad=$state;rejects(function()use(&$bad){reserve($bad,'baseline','fpm-fcgi');});
$bad=$state;rejects(function()use(&$bad){reserve($bad,'ascending','cli');});
foreach(STAGES as $stage) {
    reserve($state,$stage,'cli');check($state['optimization']['used'][$stage]['cli']===true);
    $bad=$state;rejects(function()use(&$bad,$stage){reserve($bad,$stage,'cli');});
    reserve($state,$stage,'fpm-fcgi');check($state['optimization']['used'][$stage]['fpm-fcgi']===true);
    $bad=$state;rejects(function()use(&$bad,$stage){reserve($bad,$stage,'fpm-fcgi');});
}
$bad=$state;$bad['cleaned']=true;rejects(function()use(&$bad){reserve($bad,'ascending','cli');});
check(count(COMPARISONS)===5 && count(STAGES)-1<=3);
$set=querySet($state);$want=expectedQueries();
foreach(COMPARISONS as $k){check(isset($set[$k],$want[$k]));check(str_contains($set[$k][0],'LIMIT '));check(!str_contains($set[$k][0],'FORCE INDEX'));}
check(count($want['history_wide_window'])===50);
check($set['history_wide_window'][1]===[7,'2020-01-01 00:00:00.000000','2020-01-01 07:30:00.000000']);
check(str_contains($set['history_wide_window'][0],'observed_at>=? AND observed_at<? ORDER BY observed_at,id LIMIT 50'));
check($want['history_wide_window'][0][2]===1 && $want['history_wide_window'][49][2]===50);
check($want['history_wide_window'][0][3]===$want['history_wide_window'][1][3]);
$plan=analyzeLines("-> Limit: 50 row(s) (cost=50 rows=50) (actual time=0.2..1.5 rows=50 loops=1)\n    -> Index scan on ".$state['tables']['history']." (cost=20 rows=5000) (actual time=0.1..1.4 rows=93050 loops=1)",$state['tables']);
check(count($plan)===2);
check($plan[1]['estimated_rows']===5000.0 && $plan[1]['actual_rows']===93050.0);
check($plan[1]['loops']===1 && $plan[1]['actual_last_ms']===1.4);
check(str_contains($plan[1]['operator'],'history')&&!str_contains($plan[1]['operator'],'mosa2_tmp_'));
rejects(fn()=>analyzeLines('unparsed',$state['tables']));
check(statistics(range(1,10))===['samples'=>10,'median_ms'=>5.5,'p95_ms'=>10.0]);
rejects(fn()=>statistics(range(1,31)));
echo json_encode(['ok'=>true,'optimization_checks'=>$n,'candidate_limit'=>count(STAGES)-1,'database_connections'=>0],JSON_THROW_ON_ERROR),PHP_EOL;
