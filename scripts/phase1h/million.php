<?php
declare(strict_types=1);
namespace Mosa2\Million;
require_once __DIR__.'/../phase1e/optimization.php';
use PDO;
use function Mosa2\Phase1B\ensure;
use function Mosa2\History10000\{profileSpec,saveState,proveOwnership,measureQueries,correctness,actualDigest,expectedDigest,tableStatistics,tableNames};
use function Mosa2\HistoryOptimization\{indexDetails,analyze};

function assess(array $queries): array {
    $failures=[];
    foreach($queries as $name=>$q) {
        $limit=$name==='current_single'?20:((str_starts_with($name,'history_')||$name==='chart')?100:null);
        if($limit!==null && max($q['first_ms'],$q['subsequent']['median_ms'],$q['subsequent']['p95_ms']) >= $limit) $failures[]=$name.'_latency';
        if(str_starts_with($name,'history_')||$name==='chart') foreach($q['explain'] as $plan) {
            if($plan['access']==='ALL'||$plan['key']!=='history_time'||$plan['filesort']) $failures[]=$name.'_plan';
        }
    }
    return array_values(array_unique($failures));
}
function measure(PDO $pdo,array &$state,string $path,float $deadline):array {
    ensure(profileSpec()['id']==='history1000000_v1','million_profile_required');
    ensure(($state['ready']??false)&&!($state['cleaned']??false),'dataset_not_ready');
    ensure(($state['used'][PHP_SAPI]??true)===false,'runtime_already_measured');
    $state['used'][PHP_SAPI]=true;saveState($path,$state);
    foreach(array_keys($state['tables']) as $kind)ensure(proveOwnership($pdo,$state,$kind),'owned_table_missing');
    $index=indexDetails($pdo,$state);
    $time=array_values(array_filter($index,fn($r)=>$r['name']==='history_time'));
    ensure(count($time)===3 && array_column($time,'direction')===['A','A','A'],'ascending_index_required');
    $report=['ok'=>true,'at'=>(new \DateTimeImmutable('now',new \DateTimeZone('Europe/Berlin')))->format(DATE_ATOM),'runtime'=>['php'=>PHP_VERSION,'sapi'=>PHP_SAPI],'index'=>$index,'build'=>$state['build']];
    // Timed first executions precede correctness reads; no cache flushing.
    $report['queries']=measureQueries($pdo,$state,$deadline);
    $report['analyze']=analyze($pdo,$state);
    $report['history_before']=actualDigest($pdo,$state,$deadline);
    $report['checks']=correctness($pdo,$state,$deadline);
    $report['history_after']=actualDigest($pdo,$state,$deadline);
    ensure($report['history_before']===$report['history_after'] && $report['history_after']===expectedDigest(),'million_history_changed');
    $report['approximate_table_statistics']=tableStatistics($pdo,$state);
    $report['acceptance_failures']=assess($report['queries']);
    $report['ok']=$report['acceptance_failures']===[];
    saveState(dirname($path).'/result-'.(PHP_SAPI==='cli'?'cli':'fpm').'.json',$report);
    return $report;
}
function dispatch(array $target,string $password,string $private,string $action):array {
    ensure(profileSpec()['id']==='history1000000_v1','million_profile_required');
    if($action==='--build') {
        $pdo=\Mosa2\Phase1B\connect($target,$password);
        ensure(tableNames($pdo)===[],'empty_database_required');$pdo=null;
    }
    if(PHP_SAPI==='fpm-fcgi') {
        $prior=$private.'/result-cli.json';
        ensure(is_file($prior)&&!is_link($prior),'cli_required');
        ensure((json_decode(file_get_contents($prior),true,32,JSON_THROW_ON_ERROR)['ok']??false)===true,'cli_failed');
    }
    $start=hrtime(true);
    $r=\Mosa2\History10000\dispatch($target,$password,$private,$action,__NAMESPACE__.'\\measure');
    if($action==='--build') {
        $r['total_build_ms']=round((hrtime(true)-$start)/1e6,4);
        $r['at']=(new \DateTimeImmutable('now',new \DateTimeZone('Europe/Berlin')))->format(DATE_ATOM);
        saveState($private.'/million-build.json',$r);
    }
    return $r;
}
