<?php
declare(strict_types=1);

namespace Mosa2\HistoryOptimization;

require_once __DIR__ . '/../phase1c/profile.php';

use PDO;
use Throwable;
use Mosa2\Phase1B\Failure;
use function Mosa2\Phase1B\{connect,ensure,validateObservedTarget,sessionState};
use function Mosa2\History10000\{build,cleanup,validateState,saveState,proveOwnership,ownedName,tableNames,historyTimeIndex,measureQueries,correctness,querySet,tableStatistics,checkpoint};

const STAGES = ['baseline','ordering_off','ascending'];
const COMPARISONS = ['current_single','history_latest','history_window','chart','history_wide_window'];

function stageSpec(string $stage): array
{
    ensure(in_array($stage,STAGES,true),'unknown_optimization_stage');
    return ['direction'=>$stage==='ascending'?'ASC':'DESC','prefer_ordering_index'=>$stage!=='ordering_off'];
}

function reserve(array &$state, string $stage, string $sapi): void
{
    stageSpec($stage);
    ensure(in_array($sapi,['cli','fpm-fcgi'],true),'unsupported_sapi');
    ensure(($state['ready']??false) && !($state['cleaned']??false),'dataset_not_ready');
    $opt=$state['optimization']??null;
    ensure(is_array($opt) && ($opt['version']??null)===1 && is_array($opt['used']??null),'optimization_manifest_missing');
    $n=array_search($stage,STAGES,true);
    if ($n>0) foreach (['cli','fpm-fcgi'] as $prior) ensure(($opt['used'][STAGES[$n-1]][$prior]??false)===true,'previous_stage_incomplete');
    ensure(!($opt['used'][$stage][$sapi]??false),'optimization_runtime_already_measured');
    if ($sapi==='fpm-fcgi') ensure(($opt['current']??null)===$stage && ($opt['used'][$stage]['cli']??false)===true,'cli_stage_required');
    else ensure(!isset($opt['used'][$stage]),'optimization_stage_already_started');
    $state['optimization']['current']=$stage;
    $state['optimization']['used'][$stage][$sapi]=true;
}

function targetGuard(PDO $pdo, array $target): void
{
    validateObservedTarget($pdo->query('SELECT DATABASE() AS db,CURRENT_USER() AS account,@@port AS port,VERSION() AS version')->fetch(),$target);
}

function indexDetails(PDO $pdo, array $state): array
{
    $rows=$pdo->query('SHOW INDEX FROM '.ownedName($state,'history'))->fetchAll();
    $result=[];
    foreach ($rows as $r) $result[]=['name'=>$r['Key_name'],'position'=>(int)$r['Seq_in_index'],'column'=>$r['Column_name'],'direction'=>$r['Collation'],'unique'=>(int)$r['Non_unique']===0];
    return $result;
}

function analyzeLines(string $text, array $tables): array
{
    $lines=explode("\n",$text); ensure(count($lines)<=16,'analyze_plan_too_large');
    $result=[];
    foreach($lines as $line) {
        if (!preg_match('/-> (.*?)(?: \\(cost=| \\(actual time=)/',$line,$label)) continue;
        $r=['operator'=>trim(str_replace(array_values($tables),array_keys($tables),$label[1]))];
        ensure(strlen($r['operator'])<=300,'analyze_label_too_long');
        if(preg_match('/cost=[^)]*rows=([0-9.eE+-]+)/',$line,$m))$r['estimated_rows']=(float)$m[1];
        if(preg_match('/actual time=([0-9.eE+-]+)\\.\\.([0-9.eE+-]+) rows=([0-9.eE+-]+) loops=([0-9]+)/',$line,$m)) {
            $r+=['actual_first_ms'=>(float)$m[1],'actual_last_ms'=>(float)$m[2],'actual_rows'=>(float)$m[3],'loops'=>(int)$m[4]];
        }
        $result[]=$r;
    }
    ensure($result!==[],'analyze_plan_unparsed'); return $result;
}

function analyze(PDO $pdo,array $state):array
{
    [$sql,$params]=querySet($state)['history_wide_window'];
    try {
        $q=$pdo->prepare('EXPLAIN ANALYZE '.str_replace('SELECT ','SELECT /*+ MAX_EXECUTION_TIME(3000) */ ',$sql));
        $q->execute($params);
        return ['supported'=>true,'operators'=>analyzeLines(implode("\n",$q->fetchAll(PDO::FETCH_COLUMN)),$state['tables'])];
    } catch (\PDOException $e) {
        // Unsupported syntax is an explicit missing proof, never a fabricated plan.
        if(($e->errorInfo[1]??null)===1064) return ['supported'=>false,'reason'=>'server_syntax_not_supported'];
        throw $e;
    }
}

