<?php
declare(strict_types=1);

namespace Mosa2\HistoryConcurrency;

require_once __DIR__.'/../phase1c/profile.php';

use PDO;
use PDOException;
use Throwable;
use function Mosa2\Phase1B\{connect,ensure,sessionState,validateObservedTarget};
use function Mosa2\History10000\{profileSpec,saveState,proveOwnership,ownedName,counts,expectedDigest,actualDigest,historyRow,rows,upsert,correctness,measureQueries,checkpoint};

const CONNECTIONS=4;
const REPETITIONS=3;
const READ_SAMPLES=10;
const CONFLICTS=1;
const READ_KINDS=['current_single','history_latest','history_window','chart','history_wide_window'];

function validateBudget(int $connections,int $repetitions,int $conflicts,int $reads):void
{
    ensure($connections>=2&&$connections<=4,'connection_budget_exceeded');
    ensure($repetitions>=1&&$repetitions<=10,'scenario_budget_exceeded');
    ensure($conflicts>=1&&$conflicts<=3,'conflict_budget_exceeded');
    ensure($reads>=2&&$reads<=10,'read_budget_exceeded');
}

function expectedLock(array $info):bool
{
    return ($info[0]??null)==='HY000' && (int)($info[1]??0)===1205;
}

function targetGuard(PDO $pdo,array $target):void
{
    validateObservedTarget($pdo->query('SELECT DATABASE() AS db,CURRENT_USER() AS account,@@port AS port,VERSION() AS version')->fetch(),$target);
}

function readCurrent(PDO $pdo,array $state,int $entity):array|false
{
    ensure($entity>=1&&$entity<=100,'entity_out_of_profile');
    $q=$pdo->prepare('SELECT entity_id,history_id,observed_at,synthetic_value FROM '.ownedName($state,'current').' WHERE entity_id=? LIMIT 1');
    $q->execute([$entity]);return $q->fetch(PDO::FETCH_NUM);
}

function want(int $entity,int $seq):array
{
    $h=historyRow($entity,$seq);return [$entity,$h[0],$h[3],$h[4]];
}

function beginWrite(PDO $pdo,array $target):void
{
    targetGuard($pdo,$target);ensure(!$pdo->inTransaction(),'transaction_already_open');$pdo->beginTransaction();
}

function fixture(PDO $pdo,array $target,array $state,array $entities):void
{
    beginWrite($pdo,$target);
    try {
        $q=$pdo->prepare('UPDATE '.ownedName($state,'current').' SET history_id=?,observed_at=?,synthetic_value=? WHERE entity_id=?');
        foreach($entities as $e) {
            $h=historyRow($e,profileSpec()['per_entity']-2);
            $q->execute([$h[0],$h[3],$h[4],$e]);
            ensure(readCurrent($pdo,$state,$e)===want($e,profileSpec()['per_entity']-2),'fixture_failed');
        }
        $pdo->commit();
    }catch(Throwable $e){if($pdo->inTransaction())$pdo->rollBack();throw $e;}
}

function assertLatest(PDO $pdo,array $state):void
{
    ensure($pdo->query('SELECT entity_id,history_id,observed_at,synthetic_value FROM '.ownedName($state,'current').' ORDER BY entity_id LIMIT 100')->fetchAll(PDO::FETCH_NUM)===rows('current'),'current_not_unique_latest');
}

