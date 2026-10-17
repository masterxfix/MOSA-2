<?php
declare(strict_types=1);
const MOSA2_HISTORY_PROFILE='history100000_v1';
require __DIR__.'/concurrency.php';
use Mosa2\Phase1B\Failure;
use function Mosa2\Phase1B\ensure;
use function Mosa2\HistoryConcurrency\{validateBudget,expectedLock,want};
use const Mosa2\HistoryConcurrency\{CONNECTIONS,REPETITIONS,CONFLICTS,READ_SAMPLES,READ_KINDS};
use function Mosa2\History10000\{measureQueries,querySet,historyTimeIndex};
use const Mosa2\History10000\SAMPLES;
$n=0;
function check(bool $ok):void{global $n;ensure($ok,'concurrency_offline_assertion');++$n;}
function rejects(callable $f):void{try{$f();}catch(Failure){check(true);return;}throw new RuntimeException('guard_not_rejected');}
validateBudget(CONNECTIONS,REPETITIONS,CONFLICTS,READ_SAMPLES);check(true);
check(CONNECTIONS===4&&REPETITIONS===3&&CONFLICTS===1&&READ_SAMPLES===10);
check(REPETITIONS*2<=10&&CONFLICTS*2<=3);
foreach([[5,3,1,10],[1,3,1,10],[4,11,1,10],[4,0,1,10],[4,3,4,10],[4,3,0,10],[4,3,1,11],[4,3,1,1]] as $b)rejects(fn()=>validateBudget(...$b));
check(expectedLock(['HY000',1205,'not exported']));
check(expectedLock(['HY000','1205']));
foreach([['40001',1213],['HY000',1213],['HY000',1045],['23000',1205],[],['HY000']] as $e)check(!expectedLock($e));
check(want(5,1000)===[5,5000,'2020-01-01 08:19:00.000000',6000]);
check(want(5,999)[2]===want(5,1000)[2]);
check(want(5,999)[1]<want(5,1000)[1]);
rejects(fn()=>want(101,1));rejects(fn()=>want(5,1001));
check(historyTimeIndex()==='KEY history_time(entity_id,observed_at ASC,id ASC)');
check(SAMPLES===11);
$reflection=new ReflectionFunction('Mosa2\\History10000\\measureQueries');
check($reflection->getParameters()[4]->getDefaultValue()===11);
final class UnconnectedPDO extends PDO {public function __construct(){}}
$pdo=new UnconnectedPDO();
$state=['tables'=>[]];
foreach(['entity','identity','history','current','migration'] as $k=>$kind)$state['tables'][$kind]='mosa2_tmp_'.str_pad((string)$k,16,'0',STR_PAD_LEFT);
rejects(fn()=>measureQueries($pdo,$state,microtime(true)+1,READ_KINDS,1));
rejects(fn()=>measureQueries($pdo,$state,microtime(true)+1,READ_KINDS,12));
rejects(fn()=>measureQueries($pdo,$state,microtime(true)+1,['unknown'],10));
rejects(fn()=>measureQueries($pdo,$state,microtime(true)+1,[],10));
rejects(fn()=>measureQueries($pdo,$state,microtime(true)+1,['chart','chart'],10));
$queries=querySet($state);
foreach(READ_KINDS as $kind){check(isset($queries[$kind]));check($queries[$kind][1][0]===7);check(str_contains($queries[$kind][0],'LIMIT '));}
check(count(READ_KINDS)===5);
echo json_encode(['ok'=>true,'concurrency_checks'=>$n,'connections_limit'=>CONNECTIONS,'normal_repetitions'=>REPETITIONS,'conflicts_per_runtime'=>CONFLICTS,'read_samples'=>READ_SAMPLES,'database_connections'=>0],JSON_THROW_ON_ERROR),PHP_EOL;