function measureStage(PDO $pdo,array $target,array &$state,string $path,string $stage,float $deadline):array
{
    $spec=stageSpec($stage);
    reserve($state,$stage,PHP_SAPI); saveState($path,$state);
    foreach(array_keys($state['tables']) as $kind)ensure(proveOwnership($pdo,$state,$kind),'owned_table_missing');
    if(PHP_SAPI==='cli' && $stage==='ascending') {
        targetGuard($pdo,$target); ensure(!$pdo->inTransaction(),'ddl_inside_transaction');
        $h=ownedName($state,'history');$start=hrtime(true);
        $pdo->exec('ALTER TABLE '.$h.' DROP INDEX history_time, ADD '.historyTimeIndex('ASC'));
        $state['optimization']['index_rebuild_ms']=round((hrtime(true)-$start)/1e6,4);saveState($path,$state);
    }
    $pdo->exec("SET SESSION optimizer_switch='prefer_ordering_index=".($spec['prefer_ordering_index']?'on':'off')."'");
    $switch=$pdo->query('SELECT @@session.optimizer_switch')->fetchColumn();
    ensure(str_contains($switch,'prefer_ordering_index='.($spec['prefer_ordering_index']?'on':'off')),'optimizer_session_mismatch');
    $index=indexDetails($pdo,$state);
    $time=array_values(array_filter($index,fn(array $r):bool=>$r['name']==='history_time'));
    ensure(count($time)===3 && $time[1]['direction']===($spec['direction']==='ASC'?'A':'D') && $time[2]['direction']===$time[1]['direction'],'index_direction_mismatch');
    $r=['ok'=>true,'stage'=>$stage,'runtime'=>['php'=>PHP_VERSION,'sapi'=>PHP_SAPI,'pdo_mysql'=>true],'session'=>sessionState($pdo),'index'=>$index,'prefer_ordering_index'=>$spec['prefer_ordering_index']];
    $r['queries']=measureQueries($pdo,$state,$deadline,COMPARISONS);
    $r['analyze']=analyze($pdo,$state);
    targetGuard($pdo,$target); // Shared correctness includes rolled-back Current writes.
    $r['checks']=correctness($pdo,$state,$deadline);
    $r['approximate_table_statistics']=tableStatistics($pdo,$state);
    $r['index_rebuild_ms']=$state['optimization']['index_rebuild_ms']??null;
    saveState(dirname($path).'/optimization-'.$stage.'-'.(PHP_SAPI==='cli'?'cli':'fpm').'.json',$r);
    return $r;
}

function dispatch(array $target,string $password,string $private,string $action):array
{
    ensure(in_array($action,['--build','--baseline','--ordering-off','--ascending','--measure','--cleanup'],true),'explicit_optimization_action_required');
    ensure(PHP_SAPI==='cli'||$action==='--measure','fpm_read_profile_only');
    ensure(!is_link($private)&&(fileperms($private)&0077)===0,'private_profile_directory_required');
    @set_time_limit(120);$deadline=microtime(true)+($action==='--build'?90:30);
    $pdo=connect($target,$password);unset($password);$pdo->exec('SET SESSION max_execution_time=3000');
    $path=$private.'/history100000.json';$lock=fopen($private.'/history-profile.lock','c');
    ensure($lock!==false&&chmod($private.'/history-profile.lock',0600),'profile_lock_unavailable');
    ensure(flock($lock,LOCK_EX|LOCK_NB),'profile_already_running');
    try {
        if($action==='--build') {
            ensure(tableNames($pdo)===[],'empty_test_database_required');
            targetGuard($pdo,$target);$r=build($pdo,$path,$deadline,'DESC');
            $state=json_decode(file_get_contents($path),true,32,JSON_THROW_ON_ERROR);
            $state['optimization']=['version'=>1,'current'=>null,'used'=>[]];saveState($path,$state);
            return $r;
        }
        ensure(is_file($path)&&!is_link($path)&&(fileperms($path)&0077)===0,'profile_manifest_missing');
        $state=json_decode(file_get_contents($path),true,32,JSON_THROW_ON_ERROR);validateState($state);
        if($action==='--cleanup'){targetGuard($pdo,$target);return cleanup($pdo,$state,$path,$deadline);}
        $stage=$action==='--measure'?($state['optimization']['current']??''):str_replace('-','',substr($action,2));
        if($action==='--ordering-off')$stage='ordering_off';
        if(PHP_SAPI==='fpm-fcgi') {
            $prior=$private.'/optimization-'.$stage.'-cli.json';
            ensure(is_file($prior)&&!is_link($prior),'cli_report_required');
            ensure((json_decode(file_get_contents($prior),true,32,JSON_THROW_ON_ERROR)['ok']??false)===true,'cli_report_failed');
        }
        $r=measureStage($pdo,$target,$state,$path,$stage,$deadline);
        // Protected response aggregates only the three explicitly bounded stage reports.
        if(PHP_SAPI==='fpm-fcgi') {
            $r['reports']=[];
            foreach(STAGES as $s)foreach(['cli','fpm'] as $runtime){
                $f=$private.'/optimization-'.$s.'-'.$runtime.'.json';
                if(is_file($f))$r['reports'][$s][$runtime]=json_decode(file_get_contents($f),true,32,JSON_THROW_ON_ERROR);
            }
        }
        return $r;
    } catch(Throwable $e) {
        if($pdo->inTransaction())$pdo->rollBack();
        $r=['ok'=>false,'failure'=>['code'=>$e instanceof Failure?$e->getMessage():'optimization_operation_failed']];
        if(is_file($path))try{
            $state=json_decode(file_get_contents($path),true,32,JSON_THROW_ON_ERROR);validateState($state);targetGuard($pdo,$target);
            $r['cleanup']=cleanup($pdo,$state,$path,microtime(true)+30);
        }catch(Throwable){$r['cleanup']=['ok'=>false,'manual_owned_cleanup_required'=>true];}
        return $r;
    } finally {flock($lock,LOCK_UN);fclose($lock);}
}