function measure(PDO $writer,array $target,string $password,array &$state,string $path,float $deadline):array
{
    validateBudget(CONNECTIONS,REPETITIONS,CONFLICTS,READ_SAMPLES);
    ensure(($state['ready']??false)&&!($state['cleaned']??false),'dataset_not_ready');
    ensure(($state['used'][PHP_SAPI]??null)===false,'runtime_already_measured');
    $state['used'][PHP_SAPI]=true;saveState($path,$state);
    foreach(array_keys($state['tables']) as $kind)ensure(proveOwnership($writer,$state,$kind),'owned_table_missing');
    $pool=[$writer];$events=[];$metrics=[];$checks=[];
    try {
        for($i=1;$i<CONNECTIONS;++$i)$pool[]=connect($target,$password);
        unset($password);[$a,$b,$c,$d]=$pool;
        $ids=array_map(fn(PDO $p):int=>(int)$p->query('SELECT CONNECTION_ID()')->fetchColumn(),$pool);
        ensure(count(array_unique($ids))===CONNECTIONS,'connections_not_independent');
        $session=sessionState($a);
        foreach($pool as $p){ensure(sessionState($p)===$session,'session_state_differs');$p->exec('SET SESSION max_execution_time=3000');}
        $c->exec('SET SESSION innodb_lock_wait_timeout=1');
        ensure((int)$c->query('SELECT @@session.innodb_lock_wait_timeout')->fetchColumn()===1,'bounded_lock_wait_required');
        $before=counts($a,$state);$digest=actualDigest($a,$state,$deadline);
        ensure(hash_equals(expectedDigest(),$digest),'history_seed_digest_mismatch');
        $checks=correctness($a,$state,$deadline);
        $per=profileSpec()['per_entity'];
        for($iteration=0;$iteration<REPETITIONS;++$iteration) {
            checkpoint($deadline);
            // An explicitly older Current fixture makes the committed transition observable.
            fixture($a,$target,$state,[1]);
            $old=want(1,$per-2);$new=want(1,$per);
            $b->beginTransaction();ensure(readCurrent($b,$state,1)===$old,'snapshot_initial_mismatch');
            beginWrite($a,$target);upsert($a,$state,historyRow(1,$per));
            ensure(readCurrent($a,$state,1)===$new,'writer_did_not_see_update');
            ensure(readCurrent($c,$state,1)===$old&&readCurrent($b,$state,1)===$old,'uncommitted_visible');
            $a->commit();
            ensure(readCurrent($b,$state,1)===$old,'snapshot_changed_after_commit');
            $b->commit();$b->beginTransaction();
            ensure(readCurrent($b,$state,1)===$new,'new_snapshot_missing_commit');$b->commit();
            $d->beginTransaction();ensure(readCurrent($d,$state,1)===$new,'independent_new_transaction_missing_commit');$d->commit();
            assertLatest($a,$state);
            $events['snapshot'][]=['old_snapshot_stable'=>true,'dirty_read_absent'=>true,'new_transactions_see_commit'=>true];

            beginWrite($a,$target);
            $q=$a->prepare('DELETE FROM '.ownedName($state,'current').' WHERE entity_id=?');$q->execute([2]);
            ensure($q->rowCount()===1&&readCurrent($a,$state,2)===false,'rollback_mutation_missing');
            ensure(readCurrent($c,$state,2)===want(2,$per),'uncommitted_delete_visible');
            $a->rollBack();
            foreach($pool as $p)ensure(readCurrent($p,$state,2)===want(2,$per),'rollback_left_state');
            assertLatest($a,$state);$events['rollback'][]=['all_connections_restored'=>true];

            fixture($a,$target,$state,[3,4]);
            beginWrite($a,$target);$start=hrtime(true);upsert($a,$state,historyRow(3,$per));$first=(hrtime(true)-$start)/1e6;
            beginWrite($c,$target);$start=hrtime(true);upsert($c,$state,historyRow(4,$per));$second=(hrtime(true)-$start)/1e6;
            ensure($a->inTransaction()&&$c->inTransaction(),'overlapping_writers_required');
            ensure(readCurrent($d,$state,3)===want(3,$per-2)&&readCurrent($d,$state,4)===want(4,$per-2),'dirty_read_different_entities');
            // Existing common read definitions target Entity 7, distinct from both locked rows.
            if($iteration===0)$metrics=measureQueries($b,$state,$deadline,READ_KINDS,READ_SAMPLES);
            $a->commit();$c->commit();assertLatest($d,$state);
            $events['different_entities'][]=['overlapping_transactions'=>true,'unexpected_lock_conflicts'=>0,'write_ms'=>[round($first,4),round($second,4)]];
        }

        // One deliberate row conflict; never retry a deadlock or an arbitrary SQL failure.
        fixture($a,$target,$state,[5]);
        beginWrite($a,$target);upsert($a,$state,historyRow(5,$per-1));
        beginWrite($c,$target);$waitStart=hrtime(true);$timedOut=false;
        try{upsert($c,$state,historyRow(5,$per));}
        catch(PDOException $e){ensure(expectedLock($e->errorInfo??[]),'unexpected_conflict_error');$timedOut=true;}
        $wait=(hrtime(true)-$waitStart)/1e6;ensure($timedOut,'expected_lock_wait_missing');
        // MySQL may roll back only the failed statement: explicitly end the whole attempt.
        $explicitRollback=$c->inTransaction();
        if($explicitRollback)$c->rollBack();
        ensure(!$c->inTransaction(),'waiting_attempt_not_rolled_back');
        $a->commit();ensure(readCurrent($d,$state,5)===want(5,$per-1),'first_writer_commit_missing');
        $retry=0;
        beginWrite($c,$target);++$retry;$start=hrtime(true);upsert($c,$state,historyRow(5,$per));$c->commit();
        $retryMs=(hrtime(true)-$start)/1e6;ensure($retry===1,'retry_budget_exceeded');
        assertLatest($d,$state);
        $events['same_row_conflict']=['attempts'=>1,'expected_code'=>1205,'wait_ms'=>round($wait,4),'waiting_transaction_rolled_back'=>true,'explicit_waiting_rollback'=>$explicitRollback,'retry_count'=>$retry,'retry_commit_ms'=>round($retryMs,4),'latest_state_after_retry'=>true];
        foreach($pool as $p)ensure(!$p->inTransaction(),'transaction_left_open');
        $after=counts($a,$state);$afterDigest=actualDigest($a,$state,$deadline);
        ensure($before===$after&&hash_equals($digest,$afterDigest),'history_changed');
        $final=correctness($a,$state,$deadline);
        ensure(!in_array(false,$final,true),'final_correctness_failed');
        $checks+=['independent_connections'=>true,'snapshot_commit_visibility'=>true,'uncommitted_invisible'=>true,'rollback_no_residue'=>true,'different_entities_no_conflict'=>true,'expected_lock_wait'=>true,'exactly_one_retry'=>true,'no_open_transactions'=>true,'history_count_and_digest_unchanged'=>true,'current_unique_latest'=>true];
        $goals=[];
        foreach($metrics as $k=>$q){$limit=$k==='current_single'?20:100;$goals[$k]=$q['subsequent']['median_ms']<$limit&&$q['subsequent']['p95_ms']<$limit;}
        $report=['ok'=>true,'runtime'=>['php'=>PHP_VERSION,'sapi'=>PHP_SAPI,'pdo_mysql'=>true],'session'=>$session,'connections'=>['maximum'=>CONNECTIONS,'distinct_confirmed'=>count(array_unique($ids))],'normal_repetitions_per_scenario'=>REPETITIONS,'intentional_conflicts'=>CONFLICTS,'scenarios'=>$events,'reads_during_two_open_writers'=>$metrics,'read_targets_met'=>$goals,'history'=>['before_rows'=>$before['history'],'after_rows'=>$after['history'],'checksum_before'=>$digest,'checksum_after'=>$afterDigest,'unchanged'=>true],'checks'=>$checks,'final_checks'=>$final,'build'=>$state['build']];
        saveState(dirname($path).'/result-'.(PHP_SAPI==='cli'?'cli':'fpm').'.json',$report);return $report;
    }finally{foreach($pool as $p)if($p->inTransaction())$p->rollBack();}
}

function dispatch(array $target,string $password,string $private,string $action):array
{
    return \Mosa2\History10000\dispatch($target,$password,$private,$action,
        static function(PDO $pdo,array &$state,string $path,float $deadline)use($target,$password):array {
            return measure($pdo,$target,$password,$state,$path,$deadline);
        });
}
