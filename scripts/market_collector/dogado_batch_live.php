<?php
declare(strict_types=1);
namespace Mosa2\DogadoBatch;
use Throwable;
use function Mosa2\Phase2\{check,same,connection};
use function Mosa2\MarketLive\{runtimeContract,snapshot,completePlan};
const RELEASE='@RELEASE@';
const RUN='@RUN@';
const PUBLIC_ROOT='/var/www/vhosts/web213.server10.configcenter.info/mosa2-test.scharwerk.de';
require_once RELEASE.'/scripts/market_collector/live_batch.php';
require_once RELEASE.'/scripts/collector_release/runtime.php';

/** Historical launcher delegates to the common registered-asset qualifier. */
function qualify(array $state,array $selection,?callable $manifestFactory=null): array {
    return \Mosa2\MarketBatch\qualify($state,$selection,$manifestFactory??'\Mosa2\MarketAcceptance\manifest');
}
/** Use the installed sequential coordinator unchanged, then expose unknown outcomes. */
function coordinate(array $prepared,callable $runner): array {
    $report=\Mosa2\MarketBatch\execute($prepared,$runner);
    $unknown=false;$report['requested_count']=count($prepared);
    $report['insert_count']=0;$report['duplicate_unchanged_count']=0;
    foreach($report['private_evidence']['items'] as $i=>$private){
        $r=$private['result'];$item=&$report['item_results'][$i];
        if(($r['status']??null)==='OUTCOME_UNKNOWN'||!is_bool($r['committed']??null)){
            $item['status']='OUTCOME_UNKNOWN';$unknown=true;
        }
        $item['failure_code']=$r['failure_code']??null;
        if(($item['writer']??null)==='INSERT')$report['insert_count']++;
        if(($item['writer']??null)==='DUPLICATE_UNCHANGED')$report['duplicate_unchanged_count']++;
        unset($item);
    }
    if($unknown)$report['overall_status']='OUTCOME_UNKNOWN';
    unset($report['private_evidence']);
    return $report;
}
function exceptionOutcome(bool $coordinatorStarted): string {return $coordinatorStarted?'OUTCOME_UNKNOWN':'FAILED_BEFORE_FIRST_COMMIT';}
function runBatch(string $password,array $selection): array {
    $start=hrtime(true);$report=['ok'=>false,'overall_status'=>'FAILED_BEFORE_FIRST_COMMIT',
        'requested_count'=>count($selection),'started_count'=>0,'completed_count'=>0,
        'provider_requests'=>0,'item_results'=>[],'automatic_retries'=>0];
    $p=null;$coordinatorStarted=false;
    try{
        same(realpath(RUN),RUN,'batch_run_binding');
        check(!is_link(RUN)&&fileowner(RUN)===10317&&filegroup(RUN)===1003&&(fileperms(RUN)&0777)===0700,'batch_run_binding');
        $config=\Mosa2\CollectorRelease\configuration(RELEASE);
        $contract=['schema_version'=>4,'allow_current'=>true];
        $dbStart=hrtime(true);$p=connection($password);
        $p->exec('SET TRANSACTION READ ONLY');$p->beginTransaction();
        try{
            runtimeContract($p,$contract);$expected=snapshot($p,$contract);
            foreach($expected as $rows)check(count($rows)<=10000,'bounded_test_state');
            $qualified=qualify($expected,$selection);
        }finally{if($p->inTransaction())$p->rollBack();$p=null;}
        $preflightMs=(hrtime(true)-$dbStart)/1e6;
        // No per-asset folder or manifest is created until the ENTIRE scope passes.
        $entries=[];$contexts=[];
        foreach($qualified as $i=>$q){
            $folder=RUN.'/asset-'.sprintf('%02d',$i+1);
            check(!file_exists($folder)&&!is_link($folder)&&mkdir($folder,0700),'batch_item_create');
            same(realpath($folder),$folder,'batch_run_binding');
            $f=fopen($folder.'/live-manifest.json','x');check(is_resource($f),'batch_manifest_create');
            try{$wire=json_encode($q['manifest'],JSON_THROW_ON_ERROR);same(fwrite($f,$wire),strlen($wire),'batch_manifest_write');fflush($f);check(fsync($f),'batch_manifest_write');}
            finally{fclose($f);}
            same(fileperms($folder.'/live-manifest.json')&0777,0600,'manifest_mode');
            $entries[]=['private_root'=>$folder];$contexts[$q['isin']]=$q+['run'=>$folder];
        }
        $prepared=\Mosa2\MarketBatch\prepare(RUN,PUBLIC_ROOT,$entries);
        $coordinatorStarted=true;
        $report=coordinate($prepared,static function($entry)use(&$expected,$contexts,$password){
            $q=$contexts[$entry['manifest']['instrument']];
            $r=\Mosa2\DogadoRuntime\perform($password,['isin'=>$q['isin']],[
                'release'=>RELEASE,'run'=>$q['run'],'isin'=>$q['isin'],'name'=>$q['name'],
                'prepared_manifest'=>true,'expected_manifest'=>$q['manifest'],'expected_state'=>$expected,'capture_after_state'=>true]);
            $result=$r['result']??['committed'=>false,'database_connections'=>0,'stage'=>$r['stage']??'preflight'];
            $result['ok']=$r['ok'];$result['status']=$r['status'];
            if($r['status']==='OUTCOME_UNKNOWN'&&($result['committed']??null)!==true)$result['committed']=null;
            $result['provider_requests']=$r['provider_requests'];
            $result['failure_code']=$r['failure_code']??null;
            $result['metrics']=['collector_ms'=>$r['collector_ms']??null,'item_total_ms'=>$r['total_with_preflight_ms'],
                'provider_ms'=>$result['provider_duration_ms']??null,
                'database_check_ms'=>($r['preflight_db_ms']??0)+$r['db_checkpoints_ms'],
                'current_unchanged'=>$r['current_unchanged']??'NOT_CHECKED',
                'bars_unchanged'=>$r['bars_unchanged']??'NOT_CHECKED',
                'old_observations_unchanged'=>$r['old_observations_unchanged']??'NOT_CHECKED',
                'catalog_route_unit_unchanged'=>$r['catalog_route_unit_unchanged']??'NOT_CHECKED'];
            if($r['ok'])$expected=$r['private_after_state'];
            return $result;
        });
        $report['ok']=$report['overall_status']==='COMPLETE';$report['scope_preflight_db_ms']=$preflightMs;
    }catch(Throwable $e){
        $report['ok']=false;$report['failure_code']=\Mosa2\DogadoRuntime\safeFailureCode($e->getMessage());
        // Preserve any already observed commit/unknown state; never restart here.
        $report['overall_status']=exceptionOutcome($coordinatorStarted);
    }finally{
        if($p!==null&&$p->inTransaction())$p->rollBack();$p=null;unset($password);
        $report['local_batch_ms']=(hrtime(true)-$start)/1e6;$report['automatic_retries']=0;
    }
    return $report;
}
function main(): void {
    ini_set('display_errors','0');ini_set('log_errors','0');umask(0077);
    try{
        $in=json_decode(stream_get_contents(STDIN),true,32,JSON_THROW_ON_ERROR);
        check(is_string($in['password']??null)&&$in['password']!=='','db_secret_required');
        check(is_array($in['selection']??null),'batch_selection');
        $r=runBatch($in['password'],$in['selection']);unset($in);
    }catch(Throwable){$r=['ok'=>false,'overall_status'=>'FAILED_BEFORE_FIRST_COMMIT','failure_code'=>'batch_check_failed','provider_requests'=>0];}
    echo json_encode($r,JSON_THROW_ON_ERROR);
}
